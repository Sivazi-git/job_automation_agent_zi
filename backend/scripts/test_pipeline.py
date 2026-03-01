import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from app.agents.graph import graph

initial_state = {
    # Search config — only thing you need to provide
    "search_term":          "Software Developer",
    "location":             "Remote",

    # Batch fields — graph fills these
    "fetched_jobs":          [],
    "current_job_index":     0,
    "total_jobs":            0,
    "processed_jobs":        [],
    "pipeline_complete":     False,

    # Per-job fields — graph fills these
    "job_id":                "",
    "job_title":             "",
    "company":               "",
    "job_url":               "",
    "job_description":       "",
    "job_source":            "",
    "master_resume":         {},
    "tailored_resume":       {},
    "resume_pdf_path":       "",
    "resume_pdf_url":        "",
    "resume_id":             "",
    "ats_score":             0.0,
    "ats_breakdown":         {},
    "ats_matched_keywords":  [],
    "ats_missing_keywords":  [],
    "ats_passed":            False,
    "application_status":    "",
    "applied_at":            None,
    "screening_questions":   [],
    "screening_answers":     [],

    # Control
    "should_apply":          False,
    "retry_count":           0,
    "error":                 None,
    "error_node":            None,
}

graph.invoke(initial_state)