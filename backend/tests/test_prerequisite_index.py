import csv
from collections import deque
from pathlib import Path

import pytest

from app.graph.graph_snapshot import GraphSnapshot
from app.graph.prerequisite_index import PrerequisiteGraphIndex
from app.repositories.graph_repository import GraphRepository
from app.services.path_service import recommend_path


def test_complete_seventeen_node_chain_is_not_depth_limited() -> None:
    nodes = [f"N{index:02d}" for index in range(17)]
    edges = list(zip(nodes, nodes[1:]))
    index = PrerequisiteGraphIndex(GraphSnapshot.build(nodes, edges))

    closure = index.closure(nodes[-1], max_nodes=100, max_edges=100)

    assert closure.node_ids == tuple(nodes)
    assert len(closure.edges) == 16
    assert closure.max_depth == 16
    assert closure.truncated is False
    assert closure.has_cycle is False


def test_branch_merge_topological_order_is_stable() -> None:
    nodes = {"A", "B", "C", "D", "T"}
    edges = [("A", "C"), ("B", "C"), ("C", "T"), ("D", "T")]
    index = PrerequisiteGraphIndex(GraphSnapshot.build(nodes, edges))

    first = index.closure("T", max_nodes=100, max_edges=100)
    second = index.closure("T", max_nodes=100, max_edges=100)

    assert first.node_ids == second.node_ids == ("A", "B", "C", "D", "T")
    positions = {node: position for position, node in enumerate(first.node_ids)}
    assert all(positions[source] < positions[target] for source, target in edges)


def test_cycle_and_self_loop_are_detected_without_unbounded_walk() -> None:
    index = PrerequisiteGraphIndex(
        GraphSnapshot.build({"A", "B", "T"}, {("A", "B"), ("B", "A"), ("B", "T")})
    )
    cyclic = index.closure("T", max_nodes=100, max_edges=100)
    self_loop = PrerequisiteGraphIndex(
        GraphSnapshot.build({"A"}, {("A", "A")})
    ).closure("A", max_nodes=100, max_edges=100)

    assert cyclic.has_cycle is True
    assert set(cyclic.node_ids) == {"A", "B", "T"}
    assert self_loop.has_cycle is True


def test_safety_limits_are_explicit_and_count_omissions() -> None:
    nodes = [f"N{index:02d}" for index in range(10)]
    edges = list(zip(nodes, nodes[1:]))
    closure = PrerequisiteGraphIndex(GraphSnapshot.build(nodes, edges)).closure(
        nodes[-1], max_nodes=5, max_edges=3
    )

    assert closure.truncated is True
    assert closure.omitted_node_count == 5
    assert closure.omitted_edge_count > 0
    assert nodes[-1] in closure.node_ids


def test_snapshot_hash_is_order_independent() -> None:
    first = GraphSnapshot.build(["B", "A"], [("A", "B")])
    second = GraphSnapshot.build(["A", "B"], [("A", "B"), ("A", "B")])
    assert first.content_hash == second.content_hash


def test_repository_snapshot_cache_and_force_refresh() -> None:
    nodes = [f"N{index:02d}" for index in range(17)]
    snapshot = GraphSnapshot.build(nodes, list(zip(nodes, nodes[1:])))

    class CountingRepository(GraphRepository):
        load_count = 0

        def _load_prerequisite_snapshot(self) -> GraphSnapshot:
            type(self).load_count += 1
            return snapshot

    CountingRepository.clear_snapshot_cache()
    repo = CountingRepository()
    first = repo.get_prerequisite_subgraph(nodes[-1])
    second = repo.get_prerequisite_subgraph(nodes[-1])
    repo.get_prerequisite_snapshot(force_refresh=True)

    assert len(first["node_ids"]) == 17
    assert first["max_depth"] == 16
    assert first["dataset_hash"] == second["dataset_hash"]
    assert CountingRepository.load_count == 2
    CountingRepository.clear_snapshot_cache()


def _independent_ancestors(target: str, reverse: dict[str, set[str]]) -> set[str]:
    found: set[str] = set()
    queue = deque([target])
    while queue:
        node = queue.popleft()
        for predecessor in reverse.get(node, set()):
            if predecessor not in found:
                found.add(predecessor)
                queue.append(predecessor)
    return found


def test_full_local_graph_matches_independent_csv_oracle_for_all_targets() -> None:
    root = Path(__file__).resolve().parents[2]
    concepts_path = root / "章节数据/数据汇总/outputs/fixed/concepts_all.csv"
    relations_path = root / "章节数据/数据汇总/outputs/fixed/relations_all.csv"
    if not concepts_path.exists() or not relations_path.exists():
        pytest.skip("full local graph is intentionally absent from the public repository")

    with concepts_path.open(encoding="utf-8-sig", newline="") as handle:
        concept_ids = [row["concept_id"] for row in csv.DictReader(handle)]
    with relations_path.open(encoding="utf-8-sig", newline="") as handle:
        edges = [
            (row["from_concept_id"], row["to_concept_id"])
            for row in csv.DictReader(handle)
            if row["relation_type"] == "PREREQUISITE_OF"
        ]
    reverse: dict[str, set[str]] = {node: set() for node in concept_ids}
    for source, target in edges:
        reverse[target].add(source)
    index = PrerequisiteGraphIndex(GraphSnapshot.build(concept_ids, edges))

    class SnapshotRepository:
        def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
            closure = index.closure(target_concept_id, max_nodes=2000, max_edges=10000)
            return {
                "target_exists": closure.target_exists,
                "target_concept_id": target_concept_id,
                "node_ids": list(closure.node_ids),
                "edges": list(closure.edges),
                "has_cycle": closure.has_cycle,
                "truncated": closure.truncated,
                "max_depth": closure.max_depth,
                "dataset_hash": closure.content_hash,
                "planner_strategy": "cached_graph_ancestor_closure",
            }

    repo = SnapshotRepository()

    for target in concept_ids:
        closure = index.closure(target, max_nodes=2000, max_edges=10000)
        expected = _independent_ancestors(target, reverse)
        result = recommend_path(target, [], repo)
        assert set(closure.node_ids) - {target} == expected
        assert set(result["path"]) - {target} == expected
        assert result["path"][-1] == target
        assert result["meta"]["dataset_hash"] == closure.content_hash
        assert closure.truncated is False
