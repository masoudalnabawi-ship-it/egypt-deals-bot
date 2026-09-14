from abc import ABC, abstractmethod
import os
import logging
import re
import httpx
from bs4 import BeautifulSoup
from models import Deal

logger = logging.getLogger(__name__)

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")

def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    text = text.translate(ARABIC_DIGITS)
    text = text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None

class StoreConnector(ABC):
    name: str

    def __init__(self, timeout: float, user_agent: str):
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
        }

    async def get_soup(self, url: str) -> BeautifulSoup:
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:

            try:
                r = await client.get(url)
                r.raise_for_status()
                return BeautifulSoup(r.text, "html.parser")

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status not in (403, 429):
                    raise

                cloud_url = os.getenv("CLOUD_API_URL", "").strip()
                cloud_key = os.getenv("CLOUD_API_KEY", "").strip()

                if not cloud_url or not cloud_key:
                    raise

                cloud_url = cloud_url.rstrip("/")

                if cloud_url.endswith("/api/deals"):
                    cloud_url = cloud_url[:-len("/api/deals")]

                proxy_url = cloud_url + "/api/store-proxy"

                logger.warning(
                    "%s direct access returned %s; using Cloudflare proxy",
                    self.name,
                    status,
                )

                proxy = await client.get(
                    proxy_url,
                    params={"url": url},
                    headers={
                        "x-api-key": cloud_key,
                        "Accept": "text/html",
                    },
                )

                proxy.raise_for_status()

                logger.info(
                    "%s Cloudflare proxy returned %s bytes",
                    self.name,
                    len(proxy.content),
                )

                return BeautifulSoup(
                    proxy.text,
                    "html.parser",
                )

    @abstractmethod
    async def fetch_deals(self) -> list[Deal]:
        raise NotImplementedError
