---
name: migrate
description: Run the database migration script to apply schema changes to PostgreSQL.
user-invocable: true
model: haiku
---

Run the database migration:

```bash
cd backend && .venv/Scripts/python.exe migrate_add_users.py
```

After running:
- Confirm each "[OK]" line printed (users table, jobs.user_id, resumes.user_id, applications.user_id)
- If there's an error, read `backend/migrate_add_users.py` and diagnose the issue
- Report success or failure clearly

Note: This migration uses `IF NOT EXISTS` so it's safe to run multiple times.
