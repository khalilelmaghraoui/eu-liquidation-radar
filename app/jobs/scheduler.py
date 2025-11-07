# app/jobs/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from app.services.alerts import send_hourly_digest
from app.workers import run_scrape_cycle
from app.config import settings

async def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(run_scrape_cycle, CronTrigger(minute=settings.HOURLY_SCRAPE_MINUTE))
    # pass async function directly with args — no lambda that returns a coroutine
    sched.add_job(
        send_hourly_digest,
        CronTrigger(minute=(settings.HOURLY_SCRAPE_MINUTE + 2) % 60),
        args=[bot],
    )
    sched.start()
    return sched
