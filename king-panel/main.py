# ============================ KING PANEL ============================
# Deployment bot:  repo -> Cloudflare -> address -> "new password (x2)" -> panel
#
# What this file does, in order:
#   1. On boot it connects to Cloudflare and creates/updates the DNS record
#      pointing at this deployment, so the panel already has a real address.
#   2. The first visitor sees the setup page: the panel ADDRESS is shown and the
#      new password is asked TWICE (with a match check). Afterwards the browser
#      walks straight into the panel (/admin).
#   3. The panel can also be opened from anywhere else (a static copy) by typing
#      the server address + password on its "connect" screen.
#   4. Every proxy protocol is terminated HERE and bridged to the local Xray
#      inbounds over WebSocket, which is what makes the generated configs
#      actually connect (before, Xray only listened on 127.0.0.1 with nobody
#      forwarding to it).
import os, json, time, uuid, secrets, base64, sqlite3, subprocess, threading, hashlib, hmac, re, socket
import urllib.parse, urllib.request, urllib.error
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Response, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from pydantic import BaseModel


def env(k, d=""):
    return (os.environ.get(k) or d).strip()


def host_of(u):
    """https://a.b/c  ->  a.b"""
    u = (u or "").strip()
    if not u:
        return ""
    if "//" not in u:
        u = "//" + u
    try:
        return (urllib.parse.urlsplit(u).netloc or "").split("@")[-1].split(":")[0].lower()
    except Exception:
        return ""


# optional override; by default the host of the incoming request is used for every config link
DOMAIN_ENV = re.sub(r"^https?://", "", env("DOMAIN")).split("/")[0]
TITLE = env("PANEL_TITLE", "KING PANEL")          # locked: cannot be changed from inside the panel
DATA = env("DATA_DIR", "/data")
GB = 1024 ** 3
ADMIN_USER = env("ADMIN_USER", "admin").lower()    # owner username (password: variable ADMIN_PASSWORD)
PUBLIC_URL = env("PUBLIC_URL").rstrip("/")         # optional: forces the advertised panel address
HERE = os.path.dirname(os.path.abspath(__file__))

# appearance settings each account may change (sensitive settings such as domain and title are locked)
APPEARANCE = {"accent": "#7c5cff", "accent2": "#38d4ff", "theme": "dark", "palette": "default", "radius": "16",
              "bg": "gradient", "fx": "none", "noise": "0", "cardstyle": "glass", "border": "normal", "hover": "lift",
              "spot": "1", "btn": "gradient", "titlefx": "gradient", "shape": "squircle", "pbar": "gradient",
              "layout": "list", "density": "normal", "enter": "fade", "anim": "1", "font": "system", "fsize": "15",
              "blur": "14", "opacity": "40", "glow": "40", "swidth": "20", "bgimg": "", "prefix": ""}
HEX_KEYS = ("accent", "accent2")
NUM_KEYS = ("radius", "fsize", "blur", "opacity", "glow", "swidth")

os.makedirs(DATA, exist_ok=True)
L = threading.RLock()
db = sqlite3.connect(os.path.join(DATA, "panel.db"), check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA synchronous=NORMAL")
db.execute("""CREATE TABLE IF NOT EXISTS accounts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, pw_hash TEXT, role TEXT DEFAULT 'user',
 status TEXT DEFAULT 'pending', max_users INTEGER DEFAULT 0, max_gb REAL DEFAULT 0, domain TEXT DEFAULT '', created INTEGER DEFAULT 0)""")
db.execute("""CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, uuid TEXT, token TEXT,
 limit_bytes INTEGER DEFAULT 0, expire INTEGER DEFAULT 0, up INTEGER DEFAULT 0, down INTEGER DEFAULT 0,
 enabled INTEGER DEFAULT 1, note TEXT DEFAULT '', created INTEGER DEFAULT 0, protos TEXT DEFAULT 'vmess',
 port INTEGER DEFAULT 443, fp TEXT DEFAULT '', addr TEXT DEFAULT '', ttl_days INTEGER DEFAULT 0, owner_id INTEGER DEFAULT 1)""")
db.execute("""CREATE TABLE IF NOT EXISTS account_settings(account_id INTEGER, k TEXT, v TEXT, PRIMARY KEY(account_id, k))""")
db.execute("""CREATE TABLE IF NOT EXISTS account_kv(account_id INTEGER, k TEXT, v TEXT, PRIMARY KEY(account_id, k))""")
db.execute("""CREATE TABLE IF NOT EXISTS sys(k TEXT PRIMARY KEY, v TEXT)""")
for col in ("note TEXT DEFAULT ''", "created INTEGER DEFAULT 0", "protos TEXT DEFAULT 'vmess'", "port INTEGER DEFAULT 443",
            "fp TEXT DEFAULT ''", "addr TEXT DEFAULT ''", "ttl_days INTEGER DEFAULT 0", "owner_id INTEGER DEFAULT 1"):
    try: db.execute("ALTER TABLE users ADD COLUMN " + col)
    except Exception: pass
try:  # migration from the previous version: old appearance settings <- owner
    if not db.execute("SELECT 1 FROM account_settings LIMIT 1").fetchone():
        for r in db.execute("SELECT k, v FROM settings").fetchall():
            if r["k"] in APPEARANCE:
                db.execute("INSERT OR IGNORE INTO account_settings VALUES(1, ?, ?)", (r["k"], r["v"]))
except sqlite3.OperationalError:
    pass
for r in db.execute("SELECT id, protos FROM users WHERE protos LIKE '%reality%'").fetchall():  # Reality removed
    db.execute("UPDATE users SET protos=? WHERE id=?",
               (",".join(x for x in r["protos"].split(",") if x != "reality") or "vmess", r["id"]))
db.commit()


def kv(aid, k, default=None):
    with L:
        r = db.execute("SELECT v FROM account_kv WHERE account_id=? AND k=?", (aid, k)).fetchone()
    try:
        return json.loads(r["v"]) if r else default
    except Exception:
        return default


def set_kv(aid, k, val):
    with L:
        db.execute("INSERT OR REPLACE INTO account_kv VALUES(?,?,?)", (aid, k, json.dumps(val, ensure_ascii=False)))
        db.commit()


def sys_get(k, default=None):
    with L:
        r = db.execute("SELECT v FROM sys WHERE k=?", (k,)).fetchone()
    try:
        return json.loads(r["v"]) if r else default
    except Exception:
        return default


def sys_set(k, val):
    with L:
        db.execute("INSERT OR REPLACE INTO sys VALUES(?,?)", (k, json.dumps(val, ensure_ascii=False)))
        db.commit()


# ------------------------- passwords and sessions -------------------------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()


def check_pw(pw, stored):
    try:
        s, h = stored.split("$")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(s), 200_000).hex(), h)
    except Exception:
        return False


DUMMY_HASH = hash_pw("dummy-password")

SETUP_KEY = env("SETUP_KEY")   # optional: the first-run setup page then requires ?key=<SETUP_KEY>
SETUP_USER_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


def needs_setup():
    with L:
        return db.execute("SELECT 1 FROM accounts WHERE role='owner'").fetchone() is None


