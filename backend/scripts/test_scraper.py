import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from app.services.jobs_scraper import fetch_jobs, save_jobs_to_db
from app.database import SessionLocal

def main():
    print("=== Testing Job Scraper ===\n")

    # 1. Fetch jobs
    jobs = fetch_jobs(
        search_term="Software Engineer",
        location="Remote",
        hours_old=48,       # wider window for testing
        results_wanted=10   # small number for testing
    )

    if not jobs:
        print("No jobs returned. Check your search term or try hours_old=72.")
        return

    # 2. Print first job to inspect shape
    print("\n--- Sample Job ---")
    sample = jobs[0]
    print(f"Title:       {sample.get('title')}")
    print(f"Company:     {sample.get('company')}")
    print(f"Location:    {sample.get('location')}")
    print(f"Source:      {sample.get('site')}")
    print(f"URL:         {sample.get('job_url')}")
    print(f"Posted:      {sample.get('date_posted')}")
    desc = str(sample.get('description', ''))
    print(f"Description: {desc[:200]}...")

    # 3. Save to DB
    print("\n--- Saving to DB ---")
    db = SessionLocal()
    try:
        summary = save_jobs_to_db(jobs, db)
        print(f"Result: {summary}")
    finally:
        db.close()

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()