from urllib.parse import urljoin, quote_plus

from models import Deal
from stores.base import StoreConnector, parse_price


class RayaConnector(StoreConnector):
    name = "raya"

    BASE = "https://www.rayashop.com"
    URL = "https://www.rayashop.com/ar"

    def _parse_cards(self, soup, only_discounts=False):
        deals = []
        seen = set()

        cards = soup.select("div.ProductCard__Main")

        for card in cards:
            title_el = card.select_one("p.name")
            if not title_el:
                continue

            link = None
            for a in card.select("a[href]"):
                href = a.get("href", "")
                if href.startswith("/ar/"):
                    link = href
                    break

            if not link:
                continue

            current_el = card.select_one(
                "span.currency.text-lg"
            )

            old_el = card.select_one(
                "span.currency.line-through"
            )

            if not current_el:
                continue

            current = parse_price(
                current_el.get_text(" ", strip=True)
            )

            old = None

            if old_el:
                old = parse_price(
                    old_el.get_text(" ", strip=True)
                )

            if not current:
                continue

            if old is not None and old <= current:
                old = None

            if only_discounts and not old:
                continue

            deal = Deal(
                store=self.name,
                title=title_el.get_text(" ", strip=True),
                current_price=current,
                old_price=old,
                url=urljoin(self.BASE, link),
            )

            key = (
                deal.title.lower().strip(),
                deal.current_price,
                deal.url
            )

            if key in seen:
                continue

            seen.add(key)
            deals.append(deal)

        return deals

    async def fetch_deals(self):
        soup = await self.get_soup(self.URL)
        return self._parse_cards(
            soup,
            only_discounts=True
        )

    async def search_products(self, query: str):
        url = (
            "https://www.rayashop.com/search?q="
            + quote_plus(query)
        )

        soup = await self.get_soup(url)

        return self._parse_cards(
            soup,
            only_discounts=False
        )[:30]
