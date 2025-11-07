# main.py — PTB (async) + FastAPI + APScheduler, no event-loop conflicts
import asyncio
import logging

import uvicorn
from app.config import settings
from app.db import init_db
from app.bot.handlers import build_app as build_bot_app
from app.jobs.scheduler import start_scheduler
from app.web.server import create_app as create_web_app

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

async def run():
    # 1) DB
    await init_db()

    # 2) Telegram bot (PTB 20/21 async pattern)
    application = await build_bot_app()
    await application.initialize()
    await application.start()                 # starts the bot
    await application.updater.start_polling() # start long polling (non-blocking)

    # 3) Scheduler
    scheduler = await start_scheduler(application.bot)

    # 4) FastAPI via Uvicorn (this will block until Ctrl+C / shutdown)
    web_app = create_web_app(application.bot)
    server = uvicorn.Server(
        uvicorn.Config(
            web_app,
            host=settings.WEB_HOST,
            port=settings.WEB_PORT,
            log_level=settings.LOG_LEVEL.lower(),
        )
    )

    try:
        # Run API server "forever". Bot polling & scheduler run in the background.
        await server.serve()
    finally:
        # Graceful shutdown
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        try:
            await application.updater.stop()
        except Exception:
            pass
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
