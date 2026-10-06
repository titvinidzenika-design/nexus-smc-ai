import os
import asyncio
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

# მარტივი Web სერვერი Render-ის Health Check-ისთვის
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus SMC AI Engine is Running 24/7!")

    def log_message(self, format, *args):
        return  # ლოგების გასასუფთავებლად

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
SUBSCRIBED_USERS = set()

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=30):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return None

def analyze_symbol(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=30)
    if not candles or len(candles) < 15:
        return None

    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]

    current_price = closes[-1]
    score = 60
    direction = "LONG"
    factors = []

    if current_price > sum(closes[-5:]) / 5:
        score += 20
        factors.append("📈 **HTF Trend:** Bullish Momentum (+20%)")
    else:
        direction = "SHORT"
        score += 20
        factors.append("📉 **HTF Trend:** Bearish Momentum (+20%)")

    if lows[-1] > highs[-3]:
        score += 20
        factors.append("⚡ **SMC Imbalance:** Bullish FVG Detected (+20%)")

    sl = round(min(lows[-5:]) * 0.999, 2) if direction == "LONG" else round(max(highs[-5:]) * 1.001, 2)
    tp1 = round(current_price + (current_price - sl) * 1.5, 2) if direction == "LONG" else round(current_price - (sl - current_price) * 1.5, 2)

    return {
        "symbol": symbol_display,
        "direction": direction,
        "score": score,
        "price": current_price,
        "sl": sl,
        "tp1": tp1,
        "factors": factors
    }

async def auto_scan_loop(context: ContextTypes.DEFAULT_TYPE):
    if not SUBSCRIBED_USERS:
        return
    symbols = [("BTCUSDT", "BTC/USDT")]
    for s_raw, s_disp in symbols:
        res = analyze_symbol(s_raw, s_disp)
        if res and res["score"] >= 80:
            factors_text = "\n".join(res["factors"])
            msg = f"🤖 **NEXUS SMC AI SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`"
            for u_id in SUBSCRIBED_USERS:
                try:
                    await context.bot.send_message(chat_id=u_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Error sending msg: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SUBSCRIBED_USERS.add(update.effective_chat.id)
    await update.message.reply_text("🤖 **Nexus SMC AI Active 24/7!**\n\nბოტი დაიწყებს ავტომატურ სკანირებას (BTC/USDT).", parse_mode="Markdown")

def main():
    # Web სერვერის გაშვება ცალკე Thread-ში
    Thread(target=run_web_server, daemon=True).start()
    
    if not TELEGRAM_BOT_TOKEN:
        logging.error("❌ CRITICAL ERROR: TELEGRAM_BOT_TOKEN is missing!")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    if application.job_queue:
        application.job_queue.run_repeating(auto_scan_loop, interval=60, first=5)

    logging.info("🚀 Nexus SMC AI Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()


