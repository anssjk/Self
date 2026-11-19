#!/usr/bin/env python3
"""
Self Bot تلگرام - ۲۰ صفحه × ۶ قابلیت = ۱۲۰ قابلیت (شامل ایموجی پریمیوم)
بدون Telethon؛ مبتنی بر Pyrofork (MTProto)
نیازمندی: pip install pyrofork tgcrypto
اجرا:  API_ID=... API_HASH=... BOT_TOKEN=... python selfbot.py
در چت، پنل را با  .panel  باز کنید.
(در @BotFather برای ربات دستور /setinline را بزنید.)
"""
import ast, asyncio, base64, codecs, collections, datetime as dt, hashlib, io
import json, operator as op, os, platform, random, re, secrets, string, sys, time
import urllib.parse, urllib.request

import pyrogram
from pyrogram import Client, filters, enums, raw, idle
from pyrogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle,
                            InputTextMessageContent, MessageEntity, ChatPrivileges)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

SESSION_STRING = os.environ.get("SESSION_STRING")  # برای Railway (با gen_session.py بسازید)
if SESSION_STRING:
    user = Client("self_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    user = Client("self_session", api_id=API_ID, api_hash=API_HASH)
bot = Client("panel_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN,
             in_memory=bool(SESSION_STRING))
ME = None
BOT_USERNAME = None
START = time.time()
PM = enums.ParseMode
ET = enums.MessageEntityType

# ---------------- تنظیمات ماندگار ----------------
FILE = os.environ.get("SETTINGS_FILE", "settings.json")  # روی Railway: /data/settings.json
S = json.load(open(FILE)) if os.path.exists(FILE) else {}


def save():
    json.dump(S, open(FILE, "w"), ensure_ascii=False)


def u16(s):
    """طول رشته بر حسب واحدهای UTF-16 (مورد نیاز برای entity ها)"""
    return len(s.encode("utf-16-le")) // 2


# ---------------- تعریف ۲۰ صفحه × ۶ قابلیت ----------------
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
        ("ver", "ورژن", "c", ".ver → نسخه پایتون و Pyrofork"),
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
    mark = ("🟢" if S.get(key) else "🔴") if kind == "t" else "🔹"
    return InlineKeyboardButton(f"{mark} {label}", callback_data=f"f:{key}")


def page_markup(i):
    feats = PAGES[i][2]
    rows = [[fbtn(f) for f in feats[a:a + 2]] for a in range(0, 6, 2)]
    rows.append([
        InlineKeyboardButton("◀️", callback_data=f"p:{(i - 1) % len(PAGES)}"),
        InlineKeyboardButton(f"📄 {i + 1}/{len(PAGES)}", callback_data="n:0"),
        InlineKeyboardButton("▶️", callback_data=f"p:{(i + 1) % len(PAGES)}"),
    ])
    rows.append([InlineKeyboardButton("❌ بستن", callback_data="x:0")])
    return InlineKeyboardMarkup(rows)


@bot.on_inline_query()
async def inline(_, q):
    if q.from_user.id != ME.id:
        return await q.answer([], cache_time=0)
    r = InlineQueryResultArticle(
        id="panel", title="Panel",
        input_message_content=InputTextMessageContent(page_text(0)),
        reply_markup=page_markup(0))
    await q.answer([r], cache_time=0)


async def on_toggle(key, val):
    if key == "nameclock":
        if val:
            S["ln_base"] = (await user.get_me()).last_name or ""
        else:
            await user.update_profile(last_name=S.get("ln_base", ""))
    elif key == "bioclock":
        if val:
            S["bio_base"] = (await user.get_chat("me")).bio or ""
        else:
            await user.update_profile(bio=S.get("bio_base", ""))


@bot.on_callback_query()
async def cb(_, q):
    if q.from_user.id != ME.id:
        return await q.answer("⛔ این پنل مخصوص صاحب اکانت است", show_alert=True)
    kind, _, val = q.data.partition(":")
    if kind == "p":
        i = int(val)
        await q.edit_message_text(page_text(i), reply_markup=page_markup(i))
    elif kind == "f":
        i, f = FIND[val]
        if f[2] == "t":
            S[val] = not S.get(val, False)
            await on_toggle(val, S[val])
            save()
            await q.edit_message_text(page_text(i), reply_markup=page_markup(i))
            await q.answer("روشن شد ✅" if S[val] else "خاموش شد ❌")
        else:
            await q.answer(f[3][:190], show_alert=True)
    elif kind == "x":
        await q.edit_message_text("✅ پنل بسته شد.")
    else:
        await q.answer()


# ---------------- دستورات متنی ----------------
CMD = {}


def cmd(*names):
    def deco(fn):
        for n in names:
            CMD[n] = fn
        return fn
    return deco


async def get_text(m, arg):
    if arg:
        return arg
    r = m.reply_to_message
    return ((r.text or r.caption or "") if r else "")


def sid(m):
    if m.from_user:
        return m.from_user.id
    return m.sender_chat.id if m.sender_chat else None


def textcmd(name, f):
    async def h(m, arg):
        t = await get_text(m, arg)
        if t:
            await m.edit_text(f(t), parse_mode=PM.DISABLED)
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
async def _(m, arg):
    t = time.perf_counter()
    await m.edit_text("🏓 ...")
    await m.edit_text(f"🏓 Pong! `{(time.perf_counter() - t) * 1000:.0f} ms`")


@cmd("time")
async def _(m, arg):
    await m.edit_text(f"🕒 {dt.datetime.now():%H:%M:%S}")


@cmd("date")
async def _(m, arg):
    await m.edit_text(f"📅 {dt.datetime.now():%Y-%m-%d (%A)}")


@cmd("id")
async def _(m, arg):
    r = m.reply_to_message
    await m.edit_text(f"🆔 کاربر: `{sid(r)}`\n💬 چت: `{m.chat.id}`" if r else f"💬 چت: `{m.chat.id}`")


@cmd("info")
async def _(m, arg):
    c = m.chat
    name = c.title or c.first_name or ""
    await m.edit_text(f"ℹ️ نام: {name}\n🆔 `{c.id}`\n📦 نوع: {c.type.name}")


@cmd("help")
async def _(m, arg):
    await m.edit_text("🎛 برای دیدن همه ۱۲۰ قابلیت، دستور `.panel` را بفرستید.")


@cmd("setreply")
async def _(m, arg):
    S["reply_text"] = arg or "سلام! فعلاً در دسترس نیستم، بعداً پاسخ می‌دهم."
    save()
    await m.edit_text("✅ متن پاسخ خودکار ذخیره شد.")


@cmd("save")
async def _(m, arg):
    r = m.reply_to_message
    if r:
        await r.forward("me")
    await m.delete()


@cmd("del")
async def _(m, arg):
    r = m.reply_to_message
    if r and r.outgoing:
        await r.delete()
    await m.delete()


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
async def _(m, arg):
    await m.edit_text(f"🧮 `{arg}` = `{ev(ast.parse(arg, mode='eval').body)}`")


@cmd("rand")
async def _(m, arg):
    a = [int(x) for x in arg.split()] or [1, 100]
    lo, hi = (a[0], a[1]) if len(a) > 1 else (1, a[0])
    await m.edit_text(f"🎯 `{random.randint(lo, hi)}`")


@cmd("coin")
async def _(m, arg):
    await m.edit_text(random.choice(["🪙 شیر", "🪙 خط"]))


@cmd("pass")
async def _(m, arg):
    n = min(int(arg or 16), 64)
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    await m.edit_text("🔐 `" + "".join(secrets.choice(chars) for _ in range(n)) + "`")


# --- اکانت ---
@cmd("stats")
async def _(m, arg):
    pv = gp = ch = 0
    async for d in user.get_dialogs():
        t = d.chat.type
        if t in (enums.ChatType.PRIVATE, enums.ChatType.BOT):
            pv += 1
        elif t in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            gp += 1
        elif t == enums.ChatType.CHANNEL:
            ch += 1
    await m.edit_text(f"📊 پیوی: {pv}\n👥 گروه: {gp}\n📢 کانال: {ch}")


@cmd("setbio")
async def _(m, arg):
    await user.update_profile(bio=arg[:70])
    await m.edit_text("✅ بیو تغییر کرد.")


@cmd("setname")
async def _(m, arg):
    first, _, last = arg.partition("|")
    await user.update_profile(first_name=first.strip(), last_name=last.strip())
    await m.edit_text("✅ نام تغییر کرد.")


@cmd("uptime")
async def _(m, arg):
    s = int(time.time() - START)
    await m.edit_text(f"⏱ {s // 3600}h {s % 3600 // 60}m {s % 60}s")


@cmd("me")
async def _(m, arg):
    me = await user.get_me()
    await m.edit_text(f"👤 {me.first_name} {me.last_name or ''}\n🆔 `{me.id}`\n🔗 @{me.username or '-'}")


@cmd("ver")
async def _(m, arg):
    await m.edit_text(f"🐍 Python {platform.python_version()}\n📦 Pyrofork {pyrogram.__version__}")


# --- گروه ---
@cmd("members")
async def _(m, arg):
    await m.edit_text(f"👥 تعداد اعضا: {await user.get_chat_members_count(m.chat.id)}")


@cmd("admins")
async def _(m, arg):
    names = []
    async for mem in user.get_chat_members(m.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        u = mem.user
        if u:
            names.append(f"• {u.first_name or ''} (@{u.username or '-'})")
    await m.edit_text("👮 ادمین‌ها:\n" + "\n".join(names[:30]))


@cmd("pin")
async def _(m, arg):
    r = m.reply_to_message
    if r:
        await r.pin()
    await m.delete()


@cmd("unpin")
async def _(m, arg):
    r = m.reply_to_message
    if r:
        await r.unpin()
    await m.delete()


@cmd("purge")
async def _(m, arg):
    n = min(int(arg or 5), 100)
    ids = [x.id async for x in user.search_messages(m.chat.id, from_user="me", limit=n + 1)]
    if m.id not in ids:
        ids.append(m.id)
    await user.delete_messages(m.chat.id, ids)


@cmd("whois")
async def _(m, arg):
    r = m.reply_to_message
    if not r or not r.from_user:
        return await m.edit_text("روی پیام یک نفر ریپلای کنید.")
    u = r.from_user
    await m.edit_text(f"🔎 {u.first_name or ''}\n🆔 `{u.id}`\n🔗 @{u.username or '-'}")


# --- سرگرمی ---
def dicecmd(name, emoji):
    async def h(m, arg):
        await m.delete()
        await user.send_dice(m.chat.id, emoji)
    CMD[name] = h


for n, e in [("dice", "🎲"), ("dart", "🎯"), ("basket", "🏀"),
             ("football", "⚽"), ("slot", "🎰"), ("bowling", "🎳")]:
    dicecmd(n, e)


# --- زمان و وضعیت ---
@cmd("afk")
async def _(m, arg):
    S["afk"] = arg or "نیستم"
    save()
    await m.edit_text(f"😴 AFK روشن شد: {S['afk']}")


@cmd("unafk")
async def _(m, arg):
    S.pop("afk", None)
    save()
    await m.edit_text("✅ AFK خاموش شد.")


@cmd("sd")
async def _(m, arg):
    n, _, txt = arg.partition(" ")
    await m.edit_text(txt)
    await asyncio.sleep(min(int(n), 3600))
    await m.delete()


@cmd("later")
async def _(m, arg):
    n, _, txt = arg.partition(" ")
    chat = m.chat.id
    await m.edit_text(f"⏳ ارسال می‌شود بعد از {n} ثانیه")

    async def go():
        await asyncio.sleep(min(int(n), 86400))
        await user.send_message(chat, txt)
    asyncio.create_task(go())


# ---------------- ایموجی پریمیوم ----------------
EMOJI_MAP = {}  # ایموجی ساده -> document_id ایموجی پریمیوم


def _norm(e):
    return e.replace("\ufe0f", "")


async def load_pack(short):
    r = await user.invoke(raw.functions.messages.GetStickerSet(
        stickerset=raw.types.InputStickerSetShortName(short_name=short), hash=0))
    mp = {}
    for p in r.packs:
        if p.documents:
            mp.setdefault(_norm(p.emoticon), p.documents[0])
    return mp


def pe_entities(text):
    ents, off = [], 0
    for ch in text:
        n = u16(ch)
        if ch == "\ufe0f":
            if ents and ents[-1].offset + ents[-1].length == off:
                ents[-1].length += n
        elif ch in EMOJI_MAP:
            ents.append(MessageEntity(type=ET.CUSTOM_EMOJI, offset=off, length=n,
                                      custom_emoji_id=EMOJI_MAP[ch]))
        off += n
    return ents


@cmd("setpack")
async def _(m, arg):
    short = arg.strip().split("/")[-1]
    EMOJI_MAP.clear()
    EMOJI_MAP.update(await load_pack(short))
    S["pe_pack"] = short
    save()
    warn = "" if getattr(ME, "is_premium", False) else "\n⚠️ اکانت شما پریمیوم نیست؛ ایموجی‌ها معمولی نمایش داده می‌شوند."
    await m.edit_text(f"✅ پک `{short}` لود شد ({len(EMOJI_MAP)} ایموجی){warn}")


@cmd("pe")
async def _(m, arg):
    t = await get_text(m, arg)
    if not t:
        return
    if not EMOJI_MAP:
        return await m.edit_text("اول با `.setpack` یک پک ایموجی انتخاب کنید.")
    await m.edit_text(t, entities=pe_entities(t))


@cmd("emojilist")
async def _(m, arg):
    await m.edit_text("🧩 " + (" ".join(EMOJI_MAP)[:3500] or "پکی انتخاب نشده"),
                      parse_mode=PM.DISABLED)


@cmd("ceid")
async def _(m, arg):
    r = m.reply_to_message
    ids = [str(e.custom_emoji_id) for e in ((r.entities or r.caption_entities or []) if r else [])
           if e.type == ET.CUSTOM_EMOJI]
    await m.edit_text("🆔 " + ("\n".join(f"`{i}`" for i in ids) if ids
                              else "روی پیامی که ایموجی پریمیوم دارد ریپلای کنید."))


@cmd("ce")
async def _(m, arg):
    i, _, emo = arg.partition(" ")
    emo = emo.strip() or "⭐"
    await m.edit_text(emo, entities=[MessageEntity(
        type=ET.CUSTOM_EMOJI, offset=0, length=u16(emo), custom_emoji_id=int(i))])


# =============== ابزارهای کمکی ===============
def _http(url, binary=False, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = r.read()
    return d if binary else d.decode("utf-8", "ignore")


async def fetch(url, binary=False):
    return await asyncio.get_running_loop().run_in_executor(None, _http, url, binary)


async def target(m):
    r = m.reply_to_message
    if not r or not r.from_user:
        raise ValueError("روی پیام فرد ریپلای کنید")
    return r.from_user.id


async def _del_later(chat, mid, secs):
    await asyncio.sleep(secs)
    try:
        await user.delete_messages(chat, mid)
    except Exception:
        pass


# ---- حریم و امنیت ----
MSG_CACHE = collections.OrderedDict()


@user.on_message(filters.incoming & filters.private, group=1)
async def cache_in(_, m):
    if S.get("antidel") or S.get("antiedit"):
        MSG_CACHE[m.id] = (sid(m), m.text or m.caption or "<مدیا>")
        while len(MSG_CACHE) > 3000:
            MSG_CACHE.popitem(last=False)


@user.on_deleted_messages()
async def on_deleted(_, msgs):
    if not S.get("antidel"):
        return
    for x in msgs:
        if x.id in MSG_CACHE:
            who, t = MSG_CACHE.pop(x.id)
            await user.send_message("me", f"🗑 پیام حذف‌شده از `{who}`:\n{t}",
                                    parse_mode=PM.DISABLED)


@user.on_edited_message(filters.incoming & filters.private)
async def on_edited(_, m):
    if not S.get("antiedit"):
        return
    old = MSG_CACHE.get(m.id)
    new = m.text or m.caption or "<مدیا>"
    if old and old[1] != new:
        await user.send_message("me", f"✏️ ویرایش از `{old[0]}`:\nقبل: {old[1]}\nبعد: {new}",
                                parse_mode=PM.DISABLED)
    MSG_CACHE[m.id] = (sid(m), new)


@cmd("mute")
async def _(m, arg):
    peer = await user.resolve_peer(m.chat.id)
    until = 0 if arg == "off" else 2 ** 31 - 1
    await user.invoke(raw.functions.account.UpdateNotifySettings(
        peer=raw.types.InputNotifyPeer(peer=peer),
        settings=raw.types.InputPeerNotifySettings(mute_until=until)))
    await m.edit_text("🔕 بی‌صدا شد." if until else "🔔 صدا فعال شد.")


@cmd("archive")
async def _(m, arg):
    if arg == "off":
        await user.unarchive_chats(m.chat.id)
    else:
        await user.archive_chats(m.chat.id)
    await m.edit_text("📦 انجام شد.")


@cmd("block")
async def _(m, arg):
    r = m.reply_to_message
    uid = r.from_user.id if (r and r.from_user) else m.chat.id
    if arg == "off":
        await user.unblock_user(uid)
    else:
        await user.block_user(uid)
    await m.edit_text("✅ انجام شد.")


@cmd("sessions")
async def _(m, arg):
    r = await user.invoke(raw.functions.account.GetAuthorizations())
    lines = [f"{'🟢' if a.current else '⚪'} {a.device_model} · {a.app_name} · "
             f"{a.country or '-'} · {dt.datetime.fromtimestamp(a.date_active):%m-%d %H:%M}"
             for a in r.authorizations]
    await m.edit_text("🔐 نشست‌های فعال:\n" + "\n".join(lines[:15]), parse_mode=PM.DISABLED)


# ---- متن پیشرفته ----
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
async def _(m, arg):
    k, _, t = arg.partition(" ")
    if k not in FONTS or not t.strip():
        return await m.edit_text("🔤 فونت‌ها:\n" + "\n".join(
            f"{i}. {n[0]}: {n[1]('Abc')}" for i, n in FONTS.items()))
    await m.edit_text(FONTS[k][1](t), parse_mode=PM.DISABLED)


MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.",
         "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.",
         "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-",
         "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", "0": "-----",
         "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
         "7": "--...", "8": "---..", "9": "----."}
MORSE_REV = {v: k for k, v in MORSE.items()}


@cmd("morse")
async def _(m, arg):
    t = await get_text(m, arg)
    if t and set(t) <= set(".-/ "):
        out = " ".join("".join(MORSE_REV.get(c, "?") for c in w.split()) for w in t.split("/"))
    else:
        out = " / ".join(" ".join(MORSE.get(c.upper(), "?") for c in w) for w in t.split())
    await m.edit_text(out, parse_mode=PM.DISABLED)


@cmd("bin")
async def _(m, arg):
    t = await get_text(m, arg)
    if t and set(t) <= set("01 "):
        out = bytes(int(b, 2) for b in t.split()).decode(errors="ignore")
    else:
        out = " ".join(f"{b:08b}" for b in t.encode())
    await m.edit_text(out, parse_mode=PM.DISABLED)


textcmd("rot13", lambda t: codecs.encode(t, "rot13"))


@cmd("wc")
async def _(m, arg):
    t = await get_text(m, arg)
    await m.edit_text(f"🔢 کاراکتر: {len(t)}\n📝 کلمه: {len(t.split())}\n📄 خط: {len(t.splitlines())}")


@cmd("hash")
async def _(m, arg):
    t = await get_text(m, arg)
    b = t.encode()
    await m.edit_text(f"🔑 MD5:\n`{hashlib.md5(b).hexdigest()}`\nSHA1:\n`{hashlib.sha1(b).hexdigest()}`\n"
                      f"SHA256:\n`{hashlib.sha256(b).hexdigest()}`")


# ---- کارهای روزمره ----
@cmd("todo")
async def _(m, arg):
    L = S.setdefault("todo", [])
    sub, _, rest = arg.partition(" ")
    if sub == "add" and rest:
        L.append(rest)
    elif sub == "done":
        L.pop(int(rest) - 1)
    elif sub == "clear":
        L.clear()
    save()
    await m.edit_text("📝 کارها:\n" + ("\n".join(f"{i}. {x}" for i, x in enumerate(L, 1)) or "خالی"),
                      parse_mode=PM.DISABLED)


@cmd("note")
async def _(m, arg):
    N = S.setdefault("notes", {})
    sub, _, rest = arg.partition(" ")
    if sub == "get":
        return await m.edit_text(N.get(rest.strip(), "پیدا نشد"), parse_mode=PM.DISABLED)
    if sub == "save":
        name, _, txt = rest.partition(" ")
        N[name] = txt or await get_text(m, "")
    elif sub == "del":
        N.pop(rest.strip(), None)
    save()
    await m.edit_text("🗒 یادداشت‌ها: " + (", ".join(N) or "خالی"), parse_mode=PM.DISABLED)


@cmd("remind")
async def _(m, arg):
    mt = re.match(r"(\d+)([smhd])\s+(.+)", arg)
    if not mt:
        raise ValueError("مثال: .remind 10m تماس بگیر")
    secs = int(mt[1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[mt[2]]
    msg = mt[3]

    async def go():
        await asyncio.sleep(secs)
        await user.send_message("me", f"⏰ یادآوری: {msg}", parse_mode=PM.DISABLED)
    asyncio.create_task(go())
    await m.edit_text("⏰ یادآوری ثبت شد (تا ری‌استارت بات معتبر است).")


@cmd("poll")
async def _(m, arg):
    q, *opts = [x.strip() for x in arg.split("|")]
    if len(opts) < 2:
        raise ValueError("حداقل دو گزینه لازم است")
    await m.delete()
    await user.send_poll(m.chat.id, q, opts[:10])


LEN = {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "ft": 0.3048, "in": 0.0254}
MASS = {"kg": 1, "g": 0.001, "lb": 0.45359237, "oz": 0.0283495}


@cmd("convert")
async def _(m, arg):
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
    await m.edit_text(f"📐 {v:g} {a} = `{r:.4g}` {b}")


@cmd("age")
async def _(m, arg):
    b = dt.datetime.strptime(arg.strip(), "%Y-%m-%d").date()
    t = dt.date.today()
    y = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    await m.edit_text(f"🎂 سن: {y} سال | {(t - b).days:,} روز")


# ---- اینترنت ----
@cmd("weather")
async def _(m, arg):
    await m.edit_text("🌦 " + (await fetch(f"https://wttr.in/{urllib.parse.quote(arg)}?format=3")).strip(),
                      parse_mode=PM.DISABLED)


@cmd("ip")
async def _(m, arg):
    d = json.loads(await fetch(f"http://ip-api.com/json/{urllib.parse.quote(arg)}"))
    if d.get("status") != "success":
        raise ValueError("IP نامعتبر")
    await m.edit_text(f"🌍 {d['query']}\n{d['country']} / {d['regionName']} / {d['city']}\n🏢 {d['isp']}",
                      parse_mode=PM.DISABLED)


@cmd("short")
async def _(m, arg):
    u = await fetch(f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(arg)}")
    await m.edit_text(f"🔗 {u.strip()}", parse_mode=PM.DISABLED)


@cmd("qr")
async def _(m, arg):
    t = await get_text(m, arg)
    data = await fetch("https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
                       + urllib.parse.quote(t), True)
    bio = io.BytesIO(data)
    bio.name = "qr.png"
    await m.delete()
    await user.send_photo(m.chat.id, bio, caption=f"📱 {t[:100]}", parse_mode=PM.DISABLED)


CRYPTO = {"btc": "bitcoin", "eth": "ethereum", "ton": "the-open-network",
          "sol": "solana", "doge": "dogecoin", "usdt": "tether"}


@cmd("crypto")
async def _(m, arg):
    cid = CRYPTO.get(arg.lower(), arg.lower())
    d = json.loads(await fetch("https://api.coingecko.com/api/v3/simple/price?ids="
                               f"{cid}&vs_currencies=usd&include_24hr_change=true"))[cid]
    await m.edit_text(f"💰 {cid}: ${d['usd']:,}  ({d.get('usd_24h_change', 0):+.2f}% در ۲۴ ساعت)",
                      parse_mode=PM.DISABLED)


@cmd("wiki")
async def _(m, arg):
    parts = arg.split(maxsplit=1)
    lang, title = ("en", arg)
    if len(parts) == 2 and len(parts[0]) == 2:
        lang, title = parts
    d = json.loads(await fetch(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                               + urllib.parse.quote(title.replace(" ", "_"))))
    await m.edit_text(f"📚 **{d.get('title', title)}**\n{d.get('extract', 'نتیجه‌ای نبود')[:1500]}",
                      parse_mode=PM.DISABLED)


# ---- مدیا و پروفایل ----
async def need_reply(m):
    r = m.reply_to_message
    if not r:
        raise ValueError("روی یک پیام ریپلای کنید")
    return r


@cmd("download")
async def _(m, arg):
    r = await need_reply(m)
    os.makedirs("downloads", exist_ok=True)
    await m.edit_text("📥 در حال دانلود...")
    p = await r.download(file_name="downloads/")
    if not p:
        raise ValueError("این پیام مدیا ندارد")
    await m.edit_text(f"✅ ذخیره شد: `{p}` ({os.path.getsize(p) / 1e6:.2f} MB)")


@cmd("fileinfo")
async def _(m, arg):
    r = await need_reply(m)
    f = getattr(r, r.media.value, None) if r.media else None
    if not f:
        raise ValueError("این پیام فایل ندارد")
    await m.edit_text(f"📄 نام: {getattr(f, 'file_name', None) or '-'}\n"
                      f"🧩 نوع: {getattr(f, 'mime_type', None) or r.media.name}\n"
                      f"💾 حجم: {(getattr(f, 'file_size', 0) or 0) / 1e6:.2f} MB\n"
                      f"⏱ مدت: {getattr(f, 'duration', None) or '-'}\n"
                      f"📐 ابعاد: {getattr(f, 'width', None) or '-'}×{getattr(f, 'height', None) or '-'}",
                      parse_mode=PM.DISABLED)


@cmd("asdoc")
async def _(m, arg):
    r = await need_reply(m)
    await m.delete()
    p = await r.download()
    if not p:
        return
    try:
        await user.send_document(m.chat.id, p)
    finally:
        os.remove(p)


@cmd("pfp")
async def _(m, arg):
    r = m.reply_to_message
    cid = r.from_user.id if (r and r.from_user) else m.chat.id
    photos = [p async for p in user.get_chat_photos(cid, limit=1)]
    if not photos:
        raise ValueError("عکس پروفایل ندارد")
    bio = await user.download_media(photos[0].file_id, in_memory=True)
    bio.name = "pfp.jpg"
    await m.delete()
    await user.send_photo(m.chat.id, bio)


@cmd("setpfp")
async def _(m, arg):
    r = await need_reply(m)
    os.makedirs("downloads", exist_ok=True)
    p = await r.download(file_name="downloads/pfp_new.jpg")
    await user.set_profile_photo(photo=p)
    await m.edit_text("✅ عکس پروفایل تغییر کرد.")


@cmd("delpfp")
async def _(m, arg):
    photos = [p async for p in user.get_chat_photos("me", limit=1)]
    if not photos:
        raise ValueError("عکسی وجود ندارد")
    await user.delete_profile_photos(photos[0].file_id)
    await m.edit_text("🗑 آخرین عکس پروفایل حذف شد.")


# ---- بازی و شوخی ----
@cmd("rps")
async def _(m, arg):
    names = {"r": "🪨 سنگ", "p": "📄 کاغذ", "s": "✂️ قیچی"}
    me_, bot_ = arg.strip().lower()[:1], random.choice("rps")
    if me_ not in names:
        raise ValueError("r یا p یا s بنویسید")
    win = {("r", "s"), ("p", "r"), ("s", "p")}
    res = "🤝 مساوی" if me_ == bot_ else ("🏆 بردی" if (me_, bot_) in win else "😅 باختی")
    await m.edit_text(f"شما: {names[me_]}\nبات: {names[bot_]}\n{res}")


BALL = ["حتماً ✅", "بدون شک 👌", "به نظر میاد آره 🙂", "هنوز مطمئن نیستم 🤔", "دوباره بپرس 🔄",
        "بهتره نگم 🤐", "به نظر نمیاد ❌", "جوابم نه است 🚫", "خیلی بعیده 😬", "احتمالش کمه 📉"]


@cmd("8ball")
async def _(m, arg):
    await m.edit_text(f"🎱 {arg}\n➜ {random.choice(BALL)}", parse_mode=PM.DISABLED)


TRUTH = ["آخرین دروغی که گفتی چی بود؟", "بزرگ‌ترین ترست چیه؟", "خنده‌دارترین اتفاق عمرت؟",
         "چیزی که از کسی پنهان کردی چیه؟", "اولین کراشت کی بود؟"]
DARE = ["یه استیکر خنده‌دار بفرست ✨", "تا ۱۰ دقیقه فقط با ایموجی حرف بزن 😄",
        "یه ویس ۵ ثانیه‌ای آواز بفرست 🎤", "اسم خودت رو وارونه بنویس 🔄", "یه عکس از آسمون بفرست ☁️"]


@cmd("td")
async def _(m, arg):
    k = arg.strip().lower() or random.choice(["truth", "dare"])
    await m.edit_text(("🤔 حقیقت: " + random.choice(TRUTH)) if k.startswith("t")
                      else ("😈 جرأت: " + random.choice(DARE)))


@cmd("love")
async def _(m, arg):
    a, _, b = arg.partition("|")
    pct = int(hashlib.md5((a.strip() + b.strip()).lower().encode()).hexdigest(), 16) % 101
    await m.edit_text(f"💘 {a.strip()} ❤️ {b.strip()}\n{'█' * (pct // 10)}{'░' * (10 - pct // 10)} {pct}%",
                      parse_mode=PM.DISABLED)


@cmd("hack")
async def _(m, arg):
    steps = ["🎭 شوخی: شروع هک...", "🔍 اسکن پورت‌ها... 23%", "🔓 دور زدن فایروال... 57%",
             "📡 دانلود اطلاعات... 91%", "✅ هک شد! (شوخی بود 😄)"]
    for s in steps:
        await m.edit_text(s)
        await asyncio.sleep(1)


@cmd("bar")
async def _(m, arg):
    for p in range(0, 101, 20):
        await m.edit_text(f"⏳ {'█' * (p // 10)}{'░' * (10 - p // 10)} {p}%")
        await asyncio.sleep(0.8)


# ---- اتوماسیون ----
@cmd("sign")
async def _(m, arg):
    S["sign_text"] = "" if arg in ("", "off") else arg
    save()
    await m.edit_text("✅ امضا تنظیم شد." if S["sign_text"] else "✅ امضا خاموش شد.")


@cmd("kw")
async def _(m, arg):
    K = S.setdefault("kw", {})
    sub, _, rest = arg.partition(" ")
    if sub == "add":
        k, _, v = rest.partition("|")
        K[k.strip().lower()] = v.strip()
    elif sub == "del":
        K.pop(rest.strip().lower(), None)
    save()
    await m.edit_text("🔑 کلیدواژه‌ها:\n" + ("\n".join(f"• {k} ➜ {v}" for k, v in K.items()) or "خالی"),
                      parse_mode=PM.DISABLED)


@cmd("readall")
async def _(m, arg):
    n = 0
    async for d in user.get_dialogs():
        if d.unread_messages_count:
            await user.read_chat_history(d.chat.id)
            n += 1
    await m.edit_text(f"✅ {n} چت خوانده‌شده علامت خورد.")


@cmd("backup")
async def _(m, arg):
    save()
    await user.send_document("me", FILE, caption="💾 بکاپ تنظیمات")
    await m.edit_text("✅ بکاپ در Saved Messages ارسال شد.")


KW_COOL = {}


@user.on_message(filters.incoming & filters.private, group=2)
async def kw_in(_, m):
    if not S.get("kwreply"):
        return
    if m.from_user and m.from_user.is_bot:
        return
    txt = (m.text or "").lower()
    for k, v in S.get("kw", {}).items():
        if k and k in txt and time.time() - KW_COOL.get((m.from_user.id, k), 0) > 600:
            KW_COOL[(m.from_user.id, k)] = time.time()
            return await m.reply_text(v, parse_mode=PM.DISABLED)


# ---- مدیریت گروه (نیازمند دسترسی ادمین) ----
@cmd("ban")
async def _(m, arg):
    uid = await target(m)
    if arg == "off":
        await user.unban_chat_member(m.chat.id, uid)
        return await m.edit_text("✅ آن‌بن شد.")
    await user.ban_chat_member(m.chat.id, uid)
    await m.edit_text("🚫 بن شد.")


@cmd("kick")
async def _(m, arg):
    uid = await target(m)
    await user.ban_chat_member(m.chat.id, uid)
    await user.unban_chat_member(m.chat.id, uid)
    await m.edit_text("👢 اخراج شد.")


async def _set_banned(chat_id, uid, until_ts, send_messages_banned):
    await user.invoke(raw.functions.channels.EditBanned(
        channel=await user.resolve_peer(chat_id),
        participant=await user.resolve_peer(uid),
        banned_rights=raw.types.ChatBannedRights(
            until_date=until_ts, send_messages=send_messages_banned or None)))


@cmd("muteu")
async def _(m, arg):
    uid = await target(m)
    if arg == "off":
        await _set_banned(m.chat.id, uid, 0, False)
        return await m.edit_text("🔊 سکوت برداشته شد.")
    mins = int(arg or 30)
    until = int(time.time()) + mins * 60
    await _set_banned(m.chat.id, uid, until, True)
    await m.edit_text(f"🔇 {mins} دقیقه ساکت شد.")


@cmd("promote")
async def _(m, arg):
    uid = await target(m)
    if arg == "off":
        await user.promote_chat_member(m.chat.id, uid, privileges=ChatPrivileges(
            can_manage_chat=False, can_delete_messages=False, can_restrict_members=False,
            can_invite_users=False, can_pin_messages=False))
        return await m.edit_text("⬇️ از ادمینی برداشته شد.")
    await user.promote_chat_member(m.chat.id, uid, privileges=ChatPrivileges(
        can_manage_chat=True, can_delete_messages=True, can_restrict_members=True,
        can_invite_users=True, can_pin_messages=True))
    await m.edit_text("⬆️ ادمین شد.")


@cmd("gtitle")
async def _(m, arg):
    await user.set_chat_title(m.chat.id, arg)
    await m.delete()


@cmd("slowmode")
async def _(m, arg):
    sec = int(arg or 0)
    await user.set_slow_mode(m.chat.id, sec or None)
    await m.edit_text(f"🐌 حالت آهسته: {sec} ثانیه")


# ---- ویژه ----
@cmd("autodelsec")
async def _(m, arg):
    S["autodel_s"] = max(3, int(arg or 60))
    save()
    await m.edit_text(f"⏱ زمان حذف خودکار: {S['autodel_s']} ثانیه")


@cmd("export")
async def _(m, arg):
    n = min(int(arg or 100), 2000)
    lines = []
    async for x in user.get_chat_history(m.chat.id, limit=n):
        who = "me" if x.outgoing else sid(x)
        lines.append(f"[{x.date:%Y-%m-%d %H:%M}] {who}: {x.text or x.caption or '<مدیا>'}")
    bio = io.BytesIO("\n".join(reversed(lines)).encode())
    bio.name = "chat_export.txt"
    await user.send_document("me", bio, caption=f"📤 خروجی {len(lines)} پیام")
    await m.edit_text("✅ خروجی به Saved Messages ارسال شد.")


@cmd("search")
async def _(m, arg):
    out = []
    async for x in user.search_messages(m.chat.id, query=arg, limit=5):
        out.append(f"#{x.id} ({x.date:%m-%d}): {(x.text or x.caption or '')[:60]}")
    await m.edit_text("🔎 نتایج:\n" + ("\n".join(out) or "چیزی پیدا نشد"), parse_mode=PM.DISABLED)


@cmd("msgcount")
async def _(m, arg):
    total = await user.search_messages_count(m.chat.id, from_user="me")
    await m.edit_text(f"✉️ پیام‌های شما در این چت: {total}")


@cmd("top")
async def _(m, arg):
    c = collections.Counter()
    async for x in user.get_chat_history(m.chat.id, limit=500):
        uid = sid(x)
        if uid:
            c[uid] += 1
    lines = []
    for uid, n in c.most_common(5):
        try:
            e = await user.get_chat(uid)
            name = e.first_name or e.title or str(uid)
        except Exception:
            name = str(uid)
        lines.append(f"• {name}: {n}")
    await m.edit_text("🏆 فعال‌ترین‌ها (۵۰۰ پیام اخیر):\n" + "\n".join(lines), parse_mode=PM.DISABLED)


@cmd("restart")
async def _(m, arg):
    save()
    await m.edit_text("♻️ در حال راه‌اندازی مجدد...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ---------------- هندلر پیام‌های خروجی ----------------
STY = {"bold": ET.BOLD, "italic": ET.ITALIC, "mono": ET.CODE, "underline": ET.UNDERLINE,
       "strike": ET.STRIKETHROUGH, "spoiler": ET.SPOILER}


async def style(m):
    t = m.text
    if not t or m.media or m.entities or m.via_bot:
        return
    sign = S.get("sign_text")
    if sign:
        t = f"{t}\n\n{sign}"
    n = u16(t)
    ents = [MessageEntity(type=T, offset=0, length=n) for k, T in STY.items() if S.get(k)]
    if S.get("autope") and EMOJI_MAP:
        ents += pe_entities(t)
    if ents:
        await m.edit_text(t, entities=ents)
    elif sign:
        await m.edit_text(t, parse_mode=PM.DISABLED)


@user.on_message(filters.me, group=0)
async def out(_, m):
    t = m.text or ""
    if t.startswith("."):
        name, _, arg = t[1:].partition(" ")
        name = name.lower()
        if name == "panel":
            res = await user.get_inline_bot_results(BOT_USERNAME, "panel")
            await user.send_inline_bot_result(m.chat.id, res.query_id, res.results[0].id)
            return await m.delete()
        fn = CMD.get(name)
        if fn:
            try:
                await fn(m, arg.strip())
            except Exception as e:
                try:
                    await m.edit_text(f"⚠️ خطا: {e}", parse_mode=PM.DISABLED)
                except Exception:
                    pass
        return
    await style(m)
    if S.get("autodel"):
        asyncio.create_task(_del_later(m.chat.id, m.id, S.get("autodel_s", 60)))


# ---------------- هندلر پیام‌های ورودی ----------------
last_reply = {}


@user.on_message(filters.incoming, group=3)
async def inc(_, m):
    ct = m.chat.type
    is_pv = ct == enums.ChatType.PRIVATE
    is_gp = ct in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP)
    is_ch = ct == enums.ChatType.CHANNEL

    if (is_pv and S.get("autoread_pv")) or (is_gp and S.get("autoread_gp")) or \
       (is_ch and S.get("autoread_ch")):
        await user.read_chat_history(m.chat.id)

    if m.mentioned and not is_pv and S.get("mentionlog"):
        await m.forward("me")

    if S.get("replylog") and m.reply_to_message:
        r = m.reply_to_message
        if r.from_user and r.from_user.is_self:
            await m.forward("me")

    if not is_pv or not m.from_user or m.from_user.is_bot:
        return

    for key, action in (("typing", enums.ChatAction.TYPING),
                        ("recvoice", enums.ChatAction.RECORD_AUDIO),
                        ("game", enums.ChatAction.PLAYING)):
        if S.get(key):
            await user.send_chat_action(m.chat.id, action)
            await asyncio.sleep(4)
            break

    reply = S.get("afk") and f"😴 {S['afk']}" or \
        (S.get("autoreply") and S.get("reply_text", "سلام! بعداً پاسخ می‌دهم."))
    if reply and time.time() - last_reply.get(m.from_user.id, 0) > 3600:
        last_reply[m.from_user.id] = time.time()
        await m.reply_text(reply, parse_mode=PM.DISABLED)


# ---------------- ساعت پروفایل ----------------
async def clock_loop():
    while True:
        try:
            now = dt.datetime.now().strftime("%H:%M")
            if S.get("nameclock"):
                await user.update_profile(last_name=f"| {now}")
            if S.get("bioclock"):
                await user.update_profile(bio=f"{S.get('bio_base', '')[:55]} | {now}")
        except Exception:
            pass
        await asyncio.sleep(60 - dt.datetime.now().second)


async def main():
    global ME, BOT_USERNAME
    if (os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID")) and not SESSION_STRING:
        sys.exit("❌ متغیر SESSION_STRING تنظیم نشده. اول gen_session.py را روی سیستم خودتان اجرا کنید.")
    await user.start()
    await bot.start()
    ME = await user.get_me()
    BOT_USERNAME = (await bot.get_me()).username
    if S.get("pe_pack"):
        try:
            EMOJI_MAP.update(await load_pack(S["pe_pack"]))
        except Exception:
            pass
    print(f"✅ Self bot آماده است | پنل: .panel | ربات: @{BOT_USERNAME}")
    asyncio.create_task(clock_loop())
    await idle()
    await user.stop()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
