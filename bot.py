import os
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- IMPORT SELENIUM TRÌNH DUYỆT ẢO DI ĐỘNG ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- PHẦN 1: LOGIC KIỂM TRA CHUYỂN HƯỚNG CÓ CHẠY JAVASCRIPT ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def trace_url_with_selenium(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    # Cấu hình Chrome chạy ẩn ngầm (Headless) không cần giao diện, tối ưu RAM cho Render
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    driver = None
    try:
        # Tự động tải và cấu hình phiên bản Chrome di động phù hợp với Render
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Thiết lập thời gian chờ tải trang tối đa 15 giây
        driver.set_page_load_timeout(15)
        
        # "Ấn enter" mở link
        driver.get(input_url)
        
        # Đợi 4 giây để Javascript đếm ngược ngầm hoặc chuyển hướng hoạt động xong
        time.sleep(4)
        
        # Lấy ra URL cuối cùng sau khi đã chạy xong Javascript
        final_url = driver.current_url
        
        response_text = f"🔍 **Hành trình kiểm tra bằng Trình duyệt ảo:**\n\n"
        response_text += f"🏁 **URL gốc của bạn:** {input_url}\n\n"
        
        if input_url.strip("/") == final_url.strip("/"):
            response_text += "✨ Trang web đứng yên, không phát hiện lệnh nhảy URL (Redirect) nào khác bằng Javascript.\n"
            response_text += f"📍 **Điểm dừng hiện tại:** {final_url}"
        else:
            response_text += "🚀 **Phát hiện chuyển hướng ngầm bằng Javascript!**\n"
            response_text += f"🎯 **URL đích thực tế (Điểm đến cuối cùng):**\n`{final_url}`"
            
        return response_text

    except Exception as e:
        return f"❌ Lỗi khi giả lập trình duyệt ảo: {str(e)}"
    finally:
        if driver:
            driver.quit() # Luôn đóng trình duyệt ngầm để giải phóng RAM cho server

# --- PHẦN 2: TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào mừng! Hãy gửi link cho tôi, tôi sẽ dùng trình duyệt ẩn ngầm Selenium để bóc tách mọi link chuyển hướng Javascript.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang bật trình duyệt ảo Selenium và quét chuyển hướng ngầm, vui lòng đợi vài giây...")
    
    # Chạy hàm Selenium trong luồng đồng bộ bình thường
    response_text = trace_url_with_selenium(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- PHẦN 3: WEB SERVER FLASK MINI ĐỂ TREO PORT RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Selenium Redirect Bot is alive!", 200

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
    
    # Khởi động Flask giữ kết nối Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🤖 Bot Telegram đã khởi động hoàn toàn thành công...")
    application.run_polling()

if __name__ == "__main__":
    main()
