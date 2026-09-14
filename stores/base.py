from abc import ABC, abstractmethod
import re
import httpx
from bs4 import BeautifulSoup
from models import Deal

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
            r = await client.get(url)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")

    @abstractmethod
    async def fetch_deals(self) -> list[Deal]:
        raise NotImplementedError
