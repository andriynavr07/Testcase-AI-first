import logging
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.llm import generate_draft
from app.queue import claim_next_ticket
from app.ratelimit import wait_for_slot
from app.search import search_articles
from app.sender import sender_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(threadName)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("worker")

SAVE_DRAFT_SQL = text("""
WITH d AS (
    INSERT INTO drafts (ticket_id, body, article_ids, is_mock)
    VALUES (:tid, :body, :article_ids, :is_mock)
)
UPDATE tickets SET status = 'draft_ready', locked_until = NULL WHERE id = :tid
""")

# Повернути в чергу з паузою або позначити failed після max_attempts.
RELEASE_SQL = text("""
UPDATE tickets
SET status = CASE WHEN attempts >= :max THEN 'failed' ELSE 'new' END,
    locked_until = NULL
WHERE id = :tid AND status = 'generating'
""")


def process(ticket) -> None:
    tid, ticket_id, message = ticket.id, ticket.ticket_id, ticket.message
    try:
        articles = search_articles(message)
        wait_for_slot()  # ліміт 60/хв на весь сервіс
        body, is_mock = generate_draft(message, articles)
        with SessionLocal.begin() as s:
            s.execute(SAVE_DRAFT_SQL, {
                "tid": tid, "body": body,
                "article_ids": [a["id"] for a in articles], "is_mock": is_mock,
            })
        log.info("draft ready for %s (mock=%s)", ticket_id, is_mock)
    except Exception:
        log.exception("generation failed for %s", ticket_id)
        time.sleep(5)  # проста пауза перед поверненням у чергу
        with SessionLocal.begin() as s:
            s.execute(RELEASE_SQL, {"tid": tid, "max": settings.max_attempts})


def worker_loop() -> None:
    while True:
        ticket = claim_next_ticket()
        if ticket is None:
            time.sleep(1)
            continue
        process(ticket)


def main() -> None:
    log.info("starting worker, concurrency=%d, senders=%d, mock=%s",
             settings.worker_concurrency, settings.sender_concurrency, not settings.anthropic_api_key)
    total = settings.worker_concurrency + settings.sender_concurrency
    with ThreadPoolExecutor(max_workers=total) as pool:
        for _ in range(settings.worker_concurrency):
            pool.submit(worker_loop)
        for _ in range(settings.sender_concurrency):
            pool.submit(sender_loop)


if __name__ == "__main__":
    main()