---
name: check-types
description: Run TypeScript type checking on the frontend to catch type errors without building.
user-invocable: true
model: haiku
---

Run TypeScript type check:

```bash
cd frontend && npx tsc --noEmit
```

- If there are no errors, confirm "No type errors found"
- If there are errors, list each one with file path and line number, then fix them
- After fixing, re-run to confirm clean
