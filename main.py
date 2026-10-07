import os
import time
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

# 1. USERS PERSISTENCE (მომხმარებლების ფაილში შენახვა)
USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error loading users: {e}")
    return set()

def save_users(users):
    try:
        with open(USER_FILE, "w") as f:
            json.dump(list(users), f)
    except Exception as e:
        logging.error(f"Error saving users: {e}")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus Ultra-Precision SMC Engine is Live!")

    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def keep_alive():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    while True:
        time.sleep(600)
        if render_url:
            try:
                requests.get(render_url, timeout=10)
            except Exception as e:
                logging.error(f"Keep-alive error: {e}")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error sending msg: {e}")

# ----- News Fetcher -----
def fetch_latest_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies=BTC&filter=important"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                latest = results[0]
                title = latest.get("title", "")
                votes = latest.get("votes", {})
                bullish, bearish = votes.get("positive", 0), votes.get("negative", 0)
                
                sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                if bullish > bearish: sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ"
                elif bearish > bullish: sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ"

                return f"📰 **Global News:** _{title}_\n💡 **Sentiment:** {sentiment}"
    except Exception as e:
        logging.error(f"News error: {e}")
    return "📰 **Global News:** ბაზარზე სტაბილური სიტუაციაა."

# ----- Technical Calculations -----
def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Binance fetch error: {e}")
        return None

def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return 100.0
    tr_list = []
    for i in range(1, len(candles)):
        high = float(candles[i][2])
        low = float(candles[i][3])
        prev_close = float(candles[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return sum(tr_list[-period:]) / period

# ----- Precision SMC Engine -----
def analyze_multi_timeframe(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles_1h = fetch_binance_ohlcv(symbol=symbol_raw, interval="1h", limit=60)
    candles_15m = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=60)

    if not candles_1h or not candles_15m:
        return None

    closes_1h = [float(c[4]) for c in candles_1h]
    ema_200_1h = sum(closes_1h[-50:]) / 50
    current_price = float(candles_15m[-1][4])

    htf_trend = "BULLISH" if current_price > ema_200_1h else "BEARISH"

    closes_15m = [float(c[4]) for c in candles_15m]
    highs_15m = [float(c[2]) for c in candles_15m]
    lows_15m = [float(c[3]) for c in candles_15m]
    volumes_15m = [float(c[5]) for c in candles_15m]

    score = 30
    factors = []
    direction = htf_trend

    # HTF Trend
    score += 25
    factors.append(f"🌐 **1H HTF Trend:** {htf_trend.capitalize()} (+25%)")

    # Liquidity Sweep Check
    prev_low = min(lows_15m[-20:-3])
    prev_high = max(highs_15m[-20:-3])

    if htf_trend == "BULLISH" and lows_15m[-2] < prev_low and closes_15m[-1] > prev_low:
        score += 25
        factors.append("🎯 **Liquidity Sweep:** Bullish Liquidity Grab (+25%)")
    elif htf_trend == "BEARISH" and highs_15m[-2] > prev_high and closes_15m[-1] < prev_high:
        score += 25
        factors.append("🎯 **Liquidity Sweep:** Bearish Liquidity Grab (+25%)")

    # Accurate 3-Candle FVG Check
    if htf_trend == "BULLISH" and lows_15m[-1] > highs_15m[-3]:
        score += 20
        factors.append("⚡ **15M FVG:** Valid Bullish Imbalance (+20%)")
    elif htf_trend == "BEARISH" and highs_15m[-1] < lows_15m[-3]:
        score += 20
        factors.append("⚡ **15M FVG:** Valid Bearish Imbalance (+20%)")

    # Volume Spike
    avg_vol = sum(volumes_15m[-10:-1]) / 9
    if volumes_15m[-1] > avg_vol * 1.3:
        score += 10
        factors.append("🔥 **Volume:** Institutional Volume Spike (+10%)")

    # ATR Dynamic Stop Loss Calculation
    atr = calculate_atr(candles_15m)
    if direction == "BULLISH":
        sl = round(current_price - (atr * 1.5), 2)
        tp1 = round(current_price + ((current_price - sl) * 2.0), 2)
    else:
        sl = round(current_price + (atr * 1.5), 2)
        tp1 = round(current_price - ((sl - current_price) * 2.0), 2)

    return {
        "symbol": symbol_display,
        "direction": "LONG" if direction == "BULLISH" else "SHORT",
        "htf_trend": htf_trend,
        "score": score,
        "price": current_price,
        "sl": sl,
        "tp1": tp1,
        "factors": factors
    }

# ----- Telegram Polling -----
def poll_telegram_updates(subscribed_users):
    offset = 0
    while True:
        try:
            if TELEGRAM_BOT_TOKEN:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
                res = requests.get(url, timeout=35).json()
                if res.get("ok"):
                    for result in res.get("result", []):
                        offset = result["update_id"] + 1
                        message = result.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "")
                        
                        if text == "/start" and chat_id:
                            if chat_id not in subscribed_users:
                                subscribed_users.add(chat_id)
                                save_users(subscribed_users)
                            
                            send_telegram_message(chat_id, "🤖 **Nexus Ultra-Precision SMC Engine Active!**\n\nანალიზდება: ATR SL/TP + Multi-TF Trend + FVG + News.\n\n🔍 **ვასკანირებ ბაზარს...**")
                            
                            res = analyze_multi_timeframe("BTCUSDT", "BTC/USDT")
                            news_info = fetch_latest_crypto_news()
                            
                            if res and res["score"] >= 80:
                                factors_text = "\n".join(res["factors"])
                                msg = f"🤖 **NEXUS PRECISION SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **1H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **ATR SL:** `${res['sl']}`\n🎯 **TP1 (1:2 R:R):** `${res['tp1']}`\n\n🌐 {news_info}"
                                send_telegram_message(chat_id, msg)
                            else:
                                send_telegram_message(chat_id, f"ℹ️ ამ ეტაპზე 80%+ სიგნალი არ არის (Score: `{res['score'] if res else 0}%`).\n\n🌐 {news_info}")
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(5)
        time.sleep(1)

# ----- Scan Loop -----
def scan_loop(subscribed_users):
    last_signal_price = 0
    while True:
        try:
            if subscribed_users:
                res = analyze_multi_timeframe("BTCUSDT", "BTC/USDT")
                if res and res["score"] >= 80:
                    if abs(res["price"] - last_signal_price) > 80:
                        last_signal_price = res["price"]
                        news_info = fetch_latest_crypto_news()
                        factors_text = "\n".join(res["factors"])
                        msg = f"🤖 **NEXUS PRECISION SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **1H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **ATR SL:** `${res['sl']}`\n🎯 **TP1 (1:2 R:R):** `${res['tp1']}`\n\n🌐 {news_info}"
                        for u_id in list(subscribed_users):
                            send_telegram_message(u_id, msg)
        except Exception as e:
            logging.error(f"Scan error: {e}")
        time.sleep(900)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    
    subscribed_users = load_users()
    
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    logging.info("🚀 Nexus Ultra-Precision Engine Started...")
    poll_telegram_updates(subscribed_users)
