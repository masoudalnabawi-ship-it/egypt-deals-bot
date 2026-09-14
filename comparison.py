import asyncio
import html
import re
import unicodedata
from dataclasses import dataclass, field
from rapidfuzz.fuzz import token_set_ratio

from config import settings
from models import Deal
from stores import CONNECTORS
from db import history_stats_for_key

BRAND_ALIASES = {
    "samsung": {"samsung", "سامسونج"},
    "lg": {"lg", "ال جي", "إل جي"},
    "apple": {"apple", "ابل", "آبل"},
    "xiaomi": {"xiaomi", "شاومي"},
    "infinix": {"infinix", "انفينيكس", "إنفينيكس"},
    "oppo": {"oppo", "اوبو", "أوبو"},
    "realme": {"realme", "ريلمي"},
    "honor": {"honor", "هونر"},
    "jbl": {"jbl", "جي بي ال", "جي بي إل"},
    "toshiba": {"toshiba", "توشيبا"},
    "fresh": {"fresh", "فريش"},
    "ariston": {"ariston", "اريستون", "أريستون"},
    "haier": {"haier", "هاير"},
    "sony": {"sony", "سوني"},
    "philips": {"philips", "فيليبس"},
    "dell": {"dell", "ديل"},
    "hp": {"hp", "اتش بي", "إتش بي"},
    "lenovo": {"lenovo", "لينوفو"},
    "asus": {"asus", "اسوس", "أسوس"},
}

NOISE_WORDS = {
    "جنيه", "egp", "عرض", "خصم", "ضمان", "محلي", "اللون", "لون",
    "black", "white", "اسود", "أسود", "ابيض", "أبيض",
    "new", "جديد", "موديل", "model", "with", "without",
}

