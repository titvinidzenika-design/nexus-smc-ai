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
        self.wfile.write(b"Nexus Multi-TF SMC Engine is Live!")

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

# ----- Global News -----
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
    return "📰 **Global News:** ბაზარზე სტაბილური სიტუაციაა."

# ----- Binance Data Multi-TF -----
def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Binance fetch error: {e}")
        return None

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
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

# ----- Multi-Timeframe Institutional SMC Analysis -----
def analyze_multi_timeframe(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles_1h = fetch_binance_ohlcv(symbol=symbol_raw, interval="1h", limit=50)
    candles_15m = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=60)

    if not candles_1h or not candles_15m:
        return None

    # 1H HTF Trend Check
    closes_1h = [float(c[4]) for c in candles_1h]
    ema_200_1h = sum(closes_1h[-50:]) / 50
    current_price = closes_15m[-1][4] = float(candles_15m[-1][4])

    htf_trend = "BULLISH" if current_price > ema_200_1h else "BEARISH"

    # 15M LTF Execution & Liquidity Analysis
    closes_15m = [float(c[4]) for c in candles_15m]
    highs_15m = [float(c[2]) for c in candles_15m]
    lows_15m = [float(c[3]) for c in candles_15m]
    volumes_15m = [float(c[5]) for c in candles_15m]

    score = 30
    factors = []
    direction = htf_trend

    # HTF Trend Alignment
    if htf_trend == "BULLISH":
        score += 25
        factors.append("🌐 **1H HTF Trend:** Bullish Structure (+25%)")
    else:
        score += 25
        factors.append("🌐 **1H HTF Trend:** Bearish Structure (+25%)")

    # Liquidity Sweep Check (წინა დაბალი/მაღალი წერტილის მოხსნა)
    prev_low = min(lows_15m[-15:-3])
    prev_high = max(highs_15m[-15:-3])

    if htf_trend == "BULLISH" and lows_15m[-1] < prev_low and closes_15m[-1] > prev_low:
        score += 25
        factors.append("🎯 **Liquidity Sweep:** Bullish Liquidity Grab (+25%)")
    elif htf_trend == "BEARISH" and highs_15m[-1] > prev_high and closes_15m[-1] < prev_high:
        score += 25
        factors.append("🎯 **Liquidity Sweep:** Bearish Liquidity Grab (+25%)")

    # FVG / Imbalance Confirmation
    if htf_trend == "BULLISH" and lows_15m[-1] > highs_15m[-3]:
        score += 20
        factors.append("⚡ **15M FVG:** Bullish Fair Value Gap (+20%)")
    elif htf_trend == "BEARISH" and highs_15m[-1] < lows_15m[-3]:
        score += 20
        factors.append("⚡ **15M FVG:** Bearish Fair Value Gap (+20%)")

    # RSI & Volume Spike
    rsi = calculate_rsi(closes_15m)
    avg_vol = sum(volumes_15m[-10:-1]) / 9
    if volumes_15m[-1] > avg_vol * 1.2:
        score += 10
        factors.append("🔥 **Volume:** Institutional Volume Spike (+10%)")

    sl = round(min(lows_15m[-5:]) * 0.998, 2) if direction == "BULLISH" else round(max(highs_15m[-5:]) * 1.002, 2)
    tp1 = round(current_price + (current_price - sl) * 2.0, 2) if direction == "BULLISH" else round(current_price - (sl - current_price) * 2.0, 2)

    return {
        "symbol": symbol_display,
        "direction": "LONG" if direction == "BULLISH" else "SHORT",
        "htf_trend": htf_trend,
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
                            send_telegram_message(chat_id, "🤖 **Nexus Multi-TF SMC Engine Active!**\n\nანალიზდება: 1H HTF Trend + 15M Liquidity Sweep + FVG + Volume.\n\n🔍 **ვასკანირებ ბაზარს...**")
                            
                            res = analyze_multi_timeframe("BTCUSDT", "BTC/USDT")
                            news_info = fetch_latest_crypto_news()
                            
                            if res and res["score"] >= 80:
                                factors_text = "\n".join(res["factors"])
                                msg = f"🤖 **NEXUS MULTI-TF SMC SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **1H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1 (1:2 R:R):** `${res['tp1']}`\n\n🌐 {news_info}"
                                send_telegram_message(chat_id, msg)
                            else:
                                send_telegram_message(chat_id, f"ℹ️ ამ ეტაპზე 1H/15M სინქრონული სიგნალი (80%+) არ არის (Score: `{res['score'] if res else 0}%`, 1H Trend: `{res['htf_trend'] if res else 'N/A'}`).\n\n🌐 {news_info}")
        except Exception as e:
            logging.error(f"Polling error: {e}")
        time.sleep(2)

# ----- 15 Min Loop -----
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
                        msg = f"🤖 **NEXUS MULTI-TF SMC SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **1H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1 (1:2 R:R):** `${res['tp1']}`\n\n🌐 {news_info}"
                        for u_id in list(subscribed_users):
                            send_telegram_message(u_id, msg)
        except Exception as e:
            logging.error(f"Scan error: {e}")
        time.sleep(900)

if __name__ == "__main__":
    Thread(target=run_web_server, daemon=True).start()
    subscribed_users = set()
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    logging.info("🚀 Nexus Multi-TF SMC Engine Started...")
    poll_telegram_updates(subscribed_users)
