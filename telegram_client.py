import html
import httpx
from models import Deal

def money(v):
    return "-" if v is None else f"{v:,.0f} ج.م"

def build_message(deal, is_historical_low=False):
    low = "\n📉 <b>أقل سعر مسجل عندنا</b>" if is_historical_low else ""
    old = f"\n❌ السعر السابق: <s>{money(deal.old_price)}</s>" if deal.old_price else ""
    saving = f"\n💰 التوفير: <b>{money(deal.saving)}</b>" if deal.saving > 0 else ""
    return (
        f"🔥 <b>عرض تم التحقق منه — {html.escape(deal.store.upper())}</b>\n\n"
        f"🛍️ {html.escape(deal.title)}\n"
        f"✅ السعر الآن: <b>{money(deal.current_price)}</b>{old}{saving}"
        f"\n📊 خصم المتجر: <b>{deal.discount_percent:g}%</b>{low}\n\n"
        f'<a href="{html.escape(deal.url, quote=True)}">🔗 شاهد العرض</a>'
    )

def build_featured_message(deal, is_historical_low=False):
    low = "\n🏆 <b>من أفضل الأسعار المسجلة عندنا</b>" if is_historical_low else ""
    old = f"\n❌ بدلًا من: <s>{money(deal.old_price)}</s>" if deal.old_price else ""
    return (
        "🔥🔥 <b>عرض مميز تم التحقق منه</b> 🔥🔥\n\n"
        f"⭐ <b>{html.escape(deal.title)}</b>\n\n"
        f"✅ الآن: <b>{money(deal.current_price)}</b>{old}\n"
        f"💰 وفر: <b>{money(deal.saving)}</b>\n"
        f"📉 خصم المتجر: <b>{deal.discount_percent:g}%</b>{low}\n\n"
        f"🛒 المتجر: <b>{html.escape(deal.store.upper())}</b>\n"
        f'<a href="{html.escape(deal.url, quote=True)}">🔗 اضغط هنا لمشاهدة العرض</a>\n\n'
        "⚡ السعر أو المخزون قد يتغير في أي وقت."
    )

async def _post(token, method, payload):
    async with httpx.AsyncClient(timeout=35) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data)
        return data["result"]

async def send_deal(token, channel_id, deal, is_historical_low=False, featured=False):
    text = build_featured_message(deal, is_historical_low) if featured else build_message(deal, is_historical_low)
    return await _post(token, "sendMessage", {
        "chat_id": channel_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })

async def send_admin_review(token, admin_chat_id, deal, short_fp, comparison_text=""):
    text = (
        "🔎 <b>عرض موثّق للمراجعة</b>\n\n"
        f"🛍️ {html.escape(deal.title)}\n"
        f"🏪 المتجر: <b>{html.escape(deal.store.upper())}</b>\n"
        f"✅ السعر: <b>{money(deal.current_price)}</b>\n"
        f"❌ السابق: <s>{money(deal.old_price)}</s>\n"
        f"💰 التوفير: <b>{money(deal.saving)}</b>\n"
        f"📊 خصم المتجر: <b>{deal.discount_percent:g}%</b>\n"
        f"{comparison_text}\n\n"
        f'<a href="{html.escape(deal.url, quote=True)}">🔗 فتح العرض</a>'
    )
    keyboard = {"inline_keyboard": [
        [{"text": "✅ نشر", "callback_data": f"p:{short_fp}"}, {"text": "⭐ مميز", "callback_data": f"f:{short_fp}"}],
        [{"text": "❌ تجاهل", "callback_data": f"r:{short_fp}"}],
    ]}
    return await _post(token, "sendMessage", {
        "chat_id": admin_chat_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": False, "reply_markup": keyboard,
    })

async def answer_callback(token, callback_query_id, text, show_alert=False):
    return await _post(token, "answerCallbackQuery", {
        "callback_query_id": callback_query_id, "text": text, "show_alert": show_alert,
    })

async def clear_review_buttons(token, chat_id, message_id):
    return await _post(token, "editMessageReplyMarkup", {
        "chat_id": chat_id, "message_id": message_id,
        "reply_markup": {"inline_keyboard": []},
    })

async def get_updates(token, offset=None, timeout=25):
    params = {"timeout": timeout, "allowed_updates": ["callback_query", "message"]}
    if offset is not None:
        params["offset"] = offset
    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        r = await client.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data)
        return data["result"]
