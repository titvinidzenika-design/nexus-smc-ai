import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import ccxt.async_support as ccxt
import pandas as pd

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

stats_data = {
    "total_signals": 0,
    "wins": 0,
    "losses": 0
}

active_signals = []

async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_CHAT_ID:
        return
    try:
        heartbeat_text = "🟢 **Nexus Status:** ბოტი აქტიურად მუშაობს და აკვირდება ბაზარს."
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=heartbeat_text, parse_mode="Markdown")
        logger.info("Heartbeat წარმატებით გაიგზავნა.")
    except Exception as e:
        logger.error(f"Heartbeat შეცდომა: {e}")

async def check_ema_strategy(context: ContextTypes.DEFAULT_TYPE):
    global active_signals, stats_data
    symbols = ['BTC/USDT', 'SOL/USDT', 'HYPE/USDT']
    
    try:
        exchange = ccxt.bingx()
    except Exception as e:
        logger.error(f"ბირჟასთან დაკავშირების შეცდომა: {e}")
        return

    try:
        # 1. TP / SL მონიტორინგი
        for sig in active_signals[:]:
            symbol = sig['symbol']
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=5)
                current_price = ohlcv[-1][4]
                
                if sig['type'] == 'LONG':
                    if current_price >= sig['tp']:
                        stats_data["wins"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"✅ **TP მიღწეულია (WIN)!**\n🪙 `{symbol}`\n🎯 ფასი: `{current_price}`", parse_mode="Markdown")
                    elif current_price <= sig['sl']:
                        stats_data["losses"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ **სტოპ-ლოსი (LOSS)!**\n🪙 `{symbol}`\n🛑 ფასი: `{current_price}`", parse_mode="Markdown")
                            
                elif sig['type'] == 'SHORT':
                    if current_price <= sig['tp']:
                        stats_data["wins"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"✅ **TP მიღწეულია (WIN)!**\n🪙 `{symbol}`\n🎯 ფასი: `{current_price}`", parse_mode="Markdown")
                    elif current_price >= sig['sl']:
                        stats_data["losses"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ **სტოპ-ლოსი (LOSS)!**\n🪙 `{symbol}`\n🛑 ფასი: `{current_price}`", parse_mode="Markdown")
            except Exception as pos_err:
                logger.error(f"პოზიციის შემოწმების შეცდომა {symbol}: {pos_err}")

        # 2. ახალი სიგნალების ძებნა (1h EMA 9/21 კვეთა)
        for symbol in symbols:
            if any(s['symbol'] == symbol for s in active_signals):
                continue

            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
                df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
                
                prev_row = df.iloc[-2]
                last_row = df.iloc[-1]
                current_price = last_row['close']
                
                bullish_crossover = (prev_row['EMA_9'] <= prev_row['EMA_21']) and (last_row['EMA_9'] > last_row['EMA_21'])
                bearish_crossover = (prev_row['EMA_9'] >= prev_row['EMA_21']) and (last_row['EMA_9'] < last_row['EMA_21'])
                
                signal_text = None
                
                if bullish_crossover:
                    sl = current_price * 0.99
                    tp = current_price * 1.015
                    active_signals.append({'symbol': symbol, 'type': 'LONG', 'entry': current_price, 'tp': tp, 'sl': sl})
                    stats_data["total_signals"] += 1
                    signal_text = f"🚀 **LONG SIGNAL (1h)**\n🪙 წყვილი: `{symbol}`\n🟢 შესვლა: `{current_price}`\n🎯 TP: `{tp:.2f}` | 🛑 SL: `{sl:.2f}`"
                
                elif bearish_crossover:
                    sl = current_price * 1.01
                    tp = current_price * 0.985
                    active_signals.append({'symbol': symbol, 'type': 'SHORT', 'entry': current_price, 'tp': tp, 'sl': sl})
                    stats_data["total_signals"] += 1
                    signal_text = f"📉 **SHORT SIGNAL (1h)**\n🪙 წყვილი: `{symbol}`\n🔴 შესვლა: `{current_price}`\n🎯 TP: `{tp:.2f}` | 🛑 SL: `{sl:.2f}`"
                
                if signal_text and TELEGRAM_CHAT_ID:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=signal_text, parse_mode="Markdown")
            except Exception as sym_err:
                logger.error(f"სიმბოლოს დამუშავების შეცდომა {symbol}: {sym_err}")
                
    except Exception as e:
        logger.error(f"სტრატეგიის ზოგადი შეცდომა: {e}")
    finally:
        await exchange.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Nexus სრულიად მუშა მდგომარეობაშია!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = stats_data["total_signals"]
    wins = stats_data["wins"]
    losses = stats_data["losses"]
    win_rate = (wins / total * 100) if total > 0 else 0
    
    stats_text = (
        f"📊 **სტატისტიკა:**\n\n"
        f"🔹 სულ სიგნალი: `{total}`\n"
        f"✅ მოგებული: `{wins}`\n"
        f"❌ წაგებული: `{losses}`\n"
        f"📈 Win Rate: `{win_rate:.1f}%`\n"
        f"🔄 ღია პოზიციები: `{len(active_signals)}`"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN არ არის მითითებული!")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(check_ema_strategy, interval=3600, first=10)
        job_queue.run_repeating(send_heartbeat, interval=3600, first=15)

    # ეს ხაზი წყვეტს Conflict შეცდომას ყოველგვარი შეფერხების გარეშე
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
