import threading
import time
from typing import Any

try:
    from neo4j import Driver, GraphDatabase, Query
    from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable
    _NEO4J_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local env
    Driver = Any
    GraphDatabase = None
    Query = None

    class _Neo4jDependencyError(Exception):
        pass

    AuthError = Neo4jError = ServiceUnavailable = _Neo4jDependencyError
    _NEO4J_IMPORT_ERROR = exc

from app.core.config import settings
from app.core.errors import RepositoryUnavailableError
from app.graph.graph_snapshot import GraphSnapshot
from app.graph.prerequisite_index import PrerequisiteGraphIndex


class GraphRepository:
    _snapshot_cache: GraphSnapshot | None = None
    _snapshot_cached_at: float = 0.0
    _snapshot_lock = threading.Lock()

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
        subgraph = self.get_prerequisite_subgraph(target_concept_id)
        if not subgraph["target_exists"]:
            return {
                "target_concept_id": target_concept_id,
                "missing_prerequisites": [],
            }
        nodes = set(subgraph["node_ids"])
        reverse = {node: set() for node in nodes}
        for source, target in subgraph["edges"]:
            reverse[target].add(source)
        skipped = set(mastered_concepts) & nodes
        stack = list(skipped)
        while stack:
            node = stack.pop()
            for predecessor in reverse[node]:
                if predecessor not in skipped:
                    skipped.add(predecessor)
                    stack.append(predecessor)
        return {
            "target_concept_id": target_concept_id,
            "missing_prerequisites": [
                node for node in subgraph["node_ids"] if node != target_concept_id and node not in skipped
            ],
            "truncated": subgraph["truncated"],
        }

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        snapshot = self.get_prerequisite_snapshot()
        closure = PrerequisiteGraphIndex(snapshot).closure(
            target=target_concept_id,
            max_nodes=settings.graph_max_nodes,
            max_edges=settings.graph_max_edges,
        )
        return {
            "target_exists": closure.target_exists,
            "target_concept_id": target_concept_id,
            "node_ids": list(closure.node_ids),
            "edges": list(closure.edges),
            "has_cycle": closure.has_cycle,
            "truncated": closure.truncated,
            "max_depth": closure.max_depth,
            "omitted_node_count": closure.omitted_node_count,
            "omitted_edge_count": closure.omitted_edge_count,
            "dataset_hash": closure.content_hash,
            "planner_strategy": "cached_graph_ancestor_closure",
        }

    def get_prerequisite_snapshot(self, force_refresh: bool = False) -> GraphSnapshot:
        now = time.monotonic()
        cached = type(self)._snapshot_cache
        cache_age = now - type(self)._snapshot_cached_at
        if (
            not force_refresh
            and cached is not None
            and settings.graph_cache_ttl_seconds > 0
            and cache_age < settings.graph_cache_ttl_seconds
        ):
            return cached

        with type(self)._snapshot_lock:
            now = time.monotonic()
            cached = type(self)._snapshot_cache
            cache_age = now - type(self)._snapshot_cached_at
            if (
                not force_refresh
                and cached is not None
                and settings.graph_cache_ttl_seconds > 0
                and cache_age < settings.graph_cache_ttl_seconds
            ):
                return cached
            snapshot = self._load_prerequisite_snapshot()
            type(self)._snapshot_cache = snapshot
            type(self)._snapshot_cached_at = time.monotonic()
            return snapshot

    @classmethod
    def clear_snapshot_cache(cls) -> None:
        with cls._snapshot_lock:
            cls._snapshot_cache = None
            cls._snapshot_cached_at = 0.0

    def _load_prerequisite_snapshot(self) -> GraphSnapshot:
        concept_query = """
        MATCH (c:Concept)
        WHERE c.concept_id IS NOT NULL AND trim(toString(c.concept_id)) <> ''
        RETURN c.concept_id AS concept_id
        ORDER BY concept_id
        """
        edge_query = """
        MATCH (source:Concept)-[:PREREQUISITE_OF]->(target:Concept)
        WHERE source.concept_id IS NOT NULL AND target.concept_id IS NOT NULL
        RETURN source.concept_id AS source_id, target.concept_id AS target_id
        ORDER BY source_id, target_id
        """
        driver = self._get_driver()
        try:
            with driver.session(database=settings.neo4j_database) as session:
                concepts = [
                    record.get("concept_id")
                    for record in session.run(self._timed_query(concept_query))
                    if record.get("concept_id")
                ]
                edges = [
                    (record.get("source_id"), record.get("target_id"))
                    for record in session.run(self._timed_query(edge_query))
                    if record.get("source_id") and record.get("target_id")
                ]
            return GraphSnapshot.build(concepts, edges)
        except (AuthError, ServiceUnavailable, Neo4jError) as exc:
            raise RepositoryUnavailableError(f"Neo4j query failed: {exc}") from exc

    @staticmethod
    def _timed_query(query: str):
        if Query is None:
            return query
        return Query(query, timeout=settings.graph_query_timeout_seconds)

    def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
        query = """
        MATCH (c:Concept)
        OPTIONAL MATCH (chapter:Chapter)-[:HAS_CONCEPT]->(c)
        WITH c, collect(DISTINCT chapter.name) AS source_chapters
        OPTIONAL MATCH (predecessor:Concept)-[:PREREQUISITE_OF]->(c)
        WITH c, source_chapters, collect(DISTINCT predecessor.name) AS predecessor_names
        OPTIONAL MATCH (c)-[:PREREQUISITE_OF]->(successor:Concept)
        RETURN c.concept_id AS concept_id,
               c.name AS name,
               c.name_en AS name_en,
               c.alias AS aliases,
               c.aliases_en AS aliases_en,
               c.description AS description,
               c.description_en AS description_en,
               c.difficulty AS difficulty,
               source_chapters,
               predecessor_names,
               collect(DISTINCT successor.name) AS successor_names
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
                        "name_en": record.get("name_en") or "",
                        "aliases": record.get("aliases") or [],
                        "aliases_en": record.get("aliases_en") or [],
                        "description": record.get("description") or "",
                        "description_en": record.get("description_en") or "",
                        "difficulty": record.get("difficulty") or "",
                        "source_chapters": [item for item in (record.get("source_chapters") or []) if item],
                        "predecessor_names": [item for item in (record.get("predecessor_names") or []) if item],
                        "successor_names": [item for item in (record.get("successor_names") or []) if item],
                    }
                    for record in records
                    if record.get("concept_id")
                ]
        except (AuthError, ServiceUnavailable, Neo4jError) as exc:
            raise RepositoryUnavailableError(f"Neo4j query failed: {exc}") from exc

    def get_relation_corpus(
        self, relation_types: tuple[str, ...] = ("PREREQUISITE_OF", "RELATED_TO")
    ) -> list[dict]:
        query = """
        MATCH (source:Concept)-[r]->(target:Concept)
        WHERE type(r) IN $relation_types
        OPTIONAL MATCH (source_chapter:Chapter)-[:HAS_CONCEPT]->(source)
        WITH source, target, r, collect(DISTINCT source_chapter.name) AS source_side_chapters
        OPTIONAL MATCH (target_chapter:Chapter)-[:HAS_CONCEPT]->(target)
        RETURN source.concept_id AS from_concept_id,
               source.name AS from_name,
               target.concept_id AS to_concept_id,
               target.name AS to_name,
               type(r) AS relation_type,
               r.evidence_text AS evidence_text,
               r.source_images AS source_images,
               r.confidence_max AS confidence_max,
               r.verification_status AS verification_status,
               source_side_chapters + collect(DISTINCT target_chapter.name) AS source_chapters
        ORDER BY relation_type, from_concept_id, to_concept_id
        """
        driver = self._get_driver()
        try:
            with driver.session(database=settings.neo4j_database) as session:
                records = session.run(query, {"relation_types": list(relation_types)})
                return [
                    {
                        "from_concept_id": record.get("from_concept_id"),
                        "from_name": record.get("from_name") or "",
                        "to_concept_id": record.get("to_concept_id"),
                        "to_name": record.get("to_name") or "",
                        "relation_type": record.get("relation_type") or "",
                        "evidence_text": record.get("evidence_text") or "",
                        "source_images": record.get("source_images") or [],
                        "confidence_max": record.get("confidence_max"),
                        "verification_status": record.get("verification_status") or "unreviewed",
                        "source_chapters": list(
                            dict.fromkeys(
                                item for item in (record.get("source_chapters") or []) if item
                            )
                        ),
                    }
                    for record in records
                    if record.get("from_concept_id") and record.get("to_concept_id")
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
