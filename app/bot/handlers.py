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

HELP = (
    "/start - Register & show status\n"
    "/watch <keywords> - Add a watch (e.g., /watch nike adidas 42)\n"
    "/unwatch - List & delete a watch by id\n"
    "/near <km> - Set search radius (e.g., /near 300)\n"
    "/top - Top lots last 24h\n"
)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    async with SessionLocal() as s:
        existing = (await s.execute(select(User).where(User.tg_user_id == u.id))).scalar_one_or_none()
        if not existing:
            s.add(User(tg_user_id=u.id, username=u.username or "", base_city=settings.BASE_CITY, base_lat=settings.BASE_LAT, base_lon=settings.BASE_LON))
            await s.commit()
    await update.message.reply_text(
        f"👟 *EU Liquidation Radar*\nBase: {settings.BASE_CITY} ({settings.BASE_LAT:.4f},{settings.BASE_LON:.4f})\n"
        f"Type /watch keywords to begin (e.g., /watch nike adidas shoes).",\n        parse_mode=ParseMode.MARKDOWN,\n    )\n\nasync def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):\n    await update.message.reply_text(HELP)\n\nasync def watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):\n    if not ctx.args:\n        await update.message.reply_text("Usage: /watch <keywords>  e.g. /watch nike adidas 42")\n        return\n    kws = " ".join(ctx.args)\n    async with SessionLocal() as s:\n        s.add(Watch(user_id=update.effective_user.id, keyword=kws))\n        await s.commit()\n        watches = (await s.execute(select(Watch).where(Watch.user_id==update.effective_user.id))).scalars().all()\n    items = "\n".join([f"{w.id}: {w.keyword}" for w in watches])\n    await update.message.reply_text(f"Added watch: “{escape_markdown(kws,2)}”\nYour watches:\n{items}", parse_mode=ParseMode.MARKDOWN_V2)\n\nasync def unwatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):\n    async with SessionLocal() as s:\n        watches = (await s.execute(select(Watch).where(Watch.user_id==update.effective_user.id))).scalars().all()\n        if not ctx.args:\n            if not watches:\n                await update.message.reply_text("No watches yet.")\n                return\n            await update.message.reply_text("Your watches:\n"+"\n".join([f"{w.id}: {w.keyword}" for w in watches])+"\n\nDelete with /unwatch <id>")\n            return\n        try:\n            wid = int(ctx.args[0])\n        except:\n            await update.message.reply_text("Usage: /unwatch <id>")\n            return\n        await s.execute(delete(Watch).where(Watch.id==wid, Watch.user_id==update.effective_user.id))\n        await s.commit()\n    await update.message.reply_text("Removed.")\n\nasync def near_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):\n    if not ctx.args:\n        await update.message.reply_text("Usage: /near <radius_km> (e.g., /near 300)")\n        return\n    try:\n        km = int(ctx.args[0])\n        assert 10 <= km <= 3000\n    except Exception:\n        await update.message.reply_text("Give a number between 10 and 3000 km.")\n        return\n    async with SessionLocal() as s:\n        u = (await s.execute(select(User).where(User.tg_user_id==update.effective_user.id))).scalar_one_or_none()\n        if u:\n            u.radius_km = km\n            await s.commit()\n    await update.message.reply_text(f"Radius set to {km} km.")\n\nasync def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):\n    since = datetime.now(timezone.utc) - timedelta(hours=24)\n    async with SessionLocal() as s:\n        rows = (await s.execute(select(Listing).where(Listing.created_at>=since).order_by(Listing.flip_score.desc()).limit(10))).scalars().all()\n    if not rows:\n        await update.message.reply_text("No fresh lots in the last 24h.")\n        return\n    for l in rows:\n        text = (\n            f"*{l.title[:100]}*\n"\n            f"[Open listing]({l.url}) • _{l.source}_\n"\n            f"Ask: *€{l.price_eur:,.0f}*  Est.margin: *€{(l.margin_estimate_eur or 0):,.0f}*\n"\n            f"{'€/unit: ' + format(l.price_per_unit,'.2f') if l.price_per_unit else ''} "\n            f"{'€/kg: ' + format(l.price_per_kg,'.2f') if l.price_per_kg else ''}\n"\n            f"{'Distance: ~' + str(int(l.distance_km)) + ' km' if l.distance_km else ''}"\n        ).replace(",", " ")\n        if l.photo_url:\n            await update.message.reply_photo(photo=l.photo_url, caption=text, parse_mode=ParseMode.MARKDOWN)\n        else:\n            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)\n\nasync def build_app() -> Application:\n    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()\n    app.add_handler(CommandHandler("start", start))\n    app.add_handler(CommandHandler("help", help_cmd))\n    app.add_handler(CommandHandler("watch", watch))\n    app.add_handler(CommandHandler("unwatch", unwatch))\n    app.add_handler(CommandHandler("near", near_cmd))\n    app.add_handler(CommandHandler("top", top))\n    return app\n