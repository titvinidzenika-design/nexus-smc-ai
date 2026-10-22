import math
import os
import time
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock

logging.basicConfig(level=logging.INFO)

USER_FILE = "users.json"
STATS_FILE = "stats.json"

file_lock = Lock()

def load_json(filepath, default):
    with file_lock:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading {filepath}: {e}")
    return default

def save_json(filepath, data):
    with file_lock:
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving {filepath}: {e}")

def format_price(val):
    if val is None:
        return 0.0
    val = float(val)
    if val < 1.0:
        return round(val, 8)
    return round(val, 2)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus Multi-TF ALMA/EMA Scalping Engine is Live!")

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
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error sending msg: {e}")

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logging.error(f"Binance fetch error ({symbol} {interval}): {e}")
    return None

def calculate_alma(prices, window=200, offset=0.7, sigma=20.0):
    if len(prices) < window:
        window = len(prices)
    if window < 2:
        return prices[-1]
    
    m = math.floor(offset * (window - 1))
    s = window / sigma if sigma != 0 else 1.0
    weights = []
    sum_weights = 0
    
    for i in range(window):
        w = math.exp(-((i - m) ** 2) / (2 * (s ** 2))) if s > 0 else 1.0
        weights.append(w)
        sum_weights += w
        
    sub_prices = prices[-window:]
    if sum_weights == 0:
        return sub_prices[-1]
    return sum(p * w for p, w in zip(sub_prices, weights)) / sum_weights

def calculate_ema(prices, period):
    if len(prices) < period:
        return prices[-1]
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def analyze_market(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    # ტაიმფრეიმები: 15m (სკალპინგი), 1h (იმპულსი), 4h (ტრენდი)
    candles_15m = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=100)
    candles_1h = fetch_binance_ohlcv(symbol=symbol_raw, interval="1h", limit=50)
    candles_4h = fetch_binance_ohlcv(symbol=symbol_raw, interval="4h", limit=50)

    if not candles_15m or not candles_1h or not candles_4h:
        return None

    closes_15m = [float(c[4]) for c in candles_15m]
    closes_1h = [float(c[4]) for c in candles_1h]
    closes_4h = [float(c[4]) for c in candles_4h]
    current_price = closes_15m[-1]

    # 1. გრძელვადიანი ტრენდის ფილტრი ALMA (200, 0.7, 20) 4H და 1H ტაიმფრეიმზე
    alma_200_4h = calculate_alma(closes_4h, window=min(200, len(closes_4h)), offset=0.7, sigma=20.0)
    trend_4h = "LONG" if closes_4h[-1] > alma_200_4h else "SHORT"

    alma_200_1h = calculate_alma(closes_1h, window=min(200, len(closes_1h)), offset=0.7, sigma=20.0)
    trend_1h = "LONG" if closes_1h[-1] > alma_200_1h else "SHORT"

    # 2. 15 წუთიანი სკალპინგი EMA 9 / 21 გადაკვეთით
    ema_9_15m = calculate_ema(closes_15m, 9)
    ema_21_15m = calculate_ema(closes_15m, 21)
    scalp_dir = "LONG" if ema_9_15m > ema_21_15m else "SHORT"

    # ტრენდის საპირისპირო სიგნალების მკაცრი ბლოკირება
    if trend_4h != scalp_dir or trend_1h != scalp_dir:
        logging.info(f"[{symbol_display}] Filtered: Counter-trend signal blocked (4H Trend: {trend_4h}, 1H Trend: {trend_1h}, Scalp: {scalp_dir})")
        return None

    score = 75 # რადგან ტრენდი და სკალპინგი ემთხვევა
    factors = [
        f"🟢 **4H Trend (ALMA 200):** {trend_4h}",
        f"🟢 **1H Trend (ALMA 200):** {trend_1h}",
        f"⚡ **15M Scalp (EMA 9/21):** {scalp_dir} Crossover"
    ]

    # Risk/Reward გათვლა: 1:1.5 დან 1:2.0 მდე
    risk = current_price * 0.01  # 1% რისკი SL-ისთვის
    if scalp_dir == "LONG":
        sl = format_price(current_price - risk)
        tp1 = format_price(current_price + (risk * 1.5)) # TP1 -> 1:1.5
        tp2 = format_price(current_price + (risk * 2.0)) # TP2 -> 1:2.0
    else:
        sl = format_price(current_price + risk)
        tp1 = format_price(current_price - (risk * 1.5)) # TP1 -> 1:1.5
        tp2 = format_price(current_price - (risk * 2.0)) # TP2 -> 1:2.0

    return {
        "raw_symbol": symbol_raw,
        "symbol": symbol_display,
        "direction": scalp_dir,
        "score": score,
        "price": format_price(current_price),
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "factors": factors
    }

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

                        if chat_id and text == "/start":
                            if chat_id not in subscribed_users:
                                subscribed_users.add(chat_id)
                                save_json(USER_FILE, list(subscribed_users))
                            send_telegram_message(chat_id, "🤖 **Nexus Scalp Engine Active!**\n\n📊 ალგორითმი მუშაობს: ALMA (200/0.7/20) + EMA 9/21 სკალპინგი. ტრენდის საპირისპირო სიგნალები დაბლოკილია.")
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(5)
        time.sleep(1)

def heartbeat_loop(subscribed_users):
    """საათობრივი მიმოხილვა (Heartbeat) ბოტის მუშაობის შესამოწმებლად"""
    while True:
        time.sleep(3600) # ყოველ 1 საათში
        if subscribed_users:
            msg = "🛡️ **Nexus ბოტის საათობრივი ანგარიში**\n\n⏱️ სტატუსი: სისტემა მუშაობს რეჟიმში 24/7.\n🔍 აქტივები: BTC, SOL, HYPE კონტროლქვეშაა (ტრენდული ფილტრი აქტიურია)."
            for u_id in list(subscribed_users):
                send_telegram_message(u_id, msg)

def scan_loop(subscribed_users):
    assets = [
        {"raw": "BTCUSDT", "display": "BTC/USDT"},
        {"raw": "SOLUSDT", "display": "SOL/USDT"},
        {"raw": "HYPEUSDT", "display": "HYPE/USDT"}
    ]

    while True:
        try:
            if subscribed_users:
                for asset in assets:
                    res = analyze_market(asset["raw"], asset["display"])
                    if res:
                        factors_text = "\n".join(res["factors"])
                        msg = f"🚀 **NEXUS SCALP SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **SL:** `${res['sl']}`\n🎯 **TP1 (1:1.5):** `${res['tp1']}`\n🎯 **TP2 (1:2.0):** `${res['tp2']}`"
                        
                        for u_id in list(subscribed_users):
                            send_telegram_message(u_id, msg)
                    time.sleep(5)
        except Exception as e:
            logging.error(f"Scan error: {e}")
        python_interval = 180 # 3 წუთიანი სკანირების ციკლი
        time.sleep(python_interval)

if __name__ == "__main__":
    subscribed_users = set(load_json(USER_FILE, []))
    Thread(target=poll_telegram_updates, args=(subscribed_users,), daemon=True).start()
    Thread(target=heartbeat_loop, args=(subscribed_users,), daemon=True).start()
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    run_web_server()
