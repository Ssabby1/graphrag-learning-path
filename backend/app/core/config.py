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
    graph_max_nodes: int = 2000
    graph_max_edges: int = 10000
    graph_query_timeout_seconds: float = 10.0
    graph_cache_ttl_seconds: float = 60.0
    embedding_backend: str = "sentence_transformers"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_allow_download: bool = False
    embedding_fallback_backend: str = "unicode_hashing"
    embedding_normalize: bool = True
    embedding_cache_dir: str = str(BACKEND_ROOT / ".cache" / "embeddings")
    retrieval_mode: str = "hybrid_rrf"
    retrieval_top_k_vector: int = 8
    retrieval_top_k_final: int = 6
    retrieval_rrf_k: int = 60
    reranker_backend: str = "cross_encoder"
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_allow_download: bool = False
    reranker_fallback_backend: str = "token_overlap"
    reranker_batch_size: int = 16
    reranker_max_length: int = 512
    reranker_device: str = ""
    target_resolver_top_k: int = 5
    target_resolver_min_score: float = 0.8
    target_resolver_min_margin: float = 0.01

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
            graph_max_nodes=_positive_int("GRAPH_MAX_NODES", cls.graph_max_nodes),
            graph_max_edges=_positive_int("GRAPH_MAX_EDGES", cls.graph_max_edges),
            graph_query_timeout_seconds=_positive_float(
                "GRAPH_QUERY_TIMEOUT_SECONDS", cls.graph_query_timeout_seconds
            ),
            graph_cache_ttl_seconds=_non_negative_float(
                "GRAPH_CACHE_TTL_SECONDS", cls.graph_cache_ttl_seconds
            ),
            embedding_backend=os.getenv("EMBEDDING_BACKEND", cls.embedding_backend).strip(),
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model).strip(),
            embedding_allow_download=_bool_env(
                "EMBEDDING_ALLOW_DOWNLOAD", cls.embedding_allow_download
            ),
            embedding_fallback_backend=os.getenv(
                "EMBEDDING_FALLBACK_BACKEND", cls.embedding_fallback_backend
            ).strip(),
            embedding_normalize=_bool_env("EMBEDDING_NORMALIZE", cls.embedding_normalize),
            embedding_cache_dir=os.getenv(
                "EMBEDDING_CACHE_DIR", cls.embedding_cache_dir
            ).strip(),
            retrieval_mode=os.getenv("RETRIEVAL_MODE", cls.retrieval_mode).strip(),
            retrieval_top_k_vector=_positive_int(
                "RETRIEVAL_TOP_K_VECTOR", cls.retrieval_top_k_vector
            ),
            retrieval_top_k_final=_positive_int(
                "RETRIEVAL_TOP_K_FINAL", cls.retrieval_top_k_final
            ),
            retrieval_rrf_k=_positive_int("RETRIEVAL_RRF_K", cls.retrieval_rrf_k),
            reranker_backend=os.getenv("RERANKER_BACKEND", cls.reranker_backend).strip(),
            reranker_model=os.getenv("RERANKER_MODEL", cls.reranker_model).strip(),
            reranker_allow_download=_bool_env(
                "RERANKER_ALLOW_DOWNLOAD", cls.reranker_allow_download
            ),
            reranker_fallback_backend=os.getenv(
                "RERANKER_FALLBACK_BACKEND", cls.reranker_fallback_backend
            ).strip(),
            reranker_batch_size=_positive_int(
                "RERANKER_BATCH_SIZE", cls.reranker_batch_size
            ),
            reranker_max_length=_positive_int(
                "RERANKER_MAX_LENGTH", cls.reranker_max_length
            ),
            reranker_device=os.getenv("RERANKER_DEVICE", cls.reranker_device).strip(),
            target_resolver_top_k=_positive_int(
                "TARGET_RESOLVER_TOP_K", cls.target_resolver_top_k
            ),
            target_resolver_min_score=_non_negative_float(
                "TARGET_RESOLVER_MIN_SCORE", cls.target_resolver_min_score
            ),
            target_resolver_min_margin=_non_negative_float(
                "TARGET_RESOLVER_MIN_MARGIN", cls.target_resolver_min_margin
            ),
        )


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _non_negative_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= 0 else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings.from_env()
