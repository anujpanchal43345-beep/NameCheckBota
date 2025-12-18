# ========= IMPORTS =========
import re
import random
import datetime
import asyncio
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ========= CONFIG =========
import os
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@NameCheckXHub"
ADMIN_IDS = {7978057547}

DAILY_LIMIT_NAME = 5
DAILY_LIMIT_AI = 3  # Increased daily AI checks by 1

# ========= MEMORY =========
usage_name = {}
usage_ai = {}

analytics = {
    "total_users_name": set(),
    "total_users_ai": set(),
    "users_today_name": set(),
    "users_today_ai": set(),
    "total_checks_name": 0,
    "total_checks_ai": 0,
    "total_shares": 0,
}

# ========= TRENDS =========
trends = {
    "hashtags": [],
    "songs": []
}

SEM = asyncio.Semaphore(10)

# ========= EMOJI PACK =========
EMOJIS = [
    "🔥", "✨", "🎯", "💥", "😎", "🎉", "💫", "🤩", "🎶", "🌟",
    "💖", "⚡", "🎵", "🥳", "🛑", "💎", "🕶️", "🌈", "🎬", "📸"
]

# ========= UTILS =========
def today():
    return datetime.date.today().isoformat()

def reset_usage_name(uid):
    if uid not in usage_name or usage_name[uid]["date"] != today():
        usage_name[uid] = {"date": today(), "count": 0, "bonus": 0, "shared_today": False}

def reset_usage_ai(uid):
    if uid not in usage_ai or usage_ai[uid]["date"] != today():
        usage_ai[uid] = {"date": today(), "count": 0, "bonus": 0, "shared_today": False}

def smart_names(base):
    ideas = [
        f"{base}YT", f"{base}_Official", f"Real{base}",
        f"{base}_X", f"{base}_World", f"{base}_Studio",
        f"{base}_Media", f"{base}_HQ"
    ]
    random.shuffle(ideas)
    return ideas[:6]

async def get_session(context):
    if "session" not in context.bot_data:
        context.bot_data["session"] = aiohttp.ClientSession()
    return context.bot_data["session"]

# ========= YT CHECK =========
async def check_youtube(username, context):
    async with SEM:
        session = await get_session(context)
        try:
            async with session.get(f"https://www.youtube.com/@{username}", timeout=6) as r:
                return r.status == 404
        except:
            return False

# ========= DAILY LIMIT LOGIC =========
def can_use(uid, mode):
    if mode == "yt_name":
        reset_usage_name(uid)
        total = DAILY_LIMIT_NAME + usage_name[uid].get("bonus", 0)
        return usage_name[uid]["count"] < total
    elif mode == "ai_cap":
        reset_usage_ai(uid)
        total = DAILY_LIMIT_AI + usage_ai[uid].get("bonus", 0)
        return usage_ai[uid]["count"] < total
    return False

