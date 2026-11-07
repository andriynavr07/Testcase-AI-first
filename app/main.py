from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Ticket, WebhookEvent

app = FastAPI(title="Support Draft Service")


class HelpdeskEvent(BaseModel):
    event_id: str
    ticket_id: str
    customer_email: str
    message: str
    reply_url: str


@app.get("/health")
def health():
    return Response(content="OK", media_type="text/plain", status_code=200)


@app.post("/webhooks/helpdesk", status_code=202)
def helpdesk_webhook(payload: HelpdeskEvent):
    with SessionLocal.begin() as s:
        res = s.execute(
            insert(WebhookEvent)
            .values(event_id=payload.event_id)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        if res.rowcount == 0:
            return JSONResponse({"status": "duplicate"}, status_code=200)

        s.execute(
            insert(Ticket)
            .values(
                ticket_id=payload.ticket_id,
                customer_email=payload.customer_email,
                message=payload.message,
                reply_url=payload.reply_url,
                status="new",
            )
            .on_conflict_do_nothing(index_elements=["ticket_id"])
        )
    return {"status": "accepted"}