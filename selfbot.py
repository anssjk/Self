#!/usr/bin/env python3
"""
Self Bot تلگرام - ۲۰ صفحه × ۶ قابلیت = ۱۲۰ قابلیت (شامل ایموجی پریمیوم)
نیازمندی: pip install telethon
اجرا:  API_ID=... API_HASH=... BOT_TOKEN=... python selfbot.py
در چت، پنل را با  .panel  باز کنید.
(در @BotFather برای ربات دستور /setinline را بزنید.)
"""
import ast, asyncio, base64, codecs, collections, datetime as dt, hashlib, io
import json, operator as op, os, platform, random, re, secrets, string, sys, time
import urllib.parse, urllib.request

import telethon
from telethon import TelegramClient, events, Button, types, functions
from telethon.sessions import StringSession
from telethon.helpers import add_surrogate
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetStickerSetRequest

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

SESSION_STRING = os.environ.get("SESSION_STRING")  # برای Railway (با gen_session.py بسازید)
user = TelegramClient(StringSession(SESSION_STRING) if SESSION_STRING else "self_session",
                      API_ID, API_HASH)
bot = TelegramClient(StringSession() if SESSION_STRING else "panel_bot", API_ID, API_HASH)
ME = None
BOT_USERNAME = None
START = time.time()

# ---------------- تنظیمات ماندگار ----------------
FILE = os.environ.get("SETTINGS_FILE", "settings.json")  # روی Railway: /data/settings.json
S = json.load(open(FILE)) if os.path.exists(FILE) else {}


def save():
    json.dump(S, open(FILE, "w"), ensure_ascii=False)


