---
name: add-endpoint
description: Add a new FastAPI endpoint with router, schema, service, and test.
---

# /add-endpoint

Ask the user:
1. What resource? (e.g., users, products, orders)
2. HTTP method? (GET / POST / PUT / PATCH / DELETE)
3. What does it do?
4. Does it need authentication?

Then create (or add to existing files):
- `app/routers/<resource>.py` — route handler only, calls service
- `app/schemas/<resource>.py` — `<Resource>Create` and `<Resource>Response` Pydantic models
- `app/services/<resource>_service.py` — business + DB logic
- `tests/test_<resource>.py` — at least one test using `httpx.AsyncClient`

Conventions:
- Response model uses `model_config = ConfigDict(from_attributes=True)`
- Route handler uses `db: AsyncSession = Depends(get_db)`
- Service receives `AsyncSession` in `__init__`

After creating: mount the router in `app/main.py` if it's a new router.
Run `pytest -xvs tests/test_<resource>.py` and show output.
