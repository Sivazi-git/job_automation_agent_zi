import io
import json
import os
from anthropic import Anthropic
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def parse_resume_pdf(pdf_bytes: bytes) -> dict:
    """
    Extract text from a PDF resume and parse it into structured JSON via Claude.
    Returns a dict matching the master_resume.json schema.
    """
    # Extract text from PDF
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)
    raw_text = "\n".join(pages_text)

    if not raw_text.strip():
        raise ValueError("Could not extract text from PDF — it may be scanned/image-based.")

    prompt = f"""
You are a resume parser. Convert the following resume text into a structured JSON object.

STRICT RULES:
- Return ONLY valid JSON. No explanation, no markdown, no backticks.
- Use the exact schema below. Use empty arrays/objects for missing sections.
- For skills, group them by category (e.g. "languages", "frameworks", "tools").
- For experience, include company, title, location, start_date, end_date, description (array of bullet strings).
- For education, include institution, degree, field, start_date, end_date.
- For projects, include name, description (string), technologies (array of strings), url (string or null).
- For certifications, include name, issuer, date.

SCHEMA:
{{
  "name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "linkedin": "string or null",
  "github": "string or null",
  "portfolio": "string or null",
  "summary": "string",
  "skills": {{
    "category_name": ["skill1", "skill2"]
  }},
  "experience": [
    {{
      "company": "string",
      "title": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string or Present",
      "description": ["bullet 1", "bullet 2"]
    }}
  ],
  "education": [
    {{
      "institution": "string",
      "degree": "string",
      "field": "string",
      "start_date": "string",
      "end_date": "string"
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "technologies": ["tech1"],
      "url": null
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string",
      "date": "string"
    }}
  ]
}}

RESUME TEXT:
{raw_text[:6000]}
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)
