import logging
import time

import httpx
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

log = logging.getLogger("sender")

# Атомарно бере одну відповідь і зсуває next_attempt_at на час lease:
# якщо процес помре, відповідь підхопиться знову після спливу lease.
CLAIM_SQL = text("""
WITH c AS (
    UPDATE outbound_replies
    SET attempts = attempts + 1,
        next_attempt_at = now() + make_interval(secs => :lease)
    WHERE id = (
        SELECT id FROM outbound_replies
        WHERE status = 'pending' AND next_attempt_at <= now()
        ORDER BY next_attempt_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, ticket_id, message, attempts
)
SELECT c.id, c.ticket_id, c.message, c.attempts, t.ticket_id AS ticket_key, t.reply_url
FROM c JOIN tickets t ON t.id = c.ticket_id
""")


def _mark_sent(r) -> None:
    with SessionLocal.begin() as s:
        s.execute(text("UPDATE outbound_replies SET status='sent', sent_at=now() WHERE id=:id"), {"id": r.id})
        s.execute(text("UPDATE tickets SET status='sent' WHERE id=:tid"), {"tid": r.ticket_id})


def _mark_failed(r) -> None:
    with SessionLocal.begin() as s:
        s.execute(text("UPDATE outbound_replies SET status='failed' WHERE id=:id"), {"id": r.id})
        s.execute(text("UPDATE tickets SET status='failed' WHERE id=:tid"), {"tid": r.ticket_id})


def _schedule_retry(r) -> None:
    delay = min(5 * 2 ** (r.attempts - 1), 300)  # 5, 10, 20, 40 ... максимум 300 с
    with SessionLocal.begin() as s:
        s.execute(
            text("UPDATE outbound_replies SET next_attempt_at = now() + make_interval(secs => :d) WHERE id=:id"),
            {"id": r.id, "d": delay},
        )
    log.info("retry for %s in %ss (attempt %d)", r.ticket_key, delay, r.attempts)


def send_one(r) -> None:
    retry = False
    try:
        resp = httpx.post(
            r.reply_url,
            json={"ticket_id": r.ticket_key, "message": r.message},
            headers={"Idempotency-Key": r.ticket_key},
            timeout=settings.reply_timeout,
        )
    except httpx.HTTPError as e:
        log.warning("send error for %s: %s", r.ticket_key, e.__class__.__name__)
        retry = True
    else:
        code = resp.status_code
        if code == 201:
            _mark_sent(r)
            log.info("sent reply for %s", r.ticket_key)
            return
        if 400 <= code < 500 and code not in (408, 429):
            log.error("permanent failure for %s: HTTP %d", r.ticket_key, code)
            _mark_failed(r)
            return
        log.warning("send failed for %s: HTTP %d", r.ticket_key, code)
        retry = True

    if retry:
        if r.attempts >= settings.sender_max_attempts:
            log.error("giving up on %s after %d attempts", r.ticket_key, r.attempts)
            _mark_failed(r)
        else:
            _schedule_retry(r)


def sender_loop() -> None:
    while True:
        try:
            with SessionLocal.begin() as s:
                r = s.execute(CLAIM_SQL, {"lease": settings.sender_lease_seconds}).first()
            if r is None:
                time.sleep(1)
                continue
            send_one(r)
        except Exception:
            log.exception("sender loop error")
            time.sleep(2)