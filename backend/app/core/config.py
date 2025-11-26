from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import json

class Settings(BaseSettings):
    # --- Base de données ---
    database_url: Optional[str] = None
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    FRONTEND_URL: str = "https://pompier.gandour.org"

    # --- JWT ---
    JWT_SECRET: str  # obligatoire
    JWT_ALG: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = 30

    # --- CORS ---
    # Nom du champ = CORS_ORIGINS (comme tu l'utilises déjà)
    # L'env CORS_ORIGINS sera bien pris en compte automatiquement
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def db_url(self) -> str:
        """
        Retourne l'URL de BDD utilisable par SQLAlchemy.
        - Si DATABASE_URL est défini → on l'utilise.
        - Sinon, on reconstruit depuis POSTGRES_*.
        """
        if self.database_url:
            return self.database_url

        if self.postgres_db and self.postgres_user and self.postgres_password:
            return (
                f"postgresql+psycopg://{self.postgres_user}:"
                f"{self.postgres_password}@{self.postgres_host}:"
                f"{self.postgres_port}/{self.postgres_db}"
            )

        raise ValueError(
            "Config BDD manquante : définis DATABASE_URL "
            "ou POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD"
        )

    @property
    def cors_list(self) -> List[str]:
        """
        Retourne la liste des origines CORS à partir de CORS_ORIGINS.
        On accepte :
        - '*' ou vide → ['*']
        - JSON: '["http://a","http://b"]'
        - CSV:  'http://a,http://b'
        """
        raw = (self.CORS_ORIGINS or "").strip()

        if raw in ("", "*"):
            return ["*"]

        # JSON ?
        if raw.startswith("["):
            try:
                lst = json.loads(raw)
                return [str(x).strip() for x in lst if str(x).strip()]
            except Exception:
                # si ça foire, on retombe sur CSV
                pass

        # CSV fallback
        return [x.strip() for x in raw.split(",") if x.strip()]


# Instance globale à utiliser partout
settings = Settings()
