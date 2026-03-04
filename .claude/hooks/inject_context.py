"""
UserPromptSubmit / PreCompact hook.
Reads the incoming prompt, detects topic keywords, and injects the most
relevant project docs as additionalContext so Claude doesn't have to go
re-read them on every turn.

Output format required by Claude Code:
{
  "hookSpecificOutput": {
    "hookEventName": "<event>",
    "additionalContext": "<string>"
  }
}
"""
import sys
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # project root


def read(rel: str, max_lines: int = 80) -> str:
    """Read a file relative to project root, capped at max_lines."""
    p = ROOT / rel
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[:max_lines])


def build_context(prompt: str) -> str:
    p = prompt.lower()
    sections: list[str] = []

    # ── Auth / User ──────────────────────────────────────────────────────────
    if any(k in p for k in ("auth", "login", "signup", "register", "jwt", "token", "user", "password")):
        sections.append("## Auth layer\n" + read("backend/app/auth.py"))
        sections.append("## Dependency\n" + read("backend/app/dependencies.py"))

    # ── Database / Models ────────────────────────────────────────────────────
    if any(k in p for k in ("model", "database", "db", "migration", "schema", "table", "column", "sqlalchemy")):
        sections.append("## ORM Models\n" + read("backend/app/models/models.py"))
        sections.append("## DB session\n" + read("backend/app/database.py"))

    # ── Pipeline / Agents ────────────────────────────────────────────────────
    if any(k in p for k in ("pipeline", "agent", "graph", "node", "langgraph", "state")):
        sections.append("## AgentState\n" + read("backend/app/agents/state.py"))
        sections.append("## Graph nodes (first 60 lines)\n" + read("backend/app/agents/nodes.py", 60))

    # ── ATS / Resume ─────────────────────────────────────────────────────────
    if any(k in p for k in ("ats", "score", "resume", "keyword", "tailor", "parser")):
        sections.append("## ATS scorer\n" + read("backend/app/services/ats_scorer.py"))
        sections.append("## Resume parser\n" + read("backend/app/services/resume_parser.py"))

    # ── API Routes ───────────────────────────────────────────────────────────
    if any(k in p for k in ("api", "endpoint", "route", "fastapi", "main.py")):
        sections.append("## API routes (first 80 lines of main.py)\n" + read("backend/app/main.py", 80))

    # ── Frontend ─────────────────────────────────────────────────────────────
    if any(k in p for k in ("frontend", "component", "page", "react", "next", "typescript", "tailwind", "ui")):
        sections.append("## Frontend rules\n" + read(".claude/rules/frontend.md"))

    # ── Backend general ──────────────────────────────────────────────────────
    if any(k in p for k in ("backend", "python", "fastapi", "uv", "uvicorn")):
        sections.append("## Backend rules\n" + read(".claude/rules/backend.md"))

    # ── Default: always include a lightweight project summary ────────────────
    if not sections:
        sections.append("## Project summary\n" + read("CLAUDE.md", 60))

    return "\n\n---\n\n".join(sections)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    event = data.get("hook_event_name", "UserPromptSubmit")
    prompt = data.get("prompt", "")

    context = build_context(prompt)

    output = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": context,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
