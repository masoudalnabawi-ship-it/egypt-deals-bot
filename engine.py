import asyncio
import json
import logging

from config import settings
from models import Deal
from stores import CONNECTORS
from comparison import DealVerifier, comparison_html, product_key
from db import (
    save_seen, save_market_observation, should_review, save_pending,
    set_admin_message_id, get_pending_by_short, set_pending_status,
    mark_posted, historical_low,
)
from telegram_client import (
    send_admin_review, send_deal, answer_callback,
    clear_review_buttons, get_updates,
)

log = logging.getLogger("deals-bot")

def qualifies(deal):
    return deal.discount_percent >= settings.min_discount_percent and deal.saving >= settings.min_saving_egp

async def run_store(name):
    cls = CONNECTORS.get(name)
    if not cls:
        return []
    try:
        c = cls(settings.timeout, settings.user_agent)
        deals = await c.fetch_deals()
        log.info("%s: fetched %d candidates", name, len(deals))
        return deals
    except Exception as exc:
        log.exception("%s failed: %s", name, exc)
        return []

async def scan_once():
    batches = await asyncio.gather(*(run_store(s) for s in settings.enabled_stores))
    market = [d for batch in batches for d in batch]

    for deal in market:
        save_seen(deal)
        save_market_observation(product_key(deal), deal)

    candidates = [d for d in market if qualifies(d)]
    candidates.sort(key=lambda d: (d.discount_percent, d.saving), reverse=True)
    candidates = candidates[:settings.max_verify_candidates]

    verifier = DealVerifier(market)
    sent = 0

    for deal in candidates:
        if sent >= settings.max_posts_per_cycle:
            break
        fp = save_seen(deal)
        if not should_review(fp, deal):
            continue

        report = await verifier.verify(deal)
        if settings.strict_verification and not report.verified:
            log.info("UNVERIFIED rejected: %s | %s", deal.title, report.reason)
            continue

        save_pending(fp, deal)
        result = await send_admin_review(
            settings.telegram_bot_token, settings.admin_chat_id,
            deal, fp[:16], comparison_html(report)
        )
        set_admin_message_id(fp, int(result["message_id"]))
        sent += 1
        await asyncio.sleep(1)

    log.info("Cycle complete: %d VERIFIED offers sent for review", sent)
    return sent

def _deal_from_payload(payload):
    data = json.loads(payload)
    data.pop("discount_percent", None)
    return Deal(**data)

async def handle_callback(cb):
    cb_id = cb.get("id")
    from_user = cb.get("from", {})
    message = cb.get("message", {})
    data = cb.get("data", "")

    if int(from_user.get("id", 0)) != settings.admin_chat_id:
        await answer_callback(settings.telegram_bot_token, cb_id, "غير مصرح", True)
        return
    if ":" not in data:
        return

    action, short_fp = data.split(":", 1)
    row = get_pending_by_short(short_fp)
    if not row:
        await answer_callback(settings.telegram_bot_token, cb_id, "العرض غير موجود", True)
        return
    if row["status"] != "pending":
        await answer_callback(settings.telegram_bot_token, cb_id, "تم التعامل مع العرض بالفعل")
        return

    deal = _deal_from_payload(row["payload"])
    fp = row["fingerprint"]

    if action == "r":
        set_pending_status(fp, "rejected")
        await answer_callback(settings.telegram_bot_token, cb_id, "تم تجاهل العرض ❌")
    elif action in ("p", "f"):
        # Re-check immediately before publishing.
        report = await DealVerifier([]).verify(deal)
        if settings.strict_verification and not report.verified:
            set_pending_status(fp, "rejected")
            await answer_callback(
                settings.telegram_bot_token, cb_id,
                "العرض لم يعد يحقق شروط التحقق، لذلك لم يتم نشره.", True
            )
            return

        low = historical_low(fp)
        await send_deal(
            settings.telegram_bot_token, settings.telegram_channel_id, deal,
            is_historical_low=(low is None or deal.current_price <= low),
            featured=(action == "f"),
        )
        mark_posted(fp, deal)
        set_pending_status(fp, "posted")
        await answer_callback(
            settings.telegram_bot_token, cb_id,
            "تم النشر المميز ⭐" if action == "f" else "تم النشر ✅"
        )
    else:
        return

    try:
        await clear_review_buttons(
            settings.telegram_bot_token,
            int(message["chat"]["id"]), int(message["message_id"])
        )
    except Exception:
        pass

async def moderation_loop():
    offset = None
    while True:
        try:
            updates = await get_updates(settings.telegram_bot_token, offset=offset, timeout=25)
            for update in updates:
                offset = int(update["update_id"]) + 1
                if update.get("callback_query"):
                    await handle_callback(update["callback_query"])
        except Exception as exc:
            log.exception("Moderation polling error: %s", exc)
            await asyncio.sleep(5)
