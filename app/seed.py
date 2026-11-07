import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Article

DATA = Path(__file__).resolve().parent.parent / "data" / "articles.json"


def seed() -> int:
    articles = json.loads(DATA.read_text(encoding="utf-8"))
    with SessionLocal.begin() as s:
        for a in articles:
            s.execute(
                insert(Article)
                .values(slug=a["slug"], title=a["title"], body=a["body"])
                .on_conflict_do_update(
                    index_elements=["slug"],
                    set_={"title": a["title"], "body": a["body"]},
                )
            )
    return len(articles)


if __name__ == "__main__":
    print(f"seeded {seed()} articles")