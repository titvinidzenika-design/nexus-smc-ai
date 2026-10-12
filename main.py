import os
import time
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

USER_FILE = "users.json"
STATS_FILE = "stats.json"
ACTIVE_TRADES_FILE = "active_trades.json"

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {filepath}: {e}")
    return default

def save_json(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving {filepath}: {e}")

# ----- Health Check Server for Render & UptimeRobot -----
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus 4H-1H-15M Pro Engine is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"🚀 Web server listening on port {port}...")
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

def fetch_latest_crypto_news(symbol="BTC"):
    clean_sym = symbol.replace("USDT", "").replace("/USDT", "").split(" ")[0]
    if "PAXG" in clean_sym or "GOLD" in clean_sym:
        clean_sym = "BTC,SOL"
        
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={clean_sym}&filter=important"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                results = data.get("results", [])
                if results and isinstance(results, list):
                    latest = results[0]
                    title = latest.get("title", "")
                    votes = latest.get("votes", {})
                    if not isinstance(votes, dict):
                        votes = {}
                    bullish = votes.get("positive", 0) or 0
                    bearish = votes.get("negative", 0) or 0
                    
                    sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                    if bullish > bearish: 
                        sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ"
                    elif bearish > bullish: 
                        sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ"

                    return f"📰 **Global News:** _{title}_\n💡 **Sentiment:** {sentiment}"
    except Exception as e:
        logging.error(f"News error: {e}")
    return "📰 **Global News:** ბაზარზე სტაბილური სიტუაციაა."

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logging.error(f"Binance fetch error: {e}")
    return None

