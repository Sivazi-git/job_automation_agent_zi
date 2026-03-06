import asyncio
import json
import uuid as uuid_lib
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from app.agents.state import AgentState
from app.services.jobs_scraper import fetch_jobs
from app.services.ats_scorer import passes_ats
from app.services.resume_tailor import tailor_resume as tailor_resume_llm, load_master_resume
from app.services.pdf_generator import generate_pdf as generate_pdf_file
from app.services.storage import upload_resume_pdf
from app.database import SessionLocal
from app.models.models import Job, Resume
from app import pipeline_events

load_dotenv()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(state: AgentState, message: str, level: str = "info") -> None:
    uid = state.get("user_id", "")
    if uid:
        pipeline_events.emit(uid, message, level)


def _cancelled(state: AgentState) -> bool:
    uid = state.get("user_id", "")
    return pipeline_events.is_cancelled(uid) if uid else False


def _cancelled_state(state: AgentState) -> AgentState:
    """Return a terminal state that stops the pipeline cleanly."""
    _emit(state, "Pipeline stopped by user.", level="warn")
    return {
        **state,
        "pipeline_complete": True,
        "error":             "Cancelled by user",
        "error_node":        "cancelled",
    }

def fetch_jobs_node(state: AgentState) -> AgentState:
    """
    First node. Hits JobSpy and loads all fetched jobs into state.
    Resets all per-job fields and sets up the batch for iteration.
    """
    if _cancelled(state):
        return _cancelled_state(state)

    _emit(state, f"Searching for '{state['search_term']}' in '{state['location'] or 'anywhere'}'…")
    try:
        jobs = fetch_jobs(
            search_term=state["search_term"],
            location=state["location"]
        )

        _emit(state, f"Found {len(jobs)} job listings.")

        return {
            **state,
            "fetched_jobs":       jobs,
            "current_job_index":  0,
            "total_jobs":         len(jobs),
            "processed_jobs":     [],
            "pipeline_complete":  False,
            "error":              None,
            "error_node":         None,
        }
    except Exception as e:
        _emit(state, f"Job fetch failed: {e}", level="error")
        return {
            **state,
            "fetched_jobs":      [],
            "total_jobs":        0,
            "pipeline_complete": True,
            "error":             f"fetch_jobs failed: {str(e)}",
            "error_node":        "fetch_jobs",
        }


# ── Node 2: Load Current Job ───────────────────────────────────────────────────

