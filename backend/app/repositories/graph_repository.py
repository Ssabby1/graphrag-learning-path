from typing import Any

try:
    from neo4j import Driver, GraphDatabase
    from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable
    _NEO4J_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local env
    Driver = Any
    GraphDatabase = None

    class _Neo4jDependencyError(Exception):
        pass

    AuthError = Neo4jError = ServiceUnavailable = _Neo4jDependencyError
    _NEO4J_IMPORT_ERROR = exc

from app.core.config import settings
from app.core.errors import RepositoryUnavailableError

MAX_PREREQUISITE_DEPTH = 8


class GraphRepository:
    def __init__(self) -> None:
        self._driver: Driver | None = None

    def _get_driver(self) -> Driver:
        if self._driver is not None:
            return self._driver

        if GraphDatabase is None:
            raise RepositoryUnavailableError("neo4j package is not installed.") from _NEO4J_IMPORT_ERROR

        if not settings.neo4j_password:
            raise RepositoryUnavailableError("NEO4J_PASSWORD is not configured.")

        try:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
            return self._driver
        except (AuthError, ServiceUnavailable, Neo4jError) as exc:
            if self._driver is not None:
                self._driver.close()
                self._driver = None
            raise RepositoryUnavailableError(f"Neo4j unavailable: {exc}") from exc

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def get_graph_overview(self) -> dict[str, int]:
        query = """
        MATCH (co:Course)
        WITH count(DISTINCT co) AS course_count
        MATCH (ch:Chapter)
        WITH course_count, count(DISTINCT ch) AS chapter_count
        MATCH (c:Concept)
        WITH course_count, chapter_count, count(c) AS concept_count
        MATCH ()-[r:PREREQUISITE_OF]->()
        RETURN course_count, chapter_count, concept_count, count(r) AS prerequisite_rel_count
        """
        record = self._run_single(query)
        if record is None:
            return {
                "course_count": 0,
                "chapter_count": 0,
                "concept_count": 0,
                "prerequisite_rel_count": 0,
            }

        return {
            "course_count": int(record["course_count"]),
            "chapter_count": int(record["chapter_count"]),
            "concept_count": int(record["concept_count"]),
            "prerequisite_rel_count": int(record["prerequisite_rel_count"]),
        }

    def get_concept_detail(self, concept_id: str) -> dict | None:
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        OPTIONAL MATCH (ch:Chapter)-[:HAS_CONCEPT]->(c)
        OPTIONAL MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c)
        OPTIONAL MATCH (c)-[:PREREQUISITE_OF]->(next:Concept)
        RETURN
          c.concept_id AS concept_id,
          c.name AS name,
          c.description AS description,
          ch.chapter_id AS chapter_id,
          ch.name AS chapter_name,
          collect(DISTINCT pre.concept_id) AS prerequisites,
          collect(DISTINCT next.concept_id) AS successors
        """

        record = self._run_single(query, {"concept_id": concept_id})
        if record is None:
            return None

        return {
            "concept_id": record["concept_id"],
            "name": record["name"],
            "description": record["description"],
            "chapter_id": record["chapter_id"],
            "chapter_name": record["chapter_name"],
            "prerequisites": [x for x in (record["prerequisites"] or []) if x],
            "successors": [x for x in (record["successors"] or []) if x],
        }

    def get_learning_path(self, target_concept_id: str, mastered_concepts: list[str]) -> dict:
        query = """
        MATCH (target:Concept {concept_id: $target_concept_id})
        OPTIONAL MATCH (pre:Concept)-[:PREREQUISITE_OF*1..]->(target)
        WHERE NOT pre.concept_id IN $mastered_concepts
        WITH target, collect(DISTINCT pre.concept_id) AS missing_prerequisites
        RETURN target.concept_id AS target_concept_id, missing_prerequisites
        """

        record = self._run_single(
            query,
            {
                "target_concept_id": target_concept_id,
                "mastered_concepts": mastered_concepts,
            },
        )
        if record is None:
            return {
                "target_concept_id": target_concept_id,
                "missing_prerequisites": [],
            }

        return {
            "target_concept_id": record["target_concept_id"],
            "missing_prerequisites": [x for x in (record["missing_prerequisites"] or []) if x],
        }

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        # Bound traversal depth so recommendation queries stay responsive even when
        # the prerequisite graph is dense or contains cycles.
        query = f"""
        MATCH (target:Concept {{concept_id: $target_concept_id}})
        OPTIONAL MATCH p=(pre:Concept)-[:PREREQUISITE_OF*1..{MAX_PREREQUISITE_DEPTH}]->(target)
        WITH target, collect(DISTINCT pre.concept_id) + [target.concept_id] AS node_ids, collect(DISTINCT p) AS paths
        UNWIND CASE WHEN size(paths) = 0 THEN [NULL] ELSE paths END AS one_path
        UNWIND CASE WHEN one_path IS NULL THEN [NULL] ELSE relationships(one_path) END AS rel
        WITH
          target,
          [nid IN node_ids WHERE nid IS NOT NULL] AS node_ids,
          collect(DISTINCT [
            CASE WHEN rel IS NULL THEN NULL ELSE startNode(rel).concept_id END,
            CASE WHEN rel IS NULL THEN NULL ELSE endNode(rel).concept_id END
          ]) AS raw_edges
        RETURN
          target.concept_id AS target_concept_id,
          node_ids,
          [e IN raw_edges WHERE e[0] IS NOT NULL AND e[1] IS NOT NULL] AS edges
        """

        record = self._run_single(query, {"target_concept_id": target_concept_id})
        if record is None:
            return {
                "target_exists": False,
                "target_concept_id": target_concept_id,
                "node_ids": [],
                "edges": [],
            }

        return {
            "target_exists": True,
            "target_concept_id": record["target_concept_id"],
            "node_ids": [x for x in (record["node_ids"] or []) if x],
            "edges": [tuple(edge) for edge in (record["edges"] or []) if edge],
        }

    def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
        query = """
        MATCH (c:Concept)
        RETURN c.concept_id AS concept_id, c.name AS name, c.description AS description
        ORDER BY c.concept_id
        LIMIT $limit
        """
        driver = self._get_driver()
        try:
            with driver.session(database=settings.neo4j_database) as session:
                records = session.run(query, {"limit": int(limit)})
                return [
                    {
                        "concept_id": record.get("concept_id"),
                        "name": record.get("name") or "",
                        "description": record.get("description") or "",
                    }
                    for record in records
                    if record.get("concept_id")
                ]
        except (AuthError, ServiceUnavailable, Neo4jError) as exc:
            raise RepositoryUnavailableError(f"Neo4j query failed: {exc}") from exc

    def _run_single(self, query: str, params: dict | None = None):
        driver = self._get_driver()
        try:
            with driver.session(database=settings.neo4j_database) as session:
                return session.run(query, params or {}).single()
        except (AuthError, ServiceUnavailable, Neo4jError) as exc:
            raise RepositoryUnavailableError(f"Neo4j query failed: {exc}") from exc
