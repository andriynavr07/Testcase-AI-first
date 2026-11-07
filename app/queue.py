from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

CLAIM_SQL = text("""
UPDATE tickets
SET status = 'generating',
    attempts = attempts + 1,
    locked_until = now() + make_interval(secs => :lease)
WHERE id = (
    SELECT id FROM tickets
    WHERE status = 'new'
       OR (status = 'generating' AND locked_until < now())
    ORDER BY id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, ticket_id, message
""")


def claim_next_ticket():
    with SessionLocal.begin() as s:
        return s.execute(CLAIM_SQL, {"lease": settings.lease_seconds}).first()