import httpx
from urllib.parse import quote_plus

from models import Deal
from stores.base import StoreConnector


class Dream2000Connector(StoreConnector):
    name = "dream2000"
    BASE = "https://dream2000.com"

    async def _get_products_page(self, page=1):
        url = f"{self.BASE}/products.json?limit=250&page={page}"

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=self.headers,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json().get("products", [])

    def _product_deals(self, product, discounts_only=False):
        deals = []

        title = str(product.get("title") or "").strip()
        handle = str(product.get("handle") or "").strip()

        if not title or not handle:
            return deals

        variants = product.get("variants") or []

        for variant in variants:
            try:
                current = float(variant.get("price") or 0)
            except Exception:
                continue

            try:
                old = float(variant.get("compare_at_price") or 0)
            except Exception:
                old = 0

            if current <= 0:
                continue

            old_price = old if old > current else None

            if discounts_only and not old_price:
                continue

            variant_title = str(
                variant.get("title") or ""
            ).strip()

            full_title = title

            if (
                variant_title
                and variant_title.lower() != "default title"
            ):
                full_title = f"{title} - {variant_title}"

            variant_id = variant.get("id")

            url = f"{self.BASE}/products/{handle}"

            if variant_id:
                url += f"?variant={variant_id}"

            deals.append(
                Deal(
                    store=self.name,
                    title=full_title,
                    current_price=current,
                    old_price=old_price,
                    url=url,
                )
            )

        return deals

    async def fetch_deals(self):
        deals = []
        seen = set()

        # Shopify: 250 products per page.
        # Scan several pages and stop automatically at the end.
        for page in range(1, 9):
            products = await self._get_products_page(page)

            if not products:
                break

            for product in products:
                for deal in self._product_deals(
                    product,
                    discounts_only=True
                ):
                    key = (
                        deal.title.lower().strip(),
                        deal.current_price,
                        deal.url,
                    )

                    if key in seen:
                        continue

                    seen.add(key)
                    deals.append(deal)

            if len(products) < 250:
                break

        return deals

    async def search_products(self, query: str):
        # Shopify predictive-search endpoint
        url = (
            f"{self.BASE}/search/suggest.json"
            f"?q={quote_plus(query)}"
            "&resources[type]=product"
            "&resources[limit]=10"
        )

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.headers,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()

            products = (
                data.get("resources", {})
                .get("results", {})
                .get("products", [])
            )

            deals = []

            for p in products:
                title = str(p.get("title") or "").strip()
                url_value = str(p.get("url") or "").strip()

                try:
                    current = float(p.get("price") or 0)
                except Exception:
                    continue

                try:
                    old = float(
                        p.get("compare_at_price_max") or
                        p.get("compare_at_price") or
                        0
                    )
                except Exception:
                    old = 0

                if not title or current <= 0:
                    continue

                if url_value.startswith("http"):
                    product_url = url_value
                else:
                    product_url = self.BASE + url_value

                deals.append(
                    Deal(
                        store=self.name,
                        title=title,
                        current_price=current,
                        old_price=old if old > current else None,
                        url=product_url,
                    )
                )

            if deals:
                return deals

        except Exception:
            pass

        # Fallback: first Shopify catalogue page
        products = await self._get_products_page(1)

        q = query.lower()
        result = []

        for product in products:
            title = str(product.get("title") or "")

            if q not in title.lower():
                continue

            result.extend(
                self._product_deals(
                    product,
                    discounts_only=False
                )
            )

            if len(result) >= 30:
                break

        return result[:30]
