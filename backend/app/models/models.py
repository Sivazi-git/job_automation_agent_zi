from sqlalchemy import Column, String, DateTime, Text, Enum, Integer, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    target_role = Column(String, nullable=True)
    target_location = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    master_resume_url = Column(String, nullable=True)      # Supabase PDF URL
    master_resume_data = Column(JSONB, nullable=True)      # Parsed resume JSON
    ats_threshold = Column(Integer, default=60)
    daily_limit = Column(Integer, default=8)
    onboarding_complete = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    url = Column(String, unique=True, nullable=False)
    url_hash = Column(String, unique=True)
    source = Column(String)  # linkedin, indeed, etc
    status = Column(String, default="new")  # new, queued, applied, failed, skipped
    posted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    ats_score         = Column(Float, nullable=True)
    ats_breakdown     = Column(JSONB, nullable=True)
    ats_matched_keywords  = Column(JSONB, nullable=True)
    ats_missing_keywords  = Column(JSONB, nullable=True)

    # Auto-apply fields
    # status: new|queued|applied|failed|skipped|needs_review
    screening_questions  = Column(JSONB, nullable=True)   # [{question, claude_answer, confidence, needs_review}]
    apply_status_detail  = Column(Text, nullable=True)    # last apply error or detail message


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    file_url = Column(String)
    tailored_content = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    resume_id = Column(UUID(as_uuid=True))
    status = Column(String, default="applied")  # applied, interview, rejected, offer, failed
    applied_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
