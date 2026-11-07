#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 ربات پیام ناشناس + پنل ادمین کامل (نسخه ۴ - چند-باته!)
- خوش‌اومد با اسم ادمین + دکمه‌های رنگی (success/danger/primary)
- آمار کاربران + لیست ۲ ستونه با صفحه‌بندی + جستجو + تعداد پیام هر کاربر
- پاسخ با دکمه لغو شیشه‌ای + تاییدیه با ویرایش/حذف/اطلاعات کاربر
- هدر «{اسم مدیر} جواب داد :» + ریپل واقعی روی پیام کاربر هنگام پاسخ
- دکمه «پاسخ» شیشه‌ای زیر پیام مدیر ← ریپل کاربر روی اون پیام
- واکنش ادمین روی پیام → همون واکنش روی پیام کاربر + پیام بامزه
- هدر «رییس، پیام جدید داری!» قبل از هر پیام جدید
- فوروارد دستی به چنل فقط با دکمه «فوروارد به چنل» (ناشناس، بدون دکمه)
- ساخت بات ناشناس جدید (توکن + آیدی مدیر جدید) + پنل مدیریت بات‌ها
"""

import asyncio
import html
import json
import logging
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request as UrlRequest, urlopen as url_open

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "libs"))

from telegram import (Chat, InlineKeyboardButton, InlineKeyboardMarkup,
                      InputMediaAnimation, InputMediaAudio, InputMediaDocument,
                      InputMediaPhoto, InputMediaVideo, ReactionTypeEmoji,
                      ReplyKeyboardMarkup, ReplyParameters, Update)
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, MessageReactionHandler,
                          filters)

# ---------------- config ----------------
INSTANCE_NAME = None
if "--instance" in sys.argv:
    _i = sys.argv.index("--instance")
    INSTANCE_NAME = sys.argv[_i + 1]
    _idir = os.path.join(BASE, "instances", re.sub(r"[^A-Za-z0-9_]", "_", INSTANCE_NAME))
    os.makedirs(_idir, exist_ok=True)
    with open(os.path.join(_idir, "config.json"), encoding="utf-8") as f:
        CFG = json.load(f)
    DATA_PATH = os.path.join(_idir, "data.json")
    LOG_PATH = os.path.join(_idir, "bot.log")
else:
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        CFG = json.load(f)
    DATA_PATH = os.path.join(BASE, "data.json")
    LOG_PATH = os.path.join(BASE, "bot.log")
TOKEN = CFG["token"]
ADMIN_ID = int(CFG["admin_id"])
DEPTH = int(CFG.get("depth", 0))

TEHRAN = timezone(timedelta(hours=3, minutes=30))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("anonbot")

# ---------------- data ----------------
DEFAULT_DATA = {
    "bot_on": True,
    "fj_on": False,
    "fj_channels": [],
    "fj_groups": [],
    "fwd_channel": None,
    "blocked": [],
    "users": {},
    "src_map": {},
    "dst_map": {},
    "admin_name": None,
    "stats": {"total": 0, "today": 0, "day": ""},
    "last_reply": {},
    "child_bots": [],
}

def load_data():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return {**DEFAULT_DATA, **json.load(f)}
    except Exception:
        return dict(DEFAULT_DATA)

DATA = load_data()

def save_data():
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA_PATH)

STATES = {}
BOT_INFO = {"id": 0, "username": "", "name": "ربات"}

# ---------------- texts ----------------
OFF_TEXT = "🔴 ربات در حال حاضر خاموشه! ⏳ یه وقت دیگه سر بزن 🙏"
BLOCKED_TEXT = "⛔ شما از استفاده از این ربات محروم شدید!"
LOCK_TEXT = ("🔒 <b>دسترسی محدود!</b>\n\n"
             "برای ارسال پیام، اول عضو چنل و گروه‌های زیر شو 👇")
NOT_MEMBER_TEXT = "❌ کاربر گرامی اول عضو چنل ٫ گروه ها بشید و بعد روی دکمه عضو شدم کلیک کنید"
RECEIVED_TEXT = "پیام دریافت شد و به زودی پاسخ میدم ✅"
NEW_MSG_HEADER = "👑 <b>رییس، پیام جدید داری!</b> 📬"
CHILD_MAX = 5

REACT_TEXTS = {
    "😂": "مدیر ربات به پیامت خندید 😂 یعنی خیلی بامزه بود!",
    "🤣": "مدیر ربات ترکید از خنده 🤣 آفرین!",
    "👍": "مدیر ربات پیامت رو تأیید کرد 👍 دستت درد نکنه!",
    "❤": "مدیر ربات پیامت رو دوست داشت ❤️",
    "🔥": "مدیر ربات پیامت رو آتیش زد 🔥 فوق‌العاده بود!",
    "🥰": "مدیر ربات از پیامت دلش رفت 🥰",
    "😍": "مدیر ربات عاشق پیامت شد 😍",
    "👏": "مدیر ربات برات دست زد 👏 دمت گرم!",
    "🤔": "مدیر ربات داره روی پیامت فکر می‌کنه 🤔",
    "😱": "مدیر ربات شکه شد 😱 عجب پیامی!",
    "😢": "مدیر ربات ناراحت شد 😢 دلمون سوخت",
    "😭": "مدیر ربات گریه‌ش گرفت 😭",
    "🎉": "مدیر ربات جشن گرفت 🎉 مبارکه!",
    "🙏": "مدیر ربات ممنونت شد 🙏 لطف کردی!",
    "🤡": "مدیر ربات بهت خندید 🤡 شاید هم مسخره کرد 😅",
    "🤩": "مدیر ربات هیجان‌زده شد 🤩 عالی بود!",
    "💯": "مدیر ربات نمره ۱۰۰ داد 💯 کامل بود!",
    "🫡": "مدیر ربات بهت ادب نشون داد 🫡",
    "🥱": "مدیر ربات خمیازه کشید 🥱 شاید خسته‌کننده بود 😅",
    "🕊": "مدیر ربات برات آرزوی آرامش کرد 🕊",
    "🤯": "مدیر ربات منفجر شد 🤯 چه پیامی!",
    "🤮": "مدیر ربات قی کرد 🤮 یعنی این چیه؟ 😅",
    "💩": "مدیر ربات بد شد 💩 بهترش کن 😅",
}

BTN_BROADCAST = "📢 پیام همگانی"
BTN_FJ = "🔐 جوین اجباری"
BTN_FC = "📤 چنل فوروارد"
BTN_POWER = "🔄 خاموش/روشن ربات"
BTN_STATS = "📊 آمار کاربران"
BTN_NEWBOT = "🤖 بات ناشناس جدید"
BTN_MYBOTS = "📋 بات‌های من"

def panel_kb():
    rows = [[BTN_BROADCAST, BTN_FJ],
            [BTN_FC, BTN_POWER],
            [BTN_STATS, BTN_SYS_STATS],
            [BTN_VIP]]
    if DEPTH == 0:
        rows.append([BTN_NEWBOT])
        rows.append([BTN_MYBOTS])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

FJ_PROMPT_C = ("📢 <b>تنظیم چنل</b>\n\nحالا یکی از این کارها رو بکن:\n"
               "1️⃣ یه پیام از چنل رو فوروارد کن 📨\n"
               "2️⃣ یا @username چنل رو بفرست\n"
               "3️⃣ یا آیدی عددی چنل رو بفرست (مثل <code>-1001234567890</code>)\n\n"
               "⚡️ حداکثر تا ۱۰ چنل/گروه قابل تنظیمه")
FJ_PROMPT_G = ("👥 <b>تنظیم گروه</b>\n\nحالا یکی از این کارها رو بکن:\n"
               "1️⃣ یه پیام از گروه رو فوروارد کن 📨\n"
               "2️⃣ یا @username گروه رو بفرست\n"
               "3️⃣ یا آیدی عددی گروه رو بفرست (مثل <code>-1001234567890</code>)\n\n"
               "⚡️ حداکثر تا ۱۰ چنل/گروه قابل تنظیمه")
FC_PROMPT = ("📤 <b>تنظیم چنل فوروارد</b>\n\n"
             "یه پیام از چنل فوروارد کن 📨 یا @username یا آیدی عددیش رو بفرست\n\n"
             "🚀 بعدش هر پیامی که خودت روش دکمه «فوروارد به چنل» بزنی، همون لحظه به این چنل میره!")

# ---------------- styled button (Bot API 9.4) ----------------
class StyledButton(InlineKeyboardButton):
    """دکمه شیشه‌ای رنگی: success=سبز، danger=قرمز، primary=آبی"""
    __slots__ = ("_style",)

    def __init__(self, text, callback_data=None, url=None, style=None):
        super().__init__(text=text, callback_data=callback_data, url=url)
        self._style = style

    def to_dict(self, recursive=True):
        d = super().to_dict(recursive)
        if self._style:
            d["style"] = self._style
        return d

# ---------------- helpers ----------------
def g2j(gy: int, gm: int, gd: int):
    """تبدیل میلادی به جلالی"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def jdate_only() -> str:
    dt = datetime.now(TEHRAN)
    jy, jm, jd = g2j(dt.year, dt.month, dt.day)
    return f"{jy}/{jm:02d}/{jd:02d}"

def date_str() -> str:
    dt = datetime.now(TEHRAN)
    jy, jm, jd = g2j(dt.year, dt.month, dt.day)
    return f"{jy}/{jm:02d}/{jd:02d} - {dt.strftime('%H:%M')}"

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def admin_display() -> str:
    """اسم مدیر برای نمایش در پیام‌ها (فال‌بک: «مدیر ربات»)"""
    return html.escape(DATA.get("admin_name") or "مدیر ربات")

def add_user(u):
    if not u or u.is_bot:
        return
    key = str(u.id)
    info = DATA["users"].get(key, {})
    is_new = not info
    info["name"] = u.first_name or ""
    info["username"] = ("@" + u.username) if u.username else ""
    info.setdefault("joined", jdate_only())
    info.setdefault("msgs", 0)
    DATA["users"][key] = info
    if is_new:
        ds = day_stats()
        ds["new_users"] = ds.get("new_users", 0) + 1
    save_data()

async def send(context, chat_id, text, **kw):
    return await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, **kw)

async def check_membership(context, uid: int) -> bool:
    """چک دقیق عضویت در همه چنل‌ها و گروه‌ها"""
    for c in list(DATA["fj_channels"]) + list(DATA["fj_groups"]):
        try:
            m = await context.bot.get_chat_member(c["id"], uid)
            st = m.status
            if st in ("member", "administrator", "creator"):
                continue
            if st == "restricted" and getattr(m, "is_member", False):
                continue
            return False
        except Exception as e:
            log.warning(f"member check fail {c['id']}: {e}")
            continue
    return True