# ---------------- تعریف ۱۰ صفحه × ۶ قابلیت ----------------
# kind: t = کلید روشن/خاموش ، c = دستور
PAGES = [
    ("🟦", "عمومی", [
        ("ping", "پینگ", "c", ".ping → سنجش تاخیر"),
        ("time", "ساعت", "c", ".time → ساعت فعلی"),
        ("date", "تاریخ", "c", ".date → تاریخ امروز"),
        ("id", "آیدی", "c", ".id → آیدی چت (یا ریپلای)"),
        ("info", "اطلاعات چت", "c", ".info → مشخصات چت"),
        ("help", "راهنما", "c", ".help → راهنما | .panel → پنل"),
    ]),
    ("🟩", "استایل متن", [
        ("bold", "Bold", "t", "همه پیام‌های خروجی را بولد می‌کند"),
        ("italic", "Italic", "t", "همه پیام‌های خروجی را کج می‌کند"),
        ("mono", "Mono", "t", "همه پیام‌ها را مونو می‌کند"),
        ("underline", "Underline", "t", "همه پیام‌ها را زیرخط‌دار می‌کند"),
        ("strike", "Strike", "t", "همه پیام‌ها را خط‌خورده می‌کند"),
        ("spoiler", "Spoiler", "t", "همه پیام‌ها را اسپویلر می‌کند"),
    ]),
    ("🟨", "ابزار متن", [
        ("upper", "بزرگ", "c", ".upper متن (یا ریپلای)"),
        ("lower", "کوچک", "c", ".lower متن (یا ریپلای)"),
        ("reverse", "وارونه", "c", ".reverse متن (یا ریپلای)"),
        ("mock", "مسخره", "c", ".mock متن → aLtErNaTe"),
        ("spaced", "فاصله‌دار", "c", ".spaced متن → م ت ن"),
        ("title", "تایتل", "c", ".title متن → Title Case"),
    ]),
    ("🟪", "اکشن خودکار", [
        ("typing", "تایپینگ", "t", "با پیام جدید در پیوی، حالت تایپ نشان می‌دهد"),
        ("recvoice", "ضبط ویس", "t", "با پیام جدید در پیوی، حالت ضبط ویس"),
        ("game", "بازی", "t", "با پیام جدید در پیوی، حالت بازی"),
        ("autoread_pv", "سین پیوی", "t", "پیام‌های پیوی خودکار خوانده شوند"),
        ("autoread_gp", "سین گروه", "t", "پیام‌های گروه خودکار خوانده شوند"),
        ("autoread_ch", "سین کانال", "t", "پیام‌های کانال خودکار خوانده شوند"),
    ]),
    ("🟧", "پیام‌ها", [
        ("autoreply", "پاسخ خودکار", "t", "به پیوی‌ها (هر نفر ساعتی یک‌بار) پاسخ می‌دهد"),
        ("setreply", "متن پاسخ", "c", ".setreply متن → تنظیم متن پاسخ خودکار"),
        ("mentionlog", "لاگ منشن", "t", "منشن‌ها به Saved Messages فوروارد می‌شوند"),
        ("replylog", "لاگ ریپلای", "t", "ریپلای به پیام‌های شما ذخیره می‌شود"),
        ("save", "ذخیره", "c", ".save (ریپلای) → فوروارد به Saved"),
        ("del", "حذف", "c", ".del (ریپلای) → حذف پیام ریپلای‌شده خودتان"),
    ]),
    ("🟥", "ریاضی و کدینگ", [
        ("calc", "ماشین‌حساب", "c", ".calc 2*(3+4)"),
        ("rand", "عدد تصادفی", "c", ".rand 1 100"),
        ("coin", "شیر یا خط", "c", ".coin"),
        ("pass", "رمز ساز", "c", ".pass 16 → رمز تصادفی"),
        ("b64e", "Base64 ➜", "c", ".b64e متن"),
        ("b64d", "Base64 ⬅", "c", ".b64d متن"),
    ]),
    ("🟦", "اکانت", [
        ("stats", "آمار چت‌ها", "c", ".stats → تعداد پیوی/گروه/کانال"),
        ("setbio", "بیو", "c", ".setbio متن"),
        ("setname", "نام", "c", ".setname نام | نام‌خانوادگی"),
        ("uptime", "آپتایم", "c", ".uptime → مدت روشن بودن بات"),
        ("me", "پروفایل من", "c", ".me → مشخصات اکانت"),
        ("ver", "ورژن", "c", ".ver → نسخه پایتون و Telethon"),
    ]),
    ("🟩", "گروه", [
        ("members", "تعداد اعضا", "c", ".members"),
        ("admins", "ادمین‌ها", "c", ".admins"),
        ("pin", "پین", "c", ".pin (ریپلای)"),
        ("unpin", "آن‌پین", "c", ".unpin (ریپلای)"),
        ("purge", "پاکسازی", "c", ".purge 10 → حذف ۱۰ پیام خودتان"),
        ("whois", "کیه؟", "c", ".whois (ریپلای) → مشخصات فرد"),
    ]),
    ("🟨", "سرگرمی", [
        ("dice", "🎲 تاس", "c", ".dice"),
        ("dart", "🎯 دارت", "c", ".dart"),
        ("basket", "🏀 بسکتبال", "c", ".basket"),
        ("football", "⚽ فوتبال", "c", ".football"),
        ("slot", "🎰 اسلات", "c", ".slot"),
        ("bowling", "🎳 بولینگ", "c", ".bowling"),
    ]),
    ("🟪", "زمان و وضعیت", [
        ("nameclock", "ساعت در نام", "t", "ساعت در فامیلی پروفایل (هر دقیقه)"),
        ("bioclock", "ساعت در بیو", "t", "ساعت در بیو (هر دقیقه)"),
        ("afk", "AFK روشن", "c", ".afk دلیل → پاسخ خودکار «نیستم»"),
        ("unafk", "AFK خاموش", "c", ".unafk"),
        ("sd", "پیام خودحذف", "c", ".sd 10 متن → بعد از ۱۰ ثانیه پاک می‌شود"),
        ("later", "ارسال زمان‌دار", "c", ".later 60 متن → ارسال بعد از ۶۰ ثانیه"),
    ]),
    ("⭐", "ایموجی پریمیوم", [
        ("autope", "تبدیل خودکار", "t", "ایموجی‌های پیام‌های خروجی خودکار پریمیوم شوند"),
        ("setpack", "انتخاب پک", "c", ".setpack لینک یا نام پک ایموجی"),
        ("pe", "تبدیل دستی", "c", ".pe متن (یا ریپلای) → ایموجی پریمیوم"),
        ("emojilist", "لیست پک", "c", ".emojilist → ایموجی‌های پک انتخابی"),
        ("ceid", "آیدی ایموجی", "c", ".ceid (ریپلای) → آیدی ایموجی پریمیوم"),
        ("ce", "ارسال با آیدی", "c", ".ce آیدی 😀 → ارسال ایموجی با آیدی"),
    ]),
    ("🟫", "حریم و امنیت", [
        ("antidel", "ضد حذف", "t", "پیام‌های حذف‌شده پیوی (متن) به Saved Messages می‌آید"),
        ("antiedit", "ضد ویرایش", "t", "متن قبل و بعد از ویرایش پیام‌های پیوی ذخیره می‌شود"),
        ("mute", "بی‌صدا", "c", ".mute → بی‌صدا کردن چت | .mute off"),
        ("archive", "آرشیو", "c", ".archive → آرشیو چت | .archive off"),
        ("block", "بلاک", "c", ".block (ریپلای یا پیوی) | .block off"),
        ("sessions", "نشست‌ها", "c", ".sessions → دستگاه‌های وارد‌شده به اکانت"),
    ]),
    ("🔷", "متن پیشرفته", [
        ("font", "فونت", "c", ".font 1..7 متن → فونت‌های یونیکد (بدون عدد: لیست)"),
        ("morse", "مورس", "c", ".morse متن → رمزگذاری یا رمزگشایی"),
        ("bin", "باینری", "c", ".bin متن → باینری ↔ متن"),
        ("rot13", "ROT13", "c", ".rot13 متن"),
        ("wc", "شمارش", "c", ".wc متن (یا ریپلای) → کاراکتر، کلمه، خط"),
        ("hash", "هش", "c", ".hash متن → MD5 / SHA1 / SHA256"),
    ]),
    ("🔶", "کارهای روزمره", [
        ("todo", "تودو", "c", ".todo add متن | list | done N | clear"),
        ("note", "یادداشت", "c", ".note save نام متن | get نام | list | del نام"),
        ("remind", "یادآور", "c", ".remind 10m متن → یادآوری در Saved (s/m/h/d)"),
        ("poll", "نظرسنجی", "c", ".poll سوال | گزینه۱ | گزینه۲"),
        ("convert", "تبدیل واحد", "c", ".convert 10 km mi | 30 c f | 5 kg lb"),
        ("age", "محاسبه سن", "c", ".age 1990-05-12"),
    ]),
    ("⬛", "اینترنت", [
        ("weather", "آب‌وهوا", "c", ".weather Tehran"),
        ("ip", "اطلاعات IP", "c", ".ip 8.8.8.8"),
        ("short", "کوتاه‌کننده", "c", ".short لینک → لینک کوتاه"),
        ("qr", "QR کد", "c", ".qr متن یا لینک → عکس QR"),
        ("crypto", "قیمت ارز دیجیتال", "c", ".crypto btc | eth | ton | sol | doge"),
        ("wiki", "ویکی‌پدیا", "c", ".wiki عنوان | .wiki fa عنوان"),
    ]),
    ("🔴", "مدیا و پروفایل", [
        ("download", "دانلود مدیا", "c", ".download (ریپلای) → ذخیره در پوشه downloads"),
        ("fileinfo", "مشخصات فایل", "c", ".fileinfo (ریپلای) → حجم، نوع، مدت"),
        ("asdoc", "ارسال به‌صورت فایل", "c", ".asdoc (ریپلای روی عکس/ویدیو)"),
        ("pfp", "عکس پروفایل", "c", ".pfp (ریپلای) → عکس پروفایل فرد"),
        ("setpfp", "ست پروفایل", "c", ".setpfp (ریپلای روی عکس) → عکس پروفایل شما"),
        ("delpfp", "حذف پروفایل", "c", ".delpfp → حذف آخرین عکس پروفایل شما"),
    ]),
    ("🟠", "بازی و شوخی", [
        ("rps", "سنگ کاغذ قیچی", "c", ".rps r | p | s"),
        ("8ball", "توپ جادویی", "c", ".8ball سوال شما"),
        ("td", "جرأت حقیقت", "c", ".td truth | dare"),
        ("love", "تست عشق", "c", ".love نام۱ | نام۲"),
        ("hack", "هک شوخی", "c", ".hack → انیمیشن هک الکی 😄"),
        ("bar", "نوار لودینگ", "c", ".bar → انیمیشن پیشرفت"),
    ]),
    ("🔵", "اتوماسیون", [
        ("autodel", "حذف خودکار", "t", "پیام‌های خروجی بعد از N ثانیه پاک می‌شوند (.autodelsec)"),
        ("kwreply", "پاسخ کلیدواژه", "t", "در پیوی به کلیدواژه‌های ثبت‌شده با .kw پاسخ می‌دهد"),
        ("sign", "امضا", "c", ".sign متن → امضا زیر پیام‌ها | .sign off"),
        ("kw", "کلیدواژه‌ها", "c", ".kw add کلمه | پاسخ ، .kw list ، .kw del کلمه"),
        ("readall", "خواندن همه", "c", ".readall → علامت خوانده‌شده برای همه چت‌ها"),
        ("backup", "بکاپ", "c", ".backup → ارسال فایل تنظیمات به Saved"),
    ]),
    ("🟣", "مدیریت گروه (ادمین)", [
        ("ban", "بن", "c", ".ban (ریپلای) | .ban off برای آن‌بن"),
        ("kick", "کیک", "c", ".kick (ریپلای) → اخراج بدون بن دائم"),
        ("muteu", "سکوت عضو", "c", ".muteu 30 (ریپلای) → سکوت ۳۰ دقیقه | .muteu off"),
        ("promote", "ادمین کردن", "c", ".promote (ریپلای) | .promote off"),
        ("gtitle", "نام گروه", "c", ".gtitle نام جدید"),
        ("slowmode", "حالت آهسته", "c", ".slowmode 10 (0،10،30،60،300،900،3600)"),
    ]),
    ("💎", "ویژه", [
        ("autodelsec", "زمان حذف خودکار", "c", ".autodelsec 30 → ثانیه برای حذف خودکار"),
        ("export", "خروجی چت", "c", ".export 200 → فایل متنی آخرین پیام‌ها"),
        ("search", "جستجو در چت", "c", ".search کلمه → ۵ نتیجه آخر"),
        ("msgcount", "تعداد پیام‌های من", "c", ".msgcount → تعداد پیام‌های شما در این چت"),
        ("top", "فعال‌ترین‌ها", "c", ".top → ۵ نفر فعال در ۵۰۰ پیام اخیر"),
        ("restart", "ری‌استارت", "c", ".restart → راه‌اندازی مجدد بات"),
    ]),
]
FIND = {f[0]: (i, f) for i, p in enumerate(PAGES) for f in p[2]}