def calculate_atr(candles, period=14):
    if not candles or len(candles) < period + 1:
        return 100.0
    tr_list = []
    for i in range(1, len(candles)):
        high = float(candles[i][2])
        low = float(candles[i][3])
        prev_close = float(candles[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return sum(tr_list[-period:]) / period

# ----- ADVANCED 4H-1H-15M SMC PRO ENGINE (WITH FVG) -----
def analyze_multi_timeframe(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles_4h = fetch_binance_ohlcv(symbol=symbol_raw, interval="4h", limit=60)
    candles_1h = fetch_binance_ohlcv(symbol=symbol_raw, interval="1h", limit=60)
    candles_15m = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=60)

    if not candles_4h or not candles_1h or not candles_15m:
        return None

    closes_4h = [float(c[4]) for c in candles_4h]
    highs_4h = [float(c[2]) for c in candles_4h]
    lows_4h = [float(c[3]) for c in candles_4h]
    
    ema_200_4h = sum(closes_4h[-50:]) / 50
    current_price = float(candles_15m[-1][4])

    htf_trend = "BULLISH" if current_price > ema_200_4h else "BEARISH"

    closes_1h = [float(c[4]) for c in candles_1h]

    closes_15m = [float(c[4]) for c in candles_15m]
    highs_15m = [float(c[2]) for c in candles_15m]
    lows_15m = [float(c[3]) for c in candles_15m]
    volumes_15m = [float(c[5]) for c in candles_15m]

    score = 10
    factors = []
    direction = htf_trend

    # 1. 4H Equilibrium Zone (+20%)
    range_high_4h = max(highs_4h[-20:])
    range_low_4h = min(lows_4h[-20:])
    equilibrium = (range_high_4h + range_low_4h) / 2

    if htf_trend == "BULLISH" and current_price < equilibrium:
        score += 20
        factors.append("🟢 **4H Discount Zone:** Bought at Low Equilibrium (+20%)")
    elif htf_trend == "BEARISH" and current_price > equilibrium:
        score += 20
        factors.append("🔴 **4H Premium Zone:** Sold at High Equilibrium (+20%)")

    # 2. 1H Intermediate Momentum (+15%)
    if htf_trend == "BULLISH" and closes_1h[-1] > closes_1h[-3]:
        score += 15
        factors.append("📈 **1H Structure Alignment:** Bullish Trend Momentum (+15%)")
    elif htf_trend == "BEARISH" and closes_1h[-1] < closes_1h[-3]:
        score += 15
        factors.append("📉 **1H Structure Alignment:** Bearish Trend Momentum (+15%)")

    # 3. 15M Structure Shift (+20%)
    prev_structure_high = max(highs_15m[-15:-3])
    prev_structure_low = min(lows_15m[-15:-3])

    if htf_trend == "BULLISH" and closes_15m[-1] > prev_structure_high:
        score += 20
        factors.append("🚀 **15M Structure Shift:** Bullish Break (+20%)")
    elif htf_trend == "BEARISH" and closes_15m[-1] < prev_structure_low:
        score += 20
        factors.append("📉 **15M Structure Shift:** Bearish Break (+20%)")

    # 4. 15M Liquidity Sweep (+20%)
    if htf_trend == "BULLISH" and lows_15m[-2] < prev_structure_low and closes_15m[-1] > prev_structure_low:
        score += 20
        factors.append("🎯 **15M Liquidity Sweep:** Bullish Grab (+20%)")
    elif htf_trend == "BEARISH" and highs_15m[-2] > prev_structure_high and closes_15m[-1] < prev_structure_high:
        score += 20
        factors.append("🎯 **15M Liquidity Sweep:** Bearish Grab (+20%)")

    # 5. 15M Fair Value Gap (FVG) (+15%)
    if htf_trend == "BULLISH" and lows_15m[-1] > highs_15m[-3]:
        score += 15
        factors.append("⚡ **15M FVG Imbalance:** Bullish Gap Detected (+15%)")
    elif htf_trend == "BEARISH" and highs_15m[-1] < lows_15m[-3]:
        score += 15
        factors.append("⚡ **15M FVG Imbalance:** Bearish Gap Detected (+15%)")

    # 6. Volume Spike (+10%)
    avg_vol = sum(volumes_15m[-10:-1]) / 9
    if volumes_15m[-1] > avg_vol * 1.3:
        score += 10
        factors.append("🔥 **Volume:** Institutional Volume Spike (+10%)")

    atr = calculate_atr(candles_15m)
    if direction == "BULLISH":
        sl = round(current_price - (atr * 1.5), 2)
        risk = current_price - sl
        tp1 = round(current_price + (risk * 1.5), 2)
        tp2 = round(current_price + (risk * 2.5), 2)
    else:
        sl = round(current_price + (atr * 1.5), 2)
        risk = sl - current_price
        tp1 = round(current_price - (risk * 1.5), 2)
        tp2 = round(current_price - (risk * 2.5), 2)

    return {
        "raw_symbol": symbol_raw,
        "symbol": symbol_display,
        "direction": "LONG" if direction == "BULLISH" else "SHORT",
        "htf_trend": htf_trend,
        "score": score,
        "price": current_price,
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
                        
                        if chat_id:
                            if text == "/start":
                                if chat_id not in subscribed_users:
                                    subscribed_users.add(chat_id)
                                    save_json(USER_FILE, list(subscribed_users))
                                
                                send_telegram_message(chat_id, "🤖 **Nexus 4H-1H-15M Pro Engine Active!**\n\n🎯 **ზღვარი:** `70% Score`\n📊 ბრძანება სტატისტიკისთვის: `/stats`\n🌐 **აქტივები (24/7):** `BTC, SOL, PEPE, PAXG (Gold)`\n\n🔍 **ვასკანირებ ბაზარს...**")
                                
                                res = analyze_multi_timeframe("BTCUSDT", "BTC/USDT")
                                news_info = fetch_latest_crypto_news("BTC")
                                
                                if res and res["score"] >= 70:
                                    factors_text = "\n".join(res["factors"])
                                    msg = f"🤖 **NEXUS INSTITUTIONAL SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **4H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **ATR SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n🎯 **TP2:** `${res['tp2']}`\n\n🌐 {news_info}"
                                    send_telegram_message(chat_id, msg)
                                else:
                                    send_telegram_message(chat_id, f"ℹ️ BTC მიმდინარე სკორი: `{res['score'] if res else 0}%` (ზღვარი: 70%).\n\n🌐 {news_info}")
                            
                            elif text == "/stats":
                                stats = load_json(STATS_FILE, {"total_signals": 0, "tp1_hits": 0, "assets": {}})
                                total = stats.get("total_signals", 0)
                                tp1_hits = stats.get("tp1_hits", 0)
                                assets_cnt = stats.get("assets", {})
                                
                                stats_msg = f"📊 **NEXUS BOT STATISTICS**\n\n" \
                                            f"📌 **სულ გაგზავნილი სიგნალი:** `{total}`\n" \
                                            f"🎯 **TP1 მიღწეული (BE):** `{tp1_hits}`\n\n" \
                                            f"🔹 **აქტივების მიხედვით:**\n" \
                                            f"• BTC: `{assets_cnt.get('BTC/USDT', 0)}`\n" \
                                            f"• SOL: `{assets_cnt.get('SOL/USDT', 0)}`\n" \
                                            f"• PEPE: `{assets_cnt.get('PEPE/USDT', 0)}`\n" \
                                            f"• PAXG: `{assets_cnt.get('PAXG (Gold)/USDT', 0)}`\n\n" \
                                            f"🟢 *სისტემა მუშაობს ავტომატურ რეჟიმში (24/7).* "
                                send_telegram_message(chat_id, stats_msg)

        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(5)
        time.sleep(1)

def track_active_trades(subscribed_users):
    while True:
        try:
            active_trades = load_json(ACTIVE_TRADES_FILE, [])
            updated_trades = []
            
            for trade in active_trades:
                candles = fetch_binance_ohlcv(symbol=trade["raw_symbol"], interval="5m", limit=5)
                if candles:
                    current_price = float(candles[-1][4])
                    hit_tp1 = False
                    
                    if trade["direction"] == "LONG" and current_price >= trade["tp1"]:
                        hit_tp1 = True
                    elif trade["direction"] == "SHORT" and current_price <= trade["tp1"]:
                        hit_tp1 = True
                    
                    if hit_tp1:
                        msg = f"🎯 **TP1 TARGET REACHED!**\n\n" \
                              f"🔹 `{trade['symbol']}` ({trade['direction']})\n" \
                              f"💰 **Entry:** `${trade['price']}`\n" \
                              f"🎯 **TP1:** `${trade['tp1']}`\n\n" \
                              f"🛡️ **მოქმედება:** გადაიტანეთ Stop-Loss `Break-Even (Entry: ${trade['price']})` დონეზე რისკის განულებისთვის!"
                        
                        for u_id in subscribed_users:
                            send_telegram_message(u_id, msg)
                            
                        stats = load_json(STATS_FILE, {"total_signals": 0, "tp1_hits": 0, "assets": {}})
                        stats["tp1_hits"] = stats.get("tp1_hits", 0) + 1
                        save_json(STATS_FILE, stats)
                    else:
                        updated_trades.append(trade)
                else:
                    updated_trades.append(trade)
                time.sleep(2)
                
            save_json(ACTIVE_TRADES_FILE, updated_trades)
        except Exception as e:
            logging.error(f"Trade tracking error: {e}")
            
        time.sleep(150)

def scan_loop(subscribed_users):
    assets = [
        {"raw": "BTCUSDT", "display": "BTC/USDT"},
        {"raw": "SOLUSDT", "display": "SOL/USDT"},
        {"raw": "PEPEUSDT", "display": "PEPE/USDT"},
        {"raw": "PAXGUSDT", "display": "PAXG (Gold)/USDT"}
    ]
    
    last_signal_prices = {asset["raw"]: 0 for asset in assets}
    last_heartbeat_time = 0

    while True:
        try:
            current_time = time.time()
            market_reports = []
            signal_found = False

            if subscribed_users:
                for asset in assets:
                    res = analyze_multi_timeframe(asset["raw"], asset["display"])
                    if res:
                        market_reports.append(f"🔹 `{res['symbol']}`: სკორი `{res['score']}%` (ტრენდი: `{res['htf_trend']}`)")
                        
                        if res["score"] >= 70:
                            if abs(res["price"] - last_signal_prices[asset["raw"]]) > (res["price"] * 0.005):
                                last_signal_prices[asset["raw"]] = res["price"]
                                signal_found = True
                                
                                stats = load_json(STATS_FILE, {"total_signals": 0, "tp1_hits": 0, "assets": {}})
                                stats["total_signals"] = stats.get("total_signals", 0) + 1
                                stats_assets = stats.get("assets", {})
                                stats_assets[res["symbol"]] = stats_assets.get(res["symbol"], 0) + 1
                                stats["assets"] = stats_assets
                                save_json(STATS_FILE, stats)
                                
                                active_trades = load_json(ACTIVE_TRADES_FILE, [])
                                active_trades.append(res)
                                save_json(ACTIVE_TRADES_FILE, active_trades)
                                
                                news_info = fetch_latest_crypto_news(asset["display"])
                                factors_text = "\n".join(res["factors"])
                                
                                msg = f"🤖 **NEXUS INSTITUTIONAL SIGNAL**\n\n🔹 `{res['symbol']}` ({res['direction']})\n🌐 **4H Trend:** `{res['htf_trend']}`\n🎯 **Score:** `{res['score']}%`\n\n{factors_text}\n\n💰 **Entry:** `${res['price']}`\n🛑 **ATR SL:** `${res['sl']}`\n🎯 **TP1:** `${res['tp1']}`\n🎯 **TP2:** `${res['tp2']}`\n\n💡 *TP1-ზე მიღწევისას ბოტი ავტომატურად გამოგიგზავნით შეხსენებას BE-სთვის!*\n\n🌐 {news_info}"
                                
                                for u_id in list(subscribed_users):
                                    send_telegram_message(u_id, msg)
                    time.sleep(5)

                if not signal_found and (current_time - last_heartbeat_time >= 3600):
                    last_heartbeat_time = current_time
                    news_info = fetch_latest_crypto_news("BTC")
                    reports_text = "\n".join(market_reports)
                    
                    heartbeat_msg = f"🟢 **NEXUS HEARTBEAT (სტატუსი)**\n\nბოტი აქტიურად აკონტროლებს ბაზარს 24/7 რეჟიმში ($4H-1H-15M$). მიმდინარე მდგომარეობა:\n\n{reports_text}\n\n💤 *ბაზარი წყნარია, ველით 70%+ ზონებს.*\n\n🌐 {news_info}"
                    
                    for u_id in list(subscribed_users):
                        send_telegram_message(u_id, heartbeat_msg)

        except Exception as e:
            logging.error(f"Scan error: {e}")
        
        time.sleep(300)

if __name__ == "__main__":
    subscribed_users = set(load_json(USER_FILE, []))
    
    # 1. ფონურ თრედებში ვუშვებთ სკანირებას, ტრეკინგსა და პოლინგს
    Thread(target=poll_telegram_updates, args=(subscribed_users,), daemon=True).start()
    Thread(target=scan_loop, args=(subscribed_users,), daemon=True).start()
    Thread(target=track_active_trades, args=(subscribed_users,), daemon=True).start()
    Thread(target=keep_alive, daemon=True).start()
    
    # 2. მთავარ თრედში ვუშვებთ Web Server-ს, რათა Render-მა პორტი მყისიერად დაინახოს
    run_web_server()
