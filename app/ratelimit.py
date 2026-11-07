import time

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

# Атомарно: займає слот у поточній хвилині, якщо ліміт не вичерпано.
ACQUIRE_SQL = text("""
INSERT INTO rate_limit (window_start, count)
VALUES (date_trunc('minute', now()), 1)
ON CONFLICT (window_start) DO UPDATE
SET count = rate_limit.count + 1
WHERE rate_limit.count < :limit
RETURNING count
""")


def acquire_slot() -> bool:
    with SessionLocal.begin() as s:
        return s.execute(ACQUIRE_SQL, {"limit": settings.llm_rate_limit_per_minute}).first() is not None


def wait_for_slot() -> None:
    """Блокує потік, доки не з'явиться вільний слот (максимум до початку наступної хвилини)."""
    while not acquire_slot():
        time.sleep(60 - (time.time() % 60) + 0.05)