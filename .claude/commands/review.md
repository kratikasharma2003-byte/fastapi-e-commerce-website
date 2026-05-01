---
name: review
description: Review current branch changes for code quality, security, and test coverage.
---

# /review

Run in order:

1. `git diff main...HEAD` — list changed files
2. For each changed Python file check:
   - Type hints on all functions
   - No business logic in route handlers
   - No bare `except:` clauses
   - No secrets or tokens logged
   - Pydantic models used for input validation
3. Check: do changed files have corresponding test updates?
4. Run `pytest -x` and report pass/fail
5. Run `ruff check .` and report any issues

Summary format:
- ✓ What looks good
- ✗ Issues to fix before merging
- ⚠ Suggestions (not blockers)
