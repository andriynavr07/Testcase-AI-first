from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

LIST_SQL = """
SELECT t.id, t.ticket_id, t.customer_email, t.message, t.status, t.created_at,
       d.body AS draft, d.is_mock,
       (SELECT coalesce(array_agg(a.slug), '{}') FROM articles a WHERE a.id = ANY(d.article_ids)) AS slugs,
       o.status AS out_status, o.attempts AS out_attempts
FROM tickets t
LEFT JOIN LATERAL (
    SELECT * FROM drafts WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1
) d ON true
LEFT JOIN outbound_replies o ON o.ticket_id = t.id
WHERE t.status = ANY(:statuses)
ORDER BY t.id __ORDER__
LIMIT 200
"""


def _load(statuses: list[str], order: str) -> list[dict]:
    assert order in ("ASC", "DESC")
    sql = text(LIST_SQL.replace("__ORDER__", order))
    with SessionLocal() as s:
        rows = s.execute(sql, {"statuses": statuses}).mappings().all()
    result = []
    for r in rows:
        item = dict(r)
        item["links"] = [f"{settings.kb_base_url}/{slug}" for slug in (r["slugs"] or [])]
        result.append(item)
    return result


@router.get("/")
def index(request: Request):
    pending = _load(["draft_ready"], "ASC")
    history = _load(["approved", "sent", "failed", "rejected"], "DESC")
    with SessionLocal() as s:
        counts = dict(s.execute(text("SELECT status, count(*) FROM tickets GROUP BY status")).all())
    return templates.TemplateResponse(
        request, "index.html", {"pending": pending, "history": history, "counts": counts}
    )


@router.post("/tickets/{tid}/approve")
def approve(tid: int, message: str = Form(...)):
    message = message.strip()
    if not message:
        raise HTTPException(400, "Порожня відповідь")
    with SessionLocal.begin() as s:
        # Умовний UPDATE: подвійний клік або гонка двох операторів дадуть лише одну відправку.
        row = s.execute(
            text("UPDATE tickets SET status='approved' WHERE id=:id AND status='draft_ready' RETURNING id"),
            {"id": tid},
        ).first()
        if row:
            s.execute(
                text("INSERT INTO outbound_replies (ticket_id, message) VALUES (:id, :m) "
                     "ON CONFLICT (ticket_id) DO NOTHING"),
                {"id": tid, "m": message},
            )
    return RedirectResponse("/", status_code=303)


@router.post("/tickets/{tid}/reject")
def reject(tid: int):
    with SessionLocal.begin() as s:
        s.execute(
            text("UPDATE tickets SET status='rejected' WHERE id=:id AND status='draft_ready'"),
            {"id": tid},
        )
    return RedirectResponse("/", status_code=303)