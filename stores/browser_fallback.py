"""
Fallback connectors for stores that commonly render results dynamically
or actively restrict non-browser requests.

This file is intentionally conservative: it does NOT bypass CAPTCHAs,
login walls, anti-bot protections, or access controls.

For production, install Playwright:
    pip install playwright
    playwright install chromium

Then implement each store using public pages that permit automated access
or an official/affiliate API when available.
"""
from models import Deal
from stores.base import StoreConnector

class BrowserRequiredConnector(StoreConnector):
    url = ""

    async def fetch_deals(self) -> list[Deal]:
        # Fail safely without stopping all other stores.
        raise RuntimeError(
            f"{self.name}: browser/API connector required. "
            "Use an official/affiliate API where available, or Playwright on permitted public pages."
        )

class AmazonConnector(BrowserRequiredConnector):
    name = "amazon"
    url = "https://www.amazon.eg/"

class NoonConnector(BrowserRequiredConnector):
    name = "noon"
    url = "https://www.noon.com/egypt-en/"

class RaneenConnector(BrowserRequiredConnector):
    name = "raneen"
    url = "https://www.raneen.com/"
