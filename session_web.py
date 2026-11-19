import os, html
from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
WEB_PASS = os.environ["WEB_PASS"]
S = {}


def page(body):
    return web.Response(
        content_type="text/html",
        text='<meta name="viewport" content="width=device-width,initial-scale=1">'
             '<body style="font-family:sans-serif;max-width:420px;margin:30px auto;direction:rtl">'
             + body)


def form(step, label, ph, pw):
    return page(f'<h3>{label}</h3><form method="post" action="/{step}">'
                f'<input type="hidden" name="pw" value="{html.escape(pw)}">'
                f'<input name="v" placeholder="{ph}" style="width:100%;padding:10px" autofocus>'
                '<br><br><button style="padding:10px 20px">ادامه</button></form>')


async def home(r):
    return page('<h3>ورود</h3><form method="post" action="/phone">'
                '<input name="pw" type="password" placeholder="WEB_PASS" style="width:100%;padding:10px"><br><br>'
                '<input name="v" placeholder="+989121234567" style="width:100%;padding:10px"><br><br>'
                '<button style="padding:10px 20px">ارسال کد</button></form>')


async def phone(r):
    d = await r.post()
    if d["pw"] != WEB_PASS:
        return page("رمز اشتباه است")
    c = TelegramClient(StringSession(), API_ID, API_HASH)
    await c.connect()
    phone_ = d["v"].strip()
    sent = await c.send_code_request(phone_)
    S.update(c=c, phone=phone_, hash=sent.phone_code_hash)
    return form("code", "کد تأیید تلگرام", "12345", d["pw"])


async def code(r):
    d = await r.post()
    if d["pw"] != WEB_PASS or "c" not in S:
        return page("نامعتبر")
    try:
        await S["c"].sign_in(S["phone"], d["v"].strip(), phone_code_hash=S["hash"])
    except SessionPasswordNeededError:
        return form("twofa", "رمز دو مرحله‌ای", "password", d["pw"])
    except Exception as e:
        return page(f"خطا: {html.escape(str(e))}")
    return done()


async def twofa(r):
    d = await r.post()
    if d["pw"] != WEB_PASS or "c" not in S:
        return page("نامعتبر")
    try:
        await S["c"].sign_in(password=d["v"])
    except Exception as e:
        return page(f"خطا: {html.escape(str(e))}")
    return done()


def done():
    s = S["c"].session.save()
    return page('<h3>✅ SESSION_STRING</h3>'
                f'<textarea style="width:100%;height:220px;direction:ltr">{s}</textarea>'
                '<p>کامل کپی کن، بعد این سرویس را به حالت عادی برگردان.</p>')


app = web.Application()
app.add_routes([web.get("/", home), web.post("/phone", phone),
                web.post("/code", code), web.post("/twofa", twofa)])
web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