def bootstrap_owner():
    """With ADMIN_PASSWORD set the owner is managed by variables; without it the first visitor creates the owner on the setup page."""
    pw = env("ADMIN_PASSWORD")
    if not pw:
        return
    with L:
        row = db.execute("SELECT id FROM accounts WHERE role='owner'").fetchone()
        if row:
            db.execute("UPDATE accounts SET email=?, pw_hash=?, status='active' WHERE id=?", (ADMIN_USER, hash_pw(pw), row["id"]))
        else:
            db.execute("INSERT INTO accounts(id,email,pw_hash,role,status,max_users,max_gb,created) VALUES(1,?,?,'owner','active',0,0,?)",
                       (ADMIN_USER, hash_pw(pw), int(time.time())))
        db.commit()


SESS = {}   # token -> (account_id, expiry)
fails = {}  # key (ip/email) -> (count, start)
regs = {}


def new_session(aid):
    t = secrets.token_urlsafe(32)
    SESS[t] = (aid, time.time() + 30 * 24 * 3600)
    return t


def drop_sessions(aid):
    for t in [t for t, v in SESS.items() if v[0] == aid]:
        SESS.pop(t, None)


def token_of(request: Request):
    """A session can arrive either as the cookie (same-origin panel) or as a
    bearer token (panel opened from another host, e.g. a static copy)."""
    t = (request.cookies.get("sess") or "").strip()
    if t:
        return t
    h = (request.headers.get("authorization") or "").strip()
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return ""


def me_of(request: Request):
    t = token_of(request)
    s = SESS.get(t)
    if not s or s[1] < time.time():
        SESS.pop(t, None)
        return None
    with L:
        a = db.execute("SELECT * FROM accounts WHERE id=?", (s[0],)).fetchone()
    if not a or a["status"] != "active":
        SESS.pop(t, None)
        return None
    return a


def auth(request: Request):
    a = me_of(request)
    if not a:
        raise HTTPException(401)
    if request.method not in ("GET", "HEAD"):
        # a bearer token is not auto-attached by the browser, so it already
        # protects against CSRF; the cookie path keeps the header guard.
        if (request.headers.get("authorization") or "").lower().startswith("bearer "):
            return a
        if request.headers.get("x-requested-with") != "panel":
            raise HTTPException(403)
    return a


def owner_only(a=Depends(auth)):
    if a["role"] != "owner":
        raise HTTPException(403)
    return a


