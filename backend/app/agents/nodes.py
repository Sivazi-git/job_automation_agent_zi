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

load_dotenv()

def fetch_jobs_node(state: AgentState) -> AgentState:
    """
    First node. Hits JobSpy and loads all fetched jobs into state.
    Resets all per-job fields and sets up the batch for iteration.
    """
    try:
        print(f"\n[fetch_jobs] Searching: '{state['search_term']}' in '{state['location']}'")

        jobs = fetch_jobs(
            search_term=state["search_term"],
            location=state["location"]
        )

        print(f"[fetch_jobs] Found {len(jobs)} jobs.")

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
                posted_at   = posted_at,
            )
            db.add(new_job)
            db.commit()
            job_id = str(new_job.id)
        else:
            job_id = str(existing.id)

    finally:
        db.close()

    print(f"\n[load_current_job] Processing job {index + 1}/{len(jobs)}: {job.get('title')} at {job.get('company')}")

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
        "error":                None,
        "error_node":           None,
    }

def load_master_resume_node(state: AgentState) -> AgentState:
    try:
        master = load_master_resume()
        return {**state, "master_resume": master, "error": None}
    except Exception as e:
        return {**state, "error": f"load_master_resume failed: {str(e)}", "error_node": "load_master_resume"}


def score_ats(state: AgentState) -> AgentState:
    """
    Score the job against the master resume.
    Sets ats_passed = True/False for the router to branch on.
    """
    try:
        passed, result = passes_ats(
            job_title=state["job_title"],
            job_description=state["job_description"]
        )

        print(f"ATS Score: {result['final_score']} for {state['job_title']} at {state['company']} — {'PASS' if passed else 'FAIL'}")
        print(f"Reasoning: {result.get('reasoning')}")

        return {
            **state,
            "ats_score":            result.get("final_score", 0),
            "ats_breakdown":        result,
            "ats_matched_keywords": result.get("matched_keywords", []),
            "ats_missing_keywords": result.get("missing_keywords", []),
            "ats_passed":           passed,
            "error":                None,
        }
    except Exception as e:
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
    Called when ATS score is below threshold. Marks job as filtered in DB.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == state["job_id"]).first()
        if job:
            job.status       = "filtered"
            job.ats_score    = state["ats_score"]
            job.ats_breakdown = state["ats_breakdown"]
            db.commit()
        print(f"Job filtered out: {state['job_title']} at {state['company']} (score: {state['ats_score']})")
        return {**state, "application_status": "filtered", "error": None}
    except Exception as e:
        db.rollback()
        return {**state, "error": f"filter_job failed: {str(e)}", "error_node": "filter_job"}
    finally:
        db.close()


def tailor_resume(state: AgentState) -> AgentState:
    try:
        tailored = tailor_resume_llm(
            job_title=state["job_title"],
            company=state["company"],
            job_description=state["job_description"]
        )
        return {**state, "tailored_resume": tailored, "error": None}
    except Exception as e:
        return {**state, "error": f"tailor_resume failed: {str(e)}", "error_node": "tailor_resume"}


def generate_pdf(state: AgentState) -> AgentState:
    try:
        local_path  = generate_pdf_file(state["tailored_resume"], state["job_id"])
        public_url  = upload_resume_pdf(local_path, state["job_id"])

        db = SessionLocal()
        try:
            resume_record = Resume(
                job_id           = state["job_id"],
                file_url         = public_url,
                tailored_content = json.dumps(state["tailored_resume"])
            )
            db.add(resume_record)
            db.commit()
            resume_id = str(resume_record.id)
        finally:
            db.close()

        return {
            **state,
            "resume_pdf_path": local_path,
            "resume_pdf_url":  public_url,
            "resume_id":       resume_id,
            "error":           None,
        }
    except Exception as e:
        return {**state, "error": f"generate_pdf failed: {str(e)}", "error_node": "generate_pdf"}


def apply_to_job(state: AgentState) -> AgentState:
    # Placeholder — Sprint 3 will replace this with Playwright
    print(f"[Sprint 3] apply_to_job placeholder for {state['job_url']}")
    return {
        **state,
        "application_status": "pending",
        "applied_at":         datetime.now(timezone.utc).isoformat(),
        "error":              None,
    }


def answer_screening_questions(state: AgentState) -> AgentState:
    # Placeholder — Sprint 3
    print(f"[Sprint 3] answer_screening_questions placeholder")
    return {**state, "screening_answers": [], "error": None}


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
    processed.append({
        "job_id":   state.get("job_id"),
        "title":    state.get("job_title"),
        "company":  state.get("company"),
        "score":    state.get("ats_score"),
        "passed":   state.get("ats_passed"),
        "status":   state.get("application_status") or ("queued" if state.get("ats_passed") else "filtered"),
        "resume":   state.get("resume_pdf_url", ""),
        "error":    state.get("error"),
    })

    new_index = state["current_job_index"] + 1
    is_complete = new_index >= state["total_jobs"]

    print(f"\n[record_and_advance] Job {new_index}/{state['total_jobs']} done. Pipeline complete: {is_complete}")

    return {
        **state,
        "processed_jobs":    processed,
        "current_job_index": new_index,
        "pipeline_complete": is_complete,
        "error":             None,
        "error_node":        None,
    }

def handle_failure(state: AgentState) -> AgentState:
    print(f"\n[FAILURE] Node: {state.get('error_node')} | Error: {state.get('error')}")

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

    print("\n" + "="*50)
    print("PIPELINE SUMMARY")
    print("="*50)
    print(f"Total fetched:  {state['total_jobs']}")
    print(f"ATS passed:     {len(passed)}")
    print(f"ATS filtered:   {len(filtered)}")
    print(f"Errors:         {len(failed)}")
    print("\nPassed Jobs:")
    for j in passed:
        print(f"  ✓ {j['title']} at {j['company']} — score: {j['score']}")
    print("="*50)

    return state
