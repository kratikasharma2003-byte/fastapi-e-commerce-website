---
name: claude-fit
description: Deep-scan this FastAPI project and rebuild .claude/ to be fully project-specific.
---

# /claude-fit

You are performing a **complete project analysis** to transform this `.claude/` folder from generic templates into a project-specific tool. Work through every phase completely without skipping.

---

## Phase 1: Project Discovery

Read every file below that exists (use the Read tool):

**Dependency files:**
`requirements.txt`, `requirements/base.txt`, `requirements/dev.txt`, `pyproject.toml`, `Pipfile`

**Entry points and config:**
`main.py`, `app/main.py`, `app.py`, `core/config.py`, `app/config.py`, `app/core/config.py`, `.env.example`

**Project structure — list contents of these directories if they exist:**
`app/`, `src/`, `routers/`, `app/routers/`, `models/`, `app/models/`, `schemas/`, `app/schemas/`, `services/`, `app/services/`, `tests/`, `alembic/versions/`

**Read up to 3 representative files from each existing directory:**
- Router files (any `*router*.py` or `*routers/*.py`)
- Model files (any `*model*.py` or `*models/*.py`)
- Schema files (any `*schema*.py` or `*schemas/*.py`)
- Service files (any `*service*.py` or `*services/*.py`)
- Test files from `tests/`

**Config and tooling:**
`pytest.ini`, `setup.cfg`, `Makefile`, `justfile`, `docker-compose.yml`, `.github/workflows/`

**Existing .claude/ content:**
`.claude/CLAUDE.md`, and list all files in `.claude/skills/`, `.claude/commands/`, `.claude/rules/`, `.claude/memory/`

---

## Phase 2: Extract Project Context

Build this context map from everything read:

- **PROJECT_NAME** — from `pyproject.toml` name field or directory name
- **PURPOSE** — 1–2 sentences from README intro or `main.py` docstring
- **PYTHON_VERSION** — from `pyproject.toml` or `.python-version`
- **DEV_SERVER_CMD** — exact command (e.g. `uvicorn app.main:app --reload`)
- **TEST_CMD** — exact pytest command from `pyproject.toml [tool.pytest]` or Makefile
- **LINT_CMD** — `ruff check .` / `flake8 .` / whatever is configured
- **FORMAT_CMD** — `ruff format .` / `black .` / whatever is configured
- **MIGRATE_CMD** — `alembic upgrade head` or equivalent
- **ACTUAL_ROUTERS_PATH** — real path (e.g. `app/routers/` or `routers/`)
- **ACTUAL_MODELS_PATH** — real path (e.g. `app/models/` or `models/`)
- **ACTUAL_SCHEMAS_PATH** — real path
- **ACTUAL_SERVICES_PATH** — real path
- **MODEL_NAMES** — actual model class names found in source (e.g. `User`, `Product`, `Order`)
- **DATABASE** — PostgreSQL / SQLite / MySQL (from `DATABASE_URL` pattern or driver import)
- **ORM** — SQLAlchemy / SQLModel / Tortoise / etc
- **AUTH** — JWT / OAuth2 / API keys / none (from imports in source files)
- **CACHE** — Redis / none (from imports)
- **QUEUE** — Celery / ARQ / none
- **EXTRA_LIBS** — all non-standard libraries detected beyond the above

---

## Phase 3: Fully Rewrite .claude/CLAUDE.md

**Replace** the entire contents of `.claude/CLAUDE.md` (do not append — rewrite completely):

```
# Project Rules — [PROJECT_NAME]

## Stack
[Actual versions: Python X.Y, FastAPI X.Y, ORM, migration tool, test runner]

## Dev Commands
- Start:   [DEV_SERVER_CMD]
- Test:    [TEST_CMD]
- Lint:    [LINT_CMD]
- Format:  [FORMAT_CMD]
- Migrate: [MIGRATE_CMD]

## Project Structure
[Actual layout — list only paths that exist]
- [ACTUAL_ROUTERS_PATH] — route handlers
- [ACTUAL_MODELS_PATH] — [ORM] models
- [ACTUAL_SCHEMAS_PATH] — Pydantic schemas
- [ACTUAL_SERVICES_PATH] — business logic
- tests/ — [describe test organization found]

## Code Style
[Detected from ruff/flake8/pyproject.toml config. If no config found: PEP 8, type hints required]

## Conventions Detected in This Codebase
[List actual patterns found in source: e.g. "services receive db session via constructor",
"all endpoints return Pydantic response_model", "prefix pattern: /api/v1/<resource>"]

## Always Do
[Derive from actual source patterns — make these specific to this project]

## Never Do
[Derive from anti-patterns you can infer from code style — make these specific]

## Models in This Project
[MODEL_NAMES — one line per model with its table name and key fields]

## Auth ([AUTH])
[Actual auth implementation: where JWT is validated, what dependencies inject the user, etc.]

## Database
[DATABASE] via [ORM]. Session: [exact path and function, e.g. Depends(get_db) from app/database.py].
Migrations: [MIGRATE_CMD]

## MCP Servers
[List only MCPs relevant to detected infra: Postgres if DATABASE_URL set, Redis if cache detected, etc.]
```

