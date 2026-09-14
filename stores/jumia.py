from urllib.parse import urljoin, quote_plus
from models import Deal
from stores.base import StoreConnector, parse_price

class JumiaConnector(StoreConnector):
    name = "jumia"
    BASE = "https://www.jumia.com.eg/ar/flash-sales/"
    SEARCH = "https://www.jumia.com.eg/ar/catalog/?q={query}"

    def _parse_cards(self, soup) -> list[Deal]:
        deals, seen = [], set()
        for card in soup.select("article.prd, article"):
            title_el = card.select_one(".name, h3, .prd-name")
            current_el = card.select_one(".prc")
            old_el = card.select_one(".old")
            if not (title_el and current_el):
                continue

            product_url = None
            for a in card.select("a[href]"):
                href = (a.get("href") or "").strip()
                if not href or href == "#" or href.startswith("javascript:"):
                    continue
                if "customer/account/login" in href or "wishlist" in href:
                    continue
                if ".html" in href:
                    product_url = urljoin(self.BASE, href)
                    break
            if not product_url:
                continue

            current = parse_price(current_el.get_text(" ", strip=True))
            old = parse_price(old_el.get_text(" ", strip=True)) if old_el else None
            if not current:
                continue
            if old is not None and old <= current:
                old = None

            title = title_el.get_text(" ", strip=True)
            key = product_url.split("?")[0]
            if key in seen:
                continue
            seen.add(key)

            img = card.select_one("img")
            image = None
            if img:
                image = img.get("data-src") or img.get("data-lazy") or img.get("src")

            deals.append(Deal(
                store=self.name,
                title=title,
                current_price=current,
                old_price=old,
                url=product_url,
                image_url=image,
            ))
        return deals

    async def fetch_deals(self) -> list[Deal]:
        all_deals = []
        seen_urls = set()
        for page in range(1, 31):
            url = self.BASE if page == 1 else f"{self.BASE}?page={page}"
            soup = await self.get_soup(url)
            page_deals = self._parse_cards(soup)

            fresh = []
            for d in page_deals:
                key = d.url.split("?")[0]
                if key not in seen_urls:
                    seen_urls.add(key)
                    fresh.append(d)

            if not fresh:
                break

            all_deals.extend(fresh)
            if len(page_deals) < 10:
                break
        return all_deals

    async def search_products(self, query: str) -> list[Deal]:
        url = self.SEARCH.format(query=quote_plus(query))
        soup = await self.get_soup(url)
        return self._parse_cards(soup)[:30]
