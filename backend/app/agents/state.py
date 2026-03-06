from typing import TypedDict, Optional


class AgentState(TypedDict):

    # --- User context ---
    user_id: str                         # UUID string of the running user
    master_resume_data: Optional[dict]   # injected from user DB record (overrides disk file)
    ats_threshold: int                   # per-user threshold (default 60)

    search_term: str
    location: str
    # --- Job Info ---

    job_id: str
    job_title: str
    company: str
    job_url: str
    job_description: str
    job_source: str                  # linkedin, indeed, etc.

    ats_score: float
    ats_breakdown: dict
    ats_matched_keywords: list[str]
    ats_missing_keywords: list[str]
    ats_passed: bool

    # --- Fetched Jobs Batch ---
    fetched_jobs: list[dict]         # raw list from JobSpy
    current_job_index: int           # which job we're processing right now
    total_jobs: int

    # --- Resume ---
    master_resume: dict              # loaded from master_resume.json or injected
    tailored_resume: dict            # LLM output
    resume_pdf_path: str             # local path after WeasyPrint
    resume_pdf_url: str              # Supabase public URL after upload
    resume_id: str                   # DB record ID after saving

    # --- Application ---
    application_status: str          # applied, failed, skipped, needs_review
    applied_at: Optional[str]        # ISO timestamp

    # --- Screening Q&A ---
    screening_questions: list[dict]  # [{question, claude_answer, confidence, needs_review}]
    screening_answers: list[dict]    # [{question: str, answer: str}]

    # --- Human-in-the-loop review ---
    needs_human_review: bool         # True → pause pipeline, set job to needs_review
    review_reason: str               # explanation shown in UI
    human_answers: dict              # {question_text: answer_text} submitted by user

    # --- Pipeline Summary ---
    processed_jobs: list[dict]       # log of all processed jobs with their outcomes
    pipeline_complete: bool

    # --- Pipeline Control ---
    should_apply: bool               # False = stop after tailoring, True = go apply
    retry_count: int                 # how many times this job has been retried
    error: Optional[str]             # error message if any node fails
    error_node: Optional[str]        # which node failed
