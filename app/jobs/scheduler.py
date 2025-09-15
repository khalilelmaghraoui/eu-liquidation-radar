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
    sched.add_job(lambda: send_hourly_digest(bot), CronTrigger(minute=(settings.HOURLY_SCRAPE_MINUTE + 2) % 60))
    sched.start()
    return sched
