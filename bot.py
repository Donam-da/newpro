import os
import requests
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- PHẦN 1: LOGIC KIỂM TRA CHUYỂN HƯỚNG URL (ĐÚNG Ý BẠN) ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def trace_url_redirects(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    # Chuẩn hóa link nếu người dùng nhập thiếu http/https
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        # requests.get mặc định sẽ tự động "ấn enter" và đi theo các bước chuyển hướng (allow_redirects=True)
        response = requests.get(input_url, headers=headers, timeout=15, allow_redirects=True)
        
        # Lấy ra danh sách các URL trung gian mà trang web đã đi qua
        redirect_chain = response.history
        
        response_text = f"🔍 **Hành trình chuyển hướng của URL:**\n\n"
        response_text += f"🏁 **URL gốc:** {input_url}\n"
        
        if not redirect_chain:
            response_text += "\n✨ Trang web này đứng yên tại chỗ, không có phản hồi chuyển hướng (Redirect) nào khác.\n"
            response_text += f"📍 **Điểm dừng hiện tại:** {response.url}"
            return response_text
            
        response_text += "\n🚀 **Các bước chuyển hướng trung gian:**\n"
        for index, step in enumerate(redirect_chain, 1):
            response_text += f"{index}. {step.url} *(Mã trạng thái: {step.status_code})*\n"
            
        response_text += f"\n🎯 **URL cuối cùng (Điểm đến thực tế):**\n{response.url}"
        return response_text

    except Exception as e:
        return f"❌ Không thể truy cập hoặc kiểm tra liên kết này. Lỗi: {str(e)}"

# --- PHẦN 2: TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào mừng! Hãy gửi cho tôi 1 liên kết, tôi sẽ kiểm tra xem nó tự động chuyển hướng (Redirect) đến những URL nào nhé.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🔍 Đang giả lập trình duyệt và theo dõi các bước chuyển hướng, vui lòng đợi...")
    response_text = trace_url_redirects(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- PHẦN 3: WEB SERVER FLASK MINI ĐỂ TREO RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Redirect Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

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
