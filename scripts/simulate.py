import argparse
import random
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx

QUESTIONS = [
    "Не можу експортувати звіт у PDF",
    "Забув пароль, як відновити?",
    "Як запросити колегу до команди",
    "Як змінити тариф і де рахунки",
    "Як підключити Slack",
    "Не приходять сповіщення на пошту",
    "Хочу імпортувати задачі з CSV",
    "Де взяти API токен",
    "Як приготувати борщ",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=50, help="кількість унікальних звернень")
    p.add_argument("--dup-ratio", type=float, default=0.2, help="частка звернень, які приходять 3 рази одночасно")
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--reply-base", default="http://mock-helpdesk:9000", help="адреса моку з точки зору воркера")
    p.add_argument("--concurrency", type=int, default=30)
    a = p.parse_args()

    run = int(time.time())
    jobs = []
    for i in range(a.n):
        ticket_id = f"SIM-{run}-{i}"
        event = {
            "event_id": f"evt_{run}_{i}",
            "ticket_id": ticket_id,
            "customer_email": f"user{i}@example.com",
            "message": random.choice(QUESTIONS),
            "reply_url": f"{a.reply_base}/tickets/{ticket_id}/replies",
        }
        copies = 3 if random.random() < a.dup_ratio else 1
        jobs.extend([event] * copies)
    random.shuffle(jobs)

    codes: Counter = Counter()
    latencies: list[float] = []

    with httpx.Client(timeout=10, limits=httpx.Limits(max_connections=a.concurrency)) as client:
        def send(event: dict) -> None:
            t0 = time.monotonic()
            try:
                code = client.post(f"{a.base}/webhooks/helpdesk", json=event).status_code
            except httpx.HTTPError as e:
                code = e.__class__.__name__
            latencies.append(time.monotonic() - t0)
            codes[code] += 1

        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
            list(pool.map(send, jobs))
        total = time.monotonic() - started

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0
    print(f"run id: {run}  (тікети SIM-{run}-*)")
    print(f"унікальних звернень: {a.n}, всього запитів: {len(jobs)}, за {total:.1f} с")
    print(f"статуси: {dict(codes)}")
    print(f"очікувано: 202 x {a.n}, решта 200 (дублі)")
    print(f"затримка вебхука: середня {statistics.mean(latencies):.3f} с, p95 {p95:.3f} с, макс {max(latencies):.3f} с (ліміт 2 с)")


if __name__ == "__main__":
    main()