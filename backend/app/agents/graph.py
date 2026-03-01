from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    fetch_jobs_node,
    load_current_job,
    load_master_resume_node,
    score_ats,
    save_job_to_db,
    filter_job,
    tailor_resume,
    generate_pdf,
    apply_to_job,
    answer_screening_questions,
    log_application,
    record_and_advance,
    handle_failure,
    print_summary,
)


# ── Routing Functions ──────────────────────────────────────────────────────────

def route_after_fetch(state: AgentState) -> str:
    if state.get("error") or not state.get("fetched_jobs"):
        return "print_summary"
    return "load_current_job"


def route_after_load(state: AgentState) -> str:
    """
    After loading current job, check if batch is done
    or if the job was skipped (no job_id means skip).
    """
    if state.get("pipeline_complete"):
        return "print_summary"
    if not state.get("job_id"):
        # Empty job_id = was skipped, go back and load next
        return "load_current_job"
    return "load_master_resume"

def route_after_ats(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    if state.get("ats_passed"):
        return "save_job_to_db"
    return "filter_job"


def route_after_save(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    return "tailor_resume"


def route_after_tailoring(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    if not state.get("should_apply", False):
        return "record_and_advance"
    return "generate_pdf"


def route_after_pdf(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    return "apply_to_job"


def route_after_apply(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    if state.get("screening_questions"):
        return "answer_screening_questions"
    return "record_and_advance"


def route_after_screening(state: AgentState) -> str:
    if state.get("error"):
        return "handle_failure"
    return "record_and_advance"

def route_after_advance(state: AgentState) -> str:
    """
    Core loop decision: if there are more jobs, go back.
    If batch is done, go to summary.
    """
    if state.get("pipeline_complete"):
        return "print_summary"
    return "load_current_job"


# ── Build Graph ────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("fetch_jobs",                 fetch_jobs_node)
    builder.add_node("load_current_job",           load_current_job)
    builder.add_node("load_master_resume",         load_master_resume_node)
    builder.add_node("score_ats",                  score_ats)
    builder.add_node("save_job_to_db",             save_job_to_db)
    builder.add_node("filter_job",                 filter_job)
    builder.add_node("tailor_resume",              tailor_resume)
    builder.add_node("generate_pdf",               generate_pdf)
    builder.add_node("apply_to_job",               apply_to_job)
    builder.add_node("answer_screening_questions", answer_screening_questions)
    # builder.add_node("log_application",            log_application)
    builder.add_node("record_and_advance",         record_and_advance)
    builder.add_node("handle_failure",             handle_failure)
    builder.add_node("print_summary",              print_summary)

    # Entry
    builder.set_entry_point("fetch_jobs")

    builder.add_conditional_edges(
        "fetch_jobs", route_after_fetch,
        {
            "load_current_job": "load_current_job",
            "print_summary":    "print_summary",
        }
    )

    builder.add_conditional_edges(
        "load_current_job", route_after_load,
        {
            "load_master_resume": "load_master_resume",
            "load_current_job":   "load_current_job",   # skip loop
            "print_summary":      "print_summary",
        }
    )

    # load → score
    builder.add_edge("load_master_resume", "score_ats")

    # score → save or filter
    builder.add_conditional_edges(
        "score_ats", route_after_ats,
        {
            "save_job_to_db": "save_job_to_db",
            "filter_job":     "filter_job",
            "handle_failure": "handle_failure",
        }
    )

    # save → tailor
    builder.add_conditional_edges(
        "save_job_to_db", route_after_save,
        {
            "tailor_resume":  "tailor_resume",
            "handle_failure": "handle_failure",
        }
    )

    # tailor → pdf or stop
    builder.add_conditional_edges(
        "tailor_resume", route_after_tailoring,
        {
            "generate_pdf":    "generate_pdf",
            "record_and_advance": "record_and_advance",
            "handle_failure":  "handle_failure",
        }
    )

    # pdf → apply
    builder.add_conditional_edges(
        "generate_pdf", route_after_pdf,
        {
            "apply_to_job":   "apply_to_job",
            "handle_failure": "handle_failure",
        }
    )

    # apply → screening or log
    builder.add_conditional_edges(
        "apply_to_job", route_after_apply,
        {
            "answer_screening_questions": "answer_screening_questions",
            "record_and_advance":         "record_and_advance",
            "handle_failure":             "handle_failure",
        }
    )

    builder.add_conditional_edges(
        "answer_screening_questions", route_after_screening,
        {
            "record_and_advance": "record_and_advance",
            "handle_failure":     "handle_failure",
        }
    )

    # filter and record both loop back
    builder.add_conditional_edges(
        "filter_job", lambda s: "print_summary" if s.get("pipeline_complete") else "record_and_advance",
        {
            "record_and_advance": "record_and_advance",
            "print_summary":      "print_summary",
        }
    )

    builder.add_conditional_edges(
        "record_and_advance", route_after_advance,
        {
            "load_current_job": "load_current_job",
            "print_summary":    "print_summary",
        }
    )

    builder.add_conditional_edges(
        "handle_failure", route_after_advance,
        {
            "load_current_job": "load_current_job",
            "print_summary":    "print_summary",
        }
    )

    builder.add_edge("print_summary", END)
    # Terminals
    # builder.add_edge("filter_job",      END)
    # builder.add_edge("log_application", END)
    # builder.add_edge("handle_failure",  END)

    return builder.compile()


graph = build_graph()