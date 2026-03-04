"""
One-time migration: create users table + add user_id to jobs/resumes/applications.
Run: cd backend && .venv/Scripts/python.exe migrate_add_users.py
"""
from dotenv import load_dotenv
load_dotenv()

from app.database import engine
from app.models.models import Base
from sqlalchemy import text

def run():
    # Create users table (and any other missing tables) using SQLAlchemy metadata
    Base.metadata.create_all(engine, checkfirst=True)
    print("[OK] users table created (if not exists)")

    with engine.connect() as conn:
        # Add user_id to jobs
        conn.execute(text(
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id UUID"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs(user_id)"
        ))
        print("[OK] jobs.user_id column + index")

        # Add user_id to resumes
        conn.execute(text(
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS user_id UUID"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_resumes_user_id ON resumes(user_id)"
        ))
        print("[OK] resumes.user_id column + index")

        # Add user_id to applications
        conn.execute(text(
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS user_id UUID"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_applications_user_id ON applications(user_id)"
        ))
        print("[OK] applications.user_id column + index")

        conn.commit()

    print("\nMigration complete.")

if __name__ == "__main__":
    run()
