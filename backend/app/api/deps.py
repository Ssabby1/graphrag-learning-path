from collections.abc import Generator

from app.repositories.graph_repository import GraphRepository


def get_graph_repository() -> Generator[GraphRepository, None, None]:
    repo = GraphRepository()
    try:
        yield repo
    finally:
        repo.close()