def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    text = re.sub(r"[^\w\s\-\.]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()

def detect_brand(title: str):
    n = norm(title)
    for canonical, aliases in BRAND_ALIASES.items():
        if any(norm(a) in n for a in aliases):
            return canonical
    return None

def model_tokens(title: str) -> set[str]:
    n = norm(title).upper()
    out = set()
    for raw in re.findall(r"\b[A-Z0-9][A-Z0-9\-\._/]{2,}\b", n):
        clean = raw.strip("-._/")
        if len(clean) >= 4 and re.search(r"[A-Z]", clean) and re.search(r"\d", clean):
            if clean not in {"4K", "5G"}:
                out.add(clean)
    return out

def capacity_tokens(title: str) -> set[str]:
    n = norm(title)
    out = set()
    patterns = [
        r"\b(\d+(?:\.\d+)?)\s*(gb|tb|mb)\b",
        r"\b(\d+(?:\.\d+)?)\s*(جيجا|جيجابايت|تيرا|تيرابايت)\b",
        r"\b(\d+(?:\.\d+)?)\s*(inch|inches|بوصه|بوصة)\b",
        r"\b(\d+(?:\.\d+)?)\s*(kg|كجم|لتر|liter|litre)\b",
    ]
    for p in patterns:
        for m in re.finditer(p, n, flags=re.I):
            out.add(m.group(0).replace(" ", ""))
    return out

def clean_for_fuzzy(title: str) -> str:
    return " ".join(w for w in norm(title).split() if w not in NOISE_WORDS)

def same_product_score(a: Deal, b: Deal) -> float:
    ba, bb = detect_brand(a.title), detect_brand(b.title)
    if ba and bb and ba != bb:
        return 0.0

    ma, mb = model_tokens(a.title), model_tokens(b.title)
    ca, cb = capacity_tokens(a.title), capacity_tokens(b.title)

    if ma and mb:
        if not (ma & mb):
            return 0.0
        base = 98.0
    else:
        base = float(token_set_ratio(clean_for_fuzzy(a.title), clean_for_fuzzy(b.title)))

    if ca and cb and not (ca & cb):
        return 0.0

    if ma and mb and (ma & mb):
        fuzzy = float(token_set_ratio(clean_for_fuzzy(a.title), clean_for_fuzzy(b.title)))
        return min(100.0, max(base, 92.0 + fuzzy * 0.08))

    if not (ba and bb) or base < 92:
        return 0.0
    return base

def product_key(deal: Deal) -> str:
    brand = detect_brand(deal.title) or "unknown"
    models = sorted(model_tokens(deal.title))
    caps = sorted(capacity_tokens(deal.title))
    if models:
        return "|".join([brand, ",".join(models), ",".join(caps)])
    return "|".join([brand, clean_for_fuzzy(deal.title)[:120], ",".join(caps)])

def search_query(deal: Deal) -> str:
    parts = []
    brand = detect_brand(deal.title)
    models = sorted(model_tokens(deal.title))
    caps = sorted(capacity_tokens(deal.title))
    if brand:
        parts.append(brand)
    parts += models[:2]
    parts += caps[:2]
    if len(parts) >= 2:
        return " ".join(parts)
    return " ".join(clean_for_fuzzy(deal.title).split()[:8])

@dataclass
class MarketMatch:
    store: str
    title: str
    price: float
    url: str
    confidence: float

@dataclass
class ComparisonReport:
    verified: bool
    verdict: str
    matches: list[MarketMatch] = field(default_factory=list)
    best_competitor_price: float | None = None
    market_advantage_percent: float | None = None
    history_count: int = 0
    historical_low: float | None = None
    historical_average: float | None = None
    reason: str = ""

class DealVerifier:
    def __init__(self, current_market=None):
        self.current_market = current_market or []
        self.cache = {}

    async def _search_store(self, store_name, query):
        key = (store_name, query)
        if key in self.cache:
            return self.cache[key]
        cls = CONNECTORS.get(store_name)
        if not cls:
            return []
        connector = cls(settings.timeout, settings.user_agent)
        searcher = getattr(connector, "search_products", None)
        if not searcher:
            return []
        try:
            results = await searcher(query)
        except Exception:
            results = []
        self.cache[key] = results
        return results

    async def verify(self, deal: Deal) -> ComparisonReport:
        query = search_query(deal)
        pool = list(self.current_market)

        tasks = []
        for name in settings.enabled_stores:
            if name != deal.store:
                tasks.append(self._search_store(name, query))
        if tasks:
            for results in await asyncio.gather(*tasks):
                pool.extend(results)

        matches, seen = [], set()
        for other in pool:
            if other.store == deal.store:
                continue
            key = (other.store, other.url, round(other.current_price, 2))
            if key in seen:
                continue
            seen.add(key)
            score = same_product_score(deal, other)
            if score >= settings.min_match_confidence:
                matches.append(MarketMatch(
                    store=other.store,
                    title=other.title,
                    price=other.current_price,
                    url=other.url,
                    confidence=score,
                ))

        matches.sort(key=lambda x: x.price)
        best = matches[0].price if matches else None
        advantage = None
        if best:
            advantage = round(((best - deal.current_price) / best) * 100, 1)

        hist = history_stats_for_key(product_key(deal))
        history_ok = (
            hist["count"] >= 3
            and hist["min_price"] is not None
            and hist["avg_price"] is not None
            and deal.current_price <= hist["min_price"]
            and deal.current_price <= hist["avg_price"] * 0.95
        )
        cross_store_ok = (
            best is not None
            and deal.current_price <= best
            and (advantage or 0) >= settings.min_market_advantage_percent
        )
        verified = cross_store_ok or history_ok

        if cross_store_ok:
            if advantage >= 10:
                verdict = "🔥 استثنائي"
            elif advantage >= 5:
                verdict = "🟢 ممتاز"
            elif advantage >= 2:
                verdict = "✅ جيد جدًا"
            else:
                verdict = "✅ الأفضل حاليًا"
            reason = "تمت مقارنة نفس الموديل مع متجر آخر."
        elif history_ok:
            verdict = "📉 أقل سعر مسجل"
            reason = "السعر مؤكد من تاريخ الأسعار الذي جمعه البوت."
        elif matches and best is not None and deal.current_price > best:
            verdict = "❌ ليس أفضل سعر"
            reason = "وجد البوت نفس المنتج بسعر أقل في متجر آخر."
        else:
            verdict = "⚠️ غير موثق"
            reason = "لم نجد تطابقًا قويًا كافيًا في متجر آخر حتى الآن."

        return ComparisonReport(
            verified=verified,
            verdict=verdict,
            matches=matches[:5],
            best_competitor_price=best,
            market_advantage_percent=advantage,
            history_count=hist["count"],
            historical_low=hist["min_price"],
            historical_average=hist["avg_price"],
            reason=reason,
        )

def comparison_html(report: ComparisonReport) -> str:
    lines = ["", "🧠 <b>التحقق الذكي من السعر</b>", f"التقييم: <b>{html.escape(report.verdict)}</b>"]
    if report.matches:
        lines += ["", "🔎 <b>نفس المنتج في المتاجر الأخرى:</b>"]
        for m in report.matches[:4]:
            lines.append(
                f"• {html.escape(m.store.upper())}: <b>{m.price:,.0f} ج.م</b> "
                f"(تطابق {m.confidence:.0f}%)"
            )
    if report.market_advantage_percent is not None:
        if report.market_advantage_percent >= 0:
            lines.append(f"💰 أوفر من أقرب منافس بحوالي <b>{report.market_advantage_percent:g}%</b>")
        else:
            lines.append(f"⚠️ أغلى من أقرب منافس بحوالي <b>{abs(report.market_advantage_percent):g}%</b>")
    if report.history_count:
        lines += ["", f"📚 تاريخ السعر: {report.history_count} رصد"]
        if report.historical_low is not None:
            lines.append(f"• أقل سعر مسجل: <b>{report.historical_low:,.0f} ج.م</b>")
        if report.historical_average is not None:
            lines.append(f"• متوسط السعر: <b>{report.historical_average:,.0f} ج.م</b>")
    lines += ["", f"ℹ️ {html.escape(report.reason)}"]
    return "\n".join(lines)
