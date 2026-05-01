# FastAPI Coding Standards

## Do
- Type-hint every parameter and return value
- Use Pydantic v2 models for all request/response data
- Keep route handlers under 10 lines; delegate to services
- Write one test per endpoint behavior
- Use `ruff check --fix` before every commit
- Prefix all API routes: `/api/v1/<resource>`

## Don't
- Don't put DB queries in route handlers
- Don't return raw dicts from endpoints
- Don't catch broad exceptions (`except Exception`)
- Don't commit `.env` or secrets
- Don't use synchronous DB calls in async route handlers
- Don't skip writing tests for happy path + one error case
