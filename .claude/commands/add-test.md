---
name: add-test
description: Write a pytest test for an existing FastAPI endpoint or service function.
---

# /add-test

Ask the user:
1. What to test? (endpoint path or service function name)
2. What behavior should the test verify?
3. Does it need a real DB or can it be a unit test?

Then:
- Find the file to test
- Write a focused test using `pytest-asyncio` + `httpx.AsyncClient` for endpoints
- Use `pytest.mark.asyncio` decorator
- Mock external calls (email, S3) with `unittest.mock.patch`
- Name tests: `test_<what>_<expected_outcome>` (e.g., `test_create_user_returns_201`)

Run `pytest -xvs <test_file>::<test_name>` and show output.