def load_current_job(state: AgentState) -> AgentState:
    """
    Picks the next job from fetched_jobs by current_job_index.
    Resets all per-job fields so previous job data doesn't bleed through.
    Skips jobs that are already in the DB and not in 'new' status.
    """
    if _cancelled(state):
        return _cancelled_state(state)

    index = state["current_job_index"]
    jobs  = state["fetched_jobs"]

    # Check if batch is exhausted
    if index >= len(jobs):
        return {**state, "pipeline_complete": True}

    job = jobs[index]
    url = str(job.get("job_url", ""))

    if not url:
        # No URL — skip silently by advancing index
        return {
            **state,
            "current_job_index": index + 1,
            "job_id":            "",
            "job_title":         "",
            "company":           "",
            "job_url":           "",
            "job_description":   "",
            "job_source":        "",
            "error":             None,
        }

    # Check for duplicate in DB
    db = SessionLocal()
    try:
        from app.services.jobs_scraper import generate_url_hash
        url_hash = generate_url_hash(url)
        existing = db.query(Job).filter(Job.url_hash == url_hash).first()

        if existing and existing.status not in ("new", "failed"):
            print(f"[load_current_job] Skipping already processed: {job.get('title')} at {job.get('company')}")
            # Advance index, mark as skipped in processed log
            processed = list(state.get("processed_jobs", []))
            processed.append({
                "title":   job.get("title"),
                "company": job.get("company"),
                "status":  "duplicate_skip",
                "score":   None,
            })
            return {
                **state,
                "current_job_index": index + 1,
                "processed_jobs":    processed,
                "error":             None,
            }

        # Pre-insert as 'new' if not exists
        if not existing:
            raw_date  = job.get("date_posted")
            posted_at = raw_date if isinstance(raw_date, datetime) else datetime.utcnow()
            user_uuid = None
            try:
                if state.get("user_id"):
                    import uuid as _uuid
                    user_uuid = _uuid.UUID(state["user_id"])
            except (ValueError, AttributeError):
                pass

            new_job = Job(
                id          = uuid_lib.uuid4(),
                user_id     = user_uuid,
                title       = str(job.get("title", "Unknown")),
                company     = str(job.get("company", "Unknown")),
                location    = str(job.get("location", "")),
                description = str(job.get("description", "")),
                url         = url,
                url_hash    = url_hash,
                source      = str(job.get("site", "unknown")),
                status      = "new",
                posted_at   = posted_at,
            )
            db.add(new_job)
            db.commit()
            job_id = str(new_job.id)
        else:
            job_id = str(existing.id)

    finally:
        db.close()

    _emit(state, f"[{index + 1}/{len(jobs)}] Processing: {job.get('title')} at {job.get('company')}")

    return {
        **state,
        # Per-job fields — reset cleanly
        "job_id":               job_id,
        "job_title":            str(job.get("title", "")),
        "company":              str(job.get("company", "")),
        "job_url":              url,
        "job_description":      str(job.get("description", "")),
        "job_source":           str(job.get("site", "")),
        "ats_score":            0.0,
        "ats_breakdown":        {},
        "ats_matched_keywords": [],
        "ats_missing_keywords": [],
        "ats_passed":           False,
        "tailored_resume":      {},
        "resume_pdf_path":      "",
        "resume_pdf_url":       "",
        "resume_id":            "",
        "application_status":   "",
        "applied_at":           None,
        "screening_questions":  [],
        "screening_answers":    [],
        "needs_human_review":   False,
        "review_reason":        "",
        "human_answers":        {},
        "error":                None,
        "error_node":           None,
    }

def load_master_resume_node(state: AgentState) -> AgentState:
    if _cancelled(state):
        return _cancelled_state(state)
    try:
        injected = state.get("master_resume_data")
        master = injected if injected else load_master_resume()
        return {**state, "master_resume": master, "error": None}
    except Exception as e:
        return {**state, "error": f"load_master_resume failed: {str(e)}", "error_node": "load_master_resume"}


def score_ats(state: AgentState) -> AgentState:
    """
    Score the job against the master resume.
    Sets ats_passed = True/False for the router to branch on.
    """
    if _cancelled(state):
        return _cancelled_state(state)

    _emit(state, f"Scoring ATS fit: {state['job_title']} at {state['company']}…")
    try:
        master_resume = state.get("master_resume")
        ats_threshold = state.get("ats_threshold")
        passed, result = passes_ats(
            job_title=state["job_title"],
            job_description=state["job_description"],
            master_resume=master_resume,
            threshold=ats_threshold,
        )

        score = result.get("final_score", 0)
        verdict = "PASS" if passed else "FAIL"
        _emit(state, f"ATS score: {score} — {verdict} (threshold {ats_threshold})")

        return {
            **state,
            "ats_score":            score,
            "ats_breakdown":        result,
            "ats_matched_keywords": result.get("matched_keywords", []),
            "ats_missing_keywords": result.get("missing_keywords", []),
            "ats_passed":           passed,
            "error":                None,
        }
    except Exception as e:
        _emit(state, f"ATS scoring failed: {e}", level="error")
        return {**state, "error": f"score_ats failed: {str(e)}", "error_node": "score_ats"}


