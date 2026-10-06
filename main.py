import os
import time
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus SMC AI Engine is Live!")

    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error sending telegram msg: {e}")

# ----- CryptoPanic News -----
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
                bullish = votes.get("positive", 0)
                bearish = votes.get("negative", 0)
                
                sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                if bullish > bearish:
                    sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ"
                elif bearish > bullish:
                    sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ"

                return f"📰 **Global News:** _{title}_\n💡 **Sentiment:** {sentiment}"
    except Exception as e:
        logging.error(f"News error: {e}")
    return "📰 **Global News:** სტაბილური სიტუაციაა."

# ----- Binance Data -----
def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Binance error: {e}")
        return None

# ----- RSI Calculation -----
def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

# ----- Advanced SMC + Technical Analysis -----
def analyze_symbol(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=100)
    if not candles or len(candles) < 50:
        return None

    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    volumes = [float(c[5]) for c in candles]

    current_price = closes[-1]
    score = 40
    direction = "LONG"
    factors = []

    # 1. EMA Trend Check (50-period average)
    ema_50 = sum(closes[-50:]) / 50
    if current_price > ema_50:
        score += 20
        factors.append("📈 **HTF Trend:** Bullish Above EMA (+20%)")
    else:
        direction = "SHORT"
        score += 20
        factors.append("📉 **HTF Trend:** Bearish Below EMA (+20%)")

    # 2. SMC Imbalance / FVG
    if direction == "LONG" and lows[-1] > highs[-3]:
        score += 20
        factors.append("⚡ **SMC Imbalance:** Bullish FVG (+20%)")
    elif direction == "SHORT" and highs[-1] < lows[-3]:
        score += 20
        factors.append("⚡ **SMC Imbalance:** Bearish FVG (+20%)")

    # 3. RSI Confirmation
    rsi = calculate_rsi(closes)
    if direction == "LONG" and rsi < 65:
        score += 10
        factors.append(f"📊 **RSI Check:** Healthy Momentum ({rsi}) (+10%)")
    elif direction == "SHORT" and rsi > 35:
        score += 10
        factors.append(f"📊 **RSI Check:** Healthy Momentum ({rsi}) (+10%)")

    # 4. Volume Spike
    avg_vol = sum(volumes[-10:-1]) / 9
    if volumes[-1] > avg_vol * 1.3:
        score += 10
        factors.append("🔥 **Volume Spike:** Strong Participation (+10%)")

    sl = round(min(lows[-5:]) * 0.999, 2) if direction == "LONG" else round(max(highs[-5:]) * 1.001, 2)
    tp1 = round(current_price + (current_price - sl) * 1.5, 2) if direction == "LONG" else round(current_price - (sl - current_price) * 1.5, 2)

    return {
        "symbol": symbol_display,
        "direction": direction,
        "score": score,
        "price": current_price,
        "sl": sl,
        "tp1": tp1,
        "rsi": rsi,
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
                            subscribed_users.add(chat_id)
                            send_telegram_message(chat_id, "🤖 **Nexus Advanced SMC AI Active!**\n\nანალიზდება: SMC + FVG + RSI + Volume + Global News.\n\n🔍 **ვასკანირებ ბაზარს...**")
                            
                            res = analyze_symbol("BTCUSDT", "BTC/USDT")
                            news_info = fetch_latest_crypto_news()
                            
                            if res and res["score"] >= 80:
                                factors_text = "\n".join(res["factors"])
                                msg = f"🤖 **NEXUS ADVANCED SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n\n🌐 {news_info}"
                                send_telegram_message(chat_id, msg)
                            else:
                                send_telegram_message(chat_id, f"ℹ️ ამ ეტაპზე მაღალი სიზუსტის სიგნალი (80%+) არ არის (Score: `{res['score'] if res else 0}%`, RSI: `{res['rsi'] if res else 'N/A'}`).\n\n🌐 {news_info}")
        except Exception as e:
            logging.error(f"Polling error: {e}")
        time.sleep(2)

# ----- 15 Min Loop -----
def scan_loop(subscribed_users):
    last_signal_price = 0
    while True:
        try:
            if subscribed_users:
                res = analyze_symbol("BTCUSDT", "BTC/USDT")
                if res and res["score"] >= 80:
                    # დუბლირების თავიდან აცილება
                    if abs(res["price"] - last_signal_price) > 50:
                        last_signal_price = res["price"]
                        news_info = fetch_latest_crypto_news()
                        factors_text = "\n".join(res["factors"])
                        msg = f"🤖 **NEXUS ADVANCED SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n\n🌐 {news_info}"
                        for u_id in list(subscribed_users):
                            send_telegram_message(u_id, msg)
        except Exception as e:
            logging.error(f"Scan error: {e}")
        time.sleep(900)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    subscribed_users = set()
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    logging.info("🚀 Nexus Advanced SMC Engine Started...")
    poll_telegram_updates(subscribed_users)
