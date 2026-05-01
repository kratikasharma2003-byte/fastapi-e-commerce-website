# Project Rules — FastAPI

## Stack
Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, pytest + httpx.

## Code Style
- PEP 8. Use `ruff` for linting (`ruff check --fix`).
- All functions must have type hints and return type declarations.
- No bare `except:` — always catch specific exception types.

## File/Folder Conventions
- Routers → `app/routers/<resource>.py`
- Pydantic schemas → `app/schemas/<resource>.py`
- SQLAlchemy models → `app/models/<resource>.py`
- Business logic → `app/services/<resource>_service.py`
- DB session/engine → `app/database.py`
- Shared dependencies → `app/dependencies.py`
- Entry point → `app/main.py`

## Always Do
- Use `async def` for all route handlers.
- Return Pydantic `response_model`, never raw dicts.
- Use `Depends()` for DB sessions and auth.
- Prefix routers: `/api/v1/<resource>`.
- Separate request schemas (input) from response schemas (output).

## Never Do
- No business logic in route handlers.
- No `.env` files committed.
- No `import *`.
- No `session.commit()` inside a route — service layer owns commits.

## Testing
- Tests in `tests/`, mirroring `app/` structure.
- Use `pytest-asyncio` + `httpx.AsyncClient` for endpoint tests.
- Run: `pytest -xvs`

## Recommended MCP Servers
- **Postgres MCP** — query DB from Claude. Needs: `DATABASE_URL` env var.
- **GitHub MCP** — browse issues/PRs. Needs: `GITHUB_TOKEN` env var.
- **Filesystem MCP** — read/write project files. Pre-configured.

Run `.claude/hooks/setup-mcps.sh` to install npm prerequisites.
