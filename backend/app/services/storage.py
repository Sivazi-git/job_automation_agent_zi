import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
)

BUCKET_NAME = "resumes"


def upload_resume_pdf(local_path: str, job_id: str) -> str:
    """
    Uploads a PDF to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    filename = os.path.basename(local_path)
    storage_path = f"{job_id}/{filename}"

    with open(local_path, "rb") as f:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=f,
            file_options={"content-type": "application/pdf"}
        )

    public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)
    print(f"Uploaded to Supabase: {public_url}")
    return public_url