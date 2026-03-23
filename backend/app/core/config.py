import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "KG Learning Path Backend"
    app_version: str = "0.2.0"
    api_prefix: str = ""
    cors_origins: tuple[str, ...] = ("*",)
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    @classmethod
    def from_env(cls) -> "Settings":
        raw_origins = os.getenv("CORS_ORIGINS", "*")
        origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())

        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            app_version=os.getenv("APP_VERSION", cls.app_version),
            api_prefix=os.getenv("API_PREFIX", ""),
            cors_origins=origins or ("*",),
            neo4j_uri=os.getenv("NEO4J_URI", cls.neo4j_uri),
            neo4j_user=os.getenv("NEO4J_USER", cls.neo4j_user),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            neo4j_database=os.getenv("NEO4J_DATABASE", cls.neo4j_database),
        )


settings = Settings.from_env()
