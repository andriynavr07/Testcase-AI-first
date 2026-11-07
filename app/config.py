from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    lease_seconds: int = 120
    kb_base_url: str = "https://help.planflow.example/articles"
    kb_top_k: int = 3
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    llm_rate_limit_per_minute: int = 60
    worker_concurrency: int = 25
    max_attempts: int = 5
    sender_concurrency: int = 4
    sender_lease_seconds: int = 60
    sender_max_attempts: int = 8
    reply_timeout: int = 10


settings = Settings()