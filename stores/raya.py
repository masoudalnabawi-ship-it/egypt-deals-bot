from urllib.parse import urljoin
from models import Deal
from stores.base import StoreConnector, parse_price

class RayaConnector(StoreConnector):
    name = "raya"
    URL = "https://www.rayashop.com/ar"

    async def fetch_deals(self) -> list[Deal]:
        soup = await self.get_soup(self.URL)
        deals = []
        cards = soup.select(
            ".product-item, [class*='product-card'], "
            "[class*='ProductCard'], li[class*='product']"
        )
        for card in cards:
            link = card.select_one("a[href]")
            title_el = card.select_one(
                ".product-item-link, h3, h2, [class*='title'], [class*='name']"
            )
            price_nodes = card.select(".price, [class*='price']")
            if not (link and title_el and price_nodes):
                continue
            vals = [parse_price(x.get_text(" ", strip=True)) for x in price_nodes]
            vals = [x for x in vals if x and x > 10]
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
