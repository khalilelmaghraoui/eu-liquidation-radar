# app/bot/vavato.py
from __future__ import annotations
from typing import Any
from telegram import Update, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

from app.scrapers.vavato import VavatoScraper
from app.bot.keyboards import grid_keyboard
from app.config import settings
from app.services.ingest import upsert_listings
from app.normalizer import normalize_and_snapshot

MAX_MEDIA = 10

def register_vavato_handlers(app):
    app.add_handler(CommandHandler("vavato", vavato_entry))
    app.add_handler(CallbackQueryHandler(vavato_pick_top,  pattern=r"^vvt:top:"))
    app.add_handler(CallbackQueryHandler(vavato_pick_sub,  pattern=r"^vvt:sub:"))
    app.add_handler(CallbackQueryHandler(vavato_show_mode, pattern=r"^vvt:mode:"))

# --- tiny payload stash (keeps callback_data short) ---
def _stash(ctx: ContextTypes.DEFAULT_TYPE, obj: dict[str, Any]) -> str:
    store = ctx.user_data.setdefault("vvt_payloads", {})
    counter = ctx.user_data.setdefault("vvt_counter", 0) + 1
    ctx.user_data["vvt_counter"] = counter
    key = str(counter)
    store[key] = obj
    return key

def _fetch(ctx: ContextTypes.DEFAULT_TYPE, key: str) -> dict | None:
    return ctx.user_data.get("vvt_payloads", {}).get(key)

# ----------------------------- flows -----------------------------

async def vavato_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = VavatoScraper()
    tops = await s.list_top_categories()
    if not tops:
        await update.effective_message.reply_text("Could not discover categories right now. Try again shortly.")
        return

    rows, row = [], []
    for cat in tops:
        token = _stash(ctx, {"top_name": cat.name, "top_url": cat.url})
        row.append((cat.name, f"vvt:top:{token}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)

    await update.effective_message.reply_text(
        "🧭 *Vavato — Categories*\nPick a category:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=grid_keyboard(rows),
    )

async def vavato_pick_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, token = q.data.split(":", 2)
    payload = _fetch(ctx, token)
    if not payload:
        await q.edit_message_text("Session expired. Send /vavato again.")
        return

    s = VavatoScraper()
    subs = await s.list_subcategories(payload["top_url"])

    if not subs:
        # No subcats → let user fetch lots directly from the top page
        t2 = _stash(ctx, {"mode_payload": {"url": payload["top_url"], "name": payload["top_name"]}})
        rows = [[("Latest 10", f"vvt:mode:{t2}:L"),
                 ("Top 10 (flip score)", f"vvt:mode:{t2}:T")]]
        await q.edit_message_text(
            f"📁 *{payload['top_name']}* (no subcategories)\nHow do you want them?",
            parse_mode=ParseMode.MARKDOWN,
        )
        await q.edit_message_reply_markup(grid_keyboard(rows))
        return

    labels = []
    for sc in subs:
        t2 = _stash(ctx, {"sub_name": sc.name, "sub_url": sc.url})
        labels.append((sc.name[:35], f"vvt:sub:{t2}"))

    rows = [labels[i:i+2] for i in range(0, len(labels), 2)]
    await q.edit_message_text(
        f"📂 *{payload['top_name']}* — choose a subcategory:",
        parse_mode=ParseMode.MARKDOWN,
    )
    await q.edit_message_reply_markup(grid_keyboard(rows))

async def vavato_pick_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, token = q.data.split(":", 2)
    payload = _fetch(ctx, token)
    if not payload:
        await q.edit_message_text("Session expired. Send /vavato again.")
        return

    t2 = _stash(ctx, {"mode_payload": {"url": payload["sub_url"], "name": payload["sub_name"]}})
    rows = [[("Latest 10", f"vvt:mode:{t2}:L"),
             ("Top 10 (flip score)", f"vvt:mode:{t2}:T")]]
    await q.edit_message_text(
        f"📁 *{payload['sub_name']}*\nHow do you want them?",
        parse_mode=ParseMode.MARKDOWN,
    )
    await q.edit_message_reply_markup(grid_keyboard(rows))

async def vavato_show_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, token, mode = q.data.split(":", 3)
    container = _fetch(ctx, token)
    if not container:
        await q.edit_message_text("Session expired. Send /vavato again.")
        return
    payload = container["mode_payload"]

    s = VavatoScraper()
    raws = await s.fetch_lots_from_url(payload["url"], limit=MAX_MEDIA)

    # persist + normalize
    await upsert_listings(raws, settings.BASE_LAT, settings.BASE_LON)
    snaps = [normalize_and_snapshot(r, settings.BASE_LAT, settings.BASE_LON) for r in raws]

    if mode == "T":
        snaps.sort(key=lambda x: (x.get("flip_score") or 0.0), reverse=True)

    await _send_cards(update, snaps)
    await q.edit_message_text("Here you go 👇")

# ---------------------- presentation helpers ----------------------

async def _send_cards(update: Update, snaps: list[dict]):
    chat_id = update.effective_chat.id
    media, texts = [], []
    for it in snaps[:MAX_MEDIA]:
        cap = _fmt_card(it)
        if it.get("photo_url"):
            media.append(InputMediaPhoto(media=it["photo_url"], caption=cap, parse_mode=ParseMode.MARKDOWN))
        else:
            texts.append(cap)

    if media:
        try:
            await update.get_bot().send_media_group(chat_id=chat_id, media=media)
        except Exception:
            for m in media:
                await update.get_bot().send_photo(chat_id=chat_id, photo=m.media, caption=m.caption, parse_mode=ParseMode.MARKDOWN)

    for t in texts:
        await update.get_bot().send_message(chat_id=chat_id, text=t, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)

    lines = []
    for i, it in enumerate(snaps[:MAX_MEDIA], start=1):
        price = f"€{it.get('price_eur', 0):,.0f}".replace(",", " ")
        lines.append(f"{i}. [{it['title'][:70]}]({it['url']}) — *{price}*")
    if lines:
        await update.get_bot().send_message(chat_id=chat_id, text="**Summary**\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

def _fmt_card(it: dict) -> str:
    parts = [f"*{it['title'][:100]}*", f"[Open listing]({it['url']}) • _{it['source']}_"]
    if it.get("price_eur"):
        parts.append(f"Ask: *€{it['price_eur']:,.0f}*".replace(",", " "))
    if it.get("margin_estimate_eur") is not None:
        parts.append(f"Est. margin: *€{it['margin_estimate_eur']:,.0f}*".replace(",", " "))
    if it.get("location_name"):
        parts.append(it["location_name"])
    if it.get("price_per_kg"):
        parts.append(f"€/kg: {it['price_per_kg']:.2f}")
    if it.get("price_per_unit"):
        parts.append(f"€/unit: {it['price_per_unit']:.2f}")
    return "\n".join(parts)
