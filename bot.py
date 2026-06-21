import os
import asyncio
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def crawl_links(input_url):
    if not input_url.strip():
        return "⚠️ Vui lòng nhập một liên kết."
    if not input_url.startswith(("http://", "https://")):
        input_url = "https://" + input_url
    if not is_valid_url(input_url):
        return "❌ Liên kết không hợp lệ."
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(input_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        domain_name = urlparse(input_url).netloc
        external_links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = urljoin(input_url, href)
            clean_url = absolute_url.split('#')[0]
            if is_valid_url(clean_url):
                if domain_name not in urlparse(clean_url).netloc:
                    external_links.add(clean_url)
        result_list = sorted(list(external_links))
        if not result_list:
            return "🔍 Không tìm thấy liên kết ngoại khu nào."
        response_text = f"✅ Tìm thấy {len(result_list)} liên kết ngoại khu.\n\nTop 15 kết quả đầu tiên:\n"
        for i, url in enumerate(result_list[:15], 1):
            response_text += f"{i}. {url}\n"
        if len(result_list) > 15:
            response_text += f"\n... và {len(result_list) - 15} liên kết khác."
        return response_text
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào mừng! Hãy gửi cho tôi 1 liên kết (URL), tôi sẽ quét các liên kết ngoại khu giúp bạn.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_url = update.message.text
    await update.message.reply_text("🔍 Đang tiến hành quét dữ liệu, vui lòng đợi giây lát...")
    response_text = crawl_links(user_url)
    await update.message.reply_text(response_text)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("⚠️ Thiếu biến môi trường TELEGRAM_BOT_TOKEN.")
        return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot Telegram đã khởi động thành công...")
    application.run_polling()

if __name__ == "__main__":
    main()