import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MASTER_RESUME_PATH = os.path.join(os.path.dirname(__file__), "../data/master_resume.json")


def load_master_resume() -> dict:
    with open(MASTER_RESUME_PATH, "r") as f:
        return json.load(f)


def tailor_resume(job_title: str, company: str, job_description: str) -> dict:
    """
    Takes a job posting and returns a tailored resume dict.
    Strictly based on master resume — no fabrication.
    """
    master = load_master_resume()

    prompt = f"""
        You are an expert resume tailoring assistant.

        Your job is to tailor the candidate's master resume to the job description below.

        STRICT RULES — follow these without exception:
        1. Only use information that exists in the master resume. Do not add, invent, or assume any skills, experience, or achievements.
        2. Reorder and reword bullet points to highlight what is most relevant to this job.
        3. Adjust the summary to speak directly to this role and company.
        4. Reorder the skills section to surface the most relevant skills first.
        5. Do not remove any jobs from the experience section.
        6. Return ONLY a valid JSON object with the exact same structure as the master resume. No explanation, no markdown, no backticks.
        7. Make sure to include the job title and tailoring in the summary.
        8. Include the keywords from the job description to pass ATS filters.
        9. Resume should be ATS optimized.

        JOB TITLE: {job_title}
        COMPANY: {company}

        JOB DESCRIPTION:
        {job_description[:3000]}

        MASTER RESUME:
        {json.dumps(master, indent=2)}

        Return the tailored resume as a JSON object now:
    """

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude wraps in them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    tailored = json.loads(raw)
    return tailored