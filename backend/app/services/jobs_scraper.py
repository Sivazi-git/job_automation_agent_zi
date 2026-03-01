# backend/app/services/job_scraper.py

import hashlib
import os
from datetime import datetime
from dotenv import load_dotenv
from jobspy import scrape_jobs
from sqlalchemy.orm import Session
from app.models.models import Job
import uuid as uuid_lib

load_dotenv()

def generate_url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def fetch_jobs(
    search_term: str = None,
    location: str = None,
    hours_old: int = None,
    results_wanted: int = None
) -> list[dict]:
    """
    Fetch jobs from LinkedIn and Indeed using JobSpy.
    Returns a list of job dicts.
    """
    search_term = search_term or os.getenv("TARGET_ROLE", "Software Engineer")
    location = location or os.getenv("TARGET_LOCATION", "Remote")
    hours_old = hours_old or int(os.getenv("HOURS_OLD", 24))
    results_wanted = results_wanted or int(os.getenv("RESULTS_PER_SITE", 25))

    print(f"Searching: '{search_term}' in '{location}' (last {hours_old}hrs)")

    jobs_df = scrape_jobs(
        site_name=["linkedin", "indeed"],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=hours_old,
        linkedin_fetch_description=True,  # slower but gets full JD — needed for resume tailoring
        description_format="markdown",
    )

    if jobs_df.empty:
        print("No jobs found.")
        return []

    print(f"Found {len(jobs_df)} jobs.")
    return jobs_df.to_dict(orient="records")


def save_jobs_to_db(jobs: list[dict], db: Session) -> dict:
    """
    Save fetched jobs to the database.
    Skips duplicates using URL hash.
    Returns a summary dict.
    """
    saved = 0
    skipped = 0

    for job in jobs:
        url = str(job.get("job_url", ""))
        if not url:
            skipped += 1
            continue

        url_hash = generate_url_hash(url)

        # Check for duplicate
        existing = db.query(Job).filter(Job.url_hash == url_hash).first()
        if existing:
            skipped += 1
            continue
        
        raw_date = job.get("date_posted")
        parsed_date = raw_date if isinstance(raw_date, datetime) else datetime.utcnow()
        # Map JobSpy fields to our DB model
        new_job = Job(
            title=str(job.get("title", "Unknown")),
            company=str(job.get("company", "Unknown")),
            location=str(job.get("location", "")),
            description=str(job.get("description", "")),
            url=url,
            url_hash=url_hash,
            source=str(job.get("site", "unknown")),
            status="new",
            posted_at=parsed_date,

        )

        db.add(new_job)
        saved += 1

    db.commit()
    summary = {"saved": saved, "skipped_duplicates": skipped, "total_fetched": len(jobs)}
    print(f"DB Summary: {summary}")
    return summary

def run_pipeline_for_fetched_jobs(search_term=None, location=None):
    """
    Fetch jobs → run each through the full agent graph (ATS → tailor → apply).
    Call this from the scheduler instead of just fetch_jobs().
    """
    from app.agents.graph import graph

    jobs = fetch_jobs(search_term=search_term, location=location)

    if not jobs:
        print("No jobs fetched.")
        return

    results = {"passed": 0, "filtered": 0, "failed": 0}

    for job in jobs:
        url = str(job.get("job_url", ""))
        if not url:
            continue

        url_hash = generate_url_hash(url)

        # Skip if already processed
        db = SessionLocal()
        existing = db.query(Job).filter(Job.url_hash == url_hash).first()

        if existing and existing.status != "new":
            db.close()
            continue

        # Pre-insert the job as 'new' so save_job_to_db can update it
        if not existing:
            new_job = Job(
                id          = uuid_lib.uuid4(),
                title       = str(job.get("title", "Unknown")),
                company     = str(job.get("company", "Unknown")),
                location    = str(job.get("location", "")),
                description = str(job.get("description", "")),
                url         = url,
                url_hash    = url_hash,
                source      = str(job.get("site", "unknown")),
                status      = "new",
                posted_at   = job.get("date_posted") if isinstance(job.get("date_posted"), datetime) else datetime.utcnow(),
            )
            db.add(new_job)
            db.commit()
            job_id = str(new_job.id)
        else:
            job_id = str(existing.id)

        db.close()

        # Build initial state and run the graph
        initial_state = {
            "job_id":               job_id,
            "job_title":            str(job.get("title", "")),
            "company":              str(job.get("company", "")),
            "job_url":              url,
            "job_description":      str(job.get("description", "")),
            "job_source":           str(job.get("site", "")),
            "master_resume":        {},
            "tailored_resume":      {},
            "resume_pdf_path":      "",
            "resume_pdf_url":       "",
            "resume_id":            "",
            "ats_score":            0.0,
            "ats_breakdown":        {},
            "ats_matched_keywords": [],
            "ats_missing_keywords": [],
            "ats_passed":           False,
            "application_status":   "",
            "applied_at":           None,
            "screening_questions":  [],
            "screening_answers":    [],
            "should_apply":         False,   # flip to True in Sprint 3
            "retry_count":          0,
            "error":                None,
            "error_node":           None,
        }

        final_state = graph.invoke(initial_state)
        status = final_state.get("application_status", "unknown")

        if status == "filtered":
            results["filtered"] += 1
        elif status == "failed":
            results["failed"] += 1
        else:
            results["passed"] += 1

    print(f"\nPipeline complete: {results}")