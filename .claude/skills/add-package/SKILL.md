---
name: add-package
description: Add a dependency to the backend (uv add) or frontend (npm install). Specify the package name and target.
user-invocable: true
model: haiku
argument-hint: "<package-name> [backend|frontend]"
---

Add a package dependency based on $ARGUMENTS.

Parse $ARGUMENTS to determine:
- The package name (first token)
- The target: "backend" or "frontend" (second token, or infer from context)

**Backend** (Python):
```bash
cd backend && uv add <package>
```
Then verify the import works:
```bash
cd backend && .venv/Scripts/python.exe -c "import <module>; print('ok')"
```

**Frontend** (Node):
```bash
cd frontend && npm install <package>
```
Then confirm it appears in `frontend/package.json` dependencies.

Report what was installed and the version.
