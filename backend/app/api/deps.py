from collections.abc import Generator

from app.repositories.graph_repository import GraphRepository
from app.repositories.csv_graph_repository import CsvGraphRepository
from app.core.config import settings


def get_graph_repository() -> Generator[GraphRepository, None, None]:
    repo = (
        CsvGraphRepository(settings.graph_concepts_csv, settings.graph_relations_csv)
        if settings.graph_backend == "csv"
        else GraphRepository()
    )
    try:
        yield repo
    finally:
        repo.close()
