import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from app.services.resume_tailor import tailor_resume
from app.services.pdf_generator import generate_pdf

# Paste a real job description here for best results
JOB_TITLE = "Backend Engineer"
COMPANY = "Stripe"
JOB_DESCRIPTION = """
We are looking for a Backend Engineer to join our infrastructure team.
You will build scalable APIs, work with PostgreSQL and Redis, and deploy
services on AWS using Docker and Kubernetes. Experience with Python and
FastAPI is a strong plus. You'll collaborate closely with frontend engineers
and own features end to end.
"""

def main():
    print("=== Step 1: Tailoring Resume ===")
    tailored = tailor_resume(JOB_TITLE, COMPANY, JOB_DESCRIPTION)

    print("\nTailored Summary:")
    print(tailored.get("summary"))

    print("\nTop Skills:")
    for category, items in tailored.get("skills", {}).items():
        print(f"  {category}: {', '.join(items)}")

    print("\n=== Step 2: Generating PDF ===")
    pdf_path = generate_pdf(tailored, job_id="test-001")
    print(f"PDF saved at: {pdf_path}")
    print("\n=== Done ===")

if __name__ == "__main__":
    main()