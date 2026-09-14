import json
from urllib.parse import quote_plus, urljoin
from models import Deal
from stores.base import StoreConnector, parse_price

class NoonConnector(StoreConnector):
    name = "noon"
    DEAL_URLS = [
        "https://www.noon.com/egypt-en/all-products/?sort[by]=discount&sort[dir]=desc",
        "https://www.noon.com/egypt-en/",
    ]

    def _extract_from_json(self, obj, out):
        if isinstance(obj, dict):
            title = obj.get("name") or obj.get("title") or obj.get("product_name")
            url = obj.get("url") or obj.get("productUrl") or obj.get("url_key")
            price = obj.get("sale_price") or obj.get("salePrice") or obj.get("price") or obj.get("offer_price")
            old = obj.get("old_price") or obj.get("oldPrice") or obj.get("was_price") or obj.get("regular_price")

            if title and price:
                try:
                    current = float(str(price).replace(",", ""))
                except Exception:
                    current = None
                if current:
                    try:
                        oldp = float(str(old).replace(",", "")) if old is not None else None
                    except Exception:
                        oldp = None
                    if oldp is not None and oldp <= current:
                        oldp = None
                    full = str(url) if url and str(url).startswith("http") else urljoin("https://www.noon.com", str(url or "/egypt-en/"))
                    out.append(Deal(
                        store=self.name,
                        title=str(title),
                        current_price=current,
                        old_price=oldp,
                        url=full,
                    ))
            for v in obj.values():
                self._extract_from_json(v, out)
        elif isinstance(obj, list):
            for v in obj:
                self._extract_from_json(v, out)

    def _parse_html_cards(self, soup) -> list[Deal]:
        deals = []
        for card in soup.select(
            "[data-qa='product-box'], [class*='ProductBox'], "
            "[class*='productContainer'], [class*='product-box']"
        ):
            title_el = card.select_one(
                "[data-qa='product-name'], [class*='productTitle'], [class*='name'], h2, h3"
            )
            link = card.select_one("a[href]")
            if not (title_el and link):
                continue

            vals = []
            for p in card.select(
                "[class*='priceNow'], [class*='salePrice'], [class*='price'], [data-qa='product-price']"
            ):
                val = parse_price(p.get_text(" ", strip=True))
                if val:
                    vals.append(val)
            if not vals:
                continue

            current = min(vals)
            old = max(vals) if len(vals) > 1 and max(vals) > current else None
            deals.append(Deal(
                store=self.name,
                title=title_el.get_text(" ", strip=True),
                current_price=current,
                old_price=old,
                url=urljoin("https://www.noon.com", link.get("href")),
            ))
        return deals

    def _parse_page(self, soup) -> list[Deal]:
        deals = self._parse_html_cards(soup)
        for script in soup.select("script"):
            raw = script.string or script.get_text("", strip=True)
            if not raw or len(raw) < 20:
                continue
            if script.get("type") == "application/json" or "__NEXT_DATA__" in (script.get("id") or ""):
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                self._extract_from_json(data, deals)

        unique, seen = [], set()
        for d in deals:
            key = (d.title.lower().strip(), round(d.current_price, 2), d.url)
            if key in seen:
                continue
            seen.add(key)
            unique.append(d)
        return unique

    async def fetch_deals(self) -> list[Deal]:
        all_deals, seen = [], set()
        for url in self.DEAL_URLS:
            try:
                soup = await self.get_soup(url)
            except Exception:
                continue
            for d in self._parse_page(soup):
                key = (d.title.lower().strip(), round(d.current_price, 2), d.url)
                if key not in seen:
                    seen.add(key)
                    all_deals.append(d)
        return all_deals

    async def search_products(self, query: str) -> list[Deal]:
        url = "https://www.noon.com/egypt-en/search/?q=" + quote_plus(query)
        soup = await self.get_soup(url)
        return self._parse_page(soup)[:30]
