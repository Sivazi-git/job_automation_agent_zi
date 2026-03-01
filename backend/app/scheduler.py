# backend/app/scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.jobs_scraper import fetch_jobs, save_jobs_to_db,run_pipeline_for_fetched_jobs

from app.database import SessionLocal
from dotenv import load_dotenv

load_dotenv()

def daily_job_scrape():
    print(f"[Scheduler] Starting daily job scrape...")
    db = SessionLocal()
    try:
        print("[Scheduler] Starting daily pipeline...")
        run_pipeline_for_fetched_jobs()
        print(f"[Scheduler] Done: {summary}")
    except Exception as e:
        print(f"[Scheduler] Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    scheduler = BlockingScheduler()

    # Run every day at 8:00 AM
    scheduler.add_job(
        daily_job_scrape,
        CronTrigger(hour=8, minute=0),
        id="daily_scrape",
        name="Daily LinkedIn + Indeed Job Scrape",
        replace_existing=True,
    )

    print("[Scheduler] Running. Daily scrape at 8:00 AM. Press Ctrl+C to stop.")

    # Run once immediately on startup so you don't wait until 8am to test
    daily_job_scrape()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("[Scheduler] Stopped.")