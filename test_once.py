import asyncio
import logging
from config import settings
from stores import CONNECTORS

logging.basicConfig(level=logging.INFO)

async def main():
    for name in settings.enabled_stores:
        cls = CONNECTORS.get(name)
        if not cls:
            print(name, "UNKNOWN")
            continue
        try:
            c = cls(settings.timeout, settings.user_agent)
            deals = await c.fetch_deals()
            print(f"\n{name}: {len(deals)} deals")
            for d in deals[:3]:
                print(" -", d.title[:90], d.current_price, d.old_price, d.discount_percent, d.url)
        except Exception as e:
            print(f"\n{name}: ERROR -> {e}")

if __name__ == "__main__":
    asyncio.run(main())
