---
name: commit
description: Stage and commit changes with a well-structured git commit message following the project's conventions.
user-invocable: true
argument-hint: "[optional message or context]"
---

Create a git commit for the current changes.

1. Run `git status` and `git diff` (staged + unstaged) to understand what changed
2. Run `git log --oneline -5` to match the existing commit message style
3. Stage relevant files — prefer specific filenames over `git add -A`; never stage `.env` or secrets
4. Write a commit message:
   - First line: imperative mood, max 72 chars (e.g. "Add JWT auth to pipeline endpoints")
   - If $ARGUMENTS is provided, use it as context or the message itself
   - Add `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer
5. Commit using a HEREDOC to preserve formatting
6. Run `git status` to confirm success

Never use `--no-verify`. Never amend a previous commit unless explicitly asked.
