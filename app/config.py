"""Configuration loaded from environment variables.

Works locally via a .env file (python-dotenv) and on Render via dashboard env vars.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-8"

    # ClickHouse Cloud
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8443
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"
    clickhouse_secure: bool = True


settings = Settings()
