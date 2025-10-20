import os
from dotenv import load_dotenv
from telethon import TelegramClient
import config as cfg
from modules.listener import register_handlers

load_dotenv()
cfg.API_ID = int(os.getenv("API_ID"))
cfg.API_HASH = os.getenv("API_HASH")

client = TelegramClient("session_name", cfg.API_ID, cfg.API_HASH)

async def main():
    await client.start()
    register_handlers(client, cfg)
    print("Listening for new posts...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
