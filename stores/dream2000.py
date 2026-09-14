from urllib.parse import urljoin
from models import Deal
from stores.base import StoreConnector, parse_price

class Dream2000Connector(StoreConnector):
    name = "dream2000"
    URL = "https://dream2000.com/pages/hot-deals-en"

    async def fetch_deals(self) -> list[Deal]:
        soup = await self.get_soup(self.URL)
        deals = []
        # Prefer product tiles if the offers page exposes them.
        for card in soup.select(".product-item, [class*='product-card'], li[class*='product']"):
            link = card.select_one("a[href]")
            title_el = card.select_one("h2, h3, .product-item-link, [class*='name']")
            price_nodes = card.select(".price, [class*='price']")
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
