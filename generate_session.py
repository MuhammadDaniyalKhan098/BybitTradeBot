from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n--- COPY THE TEXT BELOW THIS LINE ---")
    print(client.session.save())
    print("--------------------------------------\n")