import os
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- SỬ DỤNG BẢN SYNC CỦA PLAYWRIGHT (MÔ MÔI TRƯỜNG ĐỘC LẬP) ---
from playwright.sync_api import sync_playwright

# 🔥 CẤU HÌNH CHO 10 NGƯỜI DÙNG: Cho phép tối đa 10 trình duyệt Chromium chạy song song
browser_semaphore = threading.Semaphore(10)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def trace_url_with_sync_browser(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    redirect_chain = []
    
    # Tự động xếp hàng vào một trong 10 slot trống của hệ thống
    with browser_semaphore:
        try:
            with sync_playwright() as p:
                print("Log: Khởi chạy Chromium ngầm di động...")
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Lắng nghe liên tục mọi sự kiện nhảy URL (Cả Server lẫn Javascript Client)
                page.on("framenavigated", lambda frame: redirect_chain.append(frame.url) if frame == page.main_frame else None)
                
                # 🔥 ĐÃ NÂNG TIMEOUT LÊN 60 GIÂY (60000ms) để đợi các trang web script nặng
                try:
                    page.goto(input_url, wait_until="load", timeout=60000)
                except Exception as load_err:
                    print(f"Log: Hết thời gian chờ 1 phút hoặc trang ngừng nạp: {str(load_err)}")
                    
                # Nghỉ thêm 3 giây tĩnh lặng cuối cùng để script kích hoạt lệnh nhảy trang
                time.sleep(3)
                
                final_url = page.url
                browser.close()
                
            # Loại bỏ các URL trùng lặp liên tiếp trong lịch sử nhảy link
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
        "🤖 **Hệ thống Quét Link Nhân Chromium Đa Luồng**\n\n"
        "Chào mừng bạn và nhóm bạn của Nam! Hãy gửi link vào đây, bot sẽ bóc tách toàn bộ chuỗi nhảy URL ẩn ngầm bằng Javascript.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang nạp link vào hệ thống đa luồng, thực thi mã Script (Vui lòng đợi trong giây lát)...")
    
    # Gọi hàm xử lý đồng bộ độc lập hoàn toàn với event loop của Telegram
    response_text = trace_url_with_sync_browser(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

flask_app = Flask(__name__)
@flask_app.route('/')
def health_check(): 
    return "Multi-user Playwright Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: 
        print("⚠️ Thiếu biến môi trường TELEGRAM_BOT_TOKEN.")
        return
    
    # Đảm bảo driver của Chromium luôn được cài đặt đầy đủ khi khởi động máy ảo
    print("📦 Chuẩn bị cài đặt cấu hình driver Chromium...")
    os.system("playwright install chromium")
    print("✅ Cài đặt driver thành công!")
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Chạy Flask ở luồng riêng biệt để treo port mạng ổn định trên Render
    threading.Thread(target=run_flask, daemon=True).start()
    print("🤖 Bot Telegram khởi động thành công...")
    application.run_polling()

if __name__ == "__main__":
    main()