def client_ip(request: Request):
    return (request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for") or request.client.host).split(",")[0].strip()


def throttle(key, limit, window=600):
    now = time.time()
    n, t = fails.get(key, (0, now))
    if now - t > window:
        n, t = 0, now
    if n >= limit:
        raise HTTPException(429, "Too many attempts; try again in a few minutes")
    return n, t


def is_active(u):
    now = time.time()
    return (u["enabled"] and (u["limit_bytes"] == 0 or u["up"] + u["down"] < u["limit_bytes"])
            and (u["expire"] == 0 or u["expire"] > now))


def active_users():
    return [u for u in db.execute("SELECT users.* FROM users JOIN accounts ON accounts.id=users.owner_id WHERE accounts.status='active'")
            if is_active(u)]


# ------------------------- Xray management -------------------------
# Every inbound listens on loopback in PLAIN websocket mode. TLS is terminated
# by the platform/CDN edge and this app forwards the websocket stream to Xray.
PATHS = {"vmess": "/in2", "vless": "/vl", "trojan": "/tr", "vlessh": "/hu"}
LABEL = {"vmess": "VMess", "vless": "VLESS", "trojan": "Trojan", "vlessh": "VLESS-HU"}
# protocol: (tag, internal port, xray protocol, transport type)
INB = {"vmess": ("vmess-in", 10000, "vmess", "ws"), "vless": ("vless-in", 10001, "vless", "ws"),
       "trojan": ("trojan-in", 10002, "trojan", "ws"), "vlessh": ("vlessh-in", 10003, "vless", "ws")}
CONF = os.path.join(DATA, "xray.json")
API = "127.0.0.1:10085"
proc = None
current = None
bad_ids = None
last_err = ""
pending = False


def clients_for(p, users):
    out = []
    for u in users:
        if p not in u["protos"].split(","):
            continue
        e = f"u{u['id']}"
        if p == "vmess": out.append({"id": u["uuid"], "email": e, "alterId": 0})
        elif p == "trojan": out.append({"password": u["uuid"], "email": e})
        else: out.append({"id": u["uuid"], "email": e})
    if not out:  # xray requires at least one client
        d = str(uuid.uuid4())
        out = [{"password": d, "email": "dummy"} if p == "trojan" else {"id": d, "email": "dummy"}]
    return out


def write_config(users, path=None):
    inbounds = [{"tag": "api", "listen": "127.0.0.1", "port": 10085, "protocol": "dokodemo-door",
                 "settings": {"address": "127.0.0.1"}}]
    for p, (tag, port, proto, net) in INB.items():
        st = {"clients": clients_for(p, users)}
        if proto == "vless":
            st["decryption"] = "none"
        ss = {"network": net, "security": "none", "wsSettings": {"path": PATHS[p]}}
        inbounds.append({"tag": tag, "listen": "127.0.0.1", "port": port, "protocol": proto, "settings": st, "streamSettings": ss})
    cfg = {
        "log": {"loglevel": "warning"},
        "api": {"tag": "api", "services": ["HandlerService", "StatsService"]},
        "stats": {},
        "policy": {"levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}}},
        "inbounds": inbounds,
        "outbounds": [{"protocol": "freedom", "tag": "direct"}, {"protocol": "blackhole", "tag": "block"}],
        # security: proxy users cannot reach the internal/local network (panel, Xray API, railway.internal)
        "routing": {"domainStrategy": "IPIfNonMatch", "rules": [
            {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
            {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"}]},
    }
    with open(path or CONF, "w") as f:
        json.dump(cfg, f)
    return [i["port"] for i in inbounds]


def port_open(port, host="127.0.0.1"):
    try:
        socket.create_connection((host, port), 0.6).close()
        return True
    except OSError:
        return False


def xray_test(path):
    try:
        r = subprocess.run(["xray", "run", "-test", "-c", path], capture_output=True, text=True, timeout=20)
        msg = (r.stdout + r.stderr).strip()[-400:]
        if r.returncode != 0 and "not defined" in msg.lower():
            return True, ""
        return r.returncode == 0, msg
    except Exception:
        return True, ""


def wait_ready(ports, timeout=9):
    end = time.time() + timeout
    while time.time() < end:
        if proc is None or proc.poll() is not None:
            return False
        if all(port_open(p) for p in ports):
            return True
        time.sleep(0.3)
    return False


def pairs(users):
    return frozenset((u["id"], p) for u in users for p in u["protos"].split(",") if p in INB)


def sync():
    global proc, current, bad_ids, last_err
    with L:
        users = active_users()
        ids = pairs(users)
        alive = proc is not None and proc.poll() is None
        if alive and ids == current:
            return
        if ids == bad_ids:
            return
        new_conf = os.path.join(DATA, "xray.new.json")   # the extension must be .json
        ports = write_config(users, new_conf)
        ok, msg = xray_test(new_conf)
        if not ok:
            bad_ids = ids
            last_err = "Invalid Xray config; change not applied: " + msg
            print("[xray] config test failed:", msg, flush=True)
            return
        if alive:
            collect()  # save the usage before the restart
            proc.terminate()
            try: proc.wait(5)
            except Exception: proc.kill()
        os.replace(new_conf, CONF)
        for attempt in (1, 2):
            try:
                proc = subprocess.Popen(["xray", "run", "-c", CONF])
            except FileNotFoundError:
                # remember this set so the loop does not retry it every 10s
                bad_ids = ids
                last_err = "The xray binary is not installed in this container; configs cannot be served."
                print("[xray] binary missing", flush=True)
                return
            if wait_ready(ports):
                break
            print(f"[xray] not ready (attempt {attempt}, exit={proc.poll()})", flush=True)
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(3)
                except Exception: proc.kill()
        closed = [p for p in ports if not port_open(p)]
        ready = proc.poll() is None and not closed
        last_err = "" if ready else f"Xray did not start; ports not open: {closed or '—'}; check the logs"
        bad_ids = None
        current = ids
        print("[xray] started ready=%s users per protocol: %s" % (ready, {p: sum(1 for i, q in ids if q == p) for p in INB}), flush=True)


_ev = threading.Event()


def sync_async():
    """The API answers immediately; applying to Xray happens in the background (consecutive changes are batched)"""
    global pending
    pending = True
    _ev.set()


def _syncer():
    global pending
    while True:
        _ev.wait()
        time.sleep(0.35)
        _ev.clear()
        try:
            sync()
        except Exception as e:
            print("[sync] error:", e, flush=True)
        if not _ev.is_set():
            pending = False


def collect():
    try:
        out = subprocess.run(["xray", "api", "statsquery", "-s", API, "-pattern", "user>>>", "-reset"],
                             capture_output=True, text=True, timeout=10).stdout
        stats = json.loads(out).get("stat", []) if out.strip() else []
    except Exception:
        return
    with L:
        for s in stats:
            p = s["name"].split(">>>")
            if len(p) < 4 or not p[1].startswith("u"):
                continue
            col = "up" if p[3] == "uplink" else "down"
            db.execute(f"UPDATE users SET {col}={col}+? WHERE id=?", (int(s["value"]), int(p[1][1:])))
        db.execute("UPDATE users SET expire=?+ttl_days*86400, ttl_days=0 WHERE ttl_days>0 AND expire=0 AND up+down>0", (int(time.time()),))
        db.commit()


def loop():
    time.sleep(3)
    while True:
        try:
            collect()
            sync()
            now = time.time()
            for t in [t for t, v in SESS.items() if v[1] < now]:
                SESS.pop(t, None)
            if len(fails) > 2000: fails.clear()
        except Exception as e:
            print("loop error:", e, flush=True)
        time.sleep(10)


# ------------------------- links -------------------------
ALLOWED_PORTS = {443, 8443, 2053, 2083, 2087, 2096}
FPS = {"", "android", "chrome", "firefox", "safari", "ios", "random"}


def links(u, dom, prefix):
    """Every link is TLS + websocket on the CDN port; this app terminates the
    websocket and hands it to Xray, which is why these connect."""
    fp = u["fp"] or "chrome"
    port = u["port"] if u["port"] in ALLOWED_PORTS else 443
    name = prefix + u["name"]
    out = []
    for p in u["protos"].split(","):
        if p not in PATHS:
            continue
        if p == "vmess":
            cfg = {"v": "2", "ps": f"{name} VMess", "add": dom, "port": str(port), "id": u["uuid"], "aid": "0",
                   "scy": "auto", "net": "ws", "type": "none", "host": dom, "path": PATHS[p], "tls": "tls",
                   "sni": dom, "alpn": "http/1.1", "fp": fp}
            out.append((p, "vmess://" + base64.b64encode(json.dumps(cfg, ensure_ascii=False).encode()).decode()))
            continue
        q = {"security": "tls", "type": "ws", "host": dom, "path": PATHS[p]}
        if p != "trojan":
            q["encryption"] = "none"
        q.update(sni=dom, fp=fp, alpn="http/1.1")
        tag = urllib.parse.quote(f"{name} {LABEL[p]}")
        scheme = "trojan" if p == "trojan" else "vless"
        out.append((p, f"{scheme}://{u['uuid']}@{dom}:{port}?{urllib.parse.urlencode(q)}#{tag}"))
    return out


# clean-IP / multi-location variants: only the connect address changes, SNI and Host stay on the real domain
LINK_RE = re.compile(r"^([a-z]+://[^@]+@)(\[[^\]]+\]|[^:/?#]+)(:\d+)?([^#]*)(#.*)?$", re.I)


def with_ip(link, addr, port=""):
    try:
        if link.startswith("vmess://"):
            j = json.loads(base64.b64decode(link[8:]))
            j["host"] = j.get("host") or j["add"]
            j["sni"] = j.get("sni") or j["host"]
            j["add"] = addr
            if port:
                j["port"] = str(port)
            j["ps"] = f"{j.get('ps', '')} | {addr}"
            return "vmess://" + base64.b64encode(json.dumps(j, ensure_ascii=False).encode()).decode()
        m = LINK_RE.match(link)
        if not m:
            return link
        a, h, pt, q, f = m.groups()
        qd = dict(urllib.parse.parse_qsl(q.lstrip("?")))
        qd.setdefault("sni", h)
        if "host" not in qd and qd.get("type") in ("ws", "httpupgrade", "xhttp", "splithttp"):
            qd["host"] = h
        frag = (f + urllib.parse.quote(" | " + addr)) if f else "#" + urllib.parse.quote(addr)
        return f"{a}{addr}:{port or (pt[1:] if pt else 443)}?{urllib.parse.urlencode(qd)}{frag}"
    except Exception:
        return link


def full(u, dom, prefix):
    d = {k: u[k] for k in u.keys() if k not in ("owner_id", "addr")}
    d["active"] = bool(is_active(u))
    d["links"] = [{"p": p, "l": l} for p, l in links(u, dom, prefix)]
    return d


def settings_for(aid):
    d = dict(APPEARANCE)
    with L:
        d.update({r["k"]: r["v"] for r in db.execute("SELECT k, v FROM account_settings WHERE account_id=?", (aid,))})
    d["title"] = TITLE   # locked
    return d


HOST_RE = re.compile(r"^[A-Za-z0-9.\-]{1,253}$")


def req_host(request):
    """Config links always point at the host the panel or subscription was opened with."""
    h = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().split(":")[0].lower()
    if DOMAIN_ENV:
        return DOMAIN_ENV
    if PUBLIC_URL:
        return host_of(PUBLIC_URL) or h
    return h if HOST_RE.match(h) else "localhost"


def public_addr(request=None):
    """The address the panel advertises (used on the setup screen)."""
    if PUBLIC_URL:
        return PUBLIC_URL
    if DOMAIN_ENV:
        return "https://" + DOMAIN_ENV
    rec = sys_get("cf") or {}
    if rec.get("fqdn"):
        return "https://" + rec["fqdn"]
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "http://localhost:8080"


def clean_protos(l):
    l = [p for p in (l or []) if p in PATHS]
    return ",".join(dict.fromkeys(l)) or "vmess"


def used_bytes(aid, exclude=None):
    return db.execute("SELECT COALESCE(SUM(limit_bytes),0) s FROM users WHERE owner_id=? AND id IS NOT ?", (aid, exclude)).fetchone()["s"]


def meminfo():
    mem = {}
    try:
        for ln in open("/proc/meminfo"):
            k, v = ln.split(":")
            mem[k] = int(v.split()[0]) * 1024
    except Exception:
        pass
    total = mem.get("MemTotal", 0)
    return total - mem.get("MemAvailable", total), total


def my_stats(a):
    with L:
        us = db.execute("SELECT * FROM users WHERE owner_id=?", (a["id"],)).fetchall()
    d = {"users": len(us), "active": sum(1 for u in us if is_active(u)), "traffic": sum(u["up"] + u["down"] for u in us),
         "applying": pending, "ram_used": 0, "ram_total": 0, "load": 0, "xray_err": "", "tls": True}
    if a["role"] == "owner":
        d["ram_used"], d["ram_total"] = meminfo()
        try: d["load"] = os.getloadavg()[0]
        except Exception: d["load"] = 0.0
        d["xray_err"] = last_err
    return d


def me_info(a, request=None):
    return {"email": a["email"], "role": a["role"], "max_users": a["max_users"], "max_gb": a["max_gb"],
            "is_admin": a["role"] == "owner", "addr": public_addr(request)}


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# The panel may be opened from another origin (a static copy): allow it, and
# authorise with a bearer token rather than a cross-site cookie.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["*"], max_age=86400)

# connect-src allows https: so the panel's Scanner page can time-test clean IPs straight from the browser
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
       "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net data:; "
       "img-src 'self' data: https:; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Strict-Transport-Security"] = "max-age=31536000"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if request.url.path.startswith("/api") or request.url.path in ("/login", "/register", "/admin", "/"):
        h["Cache-Control"] = "no-store"
    if h.get("content-type", "").startswith("text/html"):
        h["Content-Security-Policy"] = CSP
    return resp


@app.on_event("startup")
def start():
    threading.Thread(target=_syncer, daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    threading.Thread(target=cf_startup, daemon=True).start()
    sync_async()


# ============================ CLOUDFLARE ============================
# repo -> Cloudflare: on boot the DNS record for this deployment is created or
# updated, so the panel already has a real, TLS-terminated address to show on
# the setup screen. Entirely optional: without CF_API_TOKEN it stays off.
CF_BASE = "https://api.cloudflare.com/client/v4"


def cf_api(method, path, body=None):
    tok = env("CF_API_TOKEN")
    req = urllib.request.Request(CF_BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or "{}")
        except Exception:
            return {"success": False, "errors": [{"message": "HTTP %s" % e.code}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": str(e)}]}


def cf_sync():
    """Create or update the DNS record; never raises (a failure must not stop the bot)."""
    out = {"state": "off", "msg": "CF_API_TOKEN not set", "fqdn": "", "proxied": False}
    tok = env("CF_API_TOKEN")
    if not tok:
        sys_set("cf", out)
        return out
    try:
        zone_id = env("CF_ZONE_ID")
        zone_name = env("CF_ZONE_NAME")
        if not zone_id:
            if not zone_name:
                out.update(state="error", msg="Set CF_ZONE_ID or CF_ZONE_NAME")
                sys_set("cf", out)
                return out
            z = cf_api("GET", "/zones?name=" + urllib.parse.quote(zone_name))
            res = (z.get("result") or [])
            if not z.get("success") or not res:
                msg = ((z.get("errors") or [{}])[0].get("message") or "zone not found")
                out.update(state="error", msg="Zone lookup failed: " + msg)
                sys_set("cf", out)
                return out
            zone_id = res[0]["id"]

        if not zone_name:
            z = cf_api("GET", "/zones?per_page=1&id=" + urllib.parse.quote(zone_id))
            res = (z.get("result") or [])
            zone_name = res[0]["name"] if res else ""

        rec = env("CF_RECORD") or "@"
        fqdn = (zone_name if rec in ("@", "") else (rec if rec.endswith(zone_name) else rec + "." + zone_name)).lower()
        target = (env("CF_TARGET") or host_of(PUBLIC_URL) or env("RAILWAY_PUBLIC_DOMAIN")
                  or env("RENDER_EXTERNAL_HOSTNAME") or env("FLY_APP_NAME") or "")
        if not target:
            out.update(state="error", msg="No target host: set CF_TARGET (or PUBLIC_URL / RAILWAY_PUBLIC_DOMAIN)")
            sys_set("cf", out)
            return out
        target = host_of(target) or target
        is_ip = bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", target))
        rtype = "A" if is_ip else "CNAME"
        proxied = env("CF_PROXIED", "1") not in ("0", "false", "no")

        found = cf_api("GET", f"/zones/{zone_id}/dns_records?name=" + urllib.parse.quote(fqdn))
        body = {"type": rtype, "name": fqdn, "content": target, "ttl": 1, "proxied": proxied}
        existing = (found.get("result") or [])
        if existing:
            rid = existing[0]["id"]
            r = cf_api("PATCH", f"/zones/{zone_id}/dns_records/{rid}", body)
        else:
            r = cf_api("POST", f"/zones/{zone_id}/dns_records", body)

        if r.get("success"):
            out = {"state": "ok", "msg": f"{rtype} {fqdn} → {target}" + (" (proxied)" if proxied else ""),
                   "fqdn": fqdn, "proxied": proxied, "target": target, "updated": int(time.time())}
        else:
            msg = ((r.get("errors") or [{}])[0].get("message") or "unknown error")
            out = {"state": "error", "msg": "Cloudflare rejected the record: " + msg, "fqdn": fqdn, "proxied": proxied}
    except Exception as e:
        out = {"state": "error", "msg": "Cloudflare sync failed: " + str(e), "fqdn": "", "proxied": False}
    sys_set("cf", out)
    print("[cf]", out.get("state"), out.get("msg"), flush=True)
    return out


def cf_startup():
    time.sleep(1.5)
    cf_sync()


# ============================ WEBSOCKET BRIDGE ============================
# This is the piece that was missing: Xray listens on loopback only, so the
# configs had nothing to talk to. Here the incoming websocket (already TLS
# terminated by the edge) is piped to the matching Xray inbound.
import asyncio

_WS_PORTS = {"in2": 10000, "vl": 10001, "tr": 10002, "hu": 10003}


async def ws_bridge(ws: WebSocket, port, path):
    try:
        import websockets
    except ImportError:
        print("[ws] the 'websockets' package is missing; run: pip install websockets", flush=True)
        await ws.close(code=1011)
        return
    await ws.accept()
    up = None
    try:
        up = await websockets.connect(f"ws://127.0.0.1:{port}{path}", max_size=None, open_timeout=8,
                                      ping_interval=20, ping_timeout=20)
    except Exception as e:
        print(f"[ws] cannot reach xray on {port}{path}: {e}", flush=True)
        try: await ws.close(code=1011)
        except Exception: pass
        return

    async def c2s():
        while True:
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                return
            if m.get("bytes") is not None:
                await up.send(m["bytes"])
            elif m.get("text") is not None:
                await up.send(m["text"])

    async def s2c():
        async for m in up:
            if isinstance(m, bytes):
                await ws.send_bytes(m)
            else:
                await ws.send_text(m)

    t1 = asyncio.create_task(c2s())
    t2 = asyncio.create_task(s2c())
    try:
        done, pend = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        for t in pend:
            t.cancel()
    except Exception:
        pass
    finally:
        for t in (t1, t2):
            if not t.done():
                t.cancel()
        try: await up.close()
        except Exception: pass
        try: await ws.close()
        except Exception: pass


@app.websocket("/in2")
async def ws_vmess(ws: WebSocket):
    await ws_bridge(ws, _WS_PORTS["in2"], "/in2")


@app.websocket("/vl")
async def ws_vless(ws: WebSocket):
    await ws_bridge(ws, _WS_PORTS["vl"], "/vl")


@app.websocket("/tr")
async def ws_trojan(ws: WebSocket):
    await ws_bridge(ws, _WS_PORTS["tr"], "/tr")


@app.websocket("/hu")
async def ws_vlessh(ws: WebSocket):
    await ws_bridge(ws, _WS_PORTS["hu"], "/hu")


# ------------------------- login and sign-up -------------------------
def need_header(request: Request):
    if request.headers.get("x-requested-with") != "panel":
        raise HTTPException(403)


def session_response(aid, ok_body=None):
    t = new_session(aid)
    r = Response(json.dumps({"ok": True, "token": t, **(ok_body or {})}), media_type="application/json")
    r.set_cookie("sess", t, max_age=30 * 24 * 3600, httponly=True, samesite="lax", secure=True, path="/")
    return r


@app.get("/api/ping")
def api_ping(request: Request):
    """Public, secret-free handshake used by the panel's connect screen to check
    that an address really is a King Panel before asking for a password."""
    cf = sys_get("cf") or {}
    return {"ok": True, "app": "king-panel", "title": TITLE, "setup": needs_setup(),
            "addr": public_addr(request), "cf": cf.get("state", "off")}


@app.post("/login")
def login(body: dict, request: Request):
    need_header(request)
    ident = str(body.get("username", body.get("email", ""))).strip().lower()[:100]
    pw = str(body.get("password", ""))[:200]
    ip = client_ip(request)
    n1, t1 = throttle("ip:" + ip, 15)
    n2, t2 = throttle("em:" + ident, 8)
    with L:
        a = db.execute("SELECT * FROM accounts WHERE email=?", (ident,)).fetchone()
    ok = check_pw(pw, a["pw_hash"] if a else DUMMY_HASH) and a is not None
    if not ok:
        fails["ip:" + ip] = (n1 + 1, t1)
        fails["em:" + ident] = (n2 + 1, t2)
        time.sleep(1.0)
        raise HTTPException(401, "Wrong username or password")
    if a["status"] == "pending":
        raise HTTPException(403, "Account is not yet approved by the owner")
    if a["status"] != "active":
        raise HTTPException(403, "Account is blocked")
    fails.pop("ip:" + ip, None)
    fails.pop("em:" + ident, None)
    return session_response(a["id"], {"me": me_info(a, request)})


@app.get("/logout")
def logout(request: Request):
    SESS.pop(token_of(request), None)
    r = RedirectResponse("/login")
    r.delete_cookie("sess", path="/")
    return r


@app.put("/api/password")
def change_password(body: dict, request: Request, a=Depends(auth)):
    """Change the password of the signed-in account (all other sessions are signed out)."""
    if a["role"] == "owner" and env("ADMIN_PASSWORD"):
        # bootstrap_owner() would overwrite the new password with the variable on the next restart
        raise HTTPException(409, "The owner password is managed by the ADMIN_PASSWORD variable; change it there")
    key = "pw:%s" % a["id"]
    n, t = throttle(key, 8)
    old, new = str(body.get("old", ""))[:200], str(body.get("new", ""))
    if not check_pw(old, a["pw_hash"]):
        fails[key] = (n + 1, t)
        time.sleep(1.0)
        raise HTTPException(403, "Current password is wrong")
    if not 8 <= len(new) <= 128:
        raise HTTPException(400, "Password must be 8 to 128 characters")
    if new.lower() == (a["email"] or "").lower():
        raise HTTPException(400, "Password must differ from the username")
    with L:
        db.execute("UPDATE accounts SET pw_hash=? WHERE id=?", (hash_pw(new), a["id"]))
        db.commit()
    fails.pop(key, None)
    drop_sessions(a["id"])
    return session_response(a["id"])


# ------------------------- API users -------------------------
class NewUser(BaseModel):
    name: str
    gb: float = 0
    days: int = 0
    note: str = ""
    protos: list = ["vmess"]
    port: int = 443
    fp: str = ""
    first_use: bool = False
    count: int = 1
    uuid: str = ""
    enabled: bool = True


class EditUser(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None
    gb: Optional[float] = None
    days: Optional[int] = None
    add_gb: Optional[float] = None
    add_days: Optional[int] = None
    enabled: Optional[bool] = None
    protos: Optional[list] = None
    port: Optional[int] = None
    fp: Optional[str] = None
    reset: bool = False


@app.get("/api/all")
def api_all(request: Request, a=Depends(auth)):
    st, dom = settings_for(a["id"]), req_host(request)
    with L:
        us = db.execute("SELECT * FROM users WHERE owner_id=? ORDER BY id DESC", (a["id"],)).fetchall()
        users = [full(u, dom, st["prefix"]) for u in us]
    return {"me": me_info(a, request), "users": users, "settings": st, "stats": my_stats(a)}


@app.post("/api/users")
def add_user(n: NewUser, request: Request, a=Depends(auth)):
    cnt = max(1, min(n.count, 200))
    gb, days = max(0.0, n.gb), max(0, n.days)
    port = n.port if n.port in ALLOWED_PORTS else 443
    fp = n.fp if n.fp in FPS else ""
    with L:
        if a["max_users"] and db.execute("SELECT COUNT(*) c FROM users WHERE owner_id=?", (a["id"],)).fetchone()["c"] + cnt > a["max_users"]:
            raise HTTPException(403, "You reached the user limit of your account")
        if a["max_gb"]:
            if gb <= 0:
                raise HTTPException(400, "This account requires you to set a volume")
            if used_bytes(a["id"]) + cnt * int(gb * GB) > a["max_gb"] * GB:
                raise HTTPException(403, "This would exceed the volume limit of your account")
        ids = []
        for i in range(cnt):
            name = (n.name.strip() or "user")[:64]
            if cnt > 1:
                name = f"{name}-{i + 1}"
            uid_ = str(uuid.uuid4())
            if cnt == 1 and n.uuid:
                try: uid_ = str(uuid.UUID(n.uuid))
                except ValueError: raise HTTPException(400, "Invalid UUID")
            first = n.first_use and days > 0
            cur = db.execute("INSERT INTO users(name,uuid,token,limit_bytes,expire,note,created,protos,port,fp,ttl_days,enabled,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (name, uid_, secrets.token_urlsafe(12), int(gb * GB),
                              0 if first or not days else int(time.time() + days * 86400), n.note[:200], int(time.time()),
                              clean_protos(n.protos), port, fp, days if first else 0, int(n.enabled), a["id"]))
            ids.append(cur.lastrowid)
        db.commit()
        st, dom = settings_for(a["id"]), req_host(request)
        rows = [db.execute("SELECT * FROM users WHERE id=?", (i,)).fetchone() for i in ids]
        created = [full(r, dom, st["prefix"]) for r in reversed(rows)]
    sync_async()
    return {"ok": True, "users": created, "stats": my_stats(a)}


@app.put("/api/users/{uid}")
def edit_user(uid: int, e: EditUser, request: Request, a=Depends(auth)):
    with L:
        u = db.execute("SELECT * FROM users WHERE id=? AND owner_id=?", (uid, a["id"])).fetchone()
        if not u:
            raise HTTPException(404)
        f = {}
        if e.name is not None: f["name"] = (e.name.strip() or u["name"])[:64]
        if e.note is not None: f["note"] = e.note[:200]
        if e.enabled is not None: f["enabled"] = int(e.enabled)
        if e.protos is not None: f["protos"] = clean_protos(e.protos)
        if e.port is not None: f["port"] = e.port if e.port in ALLOWED_PORTS else 443
        if e.fp is not None: f["fp"] = e.fp if e.fp in FPS else ""
        if e.gb is not None: f["limit_bytes"] = int(max(0.0, e.gb) * GB)
        if e.days is not None:
            f["expire"] = int(time.time() + max(0, e.days) * 86400) if e.days > 0 else 0
            f["ttl_days"] = 0
        if e.add_gb:
            f["limit_bytes"] = max(0, int(f.get("limit_bytes", u["limit_bytes"]) + e.add_gb * GB))
        if e.add_days:
            cur_exp = f.get("expire", u["expire"])
            f["expire"] = int((max(cur_exp, time.time()) if cur_exp else time.time()) + e.add_days * 86400)
        if "limit_bytes" in f and a["max_gb"]:
            if f["limit_bytes"] == 0:
                raise HTTPException(400, "This account requires you to set a volume")
            if used_bytes(a["id"], uid) + f["limit_bytes"] > a["max_gb"] * GB:
                raise HTTPException(403, "This would exceed the volume limit of your account")
        if e.reset: f["up"] = f["down"] = 0
        if f:
            db.execute("UPDATE users SET " + ",".join(f"{k}=?" for k in f) + " WHERE id=?", (*f.values(), uid))
            db.commit()
        row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        user = full(row, req_host(request), settings_for(a["id"])["prefix"])
    sync_async()
    return {"ok": True, "user": user, "stats": my_stats(a)}


@app.delete("/api/users/{uid}")
def del_user(uid: int, a=Depends(auth)):
    with L:
        db.execute("DELETE FROM users WHERE id=? AND owner_id=?", (uid, a["id"]))
        db.commit()
    sync_async()
    return {"ok": True, "stats": my_stats(a)}


@app.put("/api/settings")
def put_settings(body: dict, a=Depends(auth)):
    with L:
        for k, v in body.items():
            if k not in APPEARANCE:   # domain, title and other sensitive settings are ignored here
                continue
            v = str(v).strip()[:300]
            if k in HEX_KEYS and not re.fullmatch(r"#[0-9a-fA-F]{6}", v): v = APPEARANCE[k]
            elif k in NUM_KEYS and not v.isdigit(): v = APPEARANCE[k]
            elif k == "bgimg" and v and not re.match(r"^https://[^\s\"'()\\]+$", v): v = ""
            elif k == "prefix": v = re.sub(r"[\r\n]", "", v)[:20]
            elif k not in ("bgimg", "prefix") and k not in HEX_KEYS + NUM_KEYS and not re.fullmatch(r"[a-z0-9_-]{1,20}", v): v = APPEARANCE[k]
            db.execute("INSERT OR REPLACE INTO account_settings VALUES(?,?,?)", (a["id"], k, v))
        db.commit()
    return {"ok": True}


# ------------------------- clean-IP pool and multi-location (used by /sub) -------------------------
IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?$")


def _port_ok(p):
    return p == "" or (p.isdigit() and 1 <= int(p) <= 65535)


@app.get("/api/pool")
def get_pool(a=Depends(auth)):
    return kv(a["id"], "pool", {"ips": [], "locs": [], "n": 10, "sub": 0})


@app.put("/api/pool")
def put_pool(body: dict, a=Depends(auth)):
    ips = []
    for x in (body.get("ips") or [])[:1000]:
        x = str(x).strip()
        if IP_RE.match(x) and _port_ok(x.partition(":")[2]):
            ips.append(x)
    locs = []
    for l in (body.get("locs") or [])[:100]:
        if not isinstance(l, dict):
            continue
        h, p = str(l.get("h", "")).strip(), str(l.get("p", "")).strip()
        if HOST_RE.match(h) and _port_ok(p):
            locs.append({"n": str(l.get("n", h)).strip()[:40], "h": h, "p": p})
    try:
        n = max(1, min(100, int(body.get("n", 10))))
    except (TypeError, ValueError):
        n = 10
    set_kv(a["id"], "pool", {"ips": ips, "locs": locs, "n": n, "sub": 1 if body.get("sub") else 0})
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return PlainTextResponse("ok")


@app.get("/sub/{token}")
def sub(token: str, request: Request):
    with L:
        u = db.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
        acc = db.execute("SELECT * FROM accounts WHERE id=?", (u["owner_id"],)).fetchone() if u else None
    if not u or not acc or acc["status"] != "active":
        raise HTTPException(404)
    lk = links(u, req_host(request), settings_for(acc["id"])["prefix"])
    out = [l for _, l in lk]
    cfg = kv(acc["id"], "pool")
    if cfg and cfg.get("sub"):   # clean IPs and locations are appended after the normal links
        ips = cfg.get("ips", [])[:max(1, int(cfg.get("n", 10)))]
        for _, l in lk:
            for x in ips:
                h, _, p = x.partition(":")
                out.append(with_ip(l, h, p))
            for loc in cfg.get("locs", []):
                out.append(with_ip(l, loc["h"], loc["p"]))
    h = {"subscription-userinfo": f"upload={u['up']}; download={u['down']}; total={u['limit_bytes']}; expire={u['expire']}",
         "profile-update-interval": "1", "Cache-Control": "no-store",
         "profile-title": "base64:" + base64.b64encode(TITLE.encode()).decode()}
    return Response(base64.b64encode("\n".join(out).encode()), media_type="text/plain", headers=h)


_admin_html = None


def panel_page(request: Request):
    global _admin_html
    if not me_of(request):
        return RedirectResponse("/login")
    if _admin_html is None:
        for name in ("admin.html", "index.html"):
            fp = os.path.join(HERE, name)
            if os.path.exists(fp):
                _admin_html = open(fp, encoding="utf-8").read()
                break
        if _admin_html is None:
            _admin_html = FALLBACK_HTML
    return HTMLResponse(_admin_html)


@app.get("/")
def root(request: Request):
    return panel_page(request)


@app.get("/admin")
def admin(request: Request):
    return panel_page(request)


@app.post("/setup")
def setup(body: dict, request: Request):
    """First run: the address is already on screen, the password is asked twice."""
    need_header(request)
    ip = client_ip(request)
    n, t = throttle("setup:" + ip, 20)
    fails["setup:" + ip] = (n + 1, t)
    if SETUP_KEY and not hmac.compare_digest(str(body.get("key", "")).encode(), SETUP_KEY.encode()):
        time.sleep(1.0)
        raise HTTPException(403, "Invalid setup key")
    pw = str(body.get("password", ""))
    pw2 = str(body.get("password2", body.get("confirm", pw)))
    if pw != pw2:
        raise HTTPException(400, "The two passwords do not match")
    user = (str(body.get("username", "")).strip().lower() or ADMIN_USER or "admin")
    if not SETUP_USER_RE.match(user):
        raise HTTPException(400, "Username must be 3 to 32 characters: letters, digits, dot, dash or underscore")
    if not 8 <= len(pw) <= 128:
        raise HTTPException(400, "Password must be 8 to 128 characters")
    if pw.lower() == user:
        raise HTTPException(400, "Password must differ from the username")
    with L:
        if db.execute("SELECT 1 FROM accounts WHERE role='owner'").fetchone():
            raise HTTPException(403, "Setup is already completed")
        db.execute("INSERT INTO accounts(id,email,pw_hash,role,status,max_users,max_gb,created) VALUES(1,?,?,'owner','active',0,0,?)",
                   (user, hash_pw(pw), int(time.time())))
        db.commit()
    fails.pop("setup:" + ip, None)
    return session_response(1, {"addr": public_addr(request)})


@app.get("/api/cf")
def api_cf(request: Request):
    """Cloudflare status; re-runs the sync when asked (owner only when signed in)."""
    a = me_of(request)
    if request.query_params.get("sync") and a and a["role"] == "owner":
        return cf_sync()
    return sys_get("cf") or {"state": "off", "msg": "CF_API_TOKEN not set"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if needs_setup():
        key = request.query_params.get("key", "")
        if SETUP_KEY and not hmac.compare_digest(key.encode(), SETUP_KEY.encode()):
            raise HTTPException(404)
        cf = sys_get("cf") or {"state": "off", "msg": ""}
        addr = public_addr(request)
        cfnote = {"ok": "Connected to Cloudflare · " + (cf.get("msg") or ""),
                  "error": "Cloudflare: " + (cf.get("msg") or "error"),
                  "off": "Cloudflare is not connected (optional)"}.get(cf.get("state", "off"), "")
        return HTMLResponse(SETUP.replace("__TITLE__", TITLE).replace("__ADDR__", addr)
                            .replace("__ADDRJS__", json.dumps(addr)).replace("__CFNOTE__", cfnote)
                            .replace("__CFSTATE__", cf.get("state", "off")))
    return HTMLResponse(LOGIN.replace("__TITLE__", TITLE))


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request):
    return login_page(request)


FALLBACK_HTML = """<!doctype html><meta charset="utf-8"><title>KING PANEL</title>
<body style="font:16px system-ui;background:#0b0d13;color:#e8ebf2;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center;max-width:460px;padding:28px">
<h2 style="margin:0 0 10px">admin.html is missing</h2>
<p style="color:#8b93a7;line-height:1.7">Put the panel file next to <code>main.py</code>, named
<code>admin.html</code> (or <code>index.html</code>), then restart the bot.</p></div></body>"""

SETUP = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;
 font-family:Vazirmatn,system-ui,Tahoma,sans-serif;color:#eef0f8;
 background:radial-gradient(900px 520px at 82% -12%,#4b34c4 0,transparent 62%),
            radial-gradient(760px 520px at -6% 112%,#0f6e8c 0,transparent 58%),#08090d}
.shell{width:min(880px,96vw);display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:780px){.shell{grid-template-columns:1fr}}
.card{padding:26px;border-radius:22px;background:rgba(255,255,255,.055);
 border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(20px);
 box-shadow:0 30px 80px -40px rgba(0,0,0,.9);animation:fu .55s both}
@keyframes fu{from{opacity:0;transform:translateY(16px)}}
.eye{display:inline-flex;align-items:center;gap:8px;font-size:11.5px;letter-spacing:.14em;
 text-transform:uppercase;color:#9aa3bd;border:1px solid rgba(255,255,255,.13);
 padding:5px 11px;border-radius:99px}
.dot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.16)}
.dot.err{background:#f87171;box-shadow:0 0 0 4px rgba(248,113,113,.16)}
.dot.off{background:#8b93a7;box-shadow:0 0 0 4px rgba(139,147,167,.14)}
h1{margin:16px 0 6px;font-size:25px;letter-spacing:-.4px;
 background:linear-gradient(120deg,#fff,#b9c1ff 55%,#7ee7ff);-webkit-background-clip:text;background-clip:text;color:transparent}
p{margin:0 0 16px;color:#9aa3bd;font-size:13.5px;line-height:1.75}
.addr{display:flex;align-items:center;gap:8px;background:rgba(0,0,0,.34);
 border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:11px 12px;direction:ltr}
.addr code{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;
 color:#a9f3ff;overflow:auto;white-space:nowrap;scrollbar-width:none}
.addr code::-webkit-scrollbar{display:none}
.cp{border:0;border-radius:10px;padding:7px 12px;font-size:12px;font-weight:700;cursor:pointer;
 background:rgba(255,255,255,.1);color:#e8ebf2;transition:.15s}
.cp:hover{background:rgba(255,255,255,.18)}
.note{margin-top:12px;font-size:12px;line-height:1.6;padding:9px 11px;border-radius:11px;
 background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);color:#9aa3bd}
ol{margin:14px 0 0;padding-inline-start:18px;color:#9aa3bd;font-size:12.5px;line-height:2}
.lbl{display:block;font-size:12px;color:#8b93a7;margin:12px 0 6px;font-weight:600}
input{width:100%;padding:12px 14px;border-radius:12px;border:1px solid rgba(255,255,255,.14);
 background:rgba(0,0,0,.3);color:#fff;font-size:15px;font-family:inherit;outline:none;transition:.16s}
input:focus{border-color:#7c5cff;box-shadow:0 0 0 3px rgba(124,92,255,.2)}
button.go{width:100%;margin-top:16px;padding:13px;border:0;border-radius:12px;cursor:pointer;
 background:linear-gradient(135deg,#7c5cff,#38d4ff);color:#fff;font-size:15.5px;font-weight:800;
 font-family:inherit;transition:.18s}
button.go:hover{filter:brightness(1.12);transform:translateY(-1px)}
button.go:disabled{opacity:.6;cursor:wait;transform:none}
#e{color:#ff8b98;font-size:12.5px;min-height:17px;margin-top:9px;line-height:1.6}
.meter{height:4px;border-radius:99px;background:rgba(255,255,255,.1);margin-top:9px;overflow:hidden}
.meter i{display:block;height:100%;width:0;border-radius:99px;transition:.25s;
 background:linear-gradient(90deg,#ef4444,#f59e0b,#22c55e)}
.show{display:flex;align-items:center;gap:7px;font-size:12px;color:#9aa3bd;margin-top:10px}
.show input{width:auto;margin:0}
</style></head><body>
<div class="shell">
  <div class="card">
    <span class="eye"><span class="dot __CFSTATE__"></span> King Panel · __CFNOTE__</span>
    <h1>پنل شما آماده است</h1>
    <p>این آدرسِ پنل شماست. آن را کپی کنید و همین حالا رمز جدید را تعیین کنید —
    بلافاصله بعد از تعیین رمز وارد پنل می‌شوید.</p>
    <div class="addr"><code id="addr">__ADDR__</code><button class="cp" onclick="copyAddr()">کپی</button></div>
    <div class="note" id="cpnote">آدرس پنل را در جای امن نگه دارید؛ همین آدرس، آدرس اتصال کانفیگ‌ها هم هست.</div>
    <ol>
      <li>رمز جدید را دو بار وارد کنید</li>
      <li>دکمهٔ «ساخت پنل و ورود» را بزنید</li>
      <li>مستقیم داخل پنل ادمین می‌روید</li>
    </ol>
  </div>
  <div class="card">
    <h1 style="font-size:20px;margin:0 0 4px">تعیین رمز مدیر</h1>
    <p style="margin-bottom:4px">فقط رمز را انتخاب کنید. نام کاربری پیش‌فرض <code style="color:#a9f3ff">admin</code> است و می‌توانید همین‌جا عوضش کنید.</p>
    <form onsubmit="return go(event)" autocomplete="on">
      <label class="lbl" for="u">نام کاربری (اختیاری)</label>
      <input id="u" placeholder="admin" autocomplete="username" autocapitalize="none" spellcheck="false">
      <label class="lbl" for="p">رمز جدید</label>
      <input id="p" type="password" placeholder="حداقل ۸ کاراکتر" autocomplete="new-password">
      <div class="meter"><i id="mb"></i></div>
      <label class="lbl" for="c">تکرار رمز</label>
      <input id="c" type="password" placeholder="همان رمز را دوباره وارد کنید" autocomplete="new-password">
      <label class="show"><input type="checkbox" onchange="p.type=c.type=this.checked?'text':'password'"> نمایش رمز</label>
      <button class="go" id="btn">ساخت پنل و ورود</button>
      <div id="e"></div>
    </form>
  </div>
</div>
<script>
var ADDR=__ADDRJS__;
function copyAddr(){var t=ADDR;
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,ok2)}else{ok2()}
 function ok(){$('cpnote').textContent='✅ آدرس کپی شد.'}
 function ok2(){var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();
  try{document.execCommand('copy')}catch(x){}a.remove();$('cpnote').textContent='✅ آدرس کپی شد.'}}
function $(i){return document.getElementById(i)}
function strength(v){var s=0;if(v.length>=8)s++;if(v.length>=12)s++;if(/[A-Z]/.test(v)&&/[a-z]/.test(v))s++;if(/[0-9]/.test(v))s++;if(/[^A-Za-z0-9]/.test(v))s++;return s}
$('p').addEventListener('input',function(){var s=strength(this.value);$('mb').style.width=(s/5*100)+'%'});
async function go(ev){ev.preventDefault();var E=$('e');E.textContent='';
 var pw=$('p').value,cw=$('c').value;
 if(pw!==cw){E.textContent='⛔ دو رمز یکسان نیستند.';return false}
 if(pw.length<8){E.textContent='⛔ رمز باید حداقل ۸ کاراکتر باشد.';return false}
 var b=$('btn');b.disabled=true;b.textContent='در حال ساخت...';
 var r,j={};
 try{
  r=await fetch('/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'panel'},
   body:JSON.stringify({username:$('u').value,password:pw,password2:cw,
    key:new URLSearchParams(location.search).get('key')||''})});
  try{j=await r.json()}catch(x){}
 }catch(x){b.disabled=false;b.textContent='ساخت پنل و ورود';E.textContent='⛔ خطای شبکه؛ دوباره تلاش کنید.';return false}
 if(r.ok){b.textContent='ورود به پنل...';location='/admin'}
 else{b.disabled=false;b.textContent='ساخت پنل و ورود';E.textContent='⛔ '+(j.detail||('خطا ('+r.status+')'))}
 return false}
</script></body></html>"""

LOGIN = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
font-family:Vazirmatn,system-ui,Tahoma,sans-serif;
background:radial-gradient(900px 500px at 80% -10%,#4b34c4 0,transparent 60%),
radial-gradient(700px 500px at 0 110%,#0f6e8c 0,transparent 55%),#0a0c13;color:#eef0f8}
.b{width:min(366px,92vw);padding:28px;border-radius:22px;background:rgba(255,255,255,.06);
border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(18px);animation:fu .6s both}
@keyframes fu{from{opacity:0;transform:translateY(18px)}}
h2{margin:0 0 4px}p{margin:0 0 18px;color:#9aa3bd;font-size:14px}
input{width:100%;padding:13px 14px;margin:6px 0;border-radius:12px;border:1px solid rgba(255,255,255,.14);
background:rgba(0,0,0,.3);color:#fff;font-size:15px;font-family:inherit;outline:none}
input:focus{border-color:#7c5cff;box-shadow:0 0 0 3px rgba(124,92,255,.2)}
button{width:100%;margin-top:12px;padding:13px;border:0;border-radius:12px;
background:linear-gradient(135deg,#7c5cff,#38d4ff);color:#fff;font-size:16px;font-weight:700;font-family:inherit;cursor:pointer}
button:hover{filter:brightness(1.12)}
#e{color:#ff6b7a;font-size:13px;min-height:18px;margin-top:8px}</style></head><body>
<form class="b" onsubmit="return go(event)"><h2>🔐 __TITLE__</h2><p>برای ادامه وارد شوید</p>
<input id="u" placeholder="نام کاربری" autocomplete="username" autocapitalize="none">
<input id="p" type="password" placeholder="رمز عبور" autocomplete="current-password">
<label style="font-size:13px;color:#9aa3bd;display:block;margin-top:4px">
<input type="checkbox" style="width:auto;margin:6px" onchange="p.type=this.checked?'text':'password'"> نمایش رمز</label>
<button>ورود</button><div id="e"></div></form>
<script>async function go(ev){ev.preventDefault();var E=document.getElementById('e');E.textContent='';
 var r,j={};
 try{r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'panel'},
  body:JSON.stringify({username:document.getElementById('u').value,password:document.getElementById('p').value})});
  try{j=await r.json()}catch(x){}
 }catch(x){E.textContent='خطای شبکه';return false}
 if(r.ok)location='/admin';else E.textContent=j.detail||('خطا ('+r.status+')');
 return false}</script></body></html>"""

bootstrap_owner()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(env("PORT", "8080") or 8080), log_level="info")
