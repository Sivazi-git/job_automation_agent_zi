"""
Claude Haiku–powered screening question answerer.
Returns a list of {question, answer, confidence} dicts.
Confidence < 0.75 flags for human review.
"""
from __future__ import annotations

import json
import os
import anthropic

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are an expert job application assistant. "
    "Given a candidate's resume and a list of screening questions for a job, "
    "answer each question concisely and professionally on behalf of the candidate. "
    "For each answer, rate your confidence from 0.0 to 1.0 based on how well "
    "the resume supports the answer. "
    "Return ONLY a JSON array — no markdown, no extra text."
)

_PROMPT_TEMPLATE = """\
Candidate resume data:
{resume_json}

Job: {job_title} at {company}

Screening questions:
{questions_list}

Return a JSON array with one object per question:
[
  {{
    "question": "<exact question text>",
    "answer": "<your answer on behalf of the candidate>",
    "confidence": <float 0.0-1.0>
  }},
  ...
]
"""


def answer_questions(
    questions: list[str],
    tailored_resume: dict,
    job_title: str,
    company: str,
) -> list[dict]:
    """
    Answer a list of screening question strings using Claude Haiku.

    Returns:
        list of {question, answer, confidence}
        Any answer with confidence < 0.75 should be flagged for human review.
    """
    if not questions:
        return []

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    questions_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    resume_json = json.dumps(tailored_resume, indent=2)[:4000]  # cap to avoid token overflow

    prompt = _PROMPT_TEMPLATE.format(
        resume_json=resume_json,
        job_title=job_title,
        company=company,
        questions_list=questions_list,
    )

    message = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        answers = json.loads(raw)
        # Validate shape
        result = []
        for item in answers:
            result.append({
                "question": str(item.get("question", "")),
                "answer": str(item.get("answer", "")),
                "confidence": float(item.get("confidence", 0.5)),
            })
        return result
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Fallback: return blank answers with 0 confidence so they go to human review
        return [
            {"question": q, "answer": "", "confidence": 0.0}
            for q in questions
        ]
