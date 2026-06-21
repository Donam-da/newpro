import os
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- IMPORT ASYNC HTML SESSION ---
from requests_html import AsyncHTMLSession

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# Chuyển hàm này thành async để đồng bộ với Telegram loop
async def trace_url_with_browser_engine(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    try:
        # Sử dụng AsyncHTMLSession đúng như hệ thống yêu cầu
        session = AsyncHTMLSession()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        # Dùng await để lấy dữ liệu bất đồng bộ
        response = await session.get(input_url, headers=headers, timeout=20)
        server_url = response.url
        
        print("Log: Đang kích hoạt nhân Chromium chạy Javascript ẩn...")
        # Gọi await cho hàm render Javascript ngầm
        await response.html.render(timeout=20, wait=5, sleep=3)
        
        final_url = response.url
        await session.close()

        response_text = f"🔍 **Kết quả phân tích từ nhân Trình duyệt ảo:**\n\n"
        response_text += f"🏁 **URL gốc:** {input_url}\n"
        
        if server_url != input_url:
            response_text += f"🚀 **Bước nhảy 1 (Server):** {server_url}\n"
            
        if final_url.strip("/") == server_url.strip("/"):
            response_text += "\n⚠️ Trình duyệt ảo đã đợi 8 giây nhưng trang web vẫn đứng yên. Rất có thể trang này bắt buộc phải tương tác bằng tay (Click chuột vào nút 'Lấy Link') thì mới sinh ra link đích."
        else:
            response_text += f"\n🎯 **URL đích thực tế (Sau khi chạy Script ẩn):**\n`{final_url}`"
            
        return response_text

    except Exception as e:
        return f"❌ Lỗi trong quá trình giả lập trình duyệt thực thi Script: {str(e)}"

# --- PHẦN HẠ TẦNG BOT VÀ FLASK ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Hệ thống kiểm tra link chạy nhân Chromium đã sẵn sàng. Hãy gửi link cho tôi!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang nạp link vào trình duyệt ảo, thực thi Javascript và đợi chuyển hướng ngầm (Mất khoảng 8-10 giây), vui lòng đợi...")
    
    # Gọi await trực tiếp vì trace_url giờ đã là hàm async chuẩn
    response_text = await trace_url_with_browser_engine(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

flask_app = Flask(__name__)
@flask_app.route('/')
def health_check(): return "Browser Engine Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN: return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    threading.Thread(target=run_flask, daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
