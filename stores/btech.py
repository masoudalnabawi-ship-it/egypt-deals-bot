from urllib.parse import urljoin
from models import Deal
from stores.base import StoreConnector, parse_price

class BtechConnector(StoreConnector):
    name = "btech"
    URL = "https://btech.com/ar/collection/91342e36-259c-4ba7-b204-fbfbb217e5d1"

    async def fetch_deals(self) -> list[Deal]:
        soup = await self.get_soup(self.URL)
        deals = []
        # B.TECH frontend changes often; these selectors intentionally accept multiple layouts.
        cards = soup.select(
            "[class*='product-card'], [class*='ProductCard'], "
            "[data-testid*='product'], li[class*='product']"
        )
        for card in cards:
            link = card.select_one("a[href]")
            title_el = card.select_one("h3, h2, [class*='title'], [class*='name']")
            prices = card.select("[class*='price'], [class*='Price']")
            if not (link and title_el and prices):
                continue
            vals = [parse_price(x.get_text(" ", strip=True)) for x in prices]
            vals = [x for x in vals if x]
            if not vals:
                continue
            current = min(vals)
            old = max(vals) if len(vals) > 1 and max(vals) > current else None
            deals.append(Deal(
                store=self.name,
                title=title_el.get_text(" ", strip=True),
                current_price=current,
                old_price=old,
                url=urljoin(self.URL, link.get("href")),
            ))
        return deals
