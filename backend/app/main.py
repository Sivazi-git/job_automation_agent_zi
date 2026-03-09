from __future__ import annotations

import asyncio
import queue as _queue
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from .database import get_db
from .models.models import Job, Resume, Application, User
from .auth import hash_password, verify_password, create_access_token, decode_access_token
from .dependencies import get_current_user
from . import pipeline_events

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # On shutdown: cancel all running pipelines so background threads exit
    pipeline_events.cancel_all()

app = FastAPI(title="Job Application Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-user in-memory pipeline state
user_pipeline_states: dict[str, dict] = {}


DAILY_RUN_LIMIT = 3


def _get_user_state(user_id: str) -> dict:
    if user_id not in user_pipeline_states:
        user_pipeline_states[user_id] = {
            "status": "idle",
            "last_run_at": None,
            "current_search": None,
            "processed": 0,
            "runs": [],
            "runs_today": 0,
            "runs_reset_date": datetime.now(timezone.utc).date().isoformat(),
        }
    return user_pipeline_states[user_id]


def _refresh_daily_counter(state: dict) -> None:
    """Reset runs_today if the UTC date has rolled over."""
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("runs_reset_date") != today:
        state["runs_today"] = 0
        state["runs_reset_date"] = today


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
    needs_review = db.query(func.count(Job.id)).filter(Job.user_id == uid, Job.status == "needs_review").scalar() or 0

    return {
        "total": total,
        "passed_ats": passed_ats,
        "filtered": filtered,
        "applied": applied,
        "failed": failed,
        "queued": queued,
        "needs_review": needs_review,
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
        "screening_questions": job.screening_questions,
        "apply_status_detail": job.apply_status_detail,
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

    _refresh_daily_counter(state)
    if state["runs_today"] >= DAILY_RUN_LIMIT:
        return {"error": f"Daily limit reached. You can run the pipeline {DAILY_RUN_LIMIT} times per day."}

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
    state["runs_today"] = state.get("runs_today", 0) + 1
    state["runs"].insert(0, run_entry)
    state["runs"] = state["runs"][:5]

    # Capture values for the background task closure
    master_resume_data = current_user.master_resume_data
    ats_threshold = current_user.ats_threshold or 60

    # Reset cancel flag and flush stale logs before the new run
    pipeline_events.reset_pipeline(uid)
    pipeline_events.emit(uid, f"Pipeline starting: '{search_term}' in '{location or 'anywhere'}'")

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
                "needs_human_review": False,
                "review_reason": "",
                "human_answers": {},
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
            pipeline_events.emit(uid, f"Pipeline error: {e}", level="error")
            pipeline_events.emit_done(uid)
        finally:
            state["status"] = "idle"
            state["last_run_at"] = datetime.utcnow().isoformat()

    # Use a daemon thread so the thread is killed if the server process exits
    t = threading.Thread(target=_execute, daemon=True, name=f"pipeline-{uid[:8]}")
    t.start()

    return {
        "status": "started",
        "message": f"Pipeline started for '{search_term}' in '{location}'",
    }


@app.get("/api/pipeline/status")
def get_pipeline_status(current_user: User = Depends(get_current_user)):
    uid = str(current_user.id)
    state = _get_user_state(uid)
    _refresh_daily_counter(state)
    runs_today = state.get("runs_today", 0)
    return {
        "status": state["status"],
        "last_run_at": state["last_run_at"],
        "processed": state["processed"],
        "current_search": state["current_search"],
        "runs": state["runs"],
        "runs_today": runs_today,
        "runs_remaining": max(0, DAILY_RUN_LIMIT - runs_today),
        "daily_limit": DAILY_RUN_LIMIT,
    }


@app.post("/api/pipeline/stop")
def stop_pipeline(current_user: User = Depends(get_current_user)):
    uid = str(current_user.id)
    pipeline_events.cancel_pipeline(uid)
    state = _get_user_state(uid)
    state["status"] = "idle"
    return {"status": "stopping", "message": "Pipeline cancellation requested"}


@app.get("/api/pipeline/logs")
async def pipeline_logs(
    token: str = Query(...),
):
    """
    SSE endpoint for live pipeline logs.
    Auth via ?token= query param because EventSource doesn't support headers.
    """
    import json as _json

    try:
        payload = decode_access_token(token)
        uid = payload.get("sub")
        if not uid:
            raise ValueError("no sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    log_q = pipeline_events.drain_logs(uid)

    async def event_stream():
        while True:
            try:
                entry = log_q.get_nowait()
                if entry is None:
                    # Sentinel — pipeline finished
                    yield f"data: {_json.dumps({'done': True})}\n\n"
                    return
                yield f"data: {_json.dumps(entry)}\n\n"
            except _queue.Empty:
                # Keepalive every 0.3 s so the connection stays open
                yield ": keepalive\n\n"
                await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Auto-apply routes ─────────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/generate-resume")
async def generate_resume_for_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a tailored resume PDF for a specific job on demand."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    master_data = current_user.master_resume_data
    if not master_data:
        raise HTTPException(status_code=422, detail="No master resume on file. Upload a resume first.")

    try:
        from .services.resume_tailor import tailor_resume as tailor_resume_llm
        from .services.pdf_generator import generate_pdf as generate_pdf_file
        from .services.storage import upload_resume_pdf
        import json as _json

        tailored = tailor_resume_llm(
            job_title=job.title,
            company=job.company,
            job_description=job.description or "",
        )
        local_path = generate_pdf_file(tailored, job_id)
        public_url = upload_resume_pdf(local_path, job_id)

        resume_record = Resume(
            user_id=current_user.id,
            job_id=job_uuid,
            file_url=public_url,
            tailored_content=_json.dumps(tailored),
        )
        db.add(resume_record)
        db.commit()
        db.refresh(resume_record)

        return {
            "resume_id": str(resume_record.id),
            "file_url": resume_record.file_url,
            "tailored_content": resume_record.tailored_content,
            "created_at": resume_record.created_at.isoformat() if resume_record.created_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume generation failed: {str(e)}")


@app.get("/api/jobs/{job_id}/resume")
def get_job_resume(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the latest tailored resume record for a job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume = (
        db.query(Resume)
        .filter(Resume.job_id == job_uuid, Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found for this job")

    return {
        "resume_id": str(resume.id),
        "file_url": resume.file_url,
        "tailored_content": resume.tailored_content,
        "created_at": resume.created_at.isoformat() if resume.created_at else None,
    }


@app.post("/api/jobs/{job_id}/apply")
async def apply_to_job_route(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger Playwright-based application for a specific job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "applied":
        raise HTTPException(status_code=409, detail="Already applied to this job")

    resume = (
        db.query(Resume)
        .filter(Resume.job_id == job_uuid, Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )
    if not resume:
        raise HTTPException(status_code=422, detail="Generate a resume for this job first")

    # Gather user data for the applier
    import json as _json
    tailored_data: dict = {}
    try:
        tailored_data = _json.loads(resume.tailored_content or "{}")
    except Exception:
        pass

    user_data = {
        "full_name":     current_user.full_name or "",
        "email":         current_user.email,
        "phone":         current_user.phone or "",
        "linkedin_url":  current_user.linkedin_url or "",
        "github_url":    current_user.github_url or "",
        "portfolio_url": current_user.portfolio_url or "",
    }

    uid = str(current_user.id)

    def _run_apply():
        import asyncio
        from .services.job_applier import apply_to_job as _apply
        from .services.screening_answerer import answer_questions
        from .database import SessionLocal as _SL
        from .models.models import Job as _Job

        _db = _SL()
        try:
            _job = _db.query(_Job).filter(_Job.id == job_uuid).first()
            if not _job:
                return

            # Get local PDF path — try temp dir convention used by pdf_generator
            import tempfile, os
            local_path = os.path.join(tempfile.gettempdir(), f"resume_{job_id}.pdf")

            result = asyncio.run(_apply(
                job_url=str(_job.url),
                resume_pdf_path=local_path,
                user_data=user_data,
            ))

            if result.status == "failed":
                _job.status = "failed"
                _job.apply_status_detail = result.error
                _db.commit()
                return

            if result.status == "needs_screening":
                questions_raw = result.screening_questions
                # Ask Claude to draft answers
                answers = answer_questions(
                    questions=questions_raw,
                    tailored_resume=tailored_data,
                    job_title=_job.title,
                    company=_job.company,
                )
                enriched = []
                for q_text in questions_raw:
                    matched = next((a for a in answers if a["question"] == q_text), None)
                    conf = float(matched["confidence"]) if matched else 0.0
                    enriched.append({
                        "question":     q_text,
                        "claude_answer": matched["answer"] if matched else "",
                        "confidence":   conf,
                        "needs_review": conf < 0.75,
                    })

                needs_review = any(q["needs_review"] for q in enriched)
                _job.screening_questions = enriched
                _job.status = "needs_review" if needs_review else "queued"
                _db.commit()
                return

            # Applied successfully
            _job.status = "applied"
            _job.apply_status_detail = None
            _db.commit()

            from .models.models import Application as _App
            app_record = _App(
                user_id=_job.user_id,
                job_id=_job.id,
                resume_id=resume.id,
                status="applied",
            )
            _db.add(app_record)
            _db.commit()

        except Exception as e:
            _db.rollback()
            try:
                _job2 = _db.query(_Job).filter(_Job.id == job_uuid).first()
                if _job2:
                    _job2.status = "failed"
                    _job2.apply_status_detail = str(e)
                    _db.commit()
            except Exception:
                pass
        finally:
            _db.close()

    # Set to queued immediately so UI can show progress
    job.status = "queued"
    db.commit()

    background_tasks.add_task(_run_apply)
    return {"status": "started", "message": "Application process started in the background"}


@app.get("/api/jobs/{job_id}/screening")
def get_screening_questions(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return screening questions for human review."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"questions": job.screening_questions or []}


@app.post("/api/jobs/{job_id}/screening-answers")
async def submit_screening_answers(
    job_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    User submits human-reviewed answers.
    Merges them into the job's screening_questions and re-runs the apply step.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job = db.query(Job).filter(Job.id == job_uuid, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    answers: dict = payload.get("answers", {})
    if not answers:
        raise HTTPException(status_code=422, detail="No answers provided")

    # Merge human answers into stored screening_questions
    existing_qs = list(job.screening_questions or [])
    for q in existing_qs:
        text = q.get("question", "")
        if text in answers:
            q["claude_answer"] = answers[text]
            q["confidence"] = 1.0
            q["needs_review"] = False

    job.screening_questions = existing_qs

    resume = (
        db.query(Resume)
        .filter(Resume.job_id == job_uuid, Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )

    user_data = {
        "full_name":     current_user.full_name or "",
        "email":         current_user.email,
        "phone":         current_user.phone or "",
        "linkedin_url":  current_user.linkedin_url or "",
        "github_url":    current_user.github_url or "",
        "portfolio_url": current_user.portfolio_url or "",
    }

    job.status = "queued"
    db.commit()

    import json as _json
    tailored_data: dict = {}
    try:
        if resume:
            tailored_data = _json.loads(resume.tailored_content or "{}")
    except Exception:
        pass

    saved_qs = list(existing_qs)

    def _reapply():
        import asyncio, os, tempfile
        from .services.job_applier import apply_to_job as _apply
        from .database import SessionLocal as _SL
        from .models.models import Job as _Job, Application as _App

        _db = _SL()
        try:
            _job = _db.query(_Job).filter(_Job.id == job_uuid).first()
            if not _job:
                return

            local_path = os.path.join(tempfile.gettempdir(), f"resume_{job_id}.pdf")
            result = asyncio.run(_apply(
                job_url=str(_job.url),
                resume_pdf_path=local_path,
                user_data=user_data,
            ))

            if result.status == "failed":
                _job.status = "failed"
                _job.apply_status_detail = result.error
                _db.commit()
                return

            _job.status = "applied"
            _job.apply_status_detail = None
            _db.commit()

            app_record = _App(
                user_id=_job.user_id,
                job_id=_job.id,
                resume_id=resume.id if resume else None,
                status="applied",
            )
            _db.add(app_record)
            _db.commit()

        except Exception as e:
            _db.rollback()
            try:
                _job2 = _db.query(_Job).filter(_Job.id == job_uuid).first()
                if _job2:
                    _job2.status = "failed"
                    _job2.apply_status_detail = str(e)
                    _db.commit()
            except Exception:
                pass
        finally:
            _db.close()

    background_tasks.add_task(_reapply)
    return {"status": "started", "message": "Re-applying with your answers"}


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
