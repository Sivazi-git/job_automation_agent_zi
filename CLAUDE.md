# Job Automation Agent

AI-powered job application pipeline: scrapes jobs, scores against resume via ATS, tailors resumes, and auto-applies.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, LangGraph, Anthropic Claude, PostgreSQL (Supabase)
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, lucide-react
- **Auth**: JWT (python-jose) + bcrypt; tokens stored in localStorage (`jat_token`)
- **Storage**: Supabase Storage for PDF resumes

## Dev Commands

```bash
# Backend (port 8000)
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (port 3000)
cd frontend && npm run dev

# One-time DB migration
cd backend && .venv/Scripts/python.exe migrate_add_users.py

# Add Python package
cd backend && uv add <package>

# TypeScript check
cd frontend && npx tsc --noEmit
```

## Project Layout

```
backend/
  app/
    main.py              # FastAPI app — all routes
    auth.py              # JWT + bcrypt utilities
    dependencies.py      # get_current_user FastAPI dependency
    database.py          # SQLAlchemy engine + get_db()
    models/models.py     # User, Job, Resume, Application ORM models
    agents/
      graph.py           # LangGraph pipeline (compiled as `graph`)
      state.py           # AgentState TypedDict
      nodes.py           # All pipeline node functions
    services/
      ats_scorer.py      # Claude ATS scoring (score_job, passes_ats)
      resume_parser.py   # PDF → JSON via Claude Haiku (parse_resume_pdf)
      resume_tailor.py   # Claude resume tailoring
      jobs_scraper.py    # JobSpy wrapper
      pdf_generator.py   # WeasyPrint PDF generation
      storage.py         # Supabase Storage upload
  migrate_add_users.py   # One-time migration script (already run)

frontend/
  app/
    layout.tsx           # Root layout — AuthProvider + AppShell
    dashboard/           # Stats dashboard
    jobs/                # Jobs list (table + board toggle)
    jobs/[id]/           # Job detail page
    pipeline/            # Pipeline control panel
    login/               # Public sign-in page
    signup/              # 4-step signup wizard
    profile/             # User profile + resume management
  components/
    AppShell.tsx         # Layout wrapper + auth redirect guard
    AuthProvider.tsx     # React context + useAuth() hook
    Sidebar.tsx          # Nav + user info + logout
    JobsTable.tsx        # Table view
    JobsBoard.tsx        # Kanban board view
    ATSBreakdown.tsx     # ATS score visualization
    KeywordTags.tsx      # Matched/missing keyword pills
    StatusBadge.tsx      # Job status badge
    PipelinePanel.tsx    # Pipeline trigger + status
  lib/
    api.ts               # All API calls + Bearer token injection
    auth.ts              # localStorage token helpers
    utils.ts             # cn() helper
```

## API Routes

All routes require `Authorization: Bearer <token>` except auth endpoints.

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/auth/register` | multipart/form-data; parses PDF resume |
| POST | `/api/auth/login` | OAuth2 form (username + password) |
| GET | `/api/auth/me` | Current user profile |
| PUT | `/api/auth/profile` | Update profile fields |
| POST | `/api/auth/upload-resume` | Replace master resume PDF |
| POST | `/api/auth/upload-resume-preview` | Parse PDF preview (no auth) |
| GET | `/api/stats` | Dashboard counts (scoped to user) |
| GET | `/api/jobs` | Paginated jobs list (scoped to user) |
| GET | `/api/jobs/{id}` | Job detail + ATS breakdown |
| POST | `/api/pipeline/run` | Trigger pipeline (background task) |
| GET | `/api/pipeline/status` | Live per-user pipeline state |
| DELETE | `/api/admin/cleanup-low-ats` | Remove low-score jobs |

## Data Models

**User**: `id`, `email`, `password_hash`, `full_name`, `phone`, `target_role`, `target_location`, `linkedin_url`, `github_url`, `portfolio_url`, `master_resume_url`, `master_resume_data` (JSONB), `ats_threshold` (default 60), `daily_limit` (default 8), `onboarding_complete`, `is_active`, `created_at`

**Job**: `id`, `user_id`, `title`, `company`, `location`, `description`, `url`, `url_hash`, `source`, `status` (new|queued|applied|failed|skipped), `ats_score`, `ats_breakdown` (JSONB), `ats_matched_keywords`, `ats_missing_keywords`, `posted_at`, `created_at`

**Resume**: `id`, `user_id`, `job_id`, `file_url`, `tailored_content`, `created_at`

**Application**: `id`, `user_id`, `job_id`, `resume_id`, `status`, `applied_at`, `notes`

## Coding Rules

@.claude/rules/backend.md
@.claude/rules/frontend.md

## Key Conventions

- Never commit `.env` files
- `user_id` is always scoped per request via `get_current_user` dependency
- `master_resume_data` from DB takes priority over disk `master_resume.json` in the pipeline
- ATS threshold is per-user (from `User.ats_threshold`), not global env var
- Frontend: all API calls go through `apiFetch` in `lib/api.ts` — never call `fetch` directly
- On 401 response, `apiFetch` clears token and redirects to `/login` automatically