# ---------------- پنل شیشه‌ای ----------------
def page_text(i):
    c, title, _ = PAGES[i]
    return f"{c} **پنل سلف — {title}**\nصفحه {i + 1} از {len(PAGES)}\n\nیک قابلیت را انتخاب کنید 👇"


def fbtn(f):
    key, label, kind, _ = f
    if kind == "t":
        mark = "🟢" if S.get(key) else "🔴"
    else:
        mark = "🔹"
    return Button.inline(f"{mark} {label}", f"f:{key}")


def page_buttons(i):
    feats = PAGES[i][2]
    rows = [[fbtn(f) for f in feats[a:a + 2]] for a in range(0, 6, 2)]
    rows.append([
        Button.inline("◀️", f"p:{(i - 1) % len(PAGES)}"),
        Button.inline(f"📄 {i + 1}/{len(PAGES)}", "n:0"),
        Button.inline("▶️", f"p:{(i + 1) % len(PAGES)}"),
    ])
    rows.append([Button.inline("❌ بستن", "x:0")])
    return rows


@bot.on(events.InlineQuery)
async def inline(event):
    if event.sender_id != ME.id:
        return await event.answer([], cache_time=0)
    r = event.builder.article("Panel", text=page_text(0), buttons=page_buttons(0))
    await event.answer([r], cache_time=0)


async def on_toggle(key, val):
    if key == "nameclock":
        if val:
            S["ln_base"] = (await user.get_me()).last_name or ""
        else:
            await user(UpdateProfileRequest(last_name=S.get("ln_base", "")))
    elif key == "bioclock":
        if val:
            full = await user(GetFullUserRequest("me"))
            S["bio_base"] = full.full_user.about or ""
        else:
            await user(UpdateProfileRequest(about=S.get("bio_base", "")))


@bot.on(events.CallbackQuery)
async def cb(event):
    if event.sender_id != ME.id:
        return await event.answer("⛔ این پنل مخصوص صاحب اکانت است", alert=True)
    kind, _, val = event.data.decode().partition(":")
    if kind == "p":
        i = int(val)
        await event.edit(page_text(i), buttons=page_buttons(i))
    elif kind == "f":
        i, f = FIND[val]
        if f[2] == "t":
            S[val] = not S.get(val, False)
            await on_toggle(val, S[val])
            save()
            await event.edit(page_text(i), buttons=page_buttons(i))
            await event.answer(("روشن شد ✅" if S[val] else "خاموش شد ❌"))
        else:
            await event.answer(f[3][:190], alert=True)
    elif kind == "x":
        await event.edit("✅ پنل بسته شد.", buttons=None)
    else:
        await event.answer()


# ---------------- دستورات متنی ----------------
CMD = {}


def cmd(*names):
    def deco(fn):
        for n in names:
            CMD[n] = fn
        return fn
    return deco


async def get_text(event, arg):
    if arg:
        return arg
    r = await event.get_reply_message()
    return (r.raw_text or "") if r else ""


def textcmd(name, f):
    async def h(event, arg):
        t = await get_text(event, arg)
        if t:
            await event.edit(f(t))
    CMD[name] = h


textcmd("upper", str.upper)
textcmd("lower", str.lower)
textcmd("reverse", lambda t: t[::-1])
textcmd("mock", lambda t: "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(t)))
textcmd("spaced", lambda t: " ".join(t))
textcmd("title", str.title)
textcmd("b64e", lambda t: base64.b64encode(t.encode()).decode())
textcmd("b64d", lambda t: base64.b64decode(t.encode()).decode())


@cmd("ping")
async def _(event, arg):
    t = time.perf_counter()
    await event.edit("🏓 ...")
    await event.edit(f"🏓 Pong! `{(time.perf_counter() - t) * 1000:.0f} ms`")


@cmd("time")
async def _(event, arg):
    await event.edit(f"🕒 {dt.datetime.now():%H:%M:%S}")


@cmd("date")
async def _(event, arg):
    await event.edit(f"📅 {dt.datetime.now():%Y-%m-%d (%A)}")


@cmd("id")
async def _(event, arg):
    r = await event.get_reply_message()
    await event.edit(f"🆔 کاربر: `{r.sender_id}`\n💬 چت: `{event.chat_id}`" if r else f"💬 چت: `{event.chat_id}`")


@cmd("info")
async def _(event, arg):
    c = await event.get_chat()
    name = getattr(c, "title", None) or getattr(c, "first_name", "")
    await event.edit(f"ℹ️ نام: {name}\n🆔 `{event.chat_id}`\n📦 نوع: {type(c).__name__}")


@cmd("help")
async def _(event, arg):
    await event.edit("🎛 برای دیدن همه ۶۰ قابلیت، دستور `.panel` را بفرستید.")


@cmd("setreply")
async def _(event, arg):
    S["reply_text"] = arg or "سلام! فعلاً در دسترس نیستم، بعداً پاسخ می‌دهم."
    save()
    await event.edit("✅ متن پاسخ خودکار ذخیره شد.")


@cmd("save")
async def _(event, arg):
    r = await event.get_reply_message()
    if r:
        await r.forward_to("me")
    await event.delete()


@cmd("del")
async def _(event, arg):
    r = await event.get_reply_message()
    if r and r.out:
        await r.delete()
    await event.delete()


# --- ریاضی ---
OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
       ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv, ast.USub: op.neg}


def ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, ast.Pow) and abs(ev(n.right)) > 100:
            raise ValueError("توان خیلی بزرگ")
        return OPS[type(n.op)](ev(n.left), ev(n.right))
    if isinstance(n, ast.UnaryOp):
        return OPS[type(n.op)](ev(n.operand))
    raise ValueError("عبارت نامعتبر")


