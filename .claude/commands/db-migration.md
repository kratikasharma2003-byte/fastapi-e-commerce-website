---
name: db-migration
description: Create and apply an Alembic database migration.
---

# /db-migration

Ask: what schema change are you making?

Then:
1. Read `app/models/` to understand current model state
2. `alembic revision --autogenerate -m "<description>"`
3. Read the generated migration in `alembic/versions/`
4. Show the user `upgrade()` and `downgrade()` functions — ask to confirm
5. If confirmed: `alembic upgrade head`
6. If the migration touches existing rows: warn about data migration strategy

Always verify: does `downgrade()` correctly reverse `upgrade()`?
