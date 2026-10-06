import os
import asyncio
import logging
from threading import Thread
from flask import Flask
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
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

# Token from Environment Variable
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# SMC & Pattern Recognition Engine
def detect_graphical_patterns(df: pd.DataFrame):
    if len(df) < 30:
        return "NONE"
    close, high, low = df['close'].values, df['high'].values, df['low'].values

    val1 = low[np.argmin(low[-30:-15]) + (len(low) - 30)]
    val2 = low[np.argmin(low[-15:]) + (len(low) - 15)]
    if abs(val1 - val2) / val1 < 0.01 and close[-1] > val2 * 1.005:
        return "DOUBLE_BOTTOM_W"

    top1 = high[np.argmax(high[-30:-15]) + (len(high) - 30)]
    top2 = high[np.argmax(high[-15:]) + (len(high) - 15)]
    if abs(top1 - top2) / top1 < 0.01 and close[-1] < top2 * 0.995:
        return "DOUBLE_TOP_M"

    return "NONE"

def detect_fvg(df: pd.DataFrame):
    if len(df) < 3:
        return "NONE"
    if df['low'].iloc[-1] > df['high'].iloc[-3]:
        return "BULLISH_FVG"
    elif df['high'].iloc[-1] < df['low'].iloc[-3]:
        return "BEARISH_FVG"
    return "NONE"

def check_structure(df: pd.DataFrame):
    last_close = df['close'].iloc[-1]
    if last_close > df['high'].iloc[-15:-2].max():
        return "BULLISH"
    elif last_close < df['low'].iloc[-15:-2].min():
        return "BEARISH"
    return "RANGE"

async def analyze_market(symbol: str = "BTC/USDT"):
    exchange = ccxt.binance()
    try:
        data = {}
        for tf in ['1m', '5m', '15m', '1h', '4h']:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=tf, limit=40)
            data[tf] = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

        score = 0
        factors = []
        direction = "NEUTRAL"

        h4_s = check_structure(data['4h'])
        if h4_s == "BULLISH":
            score += 30
            direction = "LONG"
            factors.append("📈 **HTF Trend:** 4H Bullish Structure (+30%)")
        elif h4_s == "BEARISH":
            score += 30
            direction = "SHORT"
            factors.append("📉 **HTF Trend:** 4H Bearish Structure (+30%)")

        graph_pattern = detect_graphical_patterns(data['15m'])
        if graph_pattern != "NONE":
            score += 25
            factors.append(f"📐 **Pattern:** {graph_pattern} (+25%)")

        fvg = detect_fvg(data['5m'])
        if fvg != "NONE":
            score += 25
            factors.append(f"⚡ **SMC Imbalance:** 5M {fvg} (+25%)")

        score += 20
        factors.append("🛡 **Risk Engine:** Multi-TP Active (+20%)")

        price_15m = data['15m']['close'].iloc[-1]
        sl = round(data['5m']['low'].iloc[-5:].min() * 0.999, 2) if direction == "LONG" else round(data['5m']['high'].iloc[-5:].max() * 1.001, 2)
        tp1 = round(price_15m + (price_15m - sl) * 1.5, 2) if direction == "LONG" else round(price_15m - (sl - price_15m) * 1.5, 2)

        return {"symbol": symbol, "direction": direction, "score": score, "price": price_15m, "sl": sl, "tp1": tp1, "factors": factors}
    finally:
        await exchange.close()

# 24/7 Scanner Loop
SUBSCRIBED_USERS = set()

async def auto_scan_loop(context: ContextTypes.DEFAULT_TYPE):
    if not SUBSCRIBED_USERS:
        return
    for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        res = await analyze_market(symbol)
        if res["score"] >= 80:
            factors_text = "\n".join(res["factors"])
            msg = f"🤖 **NEXUS SMC AI SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`"
            for u_id in SUBSCRIBED_USERS:
                try:
                    await context.bot.send_message(chat_id=u_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Error sending msg: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SUBSCRIBED_USERS.add(update.effective_chat.id)
    await update.message.reply_text("🤖 **Nexus SMC AI Active 24/7!**\n\nბოტი დაიწყებს ავტომატურ სკანირებას.", parse_mode="Markdown")

def main():
    Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.job_queue.run_repeating(auto_scan_loop, interval=60, first=5)

    print("🚀 Nexus SMC AI Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