@cmd("calc")
async def _(event, arg):
    await event.edit(f"🧮 `{arg}` = `{ev(ast.parse(arg, mode='eval').body)}`")


@cmd("rand")
async def _(event, arg):
    a = [int(x) for x in arg.split()] or [1, 100]
    lo, hi = (a[0], a[1]) if len(a) > 1 else (1, a[0])
    await event.edit(f"🎯 `{random.randint(lo, hi)}`")


@cmd("coin")
async def _(event, arg):
    await event.edit(random.choice(["🪙 شیر", "🪙 خط"]))


@cmd("pass")
async def _(event, arg):
    n = min(int(arg or 16), 64)
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    await event.edit("🔐 `" + "".join(secrets.choice(chars) for _ in range(n)) + "`")


# --- اکانت ---
@cmd("stats")
async def _(event, arg):
    pv = gp = ch = 0
    async for d in user.iter_dialogs():
        if d.is_user:
            pv += 1
        elif d.is_group:
            gp += 1
        elif d.is_channel:
            ch += 1
    await event.edit(f"📊 پیوی: {pv}\n👥 گروه: {gp}\n📢 کانال: {ch}")


@cmd("setbio")
async def _(event, arg):
    await user(UpdateProfileRequest(about=arg[:70]))
    await event.edit("✅ بیو تغییر کرد.")


@cmd("setname")
async def _(event, arg):
    first, _, last = arg.partition("|")
    await user(UpdateProfileRequest(first_name=first.strip(), last_name=last.strip()))
    await event.edit("✅ نام تغییر کرد.")


@cmd("uptime")
async def _(event, arg):
    s = int(time.time() - START)
    await event.edit(f"⏱ {s // 3600}h {s % 3600 // 60}m {s % 60}s")


@cmd("me")
async def _(event, arg):
    m = await user.get_me()
    await event.edit(f"👤 {m.first_name} {m.last_name or ''}\n🆔 `{m.id}`\n🔗 @{m.username or '-'}")


@cmd("ver")
async def _(event, arg):
    await event.edit(f"🐍 Python {platform.python_version()}\n📦 Telethon {telethon.__version__}")


# --- گروه ---
@cmd("members")
async def _(event, arg):
    p = await user.get_participants(event.chat_id, limit=0)
    await event.edit(f"👥 تعداد اعضا: {p.total}")


@cmd("admins")
async def _(event, arg):
    names = []
    async for u in user.iter_participants(event.chat_id, filter=types.ChannelParticipantsAdmins):
        names.append(f"• {u.first_name or ''} (@{u.username or '-'})")
    await event.edit("👮 ادمین‌ها:\n" + "\n".join(names[:30]))


@cmd("pin")
async def _(event, arg):
    r = await event.get_reply_message()
    if r:
        await r.pin()
    await event.delete()


@cmd("unpin")
async def _(event, arg):
    r = await event.get_reply_message()
    if r:
        await r.unpin()
    await event.delete()


@cmd("purge")
async def _(event, arg):
    n = min(int(arg or 5), 100)
    ids = [m.id async for m in user.iter_messages(event.chat_id, from_user="me", limit=n + 1)]
    await user.delete_messages(event.chat_id, ids)


@cmd("whois")
async def _(event, arg):
    r = await event.get_reply_message()
    if not r:
        return await event.edit("روی پیام یک نفر ریپلای کنید.")
    u = await r.get_sender()
    await event.edit(f"🔎 {getattr(u, 'first_name', '')}\n🆔 `{u.id}`\n🔗 @{getattr(u, 'username', None) or '-'}")


# --- سرگرمی ---
def dicecmd(name, emoji):
    async def h(event, arg):
        await event.delete()
        await user.send_file(event.chat_id, types.InputMediaDice(emoji))
    CMD[name] = h


for n, e in [("dice", "🎲"), ("dart", "🎯"), ("basket", "🏀"),
             ("football", "⚽"), ("slot", "🎰"), ("bowling", "🎳")]:
    dicecmd(n, e)


# --- زمان و وضعیت ---
@cmd("afk")
async def _(event, arg):
    S["afk"] = arg or "نیستم"
    save()
    await event.edit(f"😴 AFK روشن شد: {S['afk']}")


@cmd("unafk")
async def _(event, arg):
    S.pop("afk", None)
    save()
    await event.edit("✅ AFK خاموش شد.")


@cmd("sd")
async def _(event, arg):
    n, _, txt = arg.partition(" ")
    await event.edit(txt)
    await asyncio.sleep(min(int(n), 3600))
    await event.delete()


@cmd("later")
async def _(event, arg):
    n, _, txt = arg.partition(" ")
    chat = event.chat_id
    await event.edit(f"⏳ ارسال می‌شود بعد از {n} ثانیه")

    async def go():
        await asyncio.sleep(min(int(n), 86400))
        await user.send_message(chat, txt)
    asyncio.create_task(go())


# ---------------- هندلر پیام‌های خروجی ----------------
# ---------------- ایموجی پریمیوم ----------------
EMOJI_MAP = {}  # ایموجی ساده -> document_id ایموجی پریمیوم


def _norm(e):
    return e.replace("\ufe0f", "")


async def load_pack(short):
    r = await user(GetStickerSetRequest(types.InputStickerSetShortName(short), hash=0))
    m = {}
    for p in r.packs:
        if p.documents:
            m.setdefault(_norm(p.emoticon), p.documents[0])
    return m


def pe_entities(text):
    ents, off = [], 0
    for ch in text:
        n = len(add_surrogate(ch))
        if ch == "\ufe0f":
            if ents and ents[-1].offset + ents[-1].length == off:
                ents[-1].length += n
        elif ch in EMOJI_MAP:
            ents.append(types.MessageEntityCustomEmoji(
                offset=off, length=n, document_id=EMOJI_MAP[ch]))
        off += n
    return ents


@cmd("setpack")
async def _(event, arg):
    short = arg.strip().split("/")[-1]
    EMOJI_MAP.clear()
    EMOJI_MAP.update(await load_pack(short))
    S["pe_pack"] = short
    save()
    warn = "" if getattr(ME, "premium", False) else "\n⚠️ اکانت شما پریمیوم نیست؛ ایموجی‌ها معمولی نمایش داده می‌شوند."
    await event.edit(f"✅ پک `{short}` لود شد ({len(EMOJI_MAP)} ایموجی){warn}")


@cmd("pe")
async def _(event, arg):
    t = await get_text(event, arg)
    if not t:
        return
    if not EMOJI_MAP:
        return await event.edit("اول با `.setpack` یک پک ایموجی انتخاب کنید.")
    await event.edit(t, formatting_entities=pe_entities(t))


@cmd("emojilist")
async def _(event, arg):
    await event.edit("🧩 " + (" ".join(EMOJI_MAP)[:3500] or "پکی انتخاب نشده"))


