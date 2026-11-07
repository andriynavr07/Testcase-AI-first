import re
import sys

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

STOPWORDS = {
    "не", "можу", "можна", "як", "що", "та", "і", "й", "в", "у", "на", "до", "це",
    "я", "мені", "мене", "мій", "моя", "для", "при", "чи", "але", "вже", "так",
    "щоб", "бо", "є", "був", "була", "треба", "допоможіть", "будь", "ласка",
}

SEARCH_SQL = text("""
SELECT id, slug, title, body, ts_rank_cd(tsv, q) AS rank
FROM articles, to_tsquery('simple', :q) AS q
WHERE tsv @@ q
ORDER BY rank DESC, id
LIMIT :limit
""")


def _stem(word: str) -> str:
    n = len(word)
    if n <= 4:
        return word
    if n <= 6:
        return word[:4]
    return word[:5]


def build_query(message: str) -> str | None:
    words = re.findall(r"[^\W_]+", message.lower())
    stems = {
        _stem(w) for w in words
        if w not in STOPWORDS and (len(w) >= 3 or w.isdigit())
    }
    if not stems:
        return None
    # лише літери/цифри, тож ін'єкція в tsquery неможлива
    return " | ".join(f"{s}:*" for s in sorted(stems))


def search_articles(message: str, limit: int | None = None) -> list[dict]:
    q = build_query(message)
    if q is None:
        return []
    with SessionLocal() as s:
        rows = s.execute(SEARCH_SQL, {"q": q, "limit": limit or settings.kb_top_k}).mappings().all()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "body": r["body"],
            "url": f"{settings.kb_base_url}/{r['slug']}",
            "rank": float(r["rank"]),
        }
        for r in rows
    ]


if __name__ == "__main__":
    for hit in search_articles(" ".join(sys.argv[1:])):
        print(f"{hit['rank']:.3f}  {hit['title']}  {hit['url']}")