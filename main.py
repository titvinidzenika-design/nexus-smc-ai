import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.async_support as ccxt  # ასინქრონული CCXT ბიბლიოთეკა BingX-ისთვის ან სხვა ბირჟებისთვის

# ლოგირების კონფიგურაცია
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ტოკენების წამოღება Railway-ს Environment Variables-დან
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # სურვილისამებრ, ავტომატური სიგნალებისთვის

# /start ბრძანების ჰენდლერი
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_message = (
        f"გამარჯობა, {user_name}! 🚀\n\n"
        f"Nexus ბოტი წარმატებით ფუნქციონირებს და მზად არის სკანირებისთვის.\n"
        f"აქტიური სტრატეგია: 3-დონიანი DCA გრიდი + სტრუქტურული სტოპ-ლოსი."
    )
    await update.message.reply_text(welcome_message)

# მაგალითი ფუნქცია ბაზრის ასინქრონული შემოწმებისთვის (ccxt გამოყენებით)
async def check_market_prices(context: ContextTypes.DEFAULT_TYPE):
    try:
        # მაგალითად BingX ბირჟის ინიციალიზაცია
        exchange = ccxt.bingx()
        ticker = await exchange.fetch_ticker('BTC/USDT')
        btc_price = ticker['last']
        await exchange.close()
        
        logger.info(f"მიმდინარე BTC ფასი: {btc_price}")
        
        # თუ გსურთ ავტომატური სიგნალის გამოგზავნა ტელეგრამის ჩათში:
        # if TELEGRAM_CHAT_ID:
        #     await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"ბიტკოინის მიმდინარე ფასი: {btc_price}")
            
    except Exception as e:
        logger.error(f"შეცდომა ბაზრის შემოწმებისას: {e}")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN არ არის მითითებული გარემო ცვლადებში!")
        return

    # აპლიკაციის აგება
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # ბრძანებების რეგისტრაცია
    application.add_handler(CommandHandler("start", start))

    # ფონური ამოცანების (JobQueue) დამატება ბაზრის პერიოდული სკანირებისთვის
    job_queue = application.job_queue
    if job_queue:
        # ყოველ 300 წუთში (ან სასურველ ინტერვალში) შეამოწმოს ფასი
        job_queue.run_repeating(check_market_prices, interval=300, first=10)

    logger.info("ბოტი იწყებს მუშაობას...")
    
    # ბოტის გაშვება Polling რეჟიმში
    application.run_polling()

if __name__ == '__main__':
    main()