def save_job_to_db(state: AgentState) -> AgentState:
    """
    Only called after ATS passes. Saves the job with its ATS data.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == state["job_id"]).first()

        if job:
            # Already exists — just update ATS fields
            job.ats_score            = state["ats_score"]
            job.ats_breakdown        = state["ats_breakdown"]
            job.ats_matched_keywords = state["ats_matched_keywords"]
            job.ats_missing_keywords = state["ats_missing_keywords"]
            job.status               = "queued"
        else:
            # Shouldn't happen in normal flow but handle gracefully
            print(f"Warning: job {state['job_id']} not found in DB during save_job_to_db")

        db.commit()
        return {**state, "error": None}
    except Exception as e:
        db.rollback()
        return {**state, "error": f"save_job_to_db failed: {str(e)}", "error_node": "save_job_to_db"}
    finally:
        db.close()


def filter_job(state: AgentState) -> AgentState:
    """
    Called when ATS score is below threshold.
    - Score < 50: delete the job from DB entirely (too weak to keep).
    - Score >= 50: mark as skipped so the user can review borderline jobs.
    """
    score = state["ats_score"]
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == state["job_id"]).first()
        if job:
            if score < 50:
                db.delete(job)
                _emit(state, f"Filtered out (score {score} < 50): {state['job_title']} at {state['company']}")
            else:
                job.status        = "skipped"
                job.ats_score     = score
                job.ats_breakdown = state["ats_breakdown"]
                _emit(state, f"Skipped borderline job (score {score}): {state['job_title']} at {state['company']}")
            db.commit()
        return {**state, "application_status": "filtered", "error": None}
    except Exception as e:
        db.rollback()
        return {**state, "error": f"filter_job failed: {str(e)}", "error_node": "filter_job"}
    finally:
        db.close()


def tailor_resume(state: AgentState) -> AgentState:
    if _cancelled(state):
        return _cancelled_state(state)

    _emit(state, f"Tailoring resume for {state['job_title']} at {state['company']}…")
    try:
        tailored = tailor_resume_llm(
            job_title=state["job_title"],
            company=state["company"],
            job_description=state["job_description"]
        )
        _emit(state, "Resume tailored successfully.")
        return {**state, "tailored_resume": tailored, "error": None}
    except Exception as e:
        _emit(state, f"Resume tailoring failed: {e}", level="error")
        return {**state, "error": f"tailor_resume failed: {str(e)}", "error_node": "tailor_resume"}


def generate_pdf(state: AgentState) -> AgentState:
    if _cancelled(state):
        return _cancelled_state(state)

    _emit(state, "Generating tailored PDF resume…")
    try:
        local_path  = generate_pdf_file(state["tailored_resume"], state["job_id"])
        public_url  = upload_resume_pdf(local_path, state["job_id"])

        db = SessionLocal()
        try:
            user_uuid = None
            try:
                if state.get("user_id"):
                    import uuid as _uuid2
                    user_uuid = _uuid2.UUID(state["user_id"])
            except (ValueError, AttributeError):
                pass
            resume_record = Resume(
                user_id          = user_uuid,
                job_id           = state["job_id"],
                file_url         = public_url,
                tailored_content = json.dumps(state["tailored_resume"])
            )
            db.add(resume_record)
            db.commit()
            resume_id = str(resume_record.id)
        finally:
            db.close()

        _emit(state, f"PDF uploaded: {public_url}")
        return {
            **state,
            "resume_pdf_path": local_path,
            "resume_pdf_url":  public_url,
            "resume_id":       resume_id,
            "error":           None,
        }
    except Exception as e:
        _emit(state, f"PDF generation failed: {e}", level="error")
        return {**state, "error": f"generate_pdf failed: {str(e)}", "error_node": "generate_pdf"}


def apply_to_job(state: AgentState) -> AgentState:
    """
    Uses Playwright to open the job URL and fill the application form.
    If screening questions are detected, returns status='screening' so the
    next node can answer them.
    """
    from app.services.job_applier import apply_to_job as _apply, ApplyResult

    if _cancelled(state):
        return _cancelled_state(state)

    _emit(state, f"Applying to {state['job_title']} at {state['company']}…")

    # Build user_data dict from pipeline state's master resume
    master = state.get("master_resume") or {}
    user_data = {
        "full_name":    master.get("name", ""),
        "email":        master.get("email", ""),
        "phone":        master.get("phone", ""),
        "linkedin_url": master.get("linkedin_url", ""),
        "github_url":   master.get("github_url", ""),
        "portfolio_url": master.get("portfolio_url", ""),
    }

    resume_path = state.get("resume_pdf_path", "")

    try:
        result: ApplyResult = asyncio.get_event_loop().run_until_complete(
            _apply(
                job_url=state["job_url"],
                resume_pdf_path=resume_path,
                user_data=user_data,
            )
        )
    except RuntimeError:
        # No running event loop (e.g. in thread) — create a new one
        result = asyncio.run(
            _apply(
                job_url=state["job_url"],
                resume_pdf_path=resume_path,
                user_data=user_data,
            )
        )

    if result.status == "failed":
        _emit(state, f"Apply failed: {result.error}", level="error")
        _persist_apply_detail(state["job_id"], None, result.error)
        return {
            **state,
            "error":      result.error,
            "error_node": "apply_to_job",
        }

    if result.status == "needs_screening":
        _emit(state, f"Screening questions detected ({len(result.screening_questions)}), drafting answers…")
        questions = [
            {"question": q, "claude_answer": "", "confidence": 0.0, "needs_review": True}
            for q in result.screening_questions
        ]
        _persist_apply_detail(state["job_id"], questions, None)
        return {
            **state,
            "screening_questions": questions,
            "application_status":  "screening",
            "error":               None,
        }

    _emit(state, f"Successfully applied to {state['job_title']} at {state['company']}.")
    _persist_apply_detail(state["job_id"], None, None, status="applied")
    return {
        **state,
        "application_status": "applied",
        "applied_at":         datetime.now(timezone.utc).isoformat(),
        "error":              None,
    }


def _persist_apply_detail(
    job_id: str,
    questions: list[dict] | None,
    error: str | None,
    status: str | None = None,
) -> None:
    """Helper: update job row with apply result details."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            if questions is not None:
                job.screening_questions = questions
            if error is not None:
                job.apply_status_detail = error
            if status:
                job.status = status
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def answer_screening_questions(state: AgentState) -> AgentState:
    """
    Uses Claude Haiku to answer screening questions extracted from the application form.
    If human_answers are provided (from the review queue), merges them instead.
    Low-confidence answers (< 0.75) trigger needs_human_review.
    """
    from app.services import screening_answerer

    raw_questions = state.get("screening_questions", [])
    if not raw_questions:
        return {**state, "application_status": "applied", "applied_at": datetime.now(timezone.utc).isoformat(), "error": None}

    q_texts = [q["question"] for q in raw_questions if q.get("question")]

    human_answers: dict = state.get("human_answers") or {}

    if human_answers:
        # Human provided answers — merge them in (mark all as high confidence)
        answered = []
        for q in raw_questions:
            text = q["question"]
            answer = human_answers.get(text, q.get("claude_answer", ""))
            answered.append({
                "question":     text,
                "claude_answer": answer,
                "confidence":   1.0,
                "needs_review": False,
            })
        needs_review = False
    else:
        # Ask Claude Haiku
        tailored = state.get("tailored_resume") or state.get("master_resume") or {}
        claude_answers = screening_answerer.answer_questions(
            questions=q_texts,
            tailored_resume=tailored,
            job_title=state.get("job_title", ""),
            company=state.get("company", ""),
        )

        # Map answers back to question dicts
        answer_map = {a["question"]: a for a in claude_answers}
        answered = []
        for q in raw_questions:
            text = q["question"]
            ca = answer_map.get(text, {"answer": "", "confidence": 0.0})
            conf = float(ca.get("confidence", 0.0))
            answered.append({
                "question":     text,
                "claude_answer": ca.get("answer", ""),
                "confidence":   conf,
                "needs_review": conf < 0.75,
            })

        needs_review = any(a["needs_review"] for a in answered)

    # Persist enriched questions to DB
    _persist_apply_detail(state["job_id"], answered, None)

    if needs_review:
        _emit(state, "Low-confidence answers found — pausing for human review.", level="warn")
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == state["job_id"]).first()
            if job:
                job.status = "needs_review"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return {
            **state,
            "screening_questions": answered,
            "needs_human_review":  True,
            "review_reason":       "One or more screening answers have low confidence",
            "application_status":  "needs_review",
            "error":               None,
        }

    _emit(state, "All screening answers confident — submitting application.")
    _persist_apply_detail(state["job_id"], answered, None, status="applied")
    return {
        **state,
        "screening_questions": answered,
        "needs_human_review":  False,
        "application_status":  "applied",
        "applied_at":          datetime.now(timezone.utc).isoformat(),
        "error":               None,
    }


