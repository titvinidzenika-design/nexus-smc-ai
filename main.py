import os
import asyncio
import logging
import requests
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

# Dummy Web Server for Render Free Tier
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Nexus SMC AI Engine is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

SUBSCRIBED_USERS = set()

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=30):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return data
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

    # Simple SMC/Structure Check
    if current_price > sum(closes[-5:]) / 5:
        score += 20
        factors.append("📈 **HTF Trend:** Bullish Momentum (+20%)")
    else:
        direction = "SHORT"
        score += 20
        factors.append("📉 **HTF Trend:** Bearish Momentum (+20%)")

    # FVG Check
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
    Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.job_queue.run_repeating(auto_scan_loop, interval=60, first=5)

    print("🚀 Nexus SMC AI Started...")
    app.run_polling()

if __name__ == "__main__":
    main()

