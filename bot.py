import os
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse
from playwright.async_api import async_playwright

# --- PHẦN 1: LOGIC TRACE URL BẰNG PLAYWRIGHT (GIẢ LẬP TRÌNH DUYỆT THẬT) ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

async def trace_url_with_browser(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    # Tạo một danh sách lưu lại chuỗi chuyển hướng
    redirect_chain = []
    
    try:
        async with async_playwright() as p:
            # Khởi chạy trình duyệt Chromium ngầm (headless)
            browser = await p.chromium.launch(headless=True)
            
            # Giả lập thiết bị di động hoặc máy tính để né bớt bot detection
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Lắng nghe sự kiện mỗi khi URL thay đổi (bao gồm cả chuyển hướng bằng Javascript)
            page.on("framenavigated", lambda frame: redirect_chain.append(frame.url) if frame == page.main_frame else None)
            
            # Truy cập trang web và đợi tối đa 15 giây cho trang tải xong (networkidle)
            await page.goto(input_url, wait_until="load", timeout=15000)
            
            # Đợi thêm 3 giây phòng trường hợp script đếm ngược trễ
            await asyncio.sleep(3)
            
            final_url = page.url
            await browser.close()
            
        # Lọc bỏ các URL trùng lặp liên tiếp trong danh sách trace
        clean_chain = []
        for url in redirect_chain:
            if not clean_chain or clean_chain[-1] != url:
                clean_chain.append(url)
                
        response_text = f"🔍 **Hành trình chuyển hướng thực tế (Có chạy Javascript):**\n\n"
        response_text += f"🏁 **URL gốc:** {input_url}\n"
        
        if len(clean_chain) <= 1 and clean_chain[0] == final_url:
            response_text += "\n✨ Trang web đứng yên, không có phản hồi chuyển hướng nào.\n"
            response_text += f"📍 **Điểm dừng:** {final_url}"
            return response_text
            
        response_text += "\n🚀 **Các bước nhảy URL:**\n"
        for index, url in enumerate(clean_chain, 1):
            if url == final_url:
                response_text += f"{index}. {url} *(Điểm dừng cuối)*\n"
            else:
                response_text += f"{index}. {url}\n"
                
        return response_text

    except Exception as e:
        return f"❌ Lỗi khi mở trình duyệt ảo: {str(e)}"

# --- PHẦN 2: TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào mừng! Tôi sử dụng trình duyệt ảo để bắt mọi loại link chuyển hướng bằng Javascript.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang khởi động trình duyệt ảo và theo dõi chuyển hướng ngầm, vui lòng đợi từ 5-10 giây...")
    # Vì hàm trace chạy async nên ta gọi await trực tiếp
    response_text = await trace_url_with_browser(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- PHẦN 3: WEB SERVER FLASK MINI ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Browser Redirect Bot is alive!", 200

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
