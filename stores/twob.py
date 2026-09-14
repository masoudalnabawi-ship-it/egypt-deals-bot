from urllib.parse import urljoin, quote_plus
from models import Deal
from stores.base import StoreConnector, parse_price

class TwoBConnector(StoreConnector):
    name = "2b"
    URL = "https://2b.com.eg/ar/offer.html"

    def _value(self, el):
        if not el:
            return None
        amount = el.get("data-price-amount")
        if amount:
            try:
                return float(amount)
            except ValueError:
                pass
        return parse_price(el.get_text(" ", strip=True))

    def _parse_cards(self, soup) -> list[Deal]:
        deals, seen = [], set()
        for card in soup.select(".product-item, li.product-item"):
            title_el = card.select_one(
                "a.product-item-link, .product-item-name, strong.product-item-name"
            )
            if not title_el:
                continue

            product_url = None
            for a in card.select("a[href]"):
                href = (a.get("href") or "").strip()
                if not href or href == "#" or href.startswith("javascript:"):
                    continue
                candidate = urljoin(self.URL, href)
                if "offer.html#" in candidate:
                    continue
                if ".html" in candidate:
                    product_url = candidate
                    break
            if not product_url:
                continue

            current_el = card.select_one(
                ".special-price [data-price-amount], .special-price .price, "
                "[data-price-type='finalPrice'][data-price-amount], "
                "[data-price-type='finalPrice'] .price"
            )
            old_el = card.select_one(
                ".old-price [data-price-amount], .old-price .price"
            )
            current = self._value(current_el)
            old = self._value(old_el)

            if not current:
                normal = card.select_one(
                    ".price-final_price [data-price-amount], "
                    ".price-final_price .price, .price-box .price"
                )
                current = self._value(normal)

            if not current:
                continue
            if old is not None and old <= current:
                old = None

            title = title_el.get_text(" ", strip=True)
            key = (title.lower(), round(current, 2), product_url)
            if key in seen:
                continue
            seen.add(key)

            deals.append(Deal(
                store=self.name,
                title=title,
                current_price=current,
                old_price=old,
                url=product_url,
            ))
        return deals

    async def fetch_deals(self) -> list[Deal]:
        return self._parse_cards(await self.get_soup(self.URL))

    async def search_products(self, query: str) -> list[Deal]:
        url = "https://2b.com.eg/ar/catalogsearch/result/?q=" + quote_plus(query)
        return self._parse_cards(await self.get_soup(url))[:20]
