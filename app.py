import asyncio
import logging
from config import settings
from db import init_db
from engine import scan_once, moderation_loop

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

async def scanner_loop():
    while True:
        await scan_once()
        await asyncio.sleep(max(60, settings.check_interval_minutes * 60))

async def main():
    init_db()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    if not settings.telegram_channel_id:
        raise RuntimeError("TELEGRAM_CHANNEL_ID missing")
    if not settings.admin_chat_id:
        raise RuntimeError("ADMIN_CHAT_ID missing")
    await asyncio.gather(scanner_loop(), moderation_loop())

if __name__ == "__main__":
    asyncio.run(main())
