import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt.pro as ccxt
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ლოგირების ρდგენა
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# სტატისტიკა და აქტიური პოზიციები (EMA 9/21)
stats_data = {
    "total_signals": 0,
    "wins": 0,
    "losses": 0
}

active_signals = []

# პატარა HTTP სერვერი Railway-სთვის (პორტი 8080)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"HTTP სერვერი გაშვებულია პორტზე {port}")
    server.serve_forever()

# საათობრივი Heartbeat შეტყობინება
async def send_heartbeat(context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_CHAT_ID:
        return
    try:
        heartbeat_text = "🟢 **Nexus Status (EMA 9/21):** ბოტი აქტიურად მუშაობს და აკვირდება ბაზარს (BTC, SOL, HYPE | 15m მონიტორინგი + 1h/4h ტრენდი)."
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=heartbeat_text, parse_mode="Markdown")
        logger.info("Heartbeat წარმატებით გაიგზავნა.")
    except Exception as e:
        logger.error(f"Heartbeat შეცდომა: {e}")

# სტრატეგია: 15-წუთიანი კვეთა + 1h & 4h ტრენდის ფილტრი + 1:1.5 რისკ/მოგების თანაფარდობა
async def check_ema_strategy(context: ContextTypes.DEFAULT_TYPE):
    global active_signals, stats_data
    symbols = ['BTC/USDT', 'SOL/USDT', 'HYPE/USDT']

    try:
        exchange = ccxt.bingx()
    except Exception as e:
        logger.error(f"ბირჟასთან დაკავშირების შეცდომა: {e}")
        return

    try:
        # 1. ღია პოზიციების მონიტორინგი (TP / SL შემოწმება 15m ფასებით)
        for sig in active_signals[:]:
            symbol = sig['symbol']
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='15m', limit=5)
                current_price = ohlcv[-1][4]

                if sig['type'] == 'LONG':
                    if current_price >= sig['tp']:
                        stats_data["wins"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"✅ **TP მიღწეულია (WIN) [15m EMA 9/21]!**\n🪙 `{symbol}`\n🎯 ფასი: `{current_price}`", parse_mode="Markdown")
                    elif current_price <= sig['sl']:
                        stats_data["losses"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ **სტოპ-ლოსი (LOSS) [15m EMA 9/21]!**\n🪙 `{symbol}`\n🛑 ფასი: `{current_price}`", parse_mode="Markdown")

                elif sig['type'] == 'SHORT':
                    if current_price <= sig['tp']:
                        stats_data["wins"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"✅ **TP მიღწეულია (WIN) [15m EMA 9/21]!**\n🪙 `{symbol}`\n🎯 ფასი: `{current_price}`", parse_mode="Markdown")
                    elif current_price >= sig['sl']:
                        stats_data["losses"] += 1
                        active_signals.remove(sig)
                        if TELEGRAM_CHAT_ID:
                            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ **სტოპ-ლოსი (LOSS) [15m EMA 9/21]!**\n🪙 `{symbol}`\n🛑 ფასი: `{current_price}`", parse_mode="Markdown")
            except Exception as pos_err:
                logger.error(f"პოზიციის შემოწმების შეცდომა {symbol}: {pos_err}")

        # 2. ახალი სიგნალების ძებნა (15m EMA 9/21 კვეთა + 1h & 4h ფილტრი)
        for symbol in symbols:
            if any(s['symbol'] == symbol for s in active_signals):
                continue

            try:
                # 15-წუთიანი გრაფიკი კვეთისთვის
                ohlcv_15m = await exchange.fetch_ohlcv(symbol, timeframe='15m', limit=100)
                if len(ohlcv_15m) < 30:
                    continue
                df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_15m['EMA_9'] = df_15m['close'].ewm(span=9, adjust=False).mean()
                df_15m['EMA_21'] = df_15m['close'].ewm(span=21, adjust=False).mean()

                prev_row = df_15m.iloc[-2]
                last_row = df_15m.iloc[-1]
                current_price = last_row['close']

                bullish_crossover = (prev_row['EMA_9'] <= prev_row['EMA_21']) and (last_row['EMA_9'] > last_row['EMA_21'])
                bearish_crossover = (prev_row['EMA_9'] >= prev_row['EMA_21']) and (last_row['EMA_9'] < last_row['EMA_21'])

                if not bullish_crossover and not bearish_crossover:
                    continue

                # 1-საათიანი ტრენდის ფილტრი
                ohlcv_1h = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
                df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_1h['EMA_9'] = df_1h['close'].ewm(span=9, adjust=False).mean()
                df_1h['EMA_21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
                h1_row = df_1h.iloc[-1]
                h1_bullish = h1_row['EMA_9'] > h1_row['EMA_21']
                h1_bearish = h1_row['EMA_9'] < h1_row['EMA_21']

                # 4-საათიანი ტრენდის ფილტრი
                ohlcv_4h = await exchange.fetch_ohlcv(symbol, timeframe='4h', limit=50)
                df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_4h['EMA_9'] = df_4h['close'].ewm(span=9, adjust=False).mean()
                df_4h['EMA_21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
                h4_row = df_4h.iloc[-1]
                h4_bullish = h4_row['EMA_9'] > h4_row['EMA_21']
                h4_bearish = h4_row['EMA_9'] < h4_row['EMA_21']

                signal_text = None

                # LONG სიგნალი (რისკი 1%, TP 1.5% -> ანუ 1:1.5 თანაფარდობა)
                if bullish_crossover and h1_bullish and h4_bullish:
                    risk_percent = 0.01   # 1% სტოპ-ლოსი
                    reward_percent = 0.015 # 1.5% თეიქ-პროფიტი (1:1.5)
                    
                    sl = current_price * (1 - risk_percent)
                    tp = current_price * (1 + reward_percent)
                    
                    active_signals.append({'symbol': symbol, 'type': 'LONG', 'entry': current_price, 'tp': tp, 'sl': sl})
                    stats_data["total_signals"] += 1
                    signal_text = (
                        f"🚀 **LONG SIGNAL (15m EMA 9/21 + 1h/4h Trend)**\n"
                        f"🪙 წყვილი: `{symbol}`\n"
                        f"🟢 შესვლა (Entry): `{current_price}`\n"
                        f"🎯 Take Profit (TP): `{tp:.4f}` (1:1.5)\n"
                        f"🛑 Stop Loss (SL): `{sl:.4f}`"
                    )

                # SHORT სიგნალი (რისკი 1%, TP 1.5% -> ანუ 1:1.5 თანაფარდობა)
                elif bearish_crossover and h1_bearish and h4_bearish:
                    risk_percent = 0.01   # 1% სტოპ-ლოსი
                    reward_percent = 0.015 # 1.5% თეიქ-პროფიტი (1:1.5)
                    
                    sl = current_price * (1 + risk_percent)
                    tp = current_price * (1 - reward_percent)
                    
                    active_signals.append({'symbol': symbol, 'type': 'SHORT', 'entry': current_price, 'tp': tp, 'sl': sl})
                    stats_data["total_signals"] += 1
                    signal_text = (
                        f"📉 **SHORT SIGNAL (15m EMA 9/21 + 1h/4h Trend)**\n"
                        f"🪙 წყვილი: `{symbol}`\n"
                        f"🔴 შესვლა (Entry): `{current_price}`\n"
                        f"🎯 Take Profit (TP): `{tp:.4f}` (1:1.5)\n"
                        f"🛑 Stop Loss (SL): `{sl:.4f}`"
                    )

                if signal_text and TELEGRAM_CHAT_ID:
                    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=signal_text, parse_mode="Markdown")
            except Exception as sym_err:
                logger.error(f"სიმბოლოს დამუშავების შეცდომა {symbol}: {sym_err}")

    except Exception as e:
        logger.error(f"სტრატეგიის ზოგადი შეცდომა: {e}")
    finally:
        await exchange.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Nexus სავაჭრო ბოტი (15m მონიტორინგი + 1:1.5 TP/SL) წარმატებით გააქტიურდა!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = stats_data["total_signals"]
    wins = stats_data["wins"]
    losses = stats_data["losses"]
    win_rate = (wins / total * 100) if total > 0 else 0

    stats_text = (
        f"📊 **Nexus (EMA 9/21) სავაჭრო სტატისტიკა:**\n\n"
        f"🔹 სულ სიგნალი: `{total}`\n"
        f"✅ მოგებული (TP): `{wins}`\n"
        f"❌ წაგებული (SL): `{losses}`\n"
        f"📈 Win Rate: `{win_rate:.1f}%`\n"
        f"🔄 ღია პოზიციები: `{len(active_signals)}`"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN არ არის მითითებული!")
        return

    # HTTP სერვერი Railway-სთვის
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))

    job_queue = application.job_queue
    if job_queue:
        # სტრატეგია ამოწმებს ყოველ 15 წუთში (900 წამში)
        job_queue.run_repeating(check_ema_strategy, interval=900, first=10)
        # Heartbeat ყოველ 1 საათში ერთხელ (3600 წამი)
        job_queue.run_repeating(send_heartbeat, interval=3600, first=15)

    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
