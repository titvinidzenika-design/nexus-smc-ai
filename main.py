import asyncio
import os
import logging
from datetime import datetime
from telegram import Bot
from validator import NexusValidator

# Logging კონფიგურაცია Render-ის კონსოლისთვის
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment Variables (Render-ზე გაწერილი Environment Variables)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")

bot = Bot(token=TELEGRAM_TOKEN)

# სავაჭრო წყვილები, რომლებსაც ბოტი აკონტროლებს
SYMBOLS = ["BTC/USDT", "SOL/USDT", "XAU/USDT"]


def get_market_data(symbol: str) -> tuple[dict, dict]:
    """
    აქ ინტეგრირდება თქვენი ბირჟის API (ccxt / Binance / Bybit).
    მაგალითისთვის მოცემულია იმიტირებული მონაცემები:
    """
    # 4H HTF Data
    htf_data = {
        "ema_200": 64000.0,
        "support_wick": 64200.0,
        "resistance_wick": 68500.0
    }
    
    # 15m LTF Data
    ltf_data = {
        "close": 65100.0,
        "entry": 65100.0,
        "volume": 2800.0,
        "volume_ma_20": 1000.0,  # 2800 > 1000 * 2.5 (Volume Spike = TRUE)
        "tp_target": 67500.0
    }
    return htf_data, ltf_data


async def send_telegram_signal(trade_info: dict, symbol: str):
    """Telegram-ში სრული სავაჭრო სიგნალის გაგზავნა"""
    message = f"""
🚨 <b>NEXUS SIGNAL CONFIRMED: {symbol} (LONG)</b>
----------------------------------------
✅ <b>1. HTF Trend (4H):</b> Uptrend (Above EMA 200)
✅ <b>2. HTF Level:</b> HTF Demand Zone Test
✅ <b>3. LTF Pattern (15m):</b> Breakout & Retest
✅ <b>4. Volume:</b> Volume Spike Confirmed (> 2.5x)
✅ <b>5. Risk/Reward:</b> 1:{trade_info['rr']:.2f}

📍 <b>Entry Price:</b> ${trade_info['entry']:.2f}
📉 <b>Stop-Loss:</b> ${trade_info['stop_loss']:.2f} (Below 4H Wick)
🎯 <b>Take-Profit:</b> ${trade_info['take_profit']:.2f}
⏱ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
    logging.info(f"Signal sent for {symbol}")


async def check_market_job():
    """15-წუთიანი სკანირების ციკლი"""
    logging.info("Starting market analysis cycle...")
    
    for symbol in SYMBOLS:
        try:
            htf_data, ltf_data = get_market_data(symbol)
            validator = NexusValidator(htf_data, ltf_data)
            result = validator.validate_long_setup()

            if result["status"]:
                await send_telegram_signal(result, symbol)
            else:
                logging.info(f"[{symbol}] Skipped: {result['reason']}")
                
        except Exception as e:
            logging.error(f"Error checking {symbol}: {e}")


async def main():
    """Render-ისთვის ოპტიმიზებული მთავარი Loop"""
    logging.info("Nexus Bot operational on Render.")
    
    while True:
        await check_market_job()
        # 15 წუთი = 900 წამი (Render-ის Free Tier-ის დასაზოგად)
        await asyncio.sleep(900)


if __name__ == "__main__":
    asyncio.run(main())
