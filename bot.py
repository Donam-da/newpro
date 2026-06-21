import os
import threading
import time
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# Giới hạn tối đa 10 trình duyệt Chromium chạy song song
browser_semaphore = threading.Semaphore(10)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# Hàm đồng bộ thuần túy xử lý Playwright
def trace_url_worker(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    redirect_chain = []
    
    with browser_semaphore:
        try:
            with sync_playwright() as p:
                print("Log: Khởi chạy Chromium ngầm di động...")
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Theo dõi hành trình URL
                page.on("framenavigated", lambda frame: redirect_chain.append(frame.url) if frame == page.main_frame else None)
                
                try:
                    page.goto(input_url, wait_until="load", timeout=60000)
                except Exception as load_err:
                    print(f"Log: Hết thời gian chờ hoặc trang ngừng nạp: {str(load_err)}")
                    
                time.sleep(3)
                final_url = page.url
                browser.close()
                
            clean_chain = []
            for url in redirect_chain:
                if not clean_chain or clean_chain[-1] != url:
                    clean_chain.append(url)
                    
            response_text = f"🔍 **Hành trình kiểm tra bằng Trình duyệt ảo (Nhân Chromium):**\n\n"
            response_text += f"🏁 **URL gốc:** {input_url}\n"
            
            if len(clean_chain) <= 1 and clean_chain[0] == final_url:
                response_text += "\n✨ Trang web này đứng yên tại chỗ, không tự động nhảy đi đâu.\n"
                response_text += f"📍 **Điểm dừng hiện tại:** {final_url}"
                return response_text
                
            response_text += "\n🚀 **Các bước nhảy URL thực tế phát hiện được:**\n"
            for index, url in enumerate(clean_chain, 1):
                if url == final_url:
                    response_text += f"{index}. {url} *(Điểm dừng cuối)*\n"
                else:
                    response_text += f"{index}. {url}\n"
                    
            return response_text

        except Exception as e:
            return f"❌ Lỗi giả lập trình duyệt: {str(e)}"

# --- HẠ TẦNG BOT VÀ WEB SERVER FLASK ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Bot Kiểm Tra Chuyển Hướng Link**\n\n"
        "Hãy gửi link vào đây, bot sẽ bóc tách chuỗi nhảy URL bằng nhân Chromium cô lập.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang nạp link vào luồng Chromium độc lập, xử lý Script ngầm...")
    
    # 🔥 ĐÂY LÀ CHÌA KHÓA: Ép hàm đồng bộ chạy trên một Thread hoàn toàn tách biệt với asyncio loop
    response_text = await asyncio.to_thread(trace_url_worker, user_url)
    
    await update.message.reply_text(response_text, parse_mode="Markdown")

flask_app = Flask(__name__)
@flask_app.route('/')
def health_check(): 
    return "Playwright Threaded Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: 
        print("⚠️ Thiếu biến môi trường TELEGRAM_BOT_TOKEN.")
        return
    
    # Khởi động Flask mở Port trước
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Flask Web Server đã mở Port thành công.")
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Telegram bắt đầu lắng nghe...")
    application.run_polling()

if __name__ == "__main__":
    main()
