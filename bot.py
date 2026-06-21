import os
import threading
import requests
import cloudscraper
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse

# --- PHẦN 1: LOGIC BẺ KHÓA VÀ THEO DÕI CHUYỂN HƯỚNG URL ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def trace_and_bypass_url(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    
    # Chuẩn hóa nếu người dùng nhập thiếu http/https
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url

    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."

    # Danh sách các domain rút gọn phổ biến cần ép dùng API bẻ khóa trực tiếp
    shortener_domains = ["uptolink.vip", "bit.ly", "tinyurl.com", "ouo.io", "linkvertise.com"]
    parsed_domain = urlparse(input_url).netloc.lower()
    
    is_shortener = any(domain in parsed_domain for domain in shortener_domains)

    # BƯỚC 1: NẾU LÀ LINK RÚT GỌN PHỨC TẠP -> GỌI API BẺ KHÓA ĐỂ LÁCH JAVASCRIPT ĐẾM NGƯỢC
    if is_shortener:
        try:
            bypass_api_url = f"https://api.bypass.vip/bypass?url={input_url}"
            api_response = requests.get(bypass_api_url, timeout=20)
            
            if api_response.status_code == 200:
                data = api_response.json()
                if data.get("status") == "success" and data.get("destination"):
                    final_destination = data.get("destination")
                    
                    response_text = f"🔓 **Đã bẻ khóa thành công Link Rút Gọn (Javascript)!**\n\n"
                    response_text += f"🏁 **URL gốc:** {input_url}\n"
                    response_text += f"⚡ **Thời gian xử lý:** {data.get('time', 'N/A')}s\n\n"
                    response_text += f"🎯 **URL đích thực tế (Điểm đến cuối cùng):**\n`{final_destination}`"
                    return response_text
        except Exception as api_err:
            print(f"Log: API Bypass tạm thời gián đoạn: {str(api_err)}")
            # Nếu API lỗi thì tự động nhảy xuống cơ chế tự quét ở dưới

    # BƯỚC 2: CƠ CHẾ QUÉT MẶC ĐỊNH CHO LINK THÔNG THƯỜNG / LÁCH TƯỜNG LỬA SERVER
    try:
        # Khởi tạo scraper giả lập trình duyệt xịn lách Cloudflare
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
        # Đi theo toàn bộ chuỗi chuyển hướng (allow_redirects=True)
        response = scraper.get(input_url, timeout=15, allow_redirects=True)
        redirect_chain = response.history
        
        response_text = f"🔍 **Hành trình chuyển hướng thực tế (Server Redirect):**\n\n"
        response_text += f"🏁 **URL gốc:** {input_url}\n"
        
        if not redirect_chain:
            response_text += "\n✨ Trang web này đứng yên tại chỗ, hệ thống đích trả về trạng thái tĩnh trực tiếp.\n"
            response_text += f"📍 **Điểm dừng hiện tại:** {response.url}"
            return response_text
            
        response_text += "\n🚀 **Các bước nhảy URL phát hiện được:**\n"
        for index, step in enumerate(redirect_chain, 1):
            response_text += f"{index}. {step.url} *(Mã trạng thái: {step.status_code})*\n"
            
        response_text += f"\n🎯 **URL cuối cùng (Điểm đến thực tế):**\n`{response.url}`"
        return response_text

    except Exception as e:
        return f"❌ Lỗi khi quét hoặc phân tích liên kết: {str(e)}"

# --- PHẦN 2: TELEGRAM BOT INTERACTION ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Chào mừng!**\n\nHãy gửi cho tôi bất kỳ liên kết nào (Kể cả link báo chí, link hệ thống hay link rút gọn kiếm tiền).\n\n"
        "Tôi sẽ phân tích hành trình chuyển hướng và lôi URL đích thực tế ra cho bạn!",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text.strip()
    await update.message.reply_text("🌐 Đang kích hoạt bộ giải mã và theo dõi chuỗi nhảy link ngầm, vui lòng đợi giây lát...")
    
    # Thực hiện gọi hàm xử lý đồng bộ một cách an toàn
    response_text = trace_and_bypass_url(user_url)
    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- PHẦN 3: WEB SERVER FLASK MINI GIỮ PORT RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Perfect Redirect Bot is alive!", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# --- PHẦN 4: HÀM KHỞI CHẠY CHÍNH ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("⚠️ Thiếu biến môi trường TELEGRAM_BOT_TOKEN.")
        return
        
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Chạy Web Server Flask ở luồng độc lập phục vụ cổng mạng Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🤖 Bot Telegram đã khởi động hoàn toàn thành công...")
    application.run_polling()

if __name__ == "__main__":
    main()
