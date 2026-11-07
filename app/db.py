from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_size=30, max_overflow=10, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)