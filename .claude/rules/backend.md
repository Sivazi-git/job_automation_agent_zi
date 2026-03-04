# Backend Rules

## Language & Style
- Python 3.12; type hints on all function signatures
- 4-space indentation; PEP 8 naming (snake_case)
- Import order: stdlib → third-party → local (separated by blank lines)

## FastAPI
- All new endpoints must use `Depends(get_current_user)` unless explicitly public
- Always scope DB queries to `current_user.id` — never return data across users
- Use `HTTPException` with specific status codes; never return error strings in 200 responses
- Pydantic models for request bodies where possible; `dict` only for simple ad-hoc payloads

## Database
- Always use `db: Session = Depends(get_db)` — never instantiate `SessionLocal()` in route handlers
- `SessionLocal()` is acceptable inside pipeline nodes (background tasks, not request scope)
- Always call `db.commit()` after mutations; `db.rollback()` in except blocks
- New columns: always `nullable=True` + `index=True` for FKs to avoid breaking existing rows

## Auth
- Password hashing: `hash_password()` / `verify_password()` in `app/auth.py` — never call bcrypt directly
- JWT: `create_access_token()` / `decode_access_token()` in `app/auth.py`
- `get_current_user` is the single source of truth for the authenticated user in a request

## Pipeline / Agents
- `AgentState` fields: `user_id`, `master_resume_data`, `ats_threshold` are injected at pipeline start
- `load_master_resume_node` prefers `state["master_resume_data"]` over disk file
- All DB writes inside nodes must set `user_id` from `state["user_id"]`
- `passes_ats()` and `score_job()` accept `master_resume=` and `threshold=` kwargs — always pass them

## Services
- `parse_resume_pdf(bytes)` → uses Claude Haiku (fast/cheap); returns master_resume schema dict
- `score_job()` → uses Claude Sonnet; expensive — avoid calling outside pipeline
- Never hardcode model names — use the constants already in each service file

## Environment
- All secrets via `os.getenv()` with a safe default or explicit error
- `.env` is never committed; use `.env.example` for documentation
