# main.py
import asyncio
import logging

from app.config import settings
from app.db import init_db
from app.bot.handlers import build_app as build_bot_app
from app.jobs.scheduler import start_scheduler
from app.web.server import create_app as create_web_app
import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

async def run():
    await init_db()
    application = await build_bot_app()
    scheduler = await start_scheduler(application.bot)

    # Start bot polling and FastAPI sidecar concurrently
    config = uvicorn.Config(create_web_app(application.bot), host=settings.WEB_HOST, port=settings.WEB_PORT, log_level=settings.LOG_LEVEL.lower())
    server = uvicorn.Server(config)

    await asyncio.gather(
        application.run_polling(close_loop=False),
        server.serve()
    )

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