@cmd("ceid")
async def _(event, arg):
    r = await event.get_reply_message()
    ids = [str(e.document_id) for e in (r.entities or [])
           if isinstance(e, types.MessageEntityCustomEmoji)] if r else []
    await event.edit("🆔 " + ("\n".join(f"`{i}`" for i in ids) if ids
                              else "روی پیامی که ایموجی پریمیوم دارد ریپلای کنید."))


@cmd("ce")
async def _(event, arg):
    i, _, emo = arg.partition(" ")
    emo = emo.strip() or "⭐"
    await event.edit(emo, formatting_entities=[types.MessageEntityCustomEmoji(
        offset=0, length=len(add_surrogate(emo)), document_id=int(i))])


# =============== پیاده‌سازی صفحه‌های ۱۲ تا ۲۰ ===============
def _http(url, binary=False, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = r.read()
    return d if binary else d.decode("utf-8", "ignore")


async def fetch(url, binary=False):
    return await asyncio.get_running_loop().run_in_executor(None, _http, url, binary)


async def target(event):
    r = await event.get_reply_message()
    if not r:
        raise ValueError("روی پیام فرد ریپلای کنید")
    return r.sender_id


async def _del_later(chat, mid, secs):
    await asyncio.sleep(secs)
    try:
        await user.delete_messages(chat, mid)
    except Exception:
        pass


# ---- ۱۲: حریم و امنیت ----
MSG_CACHE = collections.OrderedDict()


@user.on(events.NewMessage(incoming=True))
async def cache_in(event):
    if event.is_private and (S.get("antidel") or S.get("antiedit")):
        MSG_CACHE[event.id] = (event.sender_id, event.raw_text or "<مدیا>")
        while len(MSG_CACHE) > 3000:
            MSG_CACHE.popitem(last=False)


@user.on(events.MessageDeleted)
async def on_deleted(event):
    if not S.get("antidel"):
        return
    for i in event.deleted_ids:
        if i in MSG_CACHE:
            sid, t = MSG_CACHE.pop(i)
            await user.send_message("me", f"🗑 پیام حذف‌شده از `{sid}`:\n{t}")


@user.on(events.MessageEdited(incoming=True))
async def on_edited(event):
    if not (S.get("antiedit") and event.is_private):
        return
    old = MSG_CACHE.get(event.id)
    new = event.raw_text or "<مدیا>"
    if old and old[1] != new:
        await user.send_message("me", f"✏️ ویرایش از `{old[0]}`:\nقبل: {old[1]}\nبعد: {new}")
    MSG_CACHE[event.id] = (event.sender_id, new)


@cmd("mute")
async def _(event, arg):
    peer = await user.get_input_entity(event.chat_id)
    until = 0 if arg == "off" else 2 ** 31 - 1
    await user(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(peer),
        settings=types.InputPeerNotifySettings(mute_until=until)))
    await event.edit("🔕 بی‌صدا شد." if until else "🔔 صدا فعال شد.")


@cmd("archive")
async def _(event, arg):
    await user.edit_folder(event.chat_id, 0 if arg == "off" else 1)
    await event.edit("📦 انجام شد.")


@cmd("block")
async def _(event, arg):
    r = await event.get_reply_message()
    peer = await user.get_input_entity(r.sender_id if r else event.chat_id)
    req = functions.contacts.UnblockRequest if arg == "off" else functions.contacts.BlockRequest
    await user(req(peer))
    await event.edit("✅ انجام شد.")


@cmd("sessions")
async def _(event, arg):
    r = await user(functions.account.GetAuthorizationsRequest())
    lines = [f"{'🟢' if a.current else '⚪'} {a.device_model} · {a.app_name} · "
             f"{a.country or '-'} · {a.date_active:%m-%d %H:%M}" for a in r.authorizations]
    await event.edit("🔐 نشست‌های فعال:\n" + "\n".join(lines[:15]))


# ---- ۱۳: متن پیشرفته ----
def _mk(up, lo):
    def f(t):
        out = []
        for c in t:
            if "A" <= c <= "Z":
                out.append(chr(up + ord(c) - 65))
            elif "a" <= c <= "z":
                out.append(chr(lo + ord(c) - 97))
            else:
                out.append(c)
        return "".join(out)
    return f


FONTS = {
    "1": ("Bold", _mk(0x1D400, 0x1D41A)),
    "2": ("Bold Italic", _mk(0x1D468, 0x1D482)),
    "3": ("Sans", _mk(0x1D5A0, 0x1D5BA)),
    "4": ("Sans Bold", _mk(0x1D5D4, 0x1D5EE)),
    "5": ("Mono", _mk(0x1D670, 0x1D68A)),
    "6": ("Fullwidth", _mk(0xFF21, 0xFF41)),
    "7": ("Circled", _mk(0x24B6, 0x24D0)),
}


@cmd("font")
async def _(event, arg):
    k, _, t = arg.partition(" ")
    if k not in FONTS or not t.strip():
        return await event.edit("🔤 فونت‌ها:\n" + "\n".join(f"{i}. {n[0]}: {n[1]('Abc')}" for i, n in FONTS.items()))
    await event.edit(FONTS[k][1](t))


MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.",
         "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.",
         "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-",
         "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", "0": "-----",
         "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
         "7": "--...", "8": "---..", "9": "----."}
MORSE_REV = {v: k for k, v in MORSE.items()}


@cmd("morse")
async def _(event, arg):
    t = await get_text(event, arg)
    if t and set(t) <= set(".-/ "):
        out = " ".join("".join(MORSE_REV.get(c, "?") for c in w.split()) for w in t.split("/"))
    else:
        out = " / ".join(" ".join(MORSE.get(c.upper(), "?") for c in w) for w in t.split())
    await event.edit(out)


@cmd("bin")
async def _(event, arg):
    t = await get_text(event, arg)
    if t and set(t) <= set("01 "):
        out = bytes(int(b, 2) for b in t.split()).decode(errors="ignore")
    else:
        out = " ".join(f"{b:08b}" for b in t.encode())
    await event.edit(out)


textcmd("rot13", lambda t: codecs.encode(t, "rot13"))


@cmd("wc")
async def _(event, arg):
    t = await get_text(event, arg)
    await event.edit(f"🔢 کاراکتر: {len(t)}\n📝 کلمه: {len(t.split())}\n📄 خط: {len(t.splitlines())}")


@cmd("hash")
async def _(event, arg):
    t = await get_text(event, arg)
    b = t.encode()
    await event.edit(f"🔑 MD5:\n`{hashlib.md5(b).hexdigest()}`\nSHA1:\n`{hashlib.sha1(b).hexdigest()}`\n"
                     f"SHA256:\n`{hashlib.sha256(b).hexdigest()}`")


# ---- ۱۴: کارهای روزمره ----
@cmd("todo")
async def _(event, arg):
    L = S.setdefault("todo", [])
    sub, _, rest = arg.partition(" ")
    if sub == "add" and rest:
        L.append(rest)
    elif sub == "done":
        L.pop(int(rest) - 1)
    elif sub == "clear":
        L.clear()
    save()
    await event.edit("📝 کارها:\n" + ("\n".join(f"{i}. {x}" for i, x in enumerate(L, 1)) or "خالی"))


