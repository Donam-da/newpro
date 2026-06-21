import os
import threading
import cloudscraper
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- PHẦN 1: LOGIC TRACE URL DÙNG CLOUDSCRAPER LÁCH CƠ CHẾ CHẶN BOT ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def trace_url_with_scraper(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    try:
        # Khởi tạo scraper giả lập trình duyệt (Vượt qua các hệ thống chặn Javascript/Cloudflare ngầm)
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        
        # Đi theo chuỗi chuyển hướng (allow_redirects=True)
        response = scraper.get(input_url, timeout=15, allow_redirects=True)
        
        # Lấy lịch sử các bước nhảy URL
        redirect_chain = response.history
        
        response_text = f"🔍 **Hành trình chuyển hướng thực tế (Lách tường lửa):**\n\n"
        response_text += f"🏁 **URL gốc:** {input_url}\n"
        
        if not redirect_chain:
            response_text += "\n✨ Trang web này đứng yên, hoặc hệ thống đích trả về trạng thái tĩnh trực tiếp.\n"
            response_text += f"📍 **Điểm dừng hiện tại:** {response.url}"
            return response_text
            
        response_text += "\n🚀 **Các bước nhảy URL phát hiện được:**\n"
        for index, step in enumerate(redirect_chain, 1):
            response_text += f"{index}. {step.url} *(Status: {step.status_code})*\n"
            
        response_text += f"\n🎯 **URL cuối cùng (Điểm đến thực tế):**\n`{response.url}`"
        return response_text

    except Exception as e:
        return f"❌ Lỗi khi quét liên kết bằng Engine giả lập: {str(e)}"

# --- PHẦN 2: TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào mừng! Tôi sử dụng Engine giả lập để theo dõi hành trình chuyển hướng của các link bảo mật cao.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang kích hoạt bộ giải mã và theo dõi chuỗi nhảy link ngầm, vui lòng đợi...")
    
    # Chạy đồng bộ an toàn
    response_text = trace_url_with_scraper(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- PHẦN 3: WEB SERVER FLASK MINI GIỮ PORT RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Engine Redirect Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# --- PHẦN 4: KHỞI CHẠY HỆ THỐNG ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("⚠️ Thiếu biến môi trường TELEGRAM_BOT_TOKEN.")
        return
        
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🤖 Bot Telegram đã khởi động thành công...")
    application.run_polling()

if __name__ == "__main__":
    main()