def build_lock_kb():
    rows = []
    for c in list(DATA["fj_channels"]):
        url = c.get("link") or (f"https://t.me/{c['username']}" if c.get("username") else None)
        if url:
            rows.append([InlineKeyboardButton(f"📢 {c['title'][:30]}", url=url)])
    for g in list(DATA["fj_groups"]):
        url = g.get("link") or (f"https://t.me/{g['username']}" if g.get("username") else None)
        if url:
            rows.append([InlineKeyboardButton(f"👥 {g['title'][:30]}", url=url)])
    rows.append([InlineKeyboardButton("✅ عضو شدم", callback_data="joined")])
    return InlineKeyboardMarkup(rows)

def sender_kb(name: str, uid: int, uname: str, blocked: bool, date: str = None, msgs: int = 0):
    """کیبورد پیام ادمین: ۵ دکمه شیشه‌ای بزرگ + ۳ دکمه رنگی کوچک"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 Name: {name}", callback_data="noop")],
        [InlineKeyboardButton(f"📅 Date: {date or date_str()}", callback_data="noop")],
        [InlineKeyboardButton(f"🆔 ID: {uid}", callback_data="noop")],
        [InlineKeyboardButton(f"🔗 Username: {uname or '—'}", callback_data="noop")],
        [InlineKeyboardButton(f"💌 پیام‌ها: {msgs}", callback_data="noop")],
        [StyledButton("پاسخ", callback_data=f"reply:{uid}", style="success"),
         StyledButton("آنبلاک" if blocked else "بلاک", callback_data=f"block:{uid}", style="danger"),
         StyledButton("فوروارد به چنل", callback_data="fwd", style="primary")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_state")]])

def user_reply_kb(amid: int):
    """دکمه شیشه‌ای «پاسخ» زیر پیام‌هایی که مدیر برای کاربر می‌فرستد"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ", callback_data=f"rpu:{amid}")]])

