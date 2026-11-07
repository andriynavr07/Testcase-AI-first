import asyncio
import os
import random

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="Mock Helpdesk")

CHAOS = os.getenv("CHAOS", "1") != "0"
P_5XX = float(os.getenv("MOCK_P_5XX", "0.2"))    # одразу 500, відповідь не збережено
P_HANG = float(os.getenv("MOCK_P_HANG", "0.1"))  # зависає й віддає 504, відповідь не збережено
P_LATE = float(os.getenv("MOCK_P_LATE", "0.1"))  # відповідь збережено, але 201 приходить із запізненням
HANG_SECONDS = float(os.getenv("MOCK_HANG_SECONDS", "15"))  # більше за таймаут клієнта (10 с)

# ticket_id -> стан. Один event loop і немає await між перевіркою та записом, тож гонок немає.
store: dict[str, dict] = {}


def _entry(ticket_id: str) -> dict:
    return store.setdefault(ticket_id, {"keys": set(), "stored": 0, "attempts": 0})


@app.get("/health")
def health():
    return PlainTextResponse("OK")


@app.post("/tickets/{ticket_id}/replies")
async def create_reply(
    ticket_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None),
):
    body = await request.json()
    e = _entry(ticket_id)
    e["attempts"] += 1

    roll = random.random() if CHAOS else 1.0
    if roll < P_5XX:
        return JSONResponse({"error": "internal"}, status_code=500)
    if roll < P_5XX + P_HANG:
        await asyncio.sleep(HANG_SECONDS)
        return JSONResponse({"error": "timeout"}, status_code=504)

    # Обробка: без ключа дублі не відсікаються (так поводився б хелпдеск без підтримки ключів).
    if idempotency_key is None or idempotency_key not in e["keys"]:
        e["stored"] += 1
        if idempotency_key is not None:
            e["keys"].add(idempotency_key)

    if roll < P_5XX + P_HANG + P_LATE:
        await asyncio.sleep(HANG_SECONDS)  # відповідь уже збережено, клієнт отримає таймаут

    return JSONResponse({"status": "created", "ticket_id": body.get("ticket_id")}, status_code=201)


@app.get("/replies")
def replies():
    tickets = {t: {"replies_stored": v["stored"], "delivery_attempts": v["attempts"]} for t, v in store.items()}
    return {
        "total_tickets": len(tickets),
        "tickets_with_duplicates": sum(1 for v in tickets.values() if v["replies_stored"] > 1),
        "tickets_with_retries": sum(1 for v in tickets.values() if v["delivery_attempts"] > 1),
        "tickets": tickets,
    }