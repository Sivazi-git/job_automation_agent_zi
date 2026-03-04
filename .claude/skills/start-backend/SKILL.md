---
name: start-backend
description: Start the FastAPI backend development server on port 8000 with hot reload.
user-invocable: true
model: haiku
---

Start the backend server:

```bash
cd backend && .venv/Scripts/uvicorn.exe app.main:app --reload --port 8000
```

Run this in the background. After 3 seconds, check the output to confirm:
- "Application startup complete." appears
- No import errors or missing module errors

If there are errors, read the relevant file and fix the issue before retrying.

The server runs at http://127.0.0.1:8000. The interactive API docs are at http://127.0.0.1:8000/docs.
