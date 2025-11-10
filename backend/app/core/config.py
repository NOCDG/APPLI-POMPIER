from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json

class Settings(BaseSettings):
    database_url: str | None = None
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = 30
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # On accepte CSV ("http://a,http://b") OU JSON (["http://a","http://b"])
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.postgres_db and self.postgres_user and self.postgres_password:
            return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        raise ValueError("Config BDD manquante : définis DATABASE_URL ou POSTGRES_*")

    @property
    def cors_list(self) -> List[str]:
        raw = self.cors_origins.strip()
        if raw == "*" or raw == "":
            return ["*"]
        # JSON list ?
        if raw.startswith("["):
            try:
                lst = json.loads(raw)
                return [str(x).strip() for x in lst if str(x).strip()]
            except Exception:
                pass
        # CSV fallback
        return [x.strip() for x in raw.split(",") if x.strip()]

settings = Settings()
CORS_ORIGINS = settings.cors_list
