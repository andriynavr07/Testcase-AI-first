from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    lease_seconds: int = 120
    kb_base_url: str = "https://help.planflow.example/articles"
    kb_top_k: int = 3


settings = Settings()