def conf_kb(uid: int):
    """۳ دکمه بعد از ارسال پیام: ویرایش / حذف / اطلاعات کاربر"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش پیام", callback_data=f"redit:{uid}")],
        [InlineKeyboardButton("🗑 حذف پیام", callback_data=f"rdel:{uid}")],
        [InlineKeyboardButton("👤 اطلاعات کاربر", callback_data=f"uinfo:{uid}:0")],
    ])

def fj_panel():
    on = DATA["fj_on"]
    text = ("🔐 <b>تنظیمات جوین اجباری</b>\n\n"
            f"وضعیت: {'🟢 روشن' if on else '🔴 خاموش'}\n"
            f"📢 چنل‌ها: {len(DATA['fj_channels'])} | 👥 گروه‌ها: {len(DATA['fj_groups'])}\n\n"
            "⚡️ حداکثر تا ۱۰ چنل/گروه می‌تونی تنظیم کنی")
    kb = [
        [InlineKeyboardButton("🔴 خاموش کردن جوین اجباری" if on else "🟢 روشن کردن جوین اجباری",
                              callback_data="fj_toggle")],
        [InlineKeyboardButton("📢 تنظیم چنل", callback_data="fj_set:c")],
        [InlineKeyboardButton("👥 تنظیم گروه", callback_data="fj_set:g")],
        [InlineKeyboardButton("🤖 ادمین کردن ربات در چنل یا گروه", callback_data="fj_botadmin")],
        [InlineKeyboardButton("📋 لیست چنل/گروه‌ها", callback_data="fj_list")],
    ]
    return text, InlineKeyboardMarkup(kb)

def fc_panel():
    fc = DATA["fwd_channel"]
    status = f"«{html.escape(fc['title'])}» ✅" if fc else "🔴 تنظیم نشده"
    text = ("📤 <b>تنظیم چنل فوروارد</b>\n\n"
            f"چنل فعلی: {status}\n\n"
            "🚀 هر پیامی که خودت روش دکمه «فوروارد به چنل» بزنی به همین چنل میره!")
    kb = [[InlineKeyboardButton("📤 تنظیم چنل فوروارد", callback_data="fc_set")],
          [InlineKeyboardButton("🤖 ادمین کردن ربات در چنل", callback_data="fj_botadmin")]]
    if fc:
        kb.append([InlineKeyboardButton("🗑 حذف چنل فوروارد", callback_data="fc_del")])
    return text, InlineKeyboardMarkup(kb)

def fj_list_panel():
    lines = ["📋 <b>لیست چنل‌ها و گروه‌ها</b>\n"]
    kb = []
    for i, c in enumerate(DATA["fj_channels"], 1):
        lines.append(f"{i}. 📢 {html.escape(c['title'])}")
        kb.append([InlineKeyboardButton(f"🗑 حذف {c['title'][:20]}", callback_data=f"fj_del:c:{c['id']}")])
    for j, g in enumerate(DATA["fj_groups"], len(DATA["fj_channels"]) + 1):
        lines.append(f"{j}. 👥 {html.escape(g['title'])}")
        kb.append([InlineKeyboardButton(f"🗑 حذف {g['title'][:20]}", callback_data=f"fj_del:g:{g['id']}")])
    if not kb:
        lines.append("هنوز چیزی ثبت نشده 🤷‍♂️")
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="fj_back")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)

def users_list_panel(page: int = 0):
    """آمار کاربران + لیست ۲ ستونه با صفحه‌بندی (۱۰ نفر در هر صفحه)"""
    users = DATA["users"]
    ids = list(users.keys())
    total = len(ids)
    st = DATA.setdefault("stats", {"total": 0, "today": 0, "day": ""})
    per = 10
    pages = max(1, (total + per - 1) // per)
    page = max(0, min(page, pages - 1))
    text = (f"📊 <b>آمار کاربران</b>\n\n"
            f"👥 کل کاربران: {total}\n"
            f"💌 کل پیام‌ها: {st.get('total', 0)}\n"
            f"📅 پیام‌های امروز: {st.get('today', 0)}\n\n"
            f"🗂 کاربران — صفحه {page + 1} از {pages}:")
    kb = []
    for uid_s in ids[page * per:(page + 1) * per]:
        u = users.get(uid_s, {})
        nm = u.get("name") or "—"
        _uu = int(uid_s)
        prefix = "💎 " if _uu in DATA.get("vip", []) else ("🚫 " if _uu in DATA["blocked"] else "👤 ")
        kb.append([
            InlineKeyboardButton("ℹ️ اطلاعات کاربر", callback_data=f"uinfo:{uid_s}:{page}"),
            InlineKeyboardButton(f"{prefix}{nm[:18]}", callback_data="noop"),
        ])
    if not kb:
        text += "\n😕 هنوز هیچ کاربری نیست!"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("««", callback_data=f"stats:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("»»", callback_data=f"stats:{page + 1}"))
    if len(nav) > 1:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔍 جستجو کاربر", callback_data="usearch")])
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="back_panel")])
    return text, InlineKeyboardMarkup(kb)

def user_info_panel(uid: int, page: int = 0):
    """صفحه اطلاعات کاربر"""
    u = DATA["users"].get(str(uid), {})
    blocked = uid in DATA["blocked"]
    text = (f"👤 <b>اطلاعات کاربر</b>\n\n"
            f"📛 اسم: {html.escape(u.get('name') or '—')}\n"
            f"🔗 یوزرنیم: {html.escape(u.get('username') or 'نداره')}\n"
            f"🆔 آیدی عددی: <code>{uid}</code>\n"
            f"💌 تعداد پیام‌ها: {u.get('msgs', 0)}\n"
            f"📅 تاریخ عضویت: {u.get('joined', '—')}\n"
            f"🗓 آخرین پیام: {u.get('last_msg', '—')}\n"
            f"وضعیت: {'🚫 بلاک شده' if blocked else '✅ فعال'}")
    kb = [
        [InlineKeyboardButton("📨 ارسال پیام", callback_data=f"usend:{uid}")],
        [InlineKeyboardButton("✅ آنبلاک کردن" if blocked else "🚫 بلاک کردن",
                              callback_data=f"ublock:{uid}:{page}")],
        [InlineKeyboardButton("🔙 برگشت به لیست", callback_data=f"uback:{page}")],
    ]
    return text, InlineKeyboardMarkup(kb)

def search_users(q: str):
    q = q.strip()
    if not q:
        return []
    ql = q.lower().lstrip("@")
    out = []
    for uid_s, u in DATA["users"].items():
        name = (u.get("name") or "").lower()
        uname = (u.get("username") or "").lower().lstrip("@")
        if uid_s == ql or (ql in uname) or (ql in name):
            out.append(uid_s)
    return out[:10]

def search_results_panel(q: str, res):
    text = f"🔍 <b>نتایج جستجو</b> برای «{html.escape(q)}» ({len(res)} نفر):"
    kb = []
    for uid_s in res:
        u = DATA["users"].get(uid_s, {})
        nm = u.get("name") or "—"
        _uu = int(uid_s)
        prefix = "💎 " if _uu in DATA.get("vip", []) else ("🚫 " if _uu in DATA["blocked"] else "👤 ")
        kb.append([
            InlineKeyboardButton("ℹ️ اطلاعات کاربر", callback_data=f"uinfo:{uid_s}:0"),
            InlineKeyboardButton(f"{prefix}{nm[:18]}", callback_data="noop"),
        ])
    kb.append([InlineKeyboardButton("🔙 برگشت به لیست", callback_data="uback:0")])
    return text, InlineKeyboardMarkup(kb)

def chat_entry(chat):
    link = f"https://t.me/{chat.username}" if chat.username else None
    return {"id": chat.id, "title": chat.title or chat.username or str(chat.id),
            "username": chat.username or "", "link": link}

async def resolve_chat(context, msg):
    """استخراج چت از فوروارد / @username / آیدی عددی"""
    origin = getattr(msg, "forward_origin", None)
    chat = getattr(origin, "chat", None) if origin is not None else None
    if chat is not None:
        return chat
    text = (msg.text or msg.caption or "").strip()
    if text.startswith("@") and len(text) > 2:
        try:
            return await context.bot.get_chat(text)
        except Exception:
            return None
    if re.fullmatch(r"-?\d{5,}", text):
        try:
            return await context.bot.get_chat(int(text))
        except Exception:
            return None
    return None

async def send_welcome(context, chat):
    name = html.escape(chat.first_name or "دوست من")
    admin_disp = admin_display()
    t1 = (f"درود {name} عزیز 🌹\n"
          f"خوش اومدی به {html.escape(BOT_INFO['name'])} 💫\n\n"
          f"هر پیامی داری بفرست، ناشناس ارسال میشه برای {admin_disp} 🕊️")
    t2 = ("✨ دیگه نیازی نیست هر دفعه ربات رو استارت کنی!\n"
          "همینجا هر پیامی که داری بفرست، خودم متوجه میشم میخوای برای کی ارسال کنی 🤠")
    await send(context, chat.id, t1, reply_markup=user_kb())
    await send(context, chat.id, t2)

def save_last_reply(uid: int, rec: dict):
    lr = DATA.setdefault("last_reply", {})
    lr[str(uid)] = rec
    if len(lr) > 100:
        for k in list(lr.keys())[: len(lr) - 100]:
            lr.pop(k, None)
    save_data()

# ============================================================
# ✨ آپدیت v5 — لینک ناشناس اختصاصی + VIP + آمار + امنیت
# ============================================================
BTN_MY_LINK = "🔗 دریافت ناشناس من"
BTN_MY_PANEL = "📊 پنل مدیریت"
BTN_VIP = "💎 کاربران VIP"
BTN_SYS_STATS = "📈 آمار ربات"

_cfg_rl = CFG.get("rate_limit") or {}
RATE_PER_MIN = int(_cfg_rl.get("per_minute", 6))
RATE_PER_HOUR = int(_cfg_rl.get("per_hour", 30))
_RATE_HITS = {}

INVALID_LINK_TEXT = "❌ این لینک ناشناس معتبر نیست یا دیگر فعال نیست."
SELF_LINK_TEXT = "🙃 شما نمی‌توانید از لینک ناشناس خودتان برای ارسال پیام به خودتان استفاده کنید!"
RATE_TEXT = "⚠️ یه کم آروم‌تر! ⏳ چند لحظه صبر کن بعد دوباره پیام بده 🙏"
SENT_LINK_TEXT = "✅ پیامت به‌صورت ناشناس ارسال شد 🕊️"
LINK_FAIL_TEXT = "⚠️ ارسال نشد! احتمالاً صاحب لینک هنوز ربات رو استارت نکرده یا بلاکش کرده 😕"
OWNER_REPLY_FAIL = "⚠️ ارسال نشد! احتمالاً طرف مقابل ربات رو بلاک کرده 😕"
OWNER_NEW_MSG = "📩 <b>پیام ناشناس جدید</b>\n"
THREAD_GONE_TEXT = "⚠️ این گفتگو دیگه در دسترس نیست!"

def get_role(uid: int) -> str:
    """نقش کاربر — همیشه در بک‌اند چک میشه (user / vip / admin)"""
    if is_admin(uid):
        return "admin"
    if uid in DATA.get("vip", []):
        return "vip"
    return "user"

def g_today() -> str:
    return datetime.now(TEHRAN).strftime("%Y-%m-%d")

def _last_days(n: int):
    base = datetime.now(TEHRAN).date()
    return {(base - timedelta(days=i)).isoformat() for i in range(n)}

def prune_sorted_days(dd: dict, keep: int):
    if len(dd) <= keep:
        return
    for k in sorted(dd.keys())[: len(dd) - keep]:
        dd.pop(k, None)

def day_stats(date: str = None) -> dict:
    date = date or g_today()
    return DATA.setdefault("daily", {}).setdefault(
        date, {"msgs": 0, "views": 0, "new_users": 0, "active": []})

def migrate_data():
    """مهاجرت امن دیتا — فقط کلیدهای جدید اضافه می‌شه؛ هیچ داده قدیمی حذف/تغییر نمی‌کنه"""
    d = DATA
    d.setdefault("vip", [])
    d.setdefault("links", {})
    d.setdefault("link_by_uid", {})
    d.setdefault("osrc_map", {})
    d.setdefault("pending_target", {})
    d.setdefault("owner_views", {})
    d.setdefault("view_log", {})
    d.setdefault("daily", {})
    st = d.setdefault("stats", {"total": 0, "today": 0, "day": ""})
    st.setdefault("views_total", 0)
    st.setdefault("views_today", 0)
    st.setdefault("views_day", "")
    for u in d.get("users", {}).values():
        u.setdefault("recv_total", 0)
        u.setdefault("recv_daily", {})
    prune_sorted_days(d["daily"], 90)
    prune_sorted_days(d["view_log"], 30)
    for u in d.get("users", {}).values():
        prune_sorted_days(u.get("recv_daily", {}), 40)
    save_data()

migrate_data()

def bump_daily_msgs(uid: int):
    """شمارش پیام روز + کاربر فعال امروز (sync — بدون await → بدون Race Condition)"""
    ds = day_stats()
    ds["msgs"] = ds.get("msgs", 0) + 1
    act = ds.setdefault("active", [])
    su = str(uid)
    if su not in act:
        act.append(su)

def add_view(owner_uid: int, visitor_uid: int) -> bool:
    """ثبت بازدید لینک — هر بازدیدکننده در هر روز فقط یک‌بار (True = شمرده شد)"""
    date = g_today()
    vl = DATA.setdefault("view_log", {})
    okey, vkey = str(owner_uid), str(visitor_uid)
    visitors = vl.setdefault(date, {}).setdefault(okey, [])
    if vkey in visitors:
        return False
    if len(visitors) < 10000:
        visitors.append(vkey)
    prune_sorted_days(vl, 30)
    ov = DATA.setdefault("owner_views", {}).setdefault(okey, {})
    if ov.get("day") != date:
        ov["day"] = date
        ov["today"] = 0
    ov["today"] = ov.get("today", 0) + 1
    ov["total"] = ov.get("total", 0) + 1
    st = DATA.setdefault("stats", {})
    if st.get("views_day") != date:
        st["views_day"] = date
        st["views_today"] = 0
    st["views_today"] = st.get("views_today", 0) + 1
    st["views_total"] = st.get("views_total", 0) + 1
    ds = day_stats(date)
    ds["views"] = ds.get("views", 0) + 1
    save_data()
    return True

def gen_token() -> str:
    """توکن تصادفی و غیرقابل حدس — بدون user_id/username/timestamp — با چک تکراری"""
    for _ in range(50):
        tok = secrets.token_urlsafe(16)
        if tok not in DATA.get("links", {}):
            return tok
    raise RuntimeError("token collision after 50 tries")

def link_url(tok: str) -> str:
    un = BOT_INFO.get("username") or "bot"
    return f"https://t.me/{un}?start={tok}"

def get_or_create_link(uid: int):
    """لینک پایدار هر کاربر — هرگز برای همان کاربر دوباره ساخته نمی‌شود"""
    lbu = DATA.setdefault("link_by_uid", {})
    tok = lbu.get(str(uid))
    if tok and tok in DATA.get("links", {}):
        return tok, DATA["links"][tok]
    tok = gen_token()
    DATA["links"][tok] = {"owner": uid, "enabled": True, "created": jdate_only()}
    lbu[str(uid)] = tok
    save_data()
    log.info(f"🔗 link created owner={uid} token={tok[:4]}…")
    return tok, DATA["links"][tok]

def owner_display(owner_uid: int) -> str:
    u = DATA["users"].get(str(owner_uid), {})
    if u.get("name"):
        return html.escape(u["name"])
    if owner_uid == ADMIN_ID:
        return admin_display()
    return "دوست شما"

def user_kb():
    return ReplyKeyboardMarkup([[BTN_MY_LINK], [BTN_MY_PANEL]], resize_keyboard=True)

def rate_limited(uid: int) -> bool:
    """Rate Limit — مقادیر از کانفیگ (rate_limit.per_minute / per_hour)"""
    if is_admin(uid):
        return False
    now = time.time()
    hits = _RATE_HITS.setdefault(uid, [])
    hits[:] = [t for t in hits if now - t < 3600]
    if sum(1 for t in hits if now - t < 60) >= RATE_PER_MIN:
        return True
    if len(hits) >= RATE_PER_HOUR:
        return True
    hits.append(now)
    return False

def owner_recv_kb(key: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ", callback_data=f"rpo:{key}")]])

def owner_recv_stats(uid: int) -> dict:
    u = DATA["users"].get(str(uid), {})
    rd = u.get("recv_daily", {})
    today = g_today()
    return {
        "today": rd.get(today, 0),
        "week": sum(v for k, v in rd.items() if k in _last_days(7)),
        "month": sum(v for k, v in rd.items() if k.startswith(today[:7])),
        "total": u.get("recv_total", 0),
    }

async def handle_my_link(update, context, u):
    """دکمه «دریافت ناشناس من» — ثبت‌نام در صورت نبود + نمایش لینک پایدار"""
    add_user(u)
    tok, rec = get_or_create_link(u.id)
    url = link_url(tok)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        "📤 اشتراک‌گذاری لینک", url=f"https://t.me/share/url?url={url}")]])
    txt = (f"🔗 <b>لینک ناشناس اختصاصی شما:</b>\n\n"
           f"<code>{html.escape(url)}</code>\n\n"
           "هر کسی با این لینک وارد ربات بشه، پیامش ناشناس مستقیم به شما می‌رسه 🕊️\n"
           "🔗 این لینک همیشه ثابته و تغییر نمی‌کنه ✅")
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def handle_my_panel(update, context, u):
    """دکمه «پنل مدیریت» — ادمین: پنل ادمین | کاربر/VIP: آمار شخصی خودش"""
    role = get_role(u.id)
    if role == "admin":
        STATES.pop(u.id, None)
        await update.message.reply_text(
            "🎛 <b>پنل ادمین</b> 👇", parse_mode=ParseMode.HTML, reply_markup=panel_kb())
        return
    rs = owner_recv_stats(u.id)
    ov = DATA.get("owner_views", {}).get(str(u.id), {})
    if role == "vip":
        txt = (f"📊 <b>آمار من (VIP 💎)</b>\n\n"
               f"📨 پیام‌های امروز: {rs['today']}\n"
               f"📨 پیام‌های این هفته: {rs['week']}\n"
               f"📨 پیام‌های این ماه: {rs['month']}\n"
               f"📨 کل پیام‌های دریافتی: {rs['total']}\n\n"
               f"👀 بازدید لینک امروز: {ov.get('today', 0)}\n"
               f"👀 کل بازدید لینک: {ov.get('total', 0)}")
    else:
        txt = (f"📊 <b>آمار من</b>\n\n"
               f"📨 پیام‌های امروز: {rs['today']}\n"
               f"📨 کل پیام‌های دریافتی: {rs['total']}\n\n"
               f"👀 بازدیدهای لینک: {ov.get('total', 0)}")
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def handle_link_entry(update, context, u, token_arg: str):
    """ورود با Deep Link (start=token) — اعتبارسنجی کامل توکن در بک‌اند"""
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", token_arg):
        await update.message.reply_text(INVALID_LINK_TEXT)
        return
    rec = DATA.get("links", {}).get(token_arg)
    if not rec:
        await update.message.reply_text(INVALID_LINK_TEXT)
        return
    owner = int(rec.get("owner", 0))
    if not rec.get("enabled", True) or (str(owner) not in DATA["users"] and owner != ADMIN_ID):
        await update.message.reply_text(INVALID_LINK_TEXT)
        return
    if u.id == owner:
        await update.message.reply_text(SELF_LINK_TEXT, reply_markup=user_kb())
        return
    DATA.setdefault("pending_target", {})[str(u.id)] = owner
    add_view(owner, u.id)
    name = owner_display(owner)
    await update.message.reply_text(
        f"درود 👋\n\n"
        f"اینجا هر پیامی رو بفرستی مستقیم برای <b>{name}</b> ارسال میشه؛ به صورت ناشناس 🕊️\n\n"
        "✍️ پیام خودت رو ارسال کن.",
        parse_mode=ParseMode.HTML, reply_markup=user_kb())

async def send_to_owner(update, context, u, owner_uid: int, thread_ref: int = None):
    """ارسال پیام ناشناس برای صاحب لینک — اطلاعات فرستنده فقط برای VIP (چک بک‌اند)"""
    msg = update.message
    chat_id = update.effective_chat.id
    owner_uid = int(owner_uid)
    role = get_role(owner_uid)
    uname = ("@" + u.username) if u.username else ""
    uinfo0 = DATA["users"].get(str(u.id), {})
    shown_msgs = uinfo0.get("msgs", 0) + 1
    try:
        if role in ("vip", "admin"):
            info = (f"━━━━━━━━━━━━\n"
                    f"👤 <b>اطلاعات فرستنده:</b>\n"
                    f"🔗 یوزرنیم: {html.escape(uname or 'نداره')}\n"
                    f"📛 اسم: {html.escape(u.first_name or '—')}\n"
                    f"🆔 آیدی عددی: <code>{u.id}</code>\n"
                    f"💌 تعداد پیام‌های این کاربر: {shown_msgs}\n")
        else:
            info = ""  # 🔒 کاربر عادی: هیچ اطلاعات هویتی از فرستنده نمایش داده نمی‌شه
        header = OWNER_NEW_MSG + info
        if thread_ref:
            try:
                await send(context, owner_uid, header,
                           reply_to_message_id=thread_ref, allow_sending_without_reply=True)
            except Exception:
                await send(context, owner_uid, header)
        else:
            await send(context, owner_uid, header)
        key = f"{chat_id}_{msg.message_id}"
        res = await context.bot.copy_message(owner_uid, chat_id, msg.message_id,
                                             reply_markup=owner_recv_kb(key))
        osm = DATA.setdefault("osrc_map", {})
        osm[key] = {"owner": owner_uid, "chat": chat_id, "mid": msg.message_id,
                    "date": date_str(), "omid": res.message_id}
        if len(osm) > 500:
            for k in list(osm.keys())[: len(osm) - 500]:
                osm.pop(k, None)
        # 📊 شمارنده‌ها — بلوک sync بدون await بین خواندن و نوشتن (بدون Race Condition)
        sinfo = DATA["users"].setdefault(str(u.id), {})
        sinfo["msgs"] = sinfo.get("msgs", 0) + 1
        sinfo["last_msg"] = jdate_only()
        oinfo = DATA["users"].setdefault(str(owner_uid), {})
        oinfo["recv_total"] = oinfo.get("recv_total", 0) + 1
        rd = oinfo.setdefault("recv_daily", {})
        td = g_today()
        rd[td] = rd.get(td, 0) + 1
        prune_sorted_days(rd, 40)
        sts = DATA.setdefault("stats", {"total": 0, "today": 0, "day": ""})
        if sts.get("day") != td:
            sts["day"] = td
            sts["today"] = 0
        sts["total"] = sts.get("total", 0) + 1
        sts["today"] = sts.get("today", 0) + 1
        bump_daily_msgs(u.id)
        save_data()
        await msg.reply_text(SENT_LINK_TEXT, reply_markup=user_kb())
    except Exception as e:
        log.warning(f"send to owner {owner_uid} failed: {e}")
        try:
            await msg.reply_text(LINK_FAIL_TEXT)
        except Exception:
            pass

async def do_owner_reply(update, context, u, key: str):
    """پاسخ صاحب لینک به پیام ناشناس (دکمه rpo) — پاسخ ناشناس به فرستنده می‌رسه"""
    msg = update.message
    ent = DATA.get("osrc_map", {}).get(key)
    STATES.pop(u.id, None)
    if not ent:
        await msg.reply_text(THREAD_GONE_TEXT)
        return
    try:
        await send(context, ent["chat"], f"💬 <b>{owner_display(u.id)}</b> جواب داد :")
        res = await context.bot.copy_message(ent["chat"], msg.chat_id, msg.message_id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            "↩️ پاسخ", callback_data=f"rpuo:{res.message_id}:{key}")]])
        await context.bot.edit_message_reply_markup(ent["chat"], res.message_id, reply_markup=kb)
        await msg.reply_text("✅ پاسخت ارسال شد 🕊️")
    except Exception as e:
        log.warning(f"owner reply failed: {e}")
        await msg.reply_text(OWNER_REPLY_FAIL)

async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.effective_chat or update.effective_chat.type != Chat.PRIVATE:
        return
    if get_role(u.id) == "admin":
        await update.message.reply_text(
            "ℹ️ رئیس، همه پیام‌ها خودکار برای تو میاد؛ لینک ناشناس مخصوص کاربرانinale!")
        return
    await handle_my_link(update, context, u)

# ---------- پنل VIP ادمین ----------
def vip_panel():
    n = len(DATA.get("vip", []))
    txt = (f"💎 <b>مدیریت کاربران VIP</b>\n\n"
           f"تعداد VIP: {n}\n\n"
           "💎 VIP علاوه بر امکانات کاربر عادی، <b>اطلاعات فرستنده</b> پیام‌های لینکش و "
           "<b>آمار پیشرفته</b> رو می‌بینه.\n"
           "➕ افزودن با آیدی عددی انجام می‌شه.")
    kb = [[InlineKeyboardButton("➕ افزودن VIP", callback_data="vip_add"),
           InlineKeyboardButton("📋 لیست VIP", callback_data="vip_list")],
          [InlineKeyboardButton("🔍 جستجوی VIP", callback_data="vip_search"),
           InlineKeyboardButton("🔙 برگشت", callback_data="vip_back")]]
    return txt, InlineKeyboardMarkup(kb)

def vip_list_panel(page: int = 0):
    vips = DATA.get("vip", [])
    per = 10
    pages = max(1, (len(vips) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    txt = f"📋 <b>لیست کاربران VIP</b> — صفحه {page + 1} از {pages} ({len(vips)} نفر):"
    kb = []
    for uid in vips[page * per:(page + 1) * per]:
        nm = DATA["users"].get(str(uid), {}).get("name") or "—"
        kb.append([InlineKeyboardButton(f"💎 {nm[:18]}", callback_data=f"vip_info:{uid}"),
                   InlineKeyboardButton("➖ حذف", callback_data=f"vip_del:{uid}")])
    if not kb:
        txt = "📋 <b>لیست کاربران VIP</b>\n\nهنوز هیچ VIP ای اضافه نشده!"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("««", callback_data=f"vip_page:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("»»", callback_data=f"vip_page:{page + 1}"))
    if len(nav) > 1:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 برگشت", callback_data="vip_back")])
    return txt, InlineKeyboardMarkup(kb)

def vip_info_panel(uid: int):
    u = DATA["users"].get(str(uid), {})
    rs = owner_recv_stats(uid)
    ov = DATA.get("owner_views", {}).get(str(uid), {})
    is_vip = uid in DATA.get("vip", [])
    blocked = uid in DATA["blocked"]
    tok = DATA.get("link_by_uid", {}).get(str(uid))
    txt = (f"👤 <b>اطلاعات کاربر VIP</b>\n\n"
           f"📛 اسم: {html.escape(u.get('name') or '—')}\n"
           f"🔗 یوزرنیم: {html.escape(u.get('username') or 'نداره')}\n"
           f"🆔 آیدی عددی: <code>{uid}</code>\n"
           f"📅 تاریخ عضویت: {u.get('joined', '—')}\n"
           f"وضعیت VIP: {'💎 VIP' if is_vip else 'کاربر عادی'}\n"
           f"وضعیت حساب: {'🚫 بلاک شده' if blocked else '✅ فعال'}\n\n"
           f"📨 پیام‌های امروز: {rs['today']}\n"
           f"📨 کل پیام‌های دریافتی: {rs['total']}\n\n"
           f"👀 بازدید لینک امروز: {ov.get('today', 0)}\n"
           f"👀 کل بازدید لینک: {ov.get('total', 0)}\n\n"
           f"🗓 آخرین فعالیت: {u.get('last_msg', '—')}\n"
           f"🔗 لینک ناشناس: {'داره ✅' if tok else 'نداره ❌'}")
    kb = []
    if is_vip:
        kb.append([InlineKeyboardButton("➖ حذف VIP", callback_data=f"vip_del:{uid}")])
    else:
        kb.append([InlineKeyboardButton("➕ افزودن به VIP", callback_data="vip_add")])
    kb.append([InlineKeyboardButton("🔙 برگشت به لیست", callback_data="vip_list")])
    return txt, InlineKeyboardMarkup(kb)

def admin_stats_panel():
    """آمار کلی سیستم — فقط ادمین"""
    today = g_today()
    users = DATA["users"]
    st = DATA.setdefault("stats", {})
    ds = DATA.get("daily", {})
    d0 = ds.get(today, {})
    new_today = sum(1 for u in users.values() if u.get("joined") == jdate_only())
    lines = []
    for k in sorted(ds.keys())[-7:]:
        m = ds[k].get("msgs", 0)
        v = ds[k].get("views", 0)
        lines.append(f"<code>{k[5:]}</code> | 📨 {m:<4} | 👀 {v:<4} {'▮' * min(m, 18)}")
    week = sum(ds[k].get("msgs", 0) for k in ds if k in _last_days(7))
    month = sum(ds[k].get("msgs", 0) for k in ds if k.startswith(today[:7]))
    txt = (f"📈 <b>آمار کلی ربات</b>\n\n"
           f"👥 کل کاربران: {len(users)}\n"
           f"🆕 کاربران جدید امروز: {new_today}\n"
           f"🟢 کاربران فعال امروز: {len(d0.get('active', []))}\n\n"
           f"📨 پیام‌های امروز: {st.get('today', 0)}\n"
           f"📨 کل پیام‌ها: {st.get('total', 0)}\n"
           f"📨 این هفته: {week} | 📨 این ماه: {month}\n\n"
           f"💎 کاربران VIP: {len(DATA.get('vip', []))}\n\n"
           f"👀 بازدید لینک امروز: {st.get('views_today', 0)}\n"
           f"👀 کل بازدیدها: {st.get('views_total', 0)}")
    if lines:
        txt += "\n\n🗓 <b>۷ روز اخیر:</b>\n" + "\n".join(lines)
    kb = [[InlineKeyboardButton("🔙 برگشت به پنل", callback_data="back_panel")]]
    return txt, InlineKeyboardMarkup(kb)

# ---------------- چند-بات (instances) ----------------
def inst_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name or "bot")

def inst_paths(name: str):
    safe = inst_safe(name)
    d = os.path.join(BASE, "instances", safe)
    return d, os.path.join(BASE, "instances", safe + ".pid"), os.path.join(BASE, "instances", safe + ".log")

def tg_getme(token: str):
    try:
        req = UrlRequest(f"https://api.telegram.org/bot{token}/getMe")
        with url_open(req, timeout=12) as r:
            j = json.loads(r.read().decode("utf-8"))
        if j.get("ok"):
            return j["result"]
    except Exception as e:
        log.warning(f"getMe fail: {e}")
    return None

def child_alive(name: str) -> bool:
    try:
        _, pidf, _ = inst_paths(name)
        with open(pidf) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def spawn_child(name: str) -> int:
    d, pidf, logf = inst_paths(name)
    os.makedirs(d, exist_ok=True)
    lf = open(logf, "ab")
    p = subprocess.Popen(
        [sys.executable, os.path.join(BASE, "bot.py"), "--instance", name],
        stdout=lf, stderr=subprocess.STDOUT, cwd=BASE, start_new_session=True)
    with open(pidf, "w") as f:
        f.write(str(p.pid))
    log.info(f"🚀 child spawned: {name} pid={p.pid}")
    return p.pid

def stop_child(name: str):
    try:
        _, pidf, _ = inst_paths(name)
        with open(pidf) as f:
            pid = int(f.read().strip())
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            os.kill(pid, signal.SIGTERM)
        log.info(f"⏹ child stopped: {name}")
    except Exception as e:
        log.warning(f"stop child fail {name}: {e}")

def respawn_children():
    if DEPTH != 0:
        return
    for ch in list(DATA.get("child_bots", [])):
        if ch.get("on", True) and not child_alive(ch.get("name", "")):
            try:
                spawn_child(ch["name"])
            except Exception as e:
                log.warning(f"respawn fail {ch.get('name')}: {e}")

def my_bots_panel():
    kids = DATA.get("child_bots", [])
    if not kids:
        return ("🤖 <b>بات‌های من</b>\n\nهنوز باتی نساختی!\n"
                "از دکمه «🤖 بات ناشناس جدید» شروع کن 👇"), None
    lines = ["🤖 <b>بات‌های ناشناس من</b>\n"]
    kb = []
    for i, ch in enumerate(kids):
        alive = ch.get("on", True) and child_alive(ch.get("name", ""))
        lines.append(f"{i + 1}. @{ch.get('name', '?')} — {'🟢 روشن' if alive else '🔴 خاموش'}\n"
                     f"   👤 مدیر: <code>{ch.get('admin', '—')}</code> | 📅 {ch.get('added', '—')}")
        if alive:
            kb.append([InlineKeyboardButton("⏹ خاموش کردن", callback_data=f"cb_stop:{i}")])
        else:
            kb.append([InlineKeyboardButton("▶️ روشن کردن", callback_data=f"cb_start:{i}"),
                       InlineKeyboardButton("🗑 حذف", callback_data=f"cb_del:{i}")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)

# ---------------- commands ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.effective_chat or update.effective_chat.type != Chat.PRIVATE:
        return
    if is_admin(u.id):
        STATES.pop(ADMIN_ID, None)
        if u.first_name and DATA.get("admin_name") != u.first_name:
            DATA["admin_name"] = u.first_name
            save_data()
        await update.message.reply_text(
            "👋 <b>سلام رئیس!</b> خوش برگشتی 😎\nپنل ادمین آماده‌ست، از دکمه‌های پایین استفاده کن 👇",
            parse_mode=ParseMode.HTML, reply_markup=panel_kb())
        return
    add_user(u)
    STATES.pop(u.id, None)
    if not DATA["bot_on"]:
        await update.message.reply_text(OFF_TEXT)
        return
    if DATA["fj_on"] and not await check_membership(context, u.id):
        await update.message.reply_text(LOCK_TEXT, parse_mode=ParseMode.HTML,
                                        reply_markup=build_lock_kb())
        return
    # ✨ ورود با لینک ناشناس اختصاصی (Deep Link)
    _args = context.args or []
    if _args and isinstance(_args[0], str) and len(_args[0]) >= 8:
        await handle_link_entry(update, context, u, _args[0].strip())
        return
    await send_welcome(context, update.effective_chat)

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u:
        return
    if get_role(u.id) == "admin":
        STATES.pop(ADMIN_ID, None)
        await update.message.reply_text("🎛 <b>پنل ادمین</b> 👇", parse_mode=ParseMode.HTML,
                                        reply_markup=panel_kb())
    else:
        await handle_my_panel(update, context, u)

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u:
        return
    if is_admin(u.id):
        STATES.pop(ADMIN_ID, None)
        await update.message.reply_text("❌ لغو شد! برگشتی به پنل ✅", reply_markup=panel_kb())

# ---------------- messages ----------------
async def on_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, u):
    msg = update.message
    chat_id = update.effective_chat.id
    add_user(u)
    if not DATA["bot_on"]:
        await msg.reply_text(OFF_TEXT)
        return
    if u.id in DATA["blocked"]:
        await msg.reply_text(BLOCKED_TEXT)
        return
    if DATA["fj_on"] and not await check_membership(context, u.id):
        await msg.reply_text(LOCK_TEXT, parse_mode=ParseMode.HTML, reply_markup=build_lock_kb())
        return

    # ✨ دکمه‌های جدید کاربر (دریافت ناشناس من / پنل مدیریت)
    _text = (msg.text or "").strip()
    if _text == BTN_MY_LINK:
        STATES.pop(u.id, None)
        await handle_my_link(update, context, u)
        return
    if _text == BTN_MY_PANEL:
        STATES.pop(u.id, None)
        await handle_my_panel(update, context, u)
        return
    if rate_limited(u.id):
        await msg.reply_text(RATE_TEXT)
        return

    uname = ("@" + u.username) if u.username else ""
    today_str = date_str()
    uinfo0 = DATA["users"].get(str(u.id), {})
    kb = sender_kb(u.first_name or "—", u.id, uname, u.id in DATA["blocked"], today_str,
                   uinfo0.get("msgs", 0) + 1)

    # 🔗 اگه کاربر روی دکمه «پاسخ» زده یا به پیام مدیر ریپلای داده → جواب همون پیامه
    thread_amid = None
    owner_target = None
    owner_thread_ref = None
    st_u = STATES.get(u.id)
    if st_u and st_u.get("mode") == "ureply":
        thread_amid = st_u.get("amid")
        STATES.pop(u.id, None)
    elif st_u and st_u.get("mode") == "ureply_owner":
        owner_target = int(st_u.get("owner") or 0)
        owner_thread_ref = st_u.get("ref")
        STATES.pop(u.id, None)
    elif st_u and st_u.get("mode") == "oreply":
        await do_owner_reply(update, context, u, st_u.get("key") or "")
        return
    elif msg.reply_to_message:
        thread_amid = DATA.get("dst_map", {}).get(str(msg.reply_to_message.message_id))
    if owner_target is None and thread_amid is None:
        _pt = DATA.get("pending_target", {}).get(str(u.id))
        if _pt:
            owner_target = int(_pt)

    # ✨ مسیر جدید: پیام ناشناس برای صاحب لینک
    if owner_target:
        await send_to_owner(update, context, u, owner_target, owner_thread_ref)
        return

    try:
        await send(context, ADMIN_ID, NEW_MSG_HEADER)
    except Exception:
        pass

    admin_mid = None
    try:
        if thread_amid:
            try:
                res = await context.bot.copy_message(ADMIN_ID, chat_id, msg.message_id,
                                                     reply_markup=kb,
                                                     reply_to_message_id=thread_amid)
            except Exception:
                res = await context.bot.copy_message(ADMIN_ID, chat_id, msg.message_id, reply_markup=kb)
        else:
            res = await context.bot.copy_message(ADMIN_ID, chat_id, msg.message_id, reply_markup=kb)
        admin_mid = res.message_id
    except Exception as e:
        log.warning(f"copy to admin failed: {e}")
        try:
            fwd = await context.bot.forward_message(ADMIN_ID, chat_id, msg.message_id)
            admin_mid = fwd.message_id
            await send(context, ADMIN_ID, "ℹ️ <b>اطلاعات فرستنده:</b>", reply_markup=kb)
        except Exception as e2:
            log.error(f"forward to admin failed: {e2}")
            return

    sm = DATA.setdefault("src_map", {})
    sm[str(admin_mid)] = {"chat": chat_id, "mid": msg.message_id, "date": today_str}
    if len(sm) > 500:
        for k in list(sm.keys())[: len(sm) - 500]:
            sm.pop(k, None)

    # 📊 آمار
    today = datetime.now(TEHRAN).strftime("%Y-%m-%d")
    sts = DATA.setdefault("stats", {"total": 0, "today": 0, "day": today})
    if sts.get("day") != today:
        sts["day"] = today
        sts["today"] = 0
    sts["total"] = sts.get("total", 0) + 1
    sts["today"] = sts.get("today", 0) + 1
    uinfo = DATA["users"].get(str(u.id))
    if uinfo:
        uinfo["msgs"] = uinfo.get("msgs", 0) + 1
        uinfo["last_msg"] = jdate_only()
    save_data()

    await msg.reply_text(RECEIVED_TEXT)

async def do_broadcast(context, msg):
    users = [int(k) for k in DATA["users"].keys() if int(k) != ADMIN_ID]
    blocked_count = sum(1 for uid in users if uid in DATA["blocked"])
    users = [uid for uid in users if uid not in DATA["blocked"]]
    st_msg = await msg.reply_text(f"⏳ در حال ارسال به {len(users)} کاربر...")
    ok = fail = 0
    for uid in users:
        try:
            await context.bot.copy_message(uid, msg.chat_id, msg.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    try:
        await st_msg.edit_text(
            f"📢 <b>پیام همگانی تمام شد!</b>\n\n"
            f"✅ ارسال موفق: {ok}\n❌ ناموفق: {fail}\n🚫 بلاک‌شده: {blocked_count}\n👥 کل: {ok + fail + blocked_count}",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass

async def handle_set_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, mode: str):
    kind = "چنل" if mode in ("fj_c", "fc") else "گروه"
    chat = await resolve_chat(context, msg)
    if chat is None:
        await msg.reply_text("⚠️ متوجه نشدم! یا یه پیام از " + kind + " فوروارد کن، یا @username یا آیدی عددیش رو بفرست 🙏")
        return
    if mode in ("fj_c", "fc") and chat.type != Chat.CHANNEL:
        await msg.reply_text("⚠️ این چنل نیست! یه چنل معرفی کن 🙏")
        return
    if mode == "fj_g" and chat.type not in (Chat.GROUP, Chat.SUPERGROUP):
        await msg.reply_text("⚠️ این گروه نیست! یه گروه معرفی کن 🙏")
        return

    if mode == "fc":
        entry = chat_entry(chat)
        warn = ""
        try:
            m = await context.bot.get_chat_member(chat.id, BOT_INFO["id"])
            if m.status != "administrator":
                warn = f"\n\n⚠️ ربات ادمین این {kind} نیست! اول ربات رو ادمین کن تا فوروارد کار کنه 🙏"
        except Exception:
            warn = f"\n\n⚠️ ربات به این {kind} دسترسی نداره! اول ربات رو ادمین کن 🙏"
        DATA["fwd_channel"] = entry
        STATES.pop(ADMIN_ID, None)
        save_data()
        t, kb = fc_panel()
        await msg.reply_text(f"✅ <b>چنل فوروارد ثبت شد:</b> {html.escape(entry['title'])}{warn}",
                             parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if len(DATA["fj_channels"]) + len(DATA["fj_groups"]) >= 10:
        STATES.pop(ADMIN_ID, None)
        await msg.reply_text("⚠️ ظرفیت پر شده! حداکثر ۱۰ چنل/گروه می‌تونی تنظیم کنی 🙏")
        return
    lst = DATA["fj_channels"] if mode == "fj_c" else DATA["fj_groups"]
    if any(c["id"] == chat.id for c in lst):
        STATES.pop(ADMIN_ID, None)
        await msg.reply_text("⚠️ این قبلاً ثبت شده! تکراریه 😅")
        return

    entry = chat_entry(chat)
    if not entry["link"]:
        try:
            inv = await context.bot.create_chat_invite_link(chat.id)
            entry["link"] = inv.invite_link
        except Exception:
            pass
    warn = ""
    try:
        m = await context.bot.get_chat_member(chat.id, BOT_INFO["id"])
        if m.status != "administrator":
            warn = f"\n\n⚠️ ربات ادمین این {kind} نیست! اول ادمینش کن تا چک عضویت درست کار کنه 🙏"
    except Exception:
        warn = f"\n\n⚠️ ربات به این {kind} دسترسی نداره! اول ربات رو ادمین کن 🙏"
    lst.append(entry)
    STATES.pop(ADMIN_ID, None)
    save_data()
    if not entry["link"]:
        warn += "\n⚠️ این " + kind + " لینک نداره؛ ربات باید دسترسی «دعوت کاربران» داشته باشه تا دکمه عضویت ساخته بشه!"
    t, kb = fj_panel()
    await msg.reply_text(f"✅ <b>{kind} ثبت شد:</b> {html.escape(entry['title'])}{warn}",
                         parse_mode=ParseMode.HTML, reply_markup=kb)

async def on_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    u = update.effective_user
    if u and u.first_name and DATA.get("admin_name") != u.first_name:
        DATA["admin_name"] = u.first_name
        save_data()
    text = (msg.text or "").strip()

    if text == BTN_BROADCAST:
        n = sum(1 for k in DATA["users"] if int(k) != ADMIN_ID and int(k) not in DATA["blocked"])
        STATES[ADMIN_ID] = {"mode": "broadcast"}
        await msg.reply_text(
            f"📢 <b>پیام همگانی</b>\n\nپیامت رو بفرست تا برای <b>{n}</b> کاربر ارسال بشه\n"
            "(متن، عکس، ویدیو، فایل... هر چی ✅)",
            parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
        return
    if text == BTN_FJ:
        STATES.pop(ADMIN_ID, None)
        t, kb = fj_panel()
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_FC:
        STATES.pop(ADMIN_ID, None)
        t, kb = fc_panel()
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_POWER:
        DATA["bot_on"] = not DATA["bot_on"]
        save_data()
        if DATA["bot_on"]:
            await msg.reply_text("🟢 <b>ربات روشن شد!</b> پیام‌های کاربران دریافت میشه ✅",
                                 parse_mode=ParseMode.HTML)
        else:
            await msg.reply_text("🔴 <b>ربات خاموش شد!</b> کاربران فعلاً نمی‌تونن پیام بدن ⛔",
                                 parse_mode=ParseMode.HTML)
        return
    if text == BTN_STATS:
        STATES.pop(ADMIN_ID, None)
        t, kb = users_list_panel(0)
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_NEWBOT and DEPTH == 0:
        STATES[ADMIN_ID] = {"mode": "nb_tok"}
        await msg.reply_text(
            "🤖 <b>بات ناشناس جدید</b>\n\n"
            "توکن ربات جدید رو بفرست (از @BotFather بگیر):\n"
            "<code>123456789:AAHxxxxxxxxxxxxxxxxxxxxxxx</code>",
            parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
        return
    if text == BTN_MYBOTS and DEPTH == 0:
        STATES.pop(ADMIN_ID, None)
        t, kb = my_bots_panel()
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_VIP:
        STATES.pop(ADMIN_ID, None)
        t, kb = vip_panel()
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_SYS_STATS:
        STATES.pop(ADMIN_ID, None)
        t, kb = admin_stats_panel()
        await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if text == BTN_MY_PANEL:
        STATES.pop(ADMIN_ID, None)
        await msg.reply_text("🎛 <b>پنل ادمین</b> 👇", parse_mode=ParseMode.HTML,
                             reply_markup=panel_kb())
        return
    if text == BTN_MY_LINK:
        await msg.reply_text("ℹ️ رئیس، همه پیام‌ها خودکار برای تو میاد؛ لینک ناشناس مخصوص کاربرانinale!")
        return
    if text == "/cancel":
        STATES.pop(ADMIN_ID, None)
        await msg.reply_text("❌ لغو شد! برگشتی به پنل ✅", reply_markup=panel_kb())
        return

    st = STATES.get(ADMIN_ID)
    if st:
        mode = st.get("mode")
        if mode == "broadcast":
            STATES.pop(ADMIN_ID, None)
            await do_broadcast(context, msg)
            return
        if mode == "reply":
            STATES.pop(ADMIN_ID, None)
            uid = st["uid"]
            src_mid = st.get("src_mid")
            try:
                # ۱) پیام اول: اعلان جواب
                await send(context, uid, f"💬 <b>{admin_display()}</b> جواب داد :")
                # ۲) پیام دوم: خود پیام — ریپلای روی پیام اصلی کاربر + دکمه پاسخ
                try:
                    c = await context.bot.copy_message(uid, msg.chat_id, msg.message_id,
                                                       reply_to_message_id=src_mid,
                                                       reply_markup=user_reply_kb(msg.message_id))
                except Exception:
                    c = await context.bot.copy_message(uid, msg.chat_id, msg.message_id,
                                                       reply_markup=user_reply_kb(msg.message_id))
                dm = DATA.setdefault("dst_map", {})
                dm[str(c.message_id)] = msg.message_id
                if len(dm) > 500:
                    for k in list(dm.keys())[: len(dm) - 500]:
                        dm.pop(k, None)
                save_data()
                conf = await msg.reply_text("✅ پیام ارسال شد 🕊️", reply_markup=conf_kb(uid))
                save_last_reply(uid, {"chat": uid, "mid": c.message_id,
                                      "kind": "text" if msg.text else "media",
                                      "prefix": "", "conf": conf.message_id})
            except Exception:
                await msg.reply_text("⚠️ ارسال نشد! احتمالاً کاربر ربات رو بلاک کرده 😕")
            return
        if mode == "send_to":
            STATES.pop(ADMIN_ID, None)
            uid = st["uid"]
            try:
                if msg.text:
                    s = await context.bot.send_message(
                        uid, "📩 <b>پیام جدید از مدیر ربات برای شما</b> 🎁\n\n" + html.escape(msg.text),
                        parse_mode=ParseMode.HTML, reply_markup=user_reply_kb(msg.message_id))
                    rec = {"chat": uid, "mid": s.message_id, "kind": "text",
                           "prefix": "📩 پیام جدید از مدیر ربات برای شما 🎁\n\n"}
                else:
                    await context.bot.send_message(uid, "📩 <b>پیام جدید از مدیر ربات برای شما</b> 🎁",
                                                   parse_mode=ParseMode.HTML)
                    c = await context.bot.copy_message(uid, msg.chat_id, msg.message_id,
                                                       reply_markup=user_reply_kb(msg.message_id))
                    rec = {"chat": uid, "mid": c.message_id, "kind": "media", "prefix": ""}
                dm = DATA.setdefault("dst_map", {})
                dm[str(rec["mid"])] = msg.message_id
                if len(dm) > 500:
                    for k in list(dm.keys())[: len(dm) - 500]:
                        dm.pop(k, None)
                save_data()
                conf = await msg.reply_text("✅ پیام برای کاربر ارسال شد 🕊️", reply_markup=conf_kb(uid))
                rec["conf"] = conf.message_id
                save_last_reply(uid, rec)
            except Exception:
                await msg.reply_text("⚠️ ارسال نشد! احتمالاً کاربر ربات رو بلاک کرده 😕")
            return
        if mode == "edit_reply":
            STATES.pop(ADMIN_ID, None)
            uid = st["uid"]
            rec = DATA.get("last_reply", {}).get(str(uid))
            if not rec:
                await msg.reply_text("⚠️ پیامی برای ویرایش پیدا نشد!")
                return
            chat, mid = rec["chat"], rec["mid"]
            kind, prefix = rec.get("kind", "text"), rec.get("prefix", "")
            ok = False
            if msg.text:
                try:
                    if kind == "text":
                        await context.bot.edit_message_text(prefix + html.escape(msg.text),
                                                            chat_id=chat, message_id=mid,
                                                            parse_mode=ParseMode.HTML)
                    else:
                        await context.bot.edit_message_caption(chat_id=chat, message_id=mid,
                                                               caption=html.escape(msg.text),
                                                               parse_mode=ParseMode.HTML)
                    ok = True
                except Exception as e:
                    log.warning(f"edit failed: {e}")
            if not ok:
                try:
                    await context.bot.delete_message(chat, mid)
                except Exception:
                    pass
                try:
                    if msg.text:
                        s = await context.bot.send_message(chat, prefix + html.escape(msg.text),
                                                           parse_mode=ParseMode.HTML)
                        rec.update({"mid": s.message_id, "kind": "text"})
                    else:
                        s = await context.bot.copy_message(chat, msg.chat_id, msg.message_id)
                        rec.update({"mid": s.message_id, "kind": "media"})
                    ok = True
                except Exception as e:
                    log.warning(f"edit resend failed: {e}")
                    await msg.reply_text("⚠️ ویرایش نشد! 😕")
            if ok:
                save_data()
                try:
                    await context.bot.edit_message_text("✅ پیام شما ویرایش شد ✏️", chat_id=ADMIN_ID,
                                                        message_id=rec.get("conf", 0),
                                                        reply_markup=conf_kb(uid))
                except Exception:
                    await msg.reply_text("✅ پیام شما ویرایش شد ✏️")
            return
        if mode == "search_user":
            STATES.pop(ADMIN_ID, None)
            q = (msg.text or "").strip()
            if not q:
                await msg.reply_text("⚠️ یه متن بفرست تا جستجو کنم!")
                return
            res = search_users(q)
            if not res:
                await msg.reply_text(f"😕 هیچ کاربری برای «{html.escape(q)}» پیدا نشد!")
            elif len(res) == 1:
                t, kb = user_info_panel(int(res[0]), 0)
                await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                t, kb = search_results_panel(q, res)
                await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if mode == "vip_add":
            if not re.fullmatch(r"\d{4,13}", text):
                await msg.reply_text("⚠️ آیدی عددی معتبر نیست! فقط رقم بفرست (مثل <code>123456789</code>)",
                                     parse_mode=ParseMode.HTML)
                return
            vid = int(text)
            if vid == BOT_INFO["id"]:
                await msg.reply_text("⚠️ این آیدی خودِ رباته! آیدی کاربر رو بفرست 🙏")
                return
            if vid in DATA["vip"]:
                STATES.pop(ADMIN_ID, None)
                await msg.reply_text("ℹ️ این کاربر از قبل VIP هست! چیزی تغییر نکرد.")
                return
            DATA.setdefault("vip", []).append(vid)
            known = str(vid) in DATA["users"]
            if known:
                DATA["users"][str(vid)]["vip_since"] = jdate_only()
            STATES.pop(ADMIN_ID, None)
            save_data()
            log.info(f"💎 VIP added: {vid}")
            note = "" if known else ("\n\nℹ️ این کاربر هنوز ربات رو استارت نکرده؛ "
                                     "به محض اولین استارت، VIP میشه.")
            t, kb = vip_info_panel(vid)
            await msg.reply_text(f"✅ <b>کاربر <code>{vid}</code> به VIP اضافه شد!</b> 💎{note}",
                                 parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if mode == "vip_search":
            STATES.pop(ADMIN_ID, None)
            q = (msg.text or "").strip()
            if not q:
                await msg.reply_text("⚠️ آیدی عددی، یوزرنیم یا اسم کاربر رو بفرست!")
                return
            if re.fullmatch(r"\d{4,13}", q):
                vid = int(q)
                if vid in DATA.get("vip", []):
                    t, kb = vip_info_panel(vid)
                    await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
                    return
                await msg.reply_text(f"😕 کاربر <code>{html.escape(q)}</code> توی لیست VIP نیست!",
                                     parse_mode=ParseMode.HTML)
                return
            res = [r for r in search_users(q) if int(r) in DATA.get("vip", [])]
            if not res:
                await msg.reply_text(f"😕 هیچ VIP ای برای «{html.escape(q)}» پیدا نشد!")
                return
            t, kb = vip_info_panel(int(res[0]))
            await msg.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if mode == "oreply":
            await do_owner_reply(update, context, u, st.get("key") or "")
            return
        if mode == "nb_tok":
            tok = text.strip()
            if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,}", tok):
                await msg.reply_text(
                    "⚠️ این شکل توکن معتبر نیست!\nتوکن از @BotFather این شکلیه:\n"
                    "<code>123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxx</code>\n\nدوباره بفرست 🙏",
                    parse_mode=ParseMode.HTML)
                return
            wait = await msg.reply_text("⏳ دارم توکن رو چک می‌کنم...")
            me = await asyncio.to_thread(tg_getme, tok)
            if not me:
                await wait.edit_text("⚠️ تلگرام این توکن رو قبول نکرد! از @BotFather چک کن و دوباره بفرست 🙏")
                return
            STATES[ADMIN_ID] = {"mode": "nb_adm", "token": tok, "bot": me}
            await wait.edit_text(
                f"✅ توکن معتبره: <b>@{me.get('username')}</b>\n\n"
                "حالا <b>آیدی عددی مدیر جدید</b> رو بفرست:\n"
                "(مثل <code>123456789</code>)",
                parse_mode=ParseMode.HTML)
            return
        if mode == "nb_adm":
            if not re.fullmatch(r"\d{4,13}", text):
                await msg.reply_text("⚠️ آیدی عددی معتبر نیست! فقط رقم بفرست (مثل <code>123456789</code>)",
                                     parse_mode=ParseMode.HTML)
                return
            kids = DATA.setdefault("child_bots", [])
            if len(kids) >= CHILD_MAX:
                STATES.pop(ADMIN_ID, None)
                await msg.reply_text(f"⚠️ ظرفیت پره! حداکثر {CHILD_MAX} بات همزمان می‌تونی داشته باشی 🙏")
                return
            aid = int(text)
            me, tok = st["bot"], st["token"]
            name = me.get("username") or f"bot{me.get('id')}"
            for ch in kids:
                if ch.get("name") == name:
                    ch.update({"token": tok, "admin": aid, "on": True})
                    break
            else:
                kids.append({"name": name, "title": me.get("first_name") or name,
                             "token": tok, "admin": aid, "on": True, "added": jdate_only()})
            d, _, _ = inst_paths(name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"token": tok, "admin_id": aid, "depth": 1}, f, ensure_ascii=False, indent=1)
            if child_alive(name):
                stop_child(name)
                await asyncio.sleep(1.5)
            spawn_child(name)
            STATES.pop(ADMIN_ID, None)
            save_data()
            await msg.reply_text(
                "🎉 <b>بات ناشناس جدید راه افتاد!</b>\n\n"
                f"🤖 ربات: @{name}\n"
                f"👤 مدیر جدید: <code>{aid}</code>\n"
                "📊 وضعیت: 🟢 در حال اجرا\n\n"
                "ℹ️ پیام‌های این ربات فقط برای مدیر جدیدش میاد، نه تو 😎\n"
                "⚠️ مدیر جدید باید اول یه بار /start بزنه!\n"
                "🛠 مدیریتش از دکمه «📋 بات‌های من»",
                parse_mode=ParseMode.HTML)
            return
        if mode in ("fj_c", "fj_g", "fc"):
            await handle_set_chat(update, context, msg, mode)
            return

    await msg.reply_text("🎛 رئیس، از دکمه‌های پایین استفاده کن 👇", reply_markup=panel_kb())

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    u = update.effective_user
    if not msg or not u or u.is_bot:
        return
    if is_admin(u.id):
        await on_admin_message(update, context)
    else:
        await on_user_message(update, context, u)

# ---------------- callbacks ----------------
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    if not cq:
        return
    data = cq.data or ""
    try:
        if data == "noop":
            await cq.answer("ℹ️")
            return

        if data == "joined":
            uid = cq.from_user.id
            if await check_membership(context, uid):
                try:
                    await cq.message.delete()
                except Exception:
                    pass
                await cq.answer("✅ عضویت تأیید شد!")
                await send_welcome(context, cq.message.chat)
            else:
                await cq.answer()
                await send(context, uid, NOT_MEMBER_TEXT)
            return

        # ✨ دکمه‌های کاربران (غیرادمینی) — همه با چک گیرنده/مالک در بک‌اند
        if data.startswith("rpo:"):
            # صاحب لینک روی «پاسخ» پیام ناشناس زده → فقط خود صاحب لینک
            key = data.split(":", 1)[1]
            ent = DATA.get("osrc_map", {}).get(key)
            if not ent:
                await cq.answer("⚠️ این پیام دیگه در دسترس نیست!", show_alert=True)
                return
            if ent.get("owner") != cq.from_user.id:
                await cq.answer("⛔ فقط گیرنده‌ی پیام!", show_alert=True)
                return
            STATES[cq.from_user.id] = {"mode": "oreply", "key": key}
            await cq.answer()
            await send(context, cq.from_user.id,
                       "✍️ <b>پاسخ ناشناس</b>\n\nپیامت رو بفرست تا دقیقاً جواب همون پیام ارسال شه 🕊️",
                       reply_markup=cancel_kb())
            return

        if data.startswith("rpuo:"):
            # فرستنده روی «پاسخ» زیر جواب صاحب لینک زده → فقط خودش
            _p = data.split(":")
            if len(_p) < 3:
                await cq.answer("⚠️")
                return
            ref_mid = int(_p[1])
            key = _p[2]
            rq = cq.from_user.id
            if cq.message.chat.id != rq:
                await cq.answer("⛔ فقط گیرنده‌ی پیام!", show_alert=True)
                return
            ent = DATA.get("osrc_map", {}).get(key)
            if not ent:
                await cq.answer("⚠️ این گفتگو دیگه در دسترس نیست!", show_alert=True)
                return
            STATES[rq] = {"mode": "ureply_owner", "owner": ent["owner"], "ref": ref_mid}
            await cq.answer()
            await send(context, rq,
                       "💬 <b>جوابِ همون پیام رو بنویس!</b>\n\n"
                       "پیامت ناشناس می‌ره و دقیقاً جواب همون پیام می‌شینه 📩")
            return

        if data.startswith("rpu:"):
            # کاربر روی دکمه «پاسخ» زیر پیام مدیر زده → پیام بعدیش جواب همون پیامه
            try:
                amid = int(data.split(":")[1])
            except Exception:
                await cq.answer("⚠️")
                return
            rq = cq.from_user.id
            if cq.message.chat.id != rq:
                await cq.answer("⛔ فقط گیرنده‌ی پیام!", show_alert=True)
                return
            STATES[rq] = {"mode": "ureply", "amid": amid}
            await cq.answer()
            await send(context, rq,
                       "💬 <b>جوابِ همون پیام رو بنویس!</b>\n\n"
                       "پیامت رو بفرست، دقیقاً به‌عنوان جواب همون پیام مدیر ارسال میشه 📩")
            return

        # بقیه دکمه‌ها فقط برای ادمین
        if not is_admin(cq.from_user.id):
            await cq.answer("⛔ فقط ادمین!", show_alert=True)
            return

        if data == "cancel_state":
            STATES.pop(ADMIN_ID, None)
            await cq.answer("❌ لغو شد")
            try:
                await cq.edit_message_text("❌ لغو شد ✅")
            except Exception:
                pass

        elif data.startswith("reply:"):
            uid = int(data.split(":")[1])
            entry = DATA.get("src_map", {}).get(str(cq.message.message_id), {})
            STATES[ADMIN_ID] = {"mode": "reply", "uid": uid, "src_mid": entry.get("mid")}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "✍️ <b>پاسخ به کاربر</b>\n\nپیامت رو بفرست تا ناشناس براش ارسال شه 🕊️",
                       reply_markup=cancel_kb())

        elif data.startswith("block:"):
            uid = int(data.split(":")[1])
            if uid in DATA["blocked"]:
                DATA["blocked"].remove(uid)
                atxt = "✅ محرومیت کاربر لغو شد 🕊️"
            else:
                DATA["blocked"].append(uid)
                atxt = "⛔ کاربر بلاک شد! دیگه نمی‌تونه پیام بده"
            save_data()
            entry = DATA.get("src_map", {}).get(str(cq.message.message_id), {})
            u = DATA["users"].get(str(uid), {})
            try:
                await cq.edit_message_reply_markup(reply_markup=sender_kb(
                    u.get("name") or "—", uid, u.get("username") or "",
                    uid in DATA["blocked"], entry.get("date"), u.get("msgs", 0)))
            except Exception:
                pass
            await cq.answer(atxt)

        elif data == "fwd":
            fc = DATA["fwd_channel"]
            if not fc:
                await cq.answer("⚠️ اول از پنل (📤 چنل فوروارد) چنل رو تنظیم کن!", show_alert=True)
                return
            entry = DATA.get("src_map", {}).get(str(cq.message.message_id))
            try:
                if entry:
                    # فوروارد واقعی از کپی ربات (ناشناس، بدون دکمه)
                    await context.bot.forward_message(fc["id"], ADMIN_ID, cq.message.message_id)
                else:
                    await context.bot.copy_message(fc["id"], cq.message.chat_id, cq.message.message_id)
                await cq.answer("✅ پیام به چنل فوروارد شد!")
            except Exception as e:
                log.warning(f"manual fwd fail: {e}")
                await cq.answer("⚠️ ارسال نشد! مطمئن شو ربات در چنل ادمینه 🙏", show_alert=True)

        elif data.startswith("redit:"):
            uid = int(data.split(":")[1])
            if not DATA.get("last_reply", {}).get(str(uid)):
                await cq.answer("⚠️ این پیام دیگه موجود نیست!", show_alert=True)
                return
            STATES[ADMIN_ID] = {"mode": "edit_reply", "uid": uid}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "✏️ <b>ویرایش پیام</b>\n\nپیام جدید رو بفرست تا جای قبلی بشینه:\n"
                       "📝 متن بفرستی → ویرایش همون پیام\n"
                       "🖼 عکس/ویدیو بفرستی → قبلی حذف و جدید ارسال میشه",
                       reply_markup=cancel_kb())

        elif data.startswith("rdel:"):
            uid = int(data.split(":")[1])
            rec = DATA.get("last_reply", {}).get(str(uid))
            if not rec:
                await cq.answer("⚠️ این پیام دیگه موجود نیست!", show_alert=True)
                return
            try:
                await context.bot.delete_message(rec["chat"], rec["mid"])
                DATA.get("last_reply", {}).pop(str(uid), None)
                save_data()
                await cq.edit_message_text("🗑 پیام حذف شد ✅")
                await cq.answer()
            except Exception:
                await cq.answer("⚠️ حذف نشد! احتمالاً قبلاً حذف شده", show_alert=True)

        elif data.startswith("stats:"):
            page = int(data.split(":")[1])
            t, kb = users_list_panel(page)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data.startswith("uinfo:"):
            parts = data.split(":")
            uid = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 0
            t, kb = user_info_panel(uid, page)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data.startswith("uback:"):
            page = int(data.split(":")[1])
            t, kb = users_list_panel(page)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data == "back_panel":
            await cq.edit_message_text("✅ برگشتی به پنل ادمین!\nاز دکمه‌های پایین کیبورد استفاده کن 👇")
            await cq.answer()

        elif data.startswith("usend:"):
            uid = int(data.split(":")[1])
            STATES[ADMIN_ID] = {"mode": "send_to", "uid": uid}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "✍️ <b>ارسال پیام به کاربر</b>\n\nپیامت رو بفرست تا با عنوان "
                       "«📩 پیام جدید از مدیر ربات» براش ارسال شه 📨",
                       reply_markup=cancel_kb())

        elif data.startswith("ublock:"):
            parts = data.split(":")
            uid = int(parts[1])
            page = int(parts[2]) if len(parts) > 2 else 0
            if uid in DATA["blocked"]:
                DATA["blocked"].remove(uid)
                atxt = "✅ محرومیت کاربر لغو شد 🕊️"
            else:
                DATA["blocked"].append(uid)
                atxt = "⛔ کاربر بلاک شد!"
            save_data()
            t, kb = user_info_panel(uid, page)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer(atxt)

        elif data == "usearch":
            STATES[ADMIN_ID] = {"mode": "search_user"}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "🔍 <b>جستجو کاربر</b>\n\nاسم، آیدی عددی یا یوزرنیم کاربر رو بفرست:",
                       reply_markup=cancel_kb())

        elif data.startswith(("cb_start:", "cb_stop:", "cb_del:")):
            act, _, si = data.partition(":")
            idx = int(si)
            kids = DATA.get("child_bots", [])
            if not (0 <= idx < len(kids)):
                await cq.answer("⚠️ پیدا نشد!", show_alert=True)
                return
            ch = kids[idx]
            if act == "cb_start":
                if not child_alive(ch.get("name", "")):
                    spawn_child(ch["name"])
                ch["on"] = True
                save_data()
                await cq.answer("✅ ربات روشن شد")
            elif act == "cb_stop":
                stop_child(ch.get("name", ""))
                ch["on"] = False
                save_data()
                await cq.answer("⏹ ربات خاموش شد")
            else:
                stop_child(ch.get("name", ""))
                kids.pop(idx)
                save_data()
                await cq.answer("🗑 حذف شد")
            t, kb = my_bots_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)

        elif data == "fj_toggle":
            DATA["fj_on"] = not DATA["fj_on"]
            save_data()
            t, kb = fj_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer("✅ ذخیره شد")

        elif data in ("fj_set:c", "fj_set:g"):
            kind = "c" if data.endswith(":c") else "g"
            if len(DATA["fj_channels"]) + len(DATA["fj_groups"]) >= 10:
                await cq.answer("⚠️ حداکثر ۱۰ چنل/گروه می‌تونی تنظیم کنی!", show_alert=True)
                return
            STATES[ADMIN_ID] = {"mode": "fj_" + kind}
            await cq.answer()
            await send(context, ADMIN_ID, FJ_PROMPT_C if kind == "c" else FJ_PROMPT_G,
                       reply_markup=cancel_kb())

        elif data == "fj_botadmin":
            await cq.answer()
            await send(context, ADMIN_ID,
                       "🤖 <b>ادمین کردن ربات</b>\n\n"
                       f"آیدی عددی ربات:\n<code>{BOT_INFO['id']}</code>\n\n"
                       "1️⃣ ربات رو در چنل/گروه ادمین کن 👨‍💼\n"
                       "2️⃣ این دسترسی‌ها رو بده:\n"
                       "   ✅ ارسال پیام\n"
                       "   ✅ دعوت کاربران (برای ساخت لینک)\n"
                       "   ✅ مدیریت اعضا (برای چک عضویت)\n"
                       "3️⃣ بعدش برگرد و چنل/گروه رو ثبت کن ✅")

        elif data == "fj_list":
            t, kb = fj_list_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data.startswith("fj_del:"):
            _, kind, sid = data.split(":")
            cid = int(sid)
            if kind == "c":
                DATA["fj_channels"] = [c for c in DATA["fj_channels"] if c["id"] != cid]
            else:
                DATA["fj_groups"] = [g for g in DATA["fj_groups"] if g["id"] != cid]
            save_data()
            t, kb = fj_list_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer("🗑 حذف شد")

        elif data == "fj_back":
            t, kb = fj_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data == "fc_set":
            STATES[ADMIN_ID] = {"mode": "fc"}
            await cq.answer()
            await send(context, ADMIN_ID, FC_PROMPT, reply_markup=cancel_kb())

        elif data == "fc_del":
            DATA["fwd_channel"] = None
            save_data()
            t, kb = fc_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer("🗑 حذف شد")

        elif data == "vip_add":
            STATES[ADMIN_ID] = {"mode": "vip_add"}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "💎 <b>افزودن کاربر VIP</b>\n\n"
                       "لطفاً <b>آیدی عددی</b> کاربر رو بفرست:\n"
                       "(مثل <code>123456789</code>)",
                       parse_mode=ParseMode.HTML, reply_markup=cancel_kb())

        elif data == "vip_list" or data.startswith("vip_page:"):
            page = int(data.split(":")[1]) if ":" in data else 0
            t, kb = vip_list_panel(page)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data == "vip_search":
            STATES[ADMIN_ID] = {"mode": "vip_search"}
            await cq.answer()
            await send(context, ADMIN_ID,
                       "🔍 <b>جستجوی VIP</b>\n\nآیدی عددی، یوزرنیم یا اسم کاربر رو بفرست:",
                       reply_markup=cancel_kb())

        elif data.startswith("vip_del:"):
            try:
                vid = int(data.split(":")[1])
            except Exception:
                await cq.answer("⚠️", show_alert=True)
                return
            if vid in DATA.get("vip", []):
                DATA["vip"].remove(vid)
                save_data()
                log.info(f"💎 VIP removed: {vid}")
                await cq.answer("➖ VIP حذف شد — کاربر و لینک و پیام‌هاش دست‌نخورده موندن ✅")
            else:
                await cq.answer("⚠️ این کاربر VIP نیست!", show_alert=True)
            t, kb = vip_list_panel(0)
            try:
                await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                pass

        elif data.startswith("vip_info:"):
            try:
                vid = int(data.split(":")[1])
            except Exception:
                await cq.answer("⚠️", show_alert=True)
                return
            t, kb = vip_info_panel(vid)
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        elif data == "vip_back":
            t, kb = vip_panel()
            await cq.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            await cq.answer()

        else:
            await cq.answer()
    except Exception:
        log.exception("callback error")
        try:
            await cq.answer("⚠️ خطا! دوباره تلاش کن", show_alert=True)
        except Exception:
            pass

# ---------------- reactions ----------------
async def on_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = update.message_reaction
    if not r or r.chat.id != ADMIN_ID:
        return
    if r.user and r.user.id != ADMIN_ID:
        return
    entry = DATA.get("src_map", {}).get(str(r.message_id))
    if not entry:
        return
    uchat, umid = entry.get("chat"), entry.get("mid")
    new = list(r.new_reaction or [])
    old = list(r.old_reaction or [])
    if new:
        emoji = getattr(new[0], "emoji", None)
        if not emoji:
            return
        try:
            await context.bot.set_message_reaction(uchat, umid,
                                                   reaction=[ReactionTypeEmoji(emoji)])
        except Exception as e:
            log.warning(f"mirror reaction fail: {e}")
        key = emoji.replace("\ufe0f", "")
        txt = REACT_TEXTS.get(key, f"مدیر ربات به پیام شما واکنش داد {emoji}!")
        try:
            await send(context, uchat, f"👑 {txt}",
                       reply_to_message_id=umid, allow_sending_without_reply=True)
        except Exception:
            pass
    elif old:
        try:
            await context.bot.set_message_reaction(uchat, umid, reaction=[])
        except Exception:
            pass

# ---------------- startup ----------------
async def post_init(app: Application):
    me = await app.bot.get_me()
    BOT_INFO.update({"id": me.id, "username": me.username or "", "name": me.first_name or "ربات"})
    log.info(f"✅ bot online: @{BOT_INFO['username']} id={BOT_INFO['id']}")
    # گرفتن اسم ادمین برای پیام خوش‌اومد
    try:
        ac = await app.bot.get_chat(ADMIN_ID)
        nm = ac.first_name or ac.username
        if nm and nm != DATA.get("admin_name"):
            DATA["admin_name"] = nm
            save_data()
            log.info("admin name saved")
    except Exception as e:
        log.info(f"admin name fetch skipped: {getattr(e, 'message', '')}")
    respawn_children()
    app.create_task(heartbeat())

async def heartbeat():
    while True:
        await asyncio.sleep(300)
        log.info("💓 heartbeat")
        try:
            respawn_children()
        except Exception:
            log.exception("respawn_children error")

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("link", cmd_link))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageReactionHandler(on_reaction))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE & ~filters.COMMAND,
                                   on_message))
    log.info("🚀 starting polling...")
    app.run_polling(allowed_updates=["message", "callback_query", "message_reaction"])

if __name__ == "__main__":
    main()
