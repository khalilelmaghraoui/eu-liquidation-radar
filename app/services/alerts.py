# app/services/alerts.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
from app.db import SessionLocal
from app.models import Listing, User, Watch, UserSeen
from app.scoring import final_rank_score
import humanize

def _format_listing(l: Listing) -> str:
    parts = [
        f"*{l.title[:100]}*",
        f"[Open listing]({l.url}) • _{l.source}_",
    ]
    if l.price_eur:
        cost = f"€{l.price_eur:,.0f}".replace(",", " ")
        parts.append(f"Ask: *{cost}*")
    if l.margin_estimate_eur is not None:
        mg = f"€{l.margin_estimate_eur:,.0f}".replace(",", " ")
        parts.append(f"Est. margin: *{mg}*")
    if l.price_per_unit:
        parts.append(f"€/unit: {l.price_per_unit:.2f}")
    if l.price_per_kg:
        parts.append(f"€/kg: {l.price_per_kg:.2f}")
    if l.distance_km:
        parts.append(f"Distance: ~{int(l.distance_km)} km")
    if l.created_at:
        parts.append(f"{humanize.naturaltime(datetime.now(timezone.utc)-l.created_at)}")
    return "\n".join(parts)

async def send_hourly_digest(bot: Bot):
    async with SessionLocal() as s:
        users = (await s.execute(select(User))).scalars().all()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_listings = (await s.execute(select(Listing).where(Listing.created_at >= since))).scalars().all()

        for u in users:
            watches = (await s.execute(select(Watch).where(Watch.user_id == u.tg_user_id))).scalars().all()
            if not watches:
                continue

            candidates: list[Listing] = []
            for l in recent_listings:
                if l.distance_km and l.distance_km > (u.radius_km or 500):
                    continue
                if not any(k in (l.title or "").lower() for k in ("sneaker","shoe","trainer","adidas","nike")):
                    continue
                for w in watches:
                    if any(kw in (l.title or "").lower() for kw in w.keyword.lower().split()):
                        candidates.append(l)
                        break

            uniq = {l.id: l for l in candidates}.values()
            ranked = sorted(uniq, key=lambda x: final_rank_score(x.flip_score, x.created_at), reverse=True)[:10]
            if not ranked:
                continue

            seen_ids = set((await s.execute(select(UserSeen.listing_id).where(UserSeen.user_id == u.tg_user_id))).scalars().all())
            ranked = [l for l in ranked if l.id not in seen_ids]
            if not ranked:
                continue

            media, captions = [], []
            for l in ranked[:10]:
                caption = _format_listing(l)
                if l.photo_url:
                    media.append(InputMediaPhoto(media=l.photo_url, caption=caption, parse_mode=ParseMode.MARKDOWN))
                else:
                    captions.append(caption)

            chat_id = u.tg_user_id
            if media:
                try:
                    await bot.send_media_group(chat_id=chat_id, media=media)
                except Exception:
                    for m in media:
                        await bot.send_photo(chat_id=chat_id, photo=m.media, caption=m.caption, parse_mode=ParseMode.MARKDOWN)

            for cap in captions:
                await bot.send_message(chat_id=chat_id, text=cap, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)

            for l in ranked:
                s.add(UserSeen(user_id=u.tg_user_id, listing_id=l.id))
            await s.commit()