@cmd("note")
async def _(event, arg):
    N = S.setdefault("notes", {})
    sub, _, rest = arg.partition(" ")
    if sub == "get":
        return await event.edit(N.get(rest.strip(), "پیدا نشد"))
    if sub == "save":
        name, _, txt = rest.partition(" ")
        N[name] = txt or await get_text(event, "")
    elif sub == "del":
        N.pop(rest.strip(), None)
    save()
    await event.edit("🗒 یادداشت‌ها: " + (", ".join(N) or "خالی"))


@cmd("remind")
async def _(event, arg):
    m = re.match(r"(\d+)([smhd])\s+(.+)", arg)
    if not m:
        raise ValueError("مثال: .remind 10m تماس بگیر")
    secs = int(m[1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m[2]]
    msg = m[3]

    async def go():
        await asyncio.sleep(secs)
        await user.send_message("me", f"⏰ یادآوری: {msg}")
    asyncio.create_task(go())
    await event.edit(f"⏰ یادآوری ثبت شد (تا ری‌استارت بات معتبر است).")


@cmd("poll")
async def _(event, arg):
    q, *opts = [x.strip() for x in arg.split("|")]
    if len(opts) < 2:
        raise ValueError("حداقل دو گزینه لازم است")
    TW = getattr(types, "TextWithEntities", None)
    mk = (lambda s: TW(s, [])) if TW else (lambda s: s)
    poll = types.Poll(id=random.randint(1, 2 ** 31), question=mk(q),
                      answers=[types.PollAnswer(mk(o), bytes([i])) for i, o in enumerate(opts[:10])])
    await event.delete()
    await user.send_file(event.chat_id, types.InputMediaPoll(poll=poll))


LEN = {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "ft": 0.3048, "in": 0.0254}
MASS = {"kg": 1, "g": 0.001, "lb": 0.45359237, "oz": 0.0283495}


@cmd("convert")
async def _(event, arg):
    v, a, b = arg.split()
    v, a, b = float(v), a.lower(), b.lower()
    if a in ("c", "f", "k") and b in ("c", "f", "k"):
        c = {"c": v, "f": (v - 32) * 5 / 9, "k": v - 273.15}[a]
        r = {"c": c, "f": c * 9 / 5 + 32, "k": c + 273.15}[b]
    else:
        for tbl in (LEN, MASS):
            if a in tbl and b in tbl:
                r = v * tbl[a] / tbl[b]
                break
        else:
            raise ValueError("واحد نامعتبر")
    await event.edit(f"📐 {v:g} {a} = `{r:.4g}` {b}")


@cmd("age")
async def _(event, arg):
    b = dt.datetime.strptime(arg.strip(), "%Y-%m-%d").date()
    t = dt.date.today()
    y = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    await event.edit(f"🎂 سن: {y} سال | {(t - b).days:,} روز")


# ---- ۱۵: اینترنت ----
@cmd("weather")
async def _(event, arg):
    await event.edit("🌦 " + (await fetch(f"https://wttr.in/{urllib.parse.quote(arg)}?format=3")).strip())


@cmd("ip")
async def _(event, arg):
    d = json.loads(await fetch(f"http://ip-api.com/json/{urllib.parse.quote(arg)}"))
    if d.get("status") != "success":
        raise ValueError("IP نامعتبر")
    await event.edit(f"🌍 {d['query']}\n{d['country']} / {d['regionName']} / {d['city']}\n🏢 {d['isp']}")


@cmd("short")
async def _(event, arg):
    u = await fetch(f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(arg)}")
    await event.edit(f"🔗 {u.strip()}")


@cmd("qr")
async def _(event, arg):
    t = await get_text(event, arg)
    data = await fetch("https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
                       + urllib.parse.quote(t), True)
    bio = io.BytesIO(data)
    bio.name = "qr.png"
    await event.delete()
    await user.send_file(event.chat_id, bio, caption=f"📱 {t[:100]}")


CRYPTO = {"btc": "bitcoin", "eth": "ethereum", "ton": "the-open-network",
          "sol": "solana", "doge": "dogecoin", "usdt": "tether"}


@cmd("crypto")
async def _(event, arg):
    cid = CRYPTO.get(arg.lower(), arg.lower())
    d = json.loads(await fetch("https://api.coingecko.com/api/v3/simple/price?ids="
                               f"{cid}&vs_currencies=usd&include_24hr_change=true"))[cid]
    await event.edit(f"💰 {cid}: ${d['usd']:,}  ({d.get('usd_24h_change', 0):+.2f}% در ۲۴ ساعت)")


@cmd("wiki")
async def _(event, arg):
    parts = arg.split(maxsplit=1)
    lang, title = ("en", arg)
    if len(parts) == 2 and len(parts[0]) == 2:
        lang, title = parts
    d = json.loads(await fetch(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                               + urllib.parse.quote(title.replace(" ", "_"))))
    await event.edit(f"📚 **{d.get('title', title)}**\n{d.get('extract', 'نتیجه‌ای نبود')[:1500]}")


# ---- ۱۶: مدیا و پروفایل ----
async def need_reply(event):
    r = await event.get_reply_message()
    if not r:
        raise ValueError("روی یک پیام ریپلای کنید")
    return r


@cmd("download")
async def _(event, arg):
    r = await need_reply(event)
    os.makedirs("downloads", exist_ok=True)
    await event.edit("📥 در حال دانلود...")
    p = await r.download_media(file="downloads/")
    if not p:
        raise ValueError("این پیام مدیا ندارد")
    await event.edit(f"✅ ذخیره شد: `{p}` ({os.path.getsize(p) / 1e6:.2f} MB)")


@cmd("fileinfo")
async def _(event, arg):
    f = (await need_reply(event)).file
    if not f:
        raise ValueError("این پیام فایل ندارد")
    await event.edit(f"📄 نام: {f.name or '-'}\n🧩 نوع: {f.mime_type}\n"
                     f"💾 حجم: {(f.size or 0) / 1e6:.2f} MB\n⏱ مدت: {f.duration or '-'}\n"
                     f"📐 ابعاد: {f.width or '-'}×{f.height or '-'}")


@cmd("asdoc")
async def _(event, arg):
    r = await need_reply(event)
    await event.delete()
    await user.send_file(event.chat_id, r.media, force_document=True)


@cmd("pfp")
async def _(event, arg):
    r = await event.get_reply_message()
    s = await r.get_sender() if r else await event.get_chat()
    data = await user.download_profile_photo(s, file=bytes)
    if not data:
        raise ValueError("عکس پروفایل ندارد")
    bio = io.BytesIO(data)
    bio.name = "pfp.jpg"
    await event.delete()
    await user.send_file(event.chat_id, bio)


@cmd("setpfp")
async def _(event, arg):
    r = await need_reply(event)
    os.makedirs("downloads", exist_ok=True)
    p = await r.download_media(file="downloads/pfp_new")
    f = await user.upload_file(p)
    await user(functions.photos.UploadProfilePhotoRequest(file=f))
    await event.edit("✅ عکس پروفایل تغییر کرد.")


@cmd("delpfp")
async def _(event, arg):
    photos = await user.get_profile_photos("me", limit=1)
    if not photos:
        raise ValueError("عکسی وجود ندارد")
    await user(functions.photos.DeletePhotosRequest([telethon.utils.get_input_photo(p) for p in photos]))
    await event.edit("🗑 آخرین عکس پروفایل حذف شد.")


# ---- ۱۷: بازی و شوخی ----
@cmd("rps")
async def _(event, arg):
    names = {"r": "🪨 سنگ", "p": "📄 کاغذ", "s": "✂️ قیچی"}
    me_, bot_ = arg.strip().lower()[:1], random.choice("rps")
    if me_ not in names:
        raise ValueError("r یا p یا s بنویسید")
    win = {("r", "s"), ("p", "r"), ("s", "p")}
    res = "🤝 مساوی" if me_ == bot_ else ("🏆 بردی" if (me_, bot_) in win else "😅 باختی")
    await event.edit(f"شما: {names[me_]}\nبات: {names[bot_]}\n{res}")


BALL = ["حتماً ✅", "بدون شک 👌", "به نظر میاد آره 🙂", "هنوز مطمئن نیستم 🤔", "دوباره بپرس 🔄",
        "بهتره نگم 🤐", "به نظر نمیاد ❌", "جوابم نه است 🚫", "خیلی بعیده 😬", "احتمالش کمه 📉"]


@cmd("8ball")
async def _(event, arg):
    await event.edit(f"🎱 {arg}\n➜ {random.choice(BALL)}")


TRUTH = ["آخرین دروغی که گفتی چی بود؟", "بزرگ‌ترین ترست چیه؟", "خنده‌دارترین اتفاق عمرت؟",
         "چیزی که از کسی پنهان کردی چیه؟", "اولین کراشت کی بود؟"]
DARE = ["یه استیکر خنده‌دار بفرست ✨", "تا ۱۰ دقیقه فقط با ایموجی حرف بزن 😄",
        "یه ویس ۵ ثانیه‌ای آواز بفرست 🎤", "اسم خودت رو وارونه بنویس 🔄", "یه عکس از آسمون بفرست ☁️"]


@cmd("td")
async def _(event, arg):
    k = arg.strip().lower() or random.choice(["truth", "dare"])
    await event.edit(("🤔 حقیقت: " + random.choice(TRUTH)) if k.startswith("t")
                     else ("😈 جرأت: " + random.choice(DARE)))


@cmd("love")
async def _(event, arg):
    a, _, b = arg.partition("|")
    pct = int(hashlib.md5((a.strip() + b.strip()).lower().encode()).hexdigest(), 16) % 101
    await event.edit(f"💘 {a.strip()} ❤️ {b.strip()}\n{'█' * (pct // 10)}{'░' * (10 - pct // 10)} {pct}%")


@cmd("hack")
async def _(event, arg):
    steps = ["🎭 شوخی: شروع هک...", "🔍 اسکن پورت‌ها... 23%", "🔓 دور زدن فایروال... 57%",
             "📡 دانلود اطلاعات... 91%", "✅ هک شد! (شوخی بود 😄)"]
    for s in steps:
        await event.edit(s)
        await asyncio.sleep(1)


@cmd("bar")
async def _(event, arg):
    for p in range(0, 101, 20):
        await event.edit(f"⏳ {'█' * (p // 10)}{'░' * (10 - p // 10)} {p}%")
        await asyncio.sleep(0.8)


# ---- ۱۸: اتوماسیون ----
@cmd("sign")
async def _(event, arg):
    S["sign_text"] = "" if arg in ("", "off") else arg
    save()
    await event.edit("✅ امضا تنظیم شد." if S["sign_text"] else "✅ امضا خاموش شد.")


@cmd("kw")
async def _(event, arg):
    K = S.setdefault("kw", {})
    sub, _, rest = arg.partition(" ")
    if sub == "add":
        k, _, v = rest.partition("|")
        K[k.strip().lower()] = v.strip()
    elif sub == "del":
        K.pop(rest.strip().lower(), None)
    save()
    await event.edit("🔑 کلیدواژه‌ها:\n" + ("\n".join(f"• {k} ➜ {v}" for k, v in K.items()) or "خالی"))


@cmd("readall")
async def _(event, arg):
    n = 0
    async for d in user.iter_dialogs():
        if d.unread_count:
            await user.send_read_acknowledge(d.entity)
            n += 1
    await event.edit(f"✅ {n} چت خوانده‌شده علامت خورد.")


@cmd("backup")
async def _(event, arg):
    save()
    await user.send_file("me", FILE, caption="💾 بکاپ تنظیمات")
    await event.edit("✅ بکاپ در Saved Messages ارسال شد.")


KW_COOL = {}


@user.on(events.NewMessage(incoming=True))
async def kw_in(event):
    if not (S.get("kwreply") and event.is_private):
        return
    s = await event.get_sender()
    if getattr(s, "bot", False):
        return
    txt = (event.raw_text or "").lower()
    for k, v in S.get("kw", {}).items():
        if k and k in txt and time.time() - KW_COOL.get((event.sender_id, k), 0) > 600:
            KW_COOL[(event.sender_id, k)] = time.time()
            return await event.reply(v)


# ---- ۱۹: مدیریت گروه (نیازمند دسترسی ادمین) ----
@cmd("ban")
async def _(event, arg):
    uid = await target(event)
    await user.edit_permissions(event.chat_id, uid, view_messages=(arg == "off"))
    await event.edit("✅ آن‌بن شد." if arg == "off" else "🚫 بن شد.")


@cmd("kick")
async def _(event, arg):
    uid = await target(event)
    await user.edit_permissions(event.chat_id, uid, view_messages=False)
    await user.edit_permissions(event.chat_id, uid, view_messages=True)
    await event.edit("👢 اخراج شد.")


@cmd("muteu")
async def _(event, arg):
    uid = await target(event)
    if arg == "off":
        await user.edit_permissions(event.chat_id, uid, send_messages=True)
        return await event.edit("🔊 سکوت برداشته شد.")
    mins = int(arg or 30)
    until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=mins)
    await user.edit_permissions(event.chat_id, uid, until_date=until, send_messages=False)
    await event.edit(f"🔇 {mins} دقیقه ساکت شد.")


