from sqlalchemy import Column, String, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    file_url = Column(String)
    tailored_content = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), nullable=False)
    resume_id = Column(UUID(as_uuid=True))
    status = Column(String, default="applied")  # applied, interview, rejected, offer, failed
    applied_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)