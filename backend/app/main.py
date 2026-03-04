from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import uuid
from datetime import datetime

from dotenv import load_dotenv

from .database import get_db
from .models.models import Job, Resume, Application, User
from .auth import hash_password, verify_password, create_access_token
from .dependencies import get_current_user

load_dotenv()

app = FastAPI(title="Job Application Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-user in-memory pipeline state
user_pipeline_states: dict[str, dict] = {}


def _get_user_state(user_id: str) -> dict:
    if user_id not in user_pipeline_states:
        user_pipeline_states[user_id] = {
            "status": "idle",
            "last_run_at": None,
            "current_search": None,
            "processed": 0,
            "runs": [],
        }
    return user_pipeline_states[user_id]


@app.get("/")
def root():
    return {"status": "running", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def register(
    email: str = Form(...),
    password: str = Form(...),
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    target_role: Optional[str] = Form(None),
    target_location: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    github_url: Optional[str] = Form(None),
    portfolio_url: Optional[str] = Form(None),
    ats_threshold: Optional[int] = Form(60),
    daily_limit: Optional[int] = Form(8),
    resume_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    # Check duplicate email
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Parse resume PDF if provided
    resume_data = None
    resume_url = None
    if resume_file:
        pdf_bytes = await resume_file.read()
        try:
            from .services.resume_parser import parse_resume_pdf
            resume_data = parse_resume_pdf(pdf_bytes)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to parse resume: {str(e)}")

        # Upload to Supabase Storage
        try:
            import os
            from supabase import create_client
            supabase = create_client(
                os.getenv("SUPABASE_URL", ""),
                os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY", ""))
            )
            file_name = f"resumes/{uuid.uuid4()}.pdf"
            supabase.storage.from_("resumes").upload(file_name, pdf_bytes, {"content-type": "application/pdf"})
            resume_url = supabase.storage.from_("resumes").get_public_url(file_name)
        except Exception:
            # Storage upload is optional — continue without it
            pass

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        phone=phone,
        target_role=target_role,
        target_location=target_location,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        master_resume_url=resume_url,
        master_resume_data=resume_data,
        ats_threshold=ats_threshold or 60,
        daily_limit=daily_limit or 8,
        onboarding_complete=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_dict(user),
    }


@app.post("/api/auth/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    token = create_access_token(str(user.id), user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_dict(user),
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


@app.put("/api/auth/profile")
def update_profile(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {
        "full_name", "phone", "target_role", "target_location",
        "linkedin_url", "github_url", "portfolio_url",
        "ats_threshold", "daily_limit",
    }
    for key, value in payload.items():
        if key in allowed:
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return _user_dict(current_user)


@app.post("/api/auth/upload-resume")
async def upload_resume(
    resume_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pdf_bytes = await resume_file.read()
    try:
        from .services.resume_parser import parse_resume_pdf
        resume_data = parse_resume_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse resume: {str(e)}")

    resume_url = current_user.master_resume_url
    try:
        import os
        from supabase import create_client
        supabase = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY", ""))
        )
        file_name = f"resumes/{uuid.uuid4()}.pdf"
        supabase.storage.from_("resumes").upload(file_name, pdf_bytes, {"content-type": "application/pdf"})
        resume_url = supabase.storage.from_("resumes").get_public_url(file_name)
    except Exception:
        pass

    current_user.master_resume_data = resume_data
    current_user.master_resume_url = resume_url
    db.commit()
    db.refresh(current_user)
    return _user_dict(current_user)


@app.post("/api/auth/upload-resume-preview")
async def upload_resume_preview(
    resume_file: UploadFile = File(...),
):
    """Parse a PDF and return preview without saving anything."""
    pdf_bytes = await resume_file.read()
    try:
        from .services.resume_parser import parse_resume_pdf
        resume_data = parse_resume_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse resume: {str(e)}")

    # Return lightweight preview
    skills_count = sum(
        len(v) for v in resume_data.get("skills", {}).values()
        if isinstance(v, list)
    )
    return {
        "name": resume_data.get("name", ""),
        "email": resume_data.get("email", ""),
        "skills_count": skills_count,
        "experience_count": len(resume_data.get("experience", [])),
        "parsed_data": resume_data,
    }


def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "target_role": user.target_role,
        "target_location": user.target_location,
        "linkedin_url": user.linkedin_url,
        "github_url": user.github_url,
        "portfolio_url": user.portfolio_url,
        "master_resume_url": user.master_resume_url,
        "ats_threshold": user.ats_threshold,
        "daily_limit": user.daily_limit,
        "onboarding_complete": user.onboarding_complete,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    total = db.query(func.count(Job.id)).filter(Job.user_id == uid).scalar() or 0
    passed_ats = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.ats_score >= 70).scalar() or 0
    filtered = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.status == "skipped").scalar() or 0
    applied = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.status == "applied").scalar() or 0
    failed = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.status == "failed").scalar() or 0
    queued = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.status == "queued").scalar() or 0

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.user_id == current_user.id)

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
def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
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
async def run_pipeline(
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    state = _get_user_state(uid)

    if state["status"] == "in_progress":
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

    state["status"] = "in_progress"
    state["current_search"] = search_term
    state["processed"] = 0
    state["runs"].insert(0, run_entry)
    state["runs"] = state["runs"][:5]

    # Capture values for the background task closure
    master_resume_data = current_user.master_resume_data
    ats_threshold = current_user.ats_threshold or 60

    def _execute():
        try:
            from .agents.graph import graph

            initial_state = {
                "user_id": uid,
                "master_resume_data": master_resume_data,
                "ats_threshold": ats_threshold,
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
            run_entry["passed"] = sum(1 for j in processed if j.get("passed"))
            run_entry["filtered"] = sum(
                1 for j in processed if j.get("status") == "filtered"
            )
            run_entry["failed"] = sum(
                1 for j in processed if j.get("status") == "failed"
            )
            run_entry["status"] = "completed"
        except Exception as e:
            run_entry["status"] = "failed"
            run_entry["error"] = str(e)
        finally:
            state["status"] = "idle"
            state["last_run_at"] = datetime.utcnow().isoformat()

    background_tasks.add_task(_execute)
    return {
        "status": "started",
        "message": f"Pipeline started for '{search_term}' in '{location}'",
    }


@app.get("/api/pipeline/status")
def get_pipeline_status(current_user: User = Depends(get_current_user)):
    uid = str(current_user.id)
    state = _get_user_state(uid)
    return {
        "status": state["status"],
        "last_run_at": state["last_run_at"],
        "processed": state["processed"],
        "current_search": state["current_search"],
        "runs": state["runs"],
    }


@app.delete("/api/admin/cleanup-low-ats")
def cleanup_low_ats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete current user's jobs with ATS score < 50."""
    deleted = (
        db.query(Job)
        .filter(
            Job.user_id == current_user.id,
            Job.ats_score < 50,
            Job.ats_score.isnot(None),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted, "message": f"Removed {deleted} jobs with ATS score < 50"}
