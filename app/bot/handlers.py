# app/bot/handlers.py
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from sqlalchemy import select, delete
from app.config import settings
from app.db import SessionLocal
from app.models import User, Watch, Listing
from datetime import datetime, timedelta, timezone
from .troost import register_troost_handlers  # add this import
from .vavato import register_vavato_handlers

HELP = (
    "/start - Register & show status\n"
    "/watch <keywords> - Add a watch (e.g., /watch nike adidas 42)\n"
    "/unwatch - List & delete a watch by id\n"
    "/near <km> - Set search radius (e.g., /near 300)\n"
    "/top - Top lots last 24h\n"
    "/troost - Browse Troostwijk categories\n"  # <--- new
)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    async with SessionLocal() as s:
        existing = (await s.execute(select(User).where(User.tg_user_id == u.id))).scalar_one_or_none()
        if not existing:
            s.add(
                User(
                    tg_user_id=u.id,
                    username=u.username or "",
                    base_city=settings.BASE_CITY,
                    base_lat=settings.BASE_LAT,
                    base_lon=settings.BASE_LON,
                )
            )
            await s.commit()
    await update.message.reply_text(
        f"👟 *EU Liquidation Radar*\n"
        f"Base: {settings.BASE_CITY} ({settings.BASE_LAT:.4f},{settings.BASE_LON:.4f})\n"
        f"Type /watch keywords to begin (e.g., /watch nike adidas shoes).",
        parse_mode=ParseMode.MARKDOWN,
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /watch <keywords>  e.g. /watch nike adidas 42")
        return
    kws = " ".join(ctx.args)
    async with SessionLocal() as s:
        s.add(Watch(user_id=update.effective_user.id, keyword=kws))
        await s.commit()
        watches = (
            await s.execute(select(Watch).where(Watch.user_id == update.effective_user.id))
        ).scalars().all()
    items = "\n".join([f"{w.id}: {w.keyword}" for w in watches])
    await update.message.reply_text(
        f"Added watch: “{escape_markdown(kws, 2)}”\nYour watches:\n{items}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

async def unwatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with SessionLocal() as s:
        watches = (
            await s.execute(select(Watch).where(Watch.user_id == update.effective_user.id))
        ).scalars().all()
        if not ctx.args:
            if not watches:
                await update.message.reply_text("No watches yet.")
                return
            await update.message.reply_text(
                "Your watches:\n" + "\n".join([f"{w.id}: {w.keyword}" for w in watches]) + "\n\nDelete with /unwatch <id>"
            )
            return
        try:
            wid = int(ctx.args[0])
        except Exception:
            await update.message.reply_text("Usage: /unwatch <id>")
            return
        await s.execute(
            delete(Watch).where(Watch.id == wid, Watch.user_id == update.effective_user.id)
        )
        await s.commit()
    await update.message.reply_text("Removed.")

async def near_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /near <radius_km> (e.g., /near 300)")
        return
    try:
        km = int(ctx.args[0])
        assert 10 <= km <= 3000
    except Exception:
        await update.message.reply_text("Give a number between 10 and 3000 km.")
        return
    async with SessionLocal() as s:
        u = (
            await s.execute(select(User).where(User.tg_user_id == update.effective_user.id))
        ).scalar_one_or_none()
        if u:
            u.radius_km = km
            await s.commit()
    await update.message.reply_text(f"Radius set to {km} km.")

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(Listing)
                .where(Listing.created_at >= since)
                .order_by(Listing.flip_score.desc())
                .limit(10)
            )
        ).scalars().all()
    if not rows:
        await update.message.reply_text("No fresh lots in the last 24h.")
        return
    for l in rows:
        text = (
            f"*{l.title[:100]}*\n"
            f"[Open listing]({l.url}) • _{l.source}_\n"
            f"Ask: *€{l.price_eur:,.0f}*  Est.margin: *€{(l.margin_estimate_eur or 0):,.0f}*\n"
            f"{'€/unit: ' + format(l.price_per_unit, '.2f') if l.price_per_unit else ''} "
            f"{'€/kg: ' + format(l.price_per_kg, '.2f') if l.price_per_kg else ''}\n"
            f"{'Distance: ~' + str(int(l.distance_km)) + ' km' if l.distance_km else ''}"
        ).replace(",", " ")
        if l.photo_url:
            await update.message.reply_photo(
                photo=l.photo_url, caption=text, parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False
            )

async def build_app() -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("near", near_cmd))
    app.add_handler(CommandHandler("top", top))
    register_troost_handlers(app)  # <-- register /troost and callbacks
    register_vavato_handlers(app)      # <-- add this
    return app
