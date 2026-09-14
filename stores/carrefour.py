from urllib.parse import urljoin
from models import Deal
from stores.base import StoreConnector, parse_price

class CarrefourConnector(StoreConnector):
    name = "carrefour"
    URL = "https://www.carrefouregypt.com/mafegy/ar/c/00002"

    async def fetch_deals(self) -> list[Deal]:
        soup = await self.get_soup(self.URL)
        deals = []
        cards = soup.select(
            "[data-testid*='product'], [class*='product-card'], "
            "[class*='ProductCard'], [class*='product_item']"
        )
        for card in cards:
            link = card.select_one("a[href]")
            title_el = card.select_one(
                "h2, h3, [class*='name'], [class*='title']"
            )
            price_nodes = card.select("[class*='price'], [class*='Price']")
            if not (link and title_el and price_nodes):
                continue
            vals = [parse_price(x.get_text(" ", strip=True)) for x in price_nodes]
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