@cmd("promote")
async def _(event, arg):
    uid = await target(event)
    if arg == "off":
        await user.edit_admin(event.chat_id, uid, is_admin=False)
        return await event.edit("⬇️ از ادمینی برداشته شد.")
    await user.edit_admin(event.chat_id, uid, delete_messages=True, ban_users=True,
                          invite_users=True, pin_messages=True)
    await event.edit("⬆️ ادمین شد.")


@cmd("gtitle")
async def _(event, arg):
    c = await event.get_chat()
    if isinstance(c, types.Channel):
        await user(functions.channels.EditTitleRequest(c, arg))
    else:
        await user(functions.messages.EditChatTitleRequest(c.id, arg))
    await event.delete()


@cmd("slowmode")
async def _(event, arg):
    c = await event.get_chat()
    await user(functions.channels.ToggleSlowModeRequest(c, int(arg or 0)))
    await event.edit(f"🐌 حالت آهسته: {int(arg or 0)} ثانیه")


# ---- ۲۰: ویژه ----
@cmd("autodelsec")
async def _(event, arg):
    S["autodel_s"] = max(3, int(arg or 60))
    save()
    await event.edit(f"⏱ زمان حذف خودکار: {S['autodel_s']} ثانیه")


@cmd("export")
async def _(event, arg):
    n = min(int(arg or 100), 2000)
    lines = []
    async for m in user.iter_messages(event.chat_id, limit=n):
        who = "me" if m.out else m.sender_id
        lines.append(f"[{m.date:%Y-%m-%d %H:%M}] {who}: {m.text or '<مدیا>'}")
    bio = io.BytesIO("\n".join(reversed(lines)).encode())
    bio.name = "chat_export.txt"
    await user.send_file("me", bio, caption=f"📤 خروجی {len(lines)} پیام")
    await event.edit("✅ خروجی به Saved Messages ارسال شد.")


