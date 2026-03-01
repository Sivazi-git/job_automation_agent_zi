import os
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from datetime import datetime

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../../resumes")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_pdf(tailored_resume: dict, job_id: str) -> str:
    """
    Renders tailored resume dict to PDF using Jinja2 + WeasyPrint.
    Returns the local file path of the generated PDF.
    """
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("resume.html")

    html_content = template.render(resume=tailored_resume)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"resume_{job_id}_{timestamp}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)

    with open(output_path, "wb") as output_file:
        result = pisa.CreatePDF(html_content, dest=output_file)

    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} errors. Check your HTML template.")

    print(f"PDF generated: {output_path}")
    return output_path