import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ===== إعدادات البوت =====
BOT_TOKEN = "8279913352:AAF_k_uEVULcrAgJDlOt9UKH4SxxbPQo_PI"
DOWNLOAD_DIR = os.path.expanduser("~/downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ===== المنصات المدعومة =====
SUPPORTED_DOMAINS = [
    "instagram.com", "tiktok.com", "youtube.com", "youtu.be",
    "twitter.com", "x.com", "facebook.com", "fb.watch",
    "snapchat.com", "reddit.com", "vimeo.com", "dailymotion.com",
    "pinterest.com", "linkedin.com", "twitch.tv"
]

def is_supported_url(url: str) -> bool:
    return any(domain in url for domain in SUPPORTED_DOMAINS)

# ===== أمر /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *أهلاً بك في بوت تحميل الفيديوهات!*\n\n"
        "📥 أرسل رابط من أي منصة وسأقوم بتحميله لك.\n\n"
        "🌐 *المنصات المدعومة:*\n"
        "Instagram • TikTok • YouTube • Twitter/X\n"
        "Facebook • Snapchat • Reddit • Vimeo\n"
        "Dailymotion • Pinterest • LinkedIn • Twitch\n\n"
        "📌 *الأوامر المتاحة:*\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n\n"
        "⚡ فقط أرسل الرابط وسأتولى الباقي!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ===== أمر /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *كيفية الاستخدام:*\n\n"
        "1️⃣ انسخ رابط الفيديو أو الصورة\n"
        "2️⃣ أرسله هنا مباشرة\n"
        "3️⃣ اختر الجودة أو MP3\n"
        "4️⃣ انتظر حتى يصلك الملف\n\n"
        "📦 *الفرق بين المضغوط وغير المضغوط:*\n"
        "• مضغوط = يحافظ على الجودة الأصلية كاملاً، يُرسل كملف\n"
        "• غير مضغوط = يُشغَّل مباشرة في المحادثة، لكن تيليجرام يقلل جودته\n\n"
        "⚠️ *ملاحظات:*\n"
        "• بعض المنصات تتطلب أن يكون الحساب عاماً\n"
        "• الفيديوهات الطويلة قد تأخذ وقتاً أكثر\n"
        "• الحد الأقصى لحجم الملف 50MB على تيليجرام"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ===== استقبال الروابط =====
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not is_supported_url(url):
        await update.message.reply_text(
            "❌ الرابط غير مدعوم أو غير صحيح.\n"
            "أرسل /help لمعرفة المنصات المدعومة."
        )
        return

    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("🎬 أفضل جودة", callback_data="quality_best"),
            InlineKeyboardButton("📱 جودة متوسطة", callback_data="quality_medium"),
        ],
        [
            InlineKeyboardButton("💾 أقل جودة", callback_data="quality_low"),
            InlineKeyboardButton("🎵 صوت فقط MP3", callback_data="quality_mp3"),
        ],
        [
            InlineKeyboardButton("📦 مضغوط (جودة أصلية)", callback_data="quality_best_doc"),
            InlineKeyboardButton("📤 غير مضغوط", callback_data="quality_best_vid"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ *تم التعرف على الرابط!*\n\nاختر جودة التحميل وطريقة الإرسال:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ===== معالجة اختيار الجودة =====
async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مجدداً.")
        return

    choice = query.data
    quality_labels = {
        "quality_best":     "أفضل جودة 🎬",
        "quality_medium":   "جودة متوسطة 📱",
        "quality_low":      "أقل جودة 💾",
        "quality_mp3":      "صوت فقط MP3 🎵",
        "quality_best_doc": "مضغوط - جودة أصلية 📦",
        "quality_best_vid": "غير مضغوط 📤",
    }
    label = quality_labels.get(choice, "")

    progress_msg = await query.edit_message_text(
        f"⏳ جاري التحميل بـ *{label}*...\n\n"
        "▱▱▱▱▱▱▱▱▱▱ 0%",
        parse_mode="Markdown"
    )

    chat_id = query.message.chat_id
    msg_id = progress_msg.message_id
    bot = context.bot
    last_percent = [-1]

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                percent = int(downloaded / total * 100)
                if percent != last_percent[0] and percent % 10 == 0:
                    last_percent[0] = percent
                    filled = percent // 10
                    bar = "▰" * filled + "▱" * (10 - filled)
                    asyncio.get_event_loop().call_soon_threadsafe(
                        asyncio.ensure_future,
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text=f"⏳ جاري التحميل بـ *{label}*...\n\n{bar} {percent}%",
                            parse_mode="Markdown"
                        )
                    )

    # إعدادات الجودة
    if choice in ("quality_best", "quality_best_doc", "quality_best_vid"):
        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    elif choice == "quality_medium":
        fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
    elif choice == "quality_low":
        fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"
    else:
        fmt = "bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if choice == "quality_mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        loop = asyncio.get_event_loop()

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if choice == "quality_mp3":
                    path = os.path.join(DOWNLOAD_DIR, f"{info['id']}.mp3")
                else:
                    path = ydl.prepare_filename(info)
                    if not os.path.exists(path):
                        path = path.rsplit(".", 1)[0] + ".mp4"
                return path

        file_path = await loop.run_in_executor(None, download)

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text="✅ *اكتمل التحميل!* جاري الإرسال...",
            parse_mode="Markdown"
        )

        file_size = os.path.getsize(file_path)

        if file_size > 50 * 1024 * 1024:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="⚠️ حجم الملف يتجاوز 50MB، وهو الحد الأقصى لتيليجرام.\nجرب جودة أقل."
            )
        elif choice == "quality_mp3":
            with open(file_path, "rb") as f:
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    caption="🎵 تم التحميل بواسطة البوت"
                )
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        elif choice == "quality_best_vid":
            # إرسال كفيديو مباشر (غير مضغوط - تيليجرام يعالجه)
            with open(file_path, "rb") as f:
                await bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption="📤 تم التحميل بواسطة البوت",
                    supports_streaming=True
                )
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        else:
            # إرسال كمستند مضغوط يحافظ على الجودة
            with open(file_path, "rb") as f:
                await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption="📦 تم التحميل بواسطة البوت",
                    filename=os.path.basename(file_path)
                )
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)

        os.remove(file_path)

    except Exception as e:
        error_msg = str(e)
        if "Private" in error_msg or "login" in error_msg.lower():
            msg = "❌ هذا المحتوى خاص أو يتطلب تسجيل دخول."
        elif "not available" in error_msg.lower():
            msg = "❌ هذا المحتوى غير متاح في منطقتك."
        elif "Unsupported URL" in error_msg:
            msg = "❌ هذا الرابط غير مدعوم."
        else:
            msg = f"❌ حدث خطأ أثناء التحميل:\n`{error_msg[:200]}`"

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=msg,
            parse_mode="Markdown"
        )

# ===== تشغيل البوت =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality))

    print("✅ البوت يعمل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