@cmd("search")
async def _(event, arg):
    out = []
    async for m in user.iter_messages(event.chat_id, search=arg, limit=5):
        out.append(f"#{m.id} ({m.date:%m-%d}): {(m.text or '')[:60]}")
    await event.edit("🔎 نتایج:\n" + ("\n".join(out) or "چیزی پیدا نشد"))


@cmd("msgcount")
async def _(event, arg):
    res = await user.get_messages(event.chat_id, limit=0, from_user="me")
    await event.edit(f"✉️ پیام‌های شما در این چت: {res.total}")


@cmd("top")
async def _(event, arg):
    c = collections.Counter()
    async for m in user.iter_messages(event.chat_id, limit=500):
        c[m.sender_id] += 1
    lines = []
    for uid, n in c.most_common(5):
        try:
            e = await user.get_entity(uid)
            name = getattr(e, "first_name", None) or getattr(e, "title", None) or str(uid)
        except Exception:
            name = str(uid)
        lines.append(f"• {name}: {n}")
    await event.edit("🏆 فعال‌ترین‌ها (۵۰۰ پیام اخیر):\n" + "\n".join(lines))


@cmd("restart")
async def _(event, arg):
    save()
    await event.edit("♻️ در حال راه‌اندازی مجدد...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


STY = {"bold": types.MessageEntityBold, "italic": types.MessageEntityItalic,
       "mono": types.MessageEntityCode, "underline": types.MessageEntityUnderline,
       "strike": types.MessageEntityStrike, "spoiler": types.MessageEntitySpoiler}


async def style(event):
    t = event.raw_text
    if not t or event.media or event.message.entities:
        return
    sign = S.get("sign_text")
    if sign:
        t = f"{t}\n\n{sign}"
    n = len(add_surrogate(t))
    ents = [c(offset=0, length=n) for k, c in STY.items() if S.get(k)]
    if S.get("autope") and EMOJI_MAP:
        ents += pe_entities(t)
    if ents:
        await event.edit(t, formatting_entities=ents)
    elif sign:
        await event.edit(t, parse_mode=None)


@user.on(events.NewMessage(outgoing=True))
async def out(event):
    t = event.raw_text or ""
    if t.startswith("."):
        name, _, arg = t[1:].partition(" ")
        name = name.lower()
        if name == "panel":
            res = await user.inline_query(BOT_USERNAME, "panel")
            await res[0].click(event.chat_id)
            return await event.delete()
        fn = CMD.get(name)
        if fn:
            try:
                await fn(event, arg.strip())
            except Exception as e:
                await event.edit(f"⚠️ خطا: {e}")
        return
    await style(event)
    if S.get("autodel"):
        asyncio.create_task(_del_later(event.chat_id, event.id, S.get("autodel_s", 60)))


# ---------------- هندلر پیام‌های ورودی ----------------
last_reply = {}


@user.on(events.NewMessage(incoming=True))
async def inc(event):
    if (event.is_private and S.get("autoread_pv")) or \
       (event.is_group and S.get("autoread_gp")) or \
       (event.is_channel and not event.is_group and S.get("autoread_ch")):
        await user.send_read_acknowledge(event.chat_id, event.message)

    if event.message.mentioned and not event.is_private and S.get("mentionlog"):
        await event.message.forward_to("me")

    if S.get("replylog") and event.is_reply:
        r = await event.get_reply_message()
        if r and r.out:
            await event.message.forward_to("me")

    if not event.is_private:
        return
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    for key, action in (("typing", "typing"), ("recvoice", "record-audio"), ("game", "game")):
        if S.get(key):
            async with user.action(event.chat_id, action):
                await asyncio.sleep(4)
            break

    reply = S.get("afk") and f"😴 {S['afk']}" or (S.get("autoreply") and S.get("reply_text", "سلام! بعداً پاسخ می‌دهم."))
    if reply and time.time() - last_reply.get(event.sender_id, 0) > 3600:
        last_reply[event.sender_id] = time.time()
        await event.reply(reply)


# ---------------- ساعت پروفایل ----------------
async def clock_loop():
    while True:
        try:
            now = dt.datetime.now().strftime("%H:%M")
            if S.get("nameclock"):
                await user(UpdateProfileRequest(last_name=f"| {now}"))
            if S.get("bioclock"):
                await user(UpdateProfileRequest(about=f"{S.get('bio_base', '')[:55]} | {now}"))
        except Exception:
            pass
        await asyncio.sleep(60 - dt.datetime.now().second)


async def main():
    global ME, BOT_USERNAME
    if (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID")) and not SESSION_STRING:
        sys.exit("❌ متغیر SESSION_STRING تنظیم نشده. اول gen_session.py را روی سیستم خودتان اجرا کنید.")
    await user.start()
    await bot.start(bot_token=BOT_TOKEN)
    ME = await user.get_me()
    BOT_USERNAME = (await bot.get_me()).username
    if S.get("pe_pack"):
        try:
            EMOJI_MAP.update(await load_pack(S["pe_pack"]))
        except Exception:
            pass
    print(f"✅ Self bot آماده است | پنل: .panel | ربات: @{BOT_USERNAME}")
    asyncio.create_task(clock_loop())
    await asyncio.gather(user.run_until_disconnected(), bot.run_until_disconnected())


if __name__ == "__main__":
    asyncio.run(main())
