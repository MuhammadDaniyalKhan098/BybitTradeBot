import os
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession

import llm_brain
import hands
import logger
from keep_alive import keep_alive

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
STRING_SESSION = os.getenv("TG_SESSION", "")

env_channel = os.getenv("INPUT_CHANNEL", "")
INPUT_CHANNEL = int(env_channel) if env_channel.lstrip('-').isdigit() else 'me'

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

@client.on(events.NewMessage(chats=INPUT_CHANNEL))
async def handle_new_message(event):
    try:
        text = event.raw_text
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg: 
                text = f"Context: {reply_msg.raw_text}\n\nNew Message: {text}"

        print(f"\n[INFO] Analyzing new message ({len(text)} chars)...")
        trade_signals = llm_brain.parse_with_llm(text)
        
        if not trade_signals:
            print("[INFO] No actionable signals found.")
            logger.log_trade({}, "SKIPPED", "No Signal / Analysis Only", text)
            return

        for trade in trade_signals:
            report = hands.execute_trade(trade)
            status = "ERROR" if "Failed" in report or "Error" in report else "SUCCESS"
            
            print(f"[REPORT] {report}")
            logger.log_trade(trade, status, report, text)

    except Exception as e:
        print(f"[CRITICAL] Handler Error: {e}")

if __name__ == '__main__':
    keep_alive()
    print("[INFO] Service initialized. Listening for signals...")
    client.start()
    client.run_until_disconnected()