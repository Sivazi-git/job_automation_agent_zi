from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import uuid
from datetime import datetime

from dotenv import load_dotenv

from .database import get_db
from .models.models import Job, Resume, Application

load_dotenv()

app = FastAPI(title="Job Application Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory pipeline state tracker
pipeline_state: dict = {
    "status": "idle",
    "last_run_at": None,
    "current_search": None,
    "processed": 0,
    "runs": [],
}


@app.get("/")
def root():
    return {"status": "running", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Job.id)).scalar() or 0
    passed_ats = db.query(func.count(Job.id)).filter(Job.ats_score >= 70).scalar() or 0
    filtered = db.query(func.count(Job.id)).filter(Job.status == "skipped").scalar() or 0
    applied = db.query(func.count(Job.id)).filter(Job.status == "applied").scalar() or 0
    failed = db.query(func.count(Job.id)).filter(Job.status == "failed").scalar() or 0
    queued = db.query(func.count(Job.id)).filter(Job.status == "queued").scalar() or 0

    return {
        "total": total,
        "passed_ats": passed_ats,
        "filtered": filtered,
        "applied": applied,
        "failed": failed,
        "queued": queued,
    }


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def get_jobs(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("ats_score_desc"),
    db: Session = Depends(get_db),
):
    query = db.query(Job)

    if status and status != "all":
        query = query.filter(Job.status == status)

    if sort == "ats_score_desc":
        query = query.order_by(Job.ats_score.desc().nullslast())
    elif sort == "ats_score_asc":
        query = query.order_by(Job.ats_score.asc().nullsfirst())
    elif sort == "created_at_desc":
        query = query.order_by(Job.created_at.desc())
    else:
        query = query.order_by(Job.created_at.desc())

    total = query.count()
    jobs = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "jobs": [
            {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "status": job.status,
                "ats_score": job.ats_score,
                "url": job.url,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
            for job in jobs
        ],
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume = db.query(Resume).filter(Resume.job_id == job_uuid).first()
    application = db.query(Application).filter(Application.job_id == job_uuid).first()

    return {
        "id": str(job.id),
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "url": job.url,
        "source": job.source,
        "status": job.status,
        "ats_score": job.ats_score,
        "ats_breakdown": job.ats_breakdown,
        "ats_matched_keywords": job.ats_matched_keywords,
        "ats_missing_keywords": job.ats_missing_keywords,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "resume_url": resume.file_url if resume else None,
        "applied_at": application.applied_at.isoformat() if application else None,
    }


# ── Pipeline ──────────────────────────────────────────────────────────────────

@app.post("/api/pipeline/run")
async def run_pipeline(payload: dict, background_tasks: BackgroundTasks):
    if pipeline_state["status"] == "in_progress":
        return {"error": "Pipeline already running"}

    search_term = payload.get("search_term", "")
    location = payload.get("location", "")
    should_apply = payload.get("should_apply", False)

    run_entry: dict = {
        "started_at": datetime.utcnow().isoformat(),
        "search_term": search_term,
        "location": location,
        "should_apply": should_apply,
        "jobs_found": 0,
        "passed": 0,
        "filtered": 0,
        "failed": 0,
        "status": "running",
    }

    pipeline_state["status"] = "in_progress"
    pipeline_state["current_search"] = search_term
    pipeline_state["processed"] = 0
    pipeline_state["runs"].insert(0, run_entry)
    pipeline_state["runs"] = pipeline_state["runs"][:5]

    def _execute():
        try:
            from .agents.graph import graph

            initial_state = {
                "search_term": search_term,
                "location": location,
                "should_apply": should_apply,
                "fetched_jobs": [],
                "current_job_index": 0,
                "total_jobs": 0,
                "processed_jobs": [],
                "pipeline_complete": False,
                "retry_count": 0,
                "error": None,
                "error_node": None,
            }
            result = graph.invoke(initial_state)
            processed = result.get("processed_jobs", [])
            run_entry["jobs_found"] = len(processed)
            run_entry["passed"] = sum(
                1 for j in processed if j.get("outcome") not in ("filtered", "failed")
            )
            run_entry["filtered"] = sum(
                1 for j in processed if j.get("outcome") == "filtered"
            )
            run_entry["failed"] = sum(
                1 for j in processed if j.get("outcome") == "failed"
            )
            run_entry["status"] = "completed"
        except Exception as e:
            run_entry["status"] = "failed"
            run_entry["error"] = str(e)
        finally:
            pipeline_state["status"] = "idle"
            pipeline_state["last_run_at"] = datetime.utcnow().isoformat()

    background_tasks.add_task(_execute)
    return {
        "status": "started",
        "message": f"Pipeline started for '{search_term}' in '{location}'",
    }


@app.get("/api/pipeline/status")
def get_pipeline_status():
    return {
        "status": pipeline_state["status"],
        "last_run_at": pipeline_state["last_run_at"],
        "processed": pipeline_state["processed"],
        "current_search": pipeline_state["current_search"],
        "runs": pipeline_state["runs"],
    }