def log_application(state: AgentState) -> AgentState:
    print(f"\n--- Application Log ---")
    print(f"Job:     {state['job_title']} at {state['company']}")
    print(f"ATS:     {state['ats_score']}")
    print(f"Status:  {state['application_status']}")
    print(f"Resume:  {state.get('resume_pdf_url', 'N/A')}")
    print(f"Error:   {state.get('error', 'None')}")
    return state

def record_and_advance(state: AgentState) -> AgentState:
    """
    Logs the current job outcome into processed_jobs
    and advances the index so the loop picks the next job.
    """
    processed = list(state.get("processed_jobs", []))
    app_status = state.get("application_status")
    if not app_status:
        app_status = "queued" if state.get("ats_passed") else "filtered"

    processed.append({
        "job_id":   state.get("job_id"),
        "title":    state.get("job_title"),
        "company":  state.get("company"),
        "score":    state.get("ats_score"),
        "passed":   state.get("ats_passed"),
        "status":   app_status,
        "resume":   state.get("resume_pdf_url", ""),
        "error":    state.get("error"),
    })

    # Sync terminal status back to DB for jobs that didn't go through _persist_apply_detail
    if app_status in ("applied", "needs_review", "queued", "failed"):
        db = SessionLocal()
        try:
            job_id = state.get("job_id")
            if job_id:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job and job.status not in ("applied", "needs_review", "failed"):
                    if app_status == "applied":
                        job.status = "applied"
                        db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    new_index = state["current_job_index"] + 1
    is_complete = new_index >= state["total_jobs"]

    if is_complete:
        _emit(state, f"All {state['total_jobs']} jobs processed. Pipeline complete.")
    else:
        _emit(state, f"Job {new_index}/{state['total_jobs']} done. Moving to next…")

    return {
        **state,
        "processed_jobs":    processed,
        "current_job_index": new_index,
        "pipeline_complete": is_complete,
        "error":             None,
        "error_node":        None,
    }

def handle_failure(state: AgentState) -> AgentState:
    _emit(state, f"Error in {state.get('error_node')}: {state.get('error')}", level="error")

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == state["job_id"]).first()
        if job:
            job.status = "failed"
            db.commit()
    except Exception:
        pass
    finally:
        db.close()

    return {**state, "application_status": "failed"}

def print_summary(state: AgentState) -> AgentState:
    jobs     = state.get("processed_jobs", [])
    passed   = [j for j in jobs if j.get("passed")]
    filtered = [j for j in jobs if not j.get("passed") and j.get("status") != "failed"]
    failed   = [j for j in jobs if j.get("status") == "failed"]

    _emit(state, "--- Pipeline Summary ---")
    _emit(state, f"Total fetched: {state['total_jobs']} | ATS passed: {len(passed)} | Filtered: {len(filtered)} | Errors: {len(failed)}")
    for j in passed:
        _emit(state, f"  Passed: {j['title']} at {j['company']} (score {j['score']})")

    # Signal SSE stream that pipeline is done
    uid = state.get("user_id", "")
    if uid:
        pipeline_events.emit_done(uid)

    return state
