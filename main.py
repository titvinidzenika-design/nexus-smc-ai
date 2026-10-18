import asyncio
import os
import logging
from datetime import datetime
from telegram import Bot
from validator import NexusValidator

# Logging კონფიგურაცია
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment Variables-ის უსაფრთხო წაკითხვა
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ვამოწმებთ, რომ ცვლადები ნამდვილად არსებობს
if not TELEGRAM_TOKEN or not CHAT_ID:
    logging.error("TELEGRAM_TOKEN ან CHAT_ID არ არის მითითებული Environment Variables-ში!")

bot = Bot(token=TELEGRAM_TOKEN)

# სავაჭრო წყვილები
SYMBOLS = ["BTC/USDT", "SOL/USDT", "XAU/USDT"]


def get_market_data(symbol: str) -> tuple[dict, dict]:
    htf_data = {
        "ema_200": 64000.0,
        "support_wick": 64200.0,
        "resistance_wick": 68500.0
    }

    ltf_data = {
        "close": 65100.0,
        "entry": 65100.0,
        "volume": 2800.0,
        "volume_ma_20": 1000.0,
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
    try:
        # აუცილებლად გადავცემთ integer ტიპად ან ზუსტ სტრიქონად CHAT_ID-ს
        target_chat_id = int(CHAT_ID) if CHAT_ID and CHAT_ID.isdigit() else CHAT_ID
        await bot.send_message(chat_id=target_chat_id, text=message, parse_mode="HTML")
        logging.info(f"Signal sent for {symbol} to chat {target_chat_id}")
    except Exception as e:
        logging.error(f"Failed to send telegram message for {symbol}: {e}")


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
    """მთავარი Loop"""
    logging.info("Nexus Bot operational.")

    while True:
        await check_market_job()
        await asyncio.sleep(900)


if __name__ == "__main__":
    asyncio.run(main())
