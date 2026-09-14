import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlencode

from models import Deal
from stores.base import StoreConnector, parse_price


class AmazonConnector(StoreConnector):
    name = "amazon"
    BASE = "https://www.amazon.eg"
    STATE_FILE = Path(".amazon_scan_state.json")

    # Broad Amazon search aliases. These are intentionally diverse so the
    # scanner covers the store over repeated cycles instead of one category.
    SEARCH_ALIASES = [
        "electronics",
        "computers",
        "mobile",
        "appliances",
        "home",
        "kitchen",
        "fashion",
        "beauty",
        "grocery",
        "toys",
        "sports",
        "automotive",
        "office-products",
        "videogames",
        "baby",
        "pet-supplies",
        "tools",
        "garden",
        "books",
    ]

    # Pages from each department to inspect per cycle.
    PAGES_PER_ALIAS = 2

    # Number of departments handled each scan. Rotation persists between runs.
    ALIASES_PER_CYCLE = 4

    def _load_state(self):
        try:
            data = json.loads(self.STATE_FILE.read_text(encoding="utf-8"))
            return int(data.get("alias_index", 0))
        except Exception:
            return 0

    def _save_state(self, idx):
        try:
            self.STATE_FILE.write_text(
                json.dumps({"alias_index": int(idx)}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _money(self, node):
        if not node:
            return None
        off = node.select_one(".a-offscreen")
        text = off.get_text(" ", strip=True) if off else node.get_text(" ", strip=True)
        return parse_price(text)

    def _asin_from_card(self, card):
        asin = (card.get("data-asin") or "").strip()
        if asin:
            return asin

        link = card.select_one("a[href*='/dp/'], a[href*='/gp/product/']")
        if not link:
            return None
        href = link.get("href") or ""
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{8,14})", href, flags=re.I)
        return m.group(1).upper() if m else None

    def _parse_search_cards(self, soup):
        deals = []
        seen = set()

        cards = soup.select("div[data-component-type='s-search-result']")

        for card in cards:
            title_el = card.select_one("h2 span, h2 a span")
            link = card.select_one("h2 a[href], a[href*='/dp/']")
            if not (title_el and link):
                continue

            title = title_el.get_text(" ", strip=True)
            if not title:
                continue

            asin = self._asin_from_card(card)
            href = (link.get("href") or "").strip()

            if asin:
                url = f"{self.BASE}/dp/{asin}"
            elif href:
                url = urljoin(self.BASE, href)
            else:
                continue

            # Current price.
            current_node = card.select_one(
                ".a-price:not(.a-text-price), "
                "[data-a-color='price'] .a-price"
            )
            current = self._money(current_node)
            if not current:
                continue

            # Amazon normally renders the reference/list price using
            # .a-text-price when a strikethrough price exists.
            old_nodes = card.select(".a-text-price .a-offscreen, .a-text-price")
            old_values = []
            for n in old_nodes:
                v = parse_price(n.get_text(" ", strip=True))
                if v and v > current:
                    old_values.append(v)

            old = max(old_values) if old_values else None

            text = card.get_text(" ", strip=True).lower()
            deal_signal = any(
                marker in text
                for marker in [
                    "limited time deal",
                    "deal",
                    "خصم",
                    "عرض لفترة محدودة",
                    "وفر",
                    "save",
                ]
            )

            # Strict collection rule:
            # include either a genuine higher reference price or an explicit
            # deal badge. A badge without old price is still collected, but it
            # won't pass the main bot's percentage filter unless history/cross
            # store validation proves it.
            if old is None and not deal_signal:
                continue

            key = asin or url.split("?")[0]
            if key in seen:
                continue
            seen.add(key)

            deals.append(
                Deal(
                    store=self.name,
                    title=title,
                    current_price=current,
                    old_price=old,
                    url=url,
                    external_id=asin,
                )
            )

        return deals

    async def _search_alias_page(self, alias, page=1):
        params = {"i": alias, "page": page}
        url = f"{self.BASE}/s?{urlencode(params)}"
        soup = await self.get_soup(url)
        return self._parse_search_cards(soup)

    async def fetch_deals(self):
        start = self._load_state()
        aliases = self.SEARCH_ALIASES
        total = len(aliases)

        selected = [
            aliases[(start + offset) % total]
            for offset in range(min(self.ALIASES_PER_CYCLE, total))
        ]

        deals = []
        seen = set()

        for alias in selected:
            for page in range(1, self.PAGES_PER_ALIAS + 1):
                try:
                    page_deals = await self._search_alias_page(alias, page)
                except Exception:
                    # One category/page failing should never kill Amazon.
                    continue

                for d in page_deals:
                    key = d.external_id or d.url.split("?")[0]
                    if key in seen:
                        continue
                    seen.add(key)
                    deals.append(d)

        self._save_state((start + len(selected)) % total)
        return deals

    async def search_products(self, query):
        # Used by the cross-store verification engine.
        params = {"k": query}
        url = f"{self.BASE}/s?{urlencode(params)}"

        try:
            soup = await self.get_soup(url)
        except Exception:
            return []

        # For comparison we need ordinary products too, even when not deals.
        results = []
        seen = set()

        for card in soup.select("div[data-component-type='s-search-result']"):
            title_el = card.select_one("h2 span, h2 a span")
            link = card.select_one("h2 a[href], a[href*='/dp/']")
            if not (title_el and link):
                continue

            title = title_el.get_text(" ", strip=True)
            current = self._money(
                card.select_one(".a-price:not(.a-text-price), [data-a-color='price'] .a-price")
            )
            if not title or not current:
                continue

            asin = self._asin_from_card(card)
            href = (link.get("href") or "").strip()
            url = f"{self.BASE}/dp/{asin}" if asin else urljoin(self.BASE, href)

            key = asin or url.split("?")[0]
            if key in seen:
                continue
            seen.add(key)

            old_values = []
            for n in card.select(".a-text-price .a-offscreen, .a-text-price"):
                v = parse_price(n.get_text(" ", strip=True))
                if v and v > current:
                    old_values.append(v)

            results.append(
                Deal(
                    store=self.name,
                    title=title,
                    current_price=current,
                    old_price=max(old_values) if old_values else None,
                    url=url,
                    external_id=asin,
                )
            )

        return results[:30]
