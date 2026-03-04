---
name: start-frontend
description: Install frontend dependencies if needed and start the Next.js dev server on port 3000.
user-invocable: true
model: haiku
---

Start the Next.js frontend:

1. Check if `frontend/node_modules` exists; if not, run `cd frontend && npm install` first
2. Run `cd frontend && npm run dev` in the background
3. After 4 seconds, check output for "Ready" or "Local: http://localhost:3000"
4. Report the URL to the user

If there are TypeScript or compilation errors in the output, read the relevant files and fix them.

The frontend runs at http://localhost:3000.
