import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from app.services.resume_tailor import load_master_resume

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ATS_THRESHOLD = int(os.getenv("ATS_THRESHOLD", 60))
# Haiku is ~20x cheaper than Sonnet and handles structured JSON tasks well.
# Override with ATS_MODEL=claude-sonnet-4-6 if you need higher accuracy.
ATS_MODEL = os.getenv("ATS_MODEL", "claude-haiku-4-5-20251001")


def score_job(job_title: str, job_description: str, master_resume: dict = None) -> dict:
    """
    Scores how well the master resume matches a job description.
    Returns a dict with score (0-100) and reasoning breakdown.
    If master_resume is not provided, loads from disk.
    """
    master = master_resume if master_resume is not None else load_master_resume()

    prompt = f"""
    You are an ATS (Applicant Tracking System) evaluator.

    Score how well the candidate's resume matches the job description below.
    Be strict and realistic — this score determines whether to auto-apply.

    Evaluate these 4 dimensions:
    1. Skills Match      — do the candidate's skills match what the job requires?
    2. Experience Match  — does the candidate's experience level and domain fit?
    3. Title Match       — how closely does the candidate's background match the job title?
    4. Keywords Match    — how many important JD keywords appear in the resume?

    STRICT RULES:
    - Return ONLY a valid JSON object. No explanation, no markdown, no backticks.
    - Score each dimension 0-100, then provide a weighted final score.
    - Weights: Skills 35%, Experience 35%, Title 15%, Keywords 15%
    - Be honest. A score above 60 means the candidate has a real chance.

    JOB TITLE: {job_title}

    JOB DESCRIPTION:
    {job_description[:3000]}

    CANDIDATE RESUME:
    {json.dumps(master, indent=2)}

    Return this exact JSON structure:
    {{
    "skills_score": <0-100>,
    "experience_score": <0-100>,
    "title_score": <0-100>,
    "keywords_score": <0-100>,
    "final_score": <weighted 0-100>,
    "matched_keywords": ["keyword1", "keyword2"],
    "missing_keywords": ["keyword1", "keyword2"],
    "reasoning": "2-3 sentence explanation of the score"
    }}
    """

    response = client.messages.create(
        model=ATS_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    return result


def passes_ats(
    job_title: str,
    job_description: str,
    master_resume: dict = None,
    threshold: int = None,
) -> tuple[bool, dict]:
    """
    Convenience wrapper. Returns (passes: bool, score_result: dict).
    Uses per-user threshold if provided, else env var default.
    """
    score_result = score_job(job_title, job_description, master_resume=master_resume)
    effective_threshold = threshold if threshold is not None else ATS_THRESHOLD
    passes = score_result.get("final_score", 0) >= effective_threshold
    return passes, score_result
