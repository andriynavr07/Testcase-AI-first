import random
import time

import httpx

from app.config import settings

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = (
    "Ти асистент служби підтримки продукту «Планфлоу». Підготуй чернетку відповіді клієнту "
    "українською мовою для перевірки оператором. Використовуй ЛИШЕ факти зі наданих статей "
    "бази знань, нічого не вигадуй. Якщо статті не містять відповіді, чесно скажи, що "
    "питання передано спеціалісту. Наприкінці наведи посилання на використані статті (повні URL)."
)


class LLMError(Exception):
    pass


def build_user_prompt(message: str, articles: list[dict]) -> str:
    if articles:
        kb = "\n\n".join(f"Стаття: {a['title']}\nURL: {a['url']}\n{a['body']}" for a in articles)
    else:
        kb = "(релевантних статей не знайдено)"
    return f"Звернення клієнта:\n{message}\n\nБаза знань:\n{kb}"


def _static_draft(message: str, articles: list[dict]) -> str:
    if not articles:
        return "Дякуємо за звернення! Ми передали ваше питання спеціалісту, він відповість найближчим часом."
    links = "\n".join(f"- {a['title']}: {a['url']}" for a in articles)
    return (
        "Дякуємо за звернення! Відповідь на ваше питання ви знайдете в наших статтях:\n"
        f"{links}\n"
        "Якщо питання лишиться, напишіть нам, і ми допоможемо."
    )


def _call_api(api_key: str, message: str, articles: list[dict]) -> str:
    resp = httpx.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "max_tokens": 700,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": build_user_prompt(message, articles)}],
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise LLMError(f"LLM HTTP {resp.status_code}")
    data = resp.json()
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text").strip()


def generate_draft(message: str, articles: list[dict]) -> tuple[str, bool]:
    """Повертає (текст чернетки, is_mock)."""
    if settings.anthropic_api_key:
        return _call_api(settings.anthropic_api_key, message, articles), False

    # Режим без ключа: реальний запит із невалідним ключем, відповідь відкидаємо,
    # затримку добираємо до випадкових 5-30 с, як у реального виклику.
    started = time.monotonic()
    target = random.uniform(5, 30)
    try:
        _call_api("invalid-key-mock-mode", message, articles)
    except Exception:
        pass
    time.sleep(max(0.0, target - (time.monotonic() - started)))
    return _static_draft(message, articles), True