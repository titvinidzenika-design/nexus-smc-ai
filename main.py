import os
import time
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

# Web Server Render-ის პორტისთვის
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

# ----- გლობალური სიახლეების მიღების ფუნქცია -----
def fetch_latest_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies=BTC&filter=important"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            if results:
                latest = results[0]
                title = latest.get("title", "No title")
                votes = latest.get("votes", {})
                bullish = votes.get("positive", 0)
                bearish = votes.get("negative", 0)
                
                sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                if bullish > bearish:
                    sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ (Positive)"
                elif bearish > bullish:
                    sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ (Negative)"

                return f"📰 **Global Market News:**\n_{title}_\n💡 **Market Sentiment:** {sentiment}"
    except Exception as e:
        logging.error(f"Error fetching news: {e}")
    
    return "📰 **Global Market News:** სიახლეები სტაბილურია (კრიტიკული ნიუსი არ ფიქსირდება)."

# ----- Binance მონაცემების მიღება -----
def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=30):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Error fetching binance data: {e}")
        return None

# ----- SMC ტექნიკური ანალიზი -----
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

# ----- Telegram-ის შეტყობინებების მიღება -----
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
                            send_telegram_message(chat_id, "🤖 **Nexus SMC AI Active 24/7!**\n\nბოტი აანალიზებს SMC ტექნიკურ მონაცემებს + გლობალურ სიახლეებს ყოველ 15 წუთში.\n\n🔍 **ვასკანირებ ბაზარს...**")
                            
                            res = analyze_symbol("BTCUSDT", "BTC/USDT")
                            news_info = fetch_latest_crypto_news()
                            
                            if res and res["score"] >= 80:
                                factors_text = "\n".join(res["factors"])
                                msg = f"🤖 **NEXUS SMC AI SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n\n🌐 {news_info}"
                                send_telegram_message(chat_id, msg)
                            else:
                                send_telegram_message(chat_id, f"ℹ️ ამ ეტაპზე ტექნიკური სიგნალი (80%+) არ არის (Score: `{res['score'] if res else 0}%`).\n\n🌐 {news_info}")
        except Exception as e:
            logging.error(f"Polling error: {e}")
        time.sleep(2)

# ----- ავტომატური სკანირების ციკლი (15 წუთში ერთხელ) -----
def scan_loop(subscribed_users):
    while True:
        try:
            if subscribed_users:
                res = analyze_symbol("BTCUSDT", "BTC/USDT")
                if res and res["score"] >= 80:
                    news_info = fetch_latest_crypto_news()
                    factors_text = "\n".join(res["factors"])
                    msg = f"🤖 **NEXUS SMC AI SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n\n🌐 {news_info}"
                    for u_id in list(subscribed_users):
                        send_telegram_message(u_id, msg)
        except Exception as e:
            logging.error(f"Scan loop error: {e}")
        time.sleep(900)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    
    subscribed_users = set()
    
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    
    logging.info("🚀 Nexus SMC AI Engine Started...")
    poll_telegram_updates(subscribed_users)