def increment_usage(uid, mode):
    if mode == "yt_name":
        usage_name[uid]["count"] += 1
        analytics["total_checks_name"] += 1
        analytics["total_users_name"].add(uid)
        analytics["users_today_name"].add(uid)
    elif mode == "ai_cap":
        usage_ai[uid]["count"] += 1
        analytics["total_checks_ai"] += 1
        analytics["total_users_ai"].add(uid)
        analytics["users_today_ai"].add(uid)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("▶ YouTube Name Check", callback_data="yt_name")],
        [InlineKeyboardButton("🤖 AI Caption / Content", callback_data="ai_cap")],
        [InlineKeyboardButton("ℹ Help", callback_data="help")]
    ]
    await update.message.reply_text(
        "👋 Welcome to ContentXpertAI 🔥\n\n"
    "🎯 Check YouTube usernames  \n"
    "🤖 Create viral AI captions  \n"
    "📈 Grow smarter, grow faster  \n\n"
    "👇 Tap below to start",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ========= MAIN MENU =========
async def platform_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "yt_name":
        context.user_data["mode"] = "yt_name"
        await q.message.reply_text("✍ Enter YouTube username:")

    elif q.data == "ai_cap":
        context.user_data["mode"] = "ai_cap"
        try:
            member = await context.bot.get_chat_member(CHANNEL, q.from_user.id)
            joined = member.status in ("member", "administrator", "creator")
        except:
            joined = False

        if not joined:
            kb = [
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL[1:]}")],
                [InlineKeyboardButton("✅ Verify", callback_data="ai_verify")]
            ]
            await q.message.reply_text(
                "🔒 Join channel to unlock AI tools",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await show_ai_platform(q)

    elif q.data == "help":
        await q.message.reply_text(
            "📚 *Welcome to ContentXpertAI Help*\n\n"
    "👤 *YouTube Name Check*\n"
    "• Check if your desired YouTube username is available ✅\n"
    "• Get 6 creative username suggestions 🌟\n\n"
    "🤖 *AI Captions / Content*\n"
    "• Generate captions for YouTube & Instagram ✍️\n"
    "• Choose your preferred language: English, Hindi, Hinglish 🌐\n"
    "• Regenerate captions with a single click 🔁\n\n"
    "🔧 *Daily Limits & Bonuses*\n"
    "• Daily checks: YT Name = 5, AI = 3 📅\n"
    "• Share the bot to unlock +2 extra uses 🔗\n\n"
    "⚡ *Admin Trends*\n"
    "• Admin can add hashtags & trending songs 📈\n"
    "• View or clear trends anytime 🧹\n\n"
    "✨ Enjoy creating and checking names & captions with ease! 🎉"
        )

# ========= AI VERIFY =========
async def ai_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        member = await context.bot.get_chat_member(CHANNEL, q.from_user.id)
        joined = member.status in ("member", "administrator", "creator")
    except:
        joined = False

    if not joined:
        await q.message.reply_text("❌ You must join the channel first!")
        return

    await show_ai_platform(q)

# ========= PLATFORM =========
async def show_ai_platform(q):
    kb = [
        [InlineKeyboardButton("▶ YouTube", callback_data="ai_yt")],
        [InlineKeyboardButton("📸 Instagram", callback_data="ai_ig")]
    ]
    await q.message.reply_text("📌 Select platform:", reply_markup=InlineKeyboardMarkup(kb))

async def ai_platform_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["ai_platform"] = "yt" if q.data == "ai_yt" else "ig"
    await q.message.reply_text("✍ Enter content topic:")

# ========= USER INPUT =========
async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()
    mode = context.user_data.get("mode")

    if not can_use(uid, mode):
        kb = [
            [InlineKeyboardButton(
                "📤 Share Bot",
                url="https://t.me/share/url?url=https://t.me/YOUR_BOT_USERNAME&text=🔥 Best Bot"
            )],
            [InlineKeyboardButton("🔓 I Have Shared", callback_data="unlock_ai")]
        ]
        await update.message.reply_text(
            "❌ Daily limit reached\nShare bot to unlock +2 uses",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if mode == "yt_name":
        increment_usage(uid, mode)
        available = await check_youtube(text, context)
        context.user_data["username"] = text
        status = "✅ Available" if available else "❌ Taken"

        await update.message.reply_text(
            f"🔍 Username: {text}\n📊 Status: {status}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Get Best Names", callback_data="get_names")]
            ])
        )

    elif mode == "ai_cap":
        increment_usage(uid, mode)
        context.user_data["ai_topic"] = text

        kb = [
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("Hindi", callback_data="lang_hi")],
            [InlineKeyboardButton("Hinglish", callback_data="lang_hing")]
        ]
        await update.message.reply_text(
            "🌐 Select language:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ========= LANGUAGE =========
async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    mode = context.user_data.get("mode")
    if not can_use(uid, mode):
        kb = [
            [InlineKeyboardButton(
                "📤 Share Bot",
                url="https://t.me/share/url?url=https://t.me/YOUR_BOT_USERNAME&text=🔥 Best Bot"
            )],
            [InlineKeyboardButton("🔓 I Have Shared", callback_data="unlock_ai")]
        ]
        await q.message.reply_text(
            "❌ Daily limit reached\nShare bot to unlock +2 uses",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    lang_map = {"lang_en": "English", "lang_hi": "Hindi", "lang_hing": "Hinglish"}
    context.user_data["ai_language"] = lang_map[q.data]
    await send_caption(q, context)

# ========= MULTIPLE OUTPUT SYSTEM =========
def generate_multiple_caption(topic, platform, lang):
    adjectives = ["Amazing", "Incredible", "Ultimate", "Fun", "Exciting", "Crazy", "Epic", "Top"]
    verbs = ["explained", "shown", "discussed", "revealed", "uncovered", "explored"]
    connectors = ["–", "|", "•", "»", "→"]

    hashtags = trends["hashtags"] or ["#viral", "#trending", "#fun"]
    songs = trends["songs"] or ["Trending Audio", "Popular Music"]

    # Pick random combinations
    adj = random.choice(adjectives)
    verb = random.choice(verbs)
    emoji1 = random.choice(EMOJIS)
    emoji2 = random.choice(EMOJIS)
    connector = random.choice(connectors)
    hashtag_str = " ".join(random.sample(hashtags, min(6, len(hashtags))))
    song_str = ", ".join(random.sample(songs, min(3, len(songs))))

    if platform == "yt":
        title = f"{adj} {topic} {emoji1}"
        description = f"This video {verb} {topic} {emoji2}"
        msg = (
            f"🎬 YouTube Content ({lang})\n\n"
            f"📌 Title: {title} {connector}\n"
            f"📝 Description: {description}\n"
            f"🏷 Hashtags: {hashtag_str}\n"
            f"🎵 Songs: {song_str}"
        )
    else:
        msg = (
            f"📸 Instagram Caption ({lang})\n\n"
            f"{adj} {topic} {emoji1} {emoji2}\n\n"
            f"🏷 Hashtags: {hashtag_str}\n"
            f"🎵 Songs: {song_str}"
        )

    return msg

# ========= CAPTION GENERATOR =========
async def send_caption(q, context):
    topic = context.user_data["ai_topic"]
    platform = context.user_data["ai_platform"]
    lang = context.user_data["ai_language"]

    msg = generate_multiple_caption(topic, platform, lang)
    kb = [[InlineKeyboardButton("🔁 Regenerate", callback_data="regenerate")]]
    await q.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

# ========= REGENERATE =========
async def regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    mode = context.user_data.get("mode")
    await q.answer()

    if not can_use(uid, mode):
        kb = [
            [InlineKeyboardButton(
                "📤 Share Bot",
                url="https://t.me/share/url?url=https://t.me/YOUR_BOT_USERNAME&text=🔥 Best Bot"
            )],
            [InlineKeyboardButton("🔓 I Have Shared", callback_data="unlock_ai")]
        ]
        await q.message.reply_text(
            "❌ Daily limit reached\nShare bot to unlock +2 uses",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    increment_usage(uid, mode)
    if mode == "ai_cap":
        await send_caption(q, context)
    else:
        await get_best_names(q, context)

# ========= UNLOCK BONUS =========
async def unlock_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    mode = context.user_data.get("mode")

    if mode == "yt_name":
        reset_usage_name(uid)
        if not usage_name[uid].get("shared_today", False):
            usage_name[uid]["bonus"] = usage_name[uid].get("bonus", 0) + 2
            usage_name[uid]["shared_today"] = True
            analytics["total_shares"] += 1
            await q.message.reply_text("✅ +2 YT Name Checks added for today!")
        else:
            await q.message.reply_text("⚠ You already unlocked today.")
    elif mode == "ai_cap":
        reset_usage_ai(uid)
        if not usage_ai[uid].get("shared_today", False):
            usage_ai[uid]["bonus"] = usage_ai[uid].get("bonus", 0) + 2
            usage_ai[uid]["shared_today"] = True
            analytics["total_shares"] += 1
            await q.message.reply_text("✅ +2 AI uses added for today!")
        else:
            await q.message.reply_text("⚠ You already unlocked today.")

# ========= BEST NAMES =========
async def get_best_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    base = context.user_data.get("username", "Name")
    names = smart_names(base)

    kb = [[InlineKeyboardButton(f"📋 {n}", callback_data=f"copy|{n}")] for n in names]
    kb.append([InlineKeyboardButton("🔁 Restart", callback_data="restart")])

    await q.message.reply_text(
        "✨ Best Username Suggestions",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def copy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.split("|", 1)[1]
    await q.message.reply_text(f"📋 Copied:\n`{name}`", parse_mode="Markdown")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update.callback_query, context)

# ========= ADMIN COMMANDS =========
async def addhashtags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    trends["hashtags"].extend(" ".join(context.args).split(","))
    await update.message.reply_text("✅ Hashtags added")

async def addsongs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    trends["songs"].extend(" ".join(context.args).split(","))
    await update.message.reply_text("✅ Songs added")

async def viewtrends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text(
        f"🏷 Hashtags:\n{', '.join(trends['hashtags'])}\n\n🎵 Songs:\n{', '.join(trends['songs'])}"
    )

async def cleartrends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    trends["hashtags"].clear()
    trends["songs"].clear()
    await update.message.reply_text("🧹 Trends cleared")

# ========= VIEW ANALYTICS =========
async def view_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    msg = (
        f"📊 Bot Analytics:\n"
        f"🧑‍💻 Total YT Users: {len(analytics['total_users_name'])}\n"
        f"🧑‍💻 Total AI Users: {len(analytics['total_users_ai'])}\n"
        f"📅 YT Users Today: {len(analytics['users_today_name'])}\n"
        f"📅 AI Users Today: {len(analytics['users_today_ai'])}\n"
        f"✅ Total YT Checks: {analytics['total_checks_name']}\n"
        f"✅ Total AI Checks: {analytics['total_checks_ai']}\n"
        f"🔗 Total Shares: {analytics['total_shares']}"
    )
    await update.message.reply_text(msg)

# ========= MAIN =========
app = ApplicationBuilder().token(TOKEN).build()

# Command Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addhashtags", addhashtags))
app.add_handler(CommandHandler("addsongs", addsongs))
app.add_handler(CommandHandler("viewtrends", viewtrends))
app.add_handler(CommandHandler("cleartrends", cleartrends))
app.add_handler(CommandHandler("analytics", view_analytics))

# Callback Handlers
app.add_handler(CallbackQueryHandler(platform_selection, "^(yt_name|ai_cap|help)$"))
app.add_handler(CallbackQueryHandler(ai_verify, "^ai_verify$"))
app.add_handler(CallbackQueryHandler(ai_platform_select, "^(ai_yt|ai_ig)$"))
app.add_handler(CallbackQueryHandler(language_selected, "^lang_"))
app.add_handler(CallbackQueryHandler(regenerate, "^regenerate$"))
app.add_handler(CallbackQueryHandler(unlock_ai, "^unlock_ai$"))
app.add_handler(CallbackQueryHandler(get_best_names, "^get_names$"))
app.add_handler(CallbackQueryHandler(copy_name, "^copy\\|"))
app.add_handler(CallbackQueryHandler(restart, "^restart$"))

# Message Handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))

print("🔥 NameCheckXBot running smoothly")
app.run_polling()