---

## Phase 4: Create .claude/memory/ Files

Create the `.claude/memory/` directory and write these three files:

### .claude/memory/project.md
```
---
type: project
updated: [today YYYY-MM-DD]
---
# [PROJECT_NAME]

[PURPOSE]

## Quick Reference
- Dev server: [DEV_SERVER_CMD]
- Tests:      [TEST_CMD]
- Database:   [DATABASE] via [ORM]
- Auth:       [AUTH]
- Cache:      [CACHE]

## Models
[For each model in MODEL_NAMES: ModelName — what it represents, key fields]

## Entry Points
[main.py location, app factory function if present, important startup events]

## Key Files to Know
[List 5–10 files that are most important for understanding this codebase]
```

### .claude/memory/stack.md
```
---
type: reference
updated: [today YYYY-MM-DD]
---
# Stack Details — [PROJECT_NAME]

## Dependencies and Their Role
[For each non-trivial dependency detected: package_name — what it does in this project]

## Database Setup
- Engine: [DATABASE]
- ORM: [ORM]
- Session factory: [file:function]
- Migration: [MIGRATION_TOOL], run with `[MIGRATE_CMD]`
- URL env var: [detected env var name, e.g. DATABASE_URL]

## Auth Implementation
[Exact: library used, token location (header/cookie), validation function path, user injection path]

## External Services
[Only detected ones — Redis: config path; S3: bucket env var; Stripe: key env var; etc.]
```

### .claude/memory/conventions.md
```
---
type: reference
updated: [today YYYY-MM-DD]
---
# Conventions — [PROJECT_NAME]

## File Naming
[Derived from actual files found: e.g. snake_case, plural for routers, singular for models]

## Router Pattern
[How routes are structured — include an example of an actual route signature found]

## Schema Pattern
[How request/response schemas are named — include real examples]

## Service Pattern
[How services are structured — include real import/usage example]

## Test Pattern
[How tests are organized — test file naming, fixture location, assertion style]
```

---

## Phase 5: Rewrite Existing Skills with Project-Specific Code

For each file in `.claude/skills/*/SKILL.md`:
1. Read the current skill content
2. Rewrite code examples to use this project's **actual**:
   - Module paths (e.g. `from app.models.user import User` not `from models import User`)
   - Model names from MODEL_NAMES (not generic `User` if the project uses `BlogPost`, `Product`, etc.)
   - Session import path (actual `get_db` location)
   - Config import path (actual settings location)
3. Keep the skill structure (frontmatter, section headers) but replace all generic placeholders

---

## Phase 6: Add New Skills for Detected Libraries

For each library below that is detected AND not already in `.claude/skills/`, create `.claude/skills/<name>/SKILL.md`:

**redis / aioredis → redis-caching:**
Cover: connection setup using actual config path, caching decorator or pattern, cache invalidation, async client usage.

**celery / arq → background-tasks:**
Cover: task definition, task registration, calling tasks from routes, monitoring, retry config.

**boto3 / aiobotocore → s3-storage:**
Cover: client setup, upload, presigned URLs, deletion. Use actual bucket env var name if detected.

**python-jose / authlib / fastapi-users → auth-patterns:**
Cover: token creation, token validation dependency, protected route pattern using actual auth code found.

**httpx (used as client) → http-client:**
Cover: async client setup, request patterns, error handling, timeout config.

**sentry-sdk → observability:**
Cover: initialization, custom context, breadcrumbs, performance monitoring.

**pydantic-settings → settings-management:**
Cover: Settings class setup, env var loading, nested config, secret handling.

---

## Phase 7: Update Commands with Project Paths

For each file in `.claude/commands/` (except this file), update:
- All occurrences of `app/routers/` → [ACTUAL_ROUTERS_PATH]
- All occurrences of `app/models/` → [ACTUAL_MODELS_PATH]
- All occurrences of `app/schemas/` → [ACTUAL_SCHEMAS_PATH]
- All occurrences of `app/services/` → [ACTUAL_SERVICES_PATH]
- Generic `User` model examples → first model from MODEL_NAMES
- `pytest -xvs` → [TEST_CMD]
- `uvicorn app.main:app --reload` → [DEV_SERVER_CMD]
- `alembic upgrade head` → [MIGRATE_CMD]

---

## Phase 8: Update .claude/rules/

Read `.claude/rules/coding-standards.md`. Rewrite it with:
- Actual linter and formatter detected (not assumptions)
- Line length from config if present
- Type checking tool if detected (mypy / pyright)
- Import ordering style if configured
- Any project-specific naming rules derived from actual source files

---

## Phase 9: Report

Print a summary:

```
✓ Rewrote .claude/CLAUDE.md — [PROJECT_NAME] context
✓ Created .claude/memory/project.md
✓ Created .claude/memory/stack.md
✓ Created .claude/memory/conventions.md
✓ Updated N skills with project-specific code examples
✓ Added new skills: [list or "none"]
✓ Updated N commands with actual paths
✓ Rewrote .claude/rules/coding-standards.md

.claude/ is now tuned for [PROJECT_NAME].
Run /claude-fit again after adding major new dependencies.
```
