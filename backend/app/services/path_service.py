import heapq

from app.repositories.graph_repository import GraphRepository
from app.services.explanation_service import get_fallback_reasoning_and_explanation


def recommend_path(target_concept_id: str, mastered_concepts: list[str], repo: GraphRepository) -> dict:
    mastered_set = set(mastered_concepts)

    subgraph = repo.get_prerequisite_subgraph(target_concept_id=target_concept_id)
    if not subgraph.get("target_exists", False):
        return {
            "status": "not_found",
            "target_concept_id": target_concept_id,
            "path": [],
            "evidence": [],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept is not found in the graph"],
            "explanation": "目标知识点不存在，无法生成学习路径。",
            "has_cycle": False,
            "truncated": False,
            "max_depth": 0,
            "meta": _meta(node_count=0, edge_count=0),
            "explanation_source": "fallback",
        }

    if target_concept_id in mastered_set:
        return {
            "status": "already_mastered",
            "target_concept_id": target_concept_id,
            "path": [],
            "evidence": [f"{target_concept_id} already in mastered_concepts"],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept already mastered"],
            "explanation": "目标知识点已掌握，无需额外学习路径。",
            "has_cycle": False,
            "truncated": False,
            "max_depth": 0,
            "meta": _meta(node_count=0, edge_count=0, skipped_mastered_count=1),
            "explanation_source": "fallback",
        }

    raw_nodes = set(subgraph.get("node_ids", []))
    raw_nodes.add(target_concept_id)
    raw_edges = [
        (source, target)
        for source, target in subgraph.get("edges", [])
        if source in raw_nodes and target in raw_nodes
    ]

    skipped_nodes = _mastered_with_ancestors(mastered_set & raw_nodes, raw_nodes, raw_edges)
    required_nodes = {node for node in raw_nodes if node not in skipped_nodes}
    required_nodes.add(target_concept_id)

    filtered_edges = [
        (source, target)
        for source, target in raw_edges
        if source in required_nodes and target in required_nodes
    ]

    ordered_path, path_has_cycle = _topo_sort(required_nodes, filtered_edges)
    if target_concept_id in ordered_path:
        ordered_path = [node for node in ordered_path if node != target_concept_id] + [target_concept_id]

    missing_prerequisites = [node for node in ordered_path if node != target_concept_id]
    graph_nodes, _ = _topo_sort(raw_nodes, raw_edges)
    if target_concept_id in graph_nodes:
        graph_nodes = [node for node in graph_nodes if node != target_concept_id] + [target_concept_id]

    graph_edges = _sort_graph_edges(raw_edges, graph_nodes)
    has_cycle = bool(subgraph.get("has_cycle", False) or path_has_cycle)
    truncated = bool(subgraph.get("truncated", False))
    max_depth = int(
        subgraph.get("max_depth", _max_depth(raw_nodes, raw_edges, target_concept_id, has_cycle))
    )
    reasoning_steps, explanation = get_fallback_reasoning_and_explanation(has_cycle)
    if truncated:
        reasoning_steps = [*reasoning_steps, "Report explicit graph safety-limit truncation"]
        explanation = (
            f"{explanation} 图安全限制已触发，当前路径不完整；"
            f"省略 {int(subgraph.get('omitted_node_count', 0))} 个节点和"
            f" {int(subgraph.get('omitted_edge_count', 0))} 条关系。"
        )

    meta = _meta(
        has_cycle=has_cycle,
        truncated=truncated,
        max_depth=max_depth,
        node_count=len(raw_nodes),
        edge_count=len(graph_edges),
        omitted_node_count=int(subgraph.get("omitted_node_count", 0)),
        omitted_edge_count=int(subgraph.get("omitted_edge_count", 0)),
        skipped_mastered_count=len(skipped_nodes),
        planner_strategy=subgraph.get("planner_strategy", "legacy_repository_subgraph"),
        dataset_hash=subgraph.get("dataset_hash"),
    )

    return {
        "status": "cycle" if has_cycle else "truncated" if truncated else "ok",
        "target_concept_id": target_concept_id,
        "path": ordered_path,
        "evidence": missing_prerequisites,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "reasoning_steps": reasoning_steps,
        "explanation": explanation,
        "has_cycle": has_cycle,
        "truncated": truncated,
        "max_depth": max_depth,
        "meta": meta,
        "explanation_source": "fallback",
    }


def _mastered_with_ancestors(
    mastered_nodes: set[str], raw_nodes: set[str], raw_edges: list[tuple[str, str]]
) -> set[str]:
    reverse: dict[str, set[str]] = {node: set() for node in raw_nodes}
    for source, target in raw_edges:
        reverse[target].add(source)
    skipped = set(mastered_nodes)
    stack = sorted(mastered_nodes, reverse=True)
    while stack:
        node = stack.pop()
        for predecessor in sorted(reverse[node], reverse=True):
            if predecessor not in skipped:
                skipped.add(predecessor)
                stack.append(predecessor)
    return skipped


def _meta(**overrides) -> dict:
    result = {
        "has_cycle": False,
        "truncated": False,
        "max_depth": 0,
        "node_count": 0,
        "edge_count": 0,
        "omitted_node_count": 0,
        "omitted_edge_count": 0,
        "skipped_mastered_count": 0,
        "planner_strategy": "cached_graph_ancestor_closure",
        "dataset_hash": None,
    }
    result.update(overrides)
    return result


def _max_depth(
    nodes: set[str], edges: list[tuple[str, str]], target: str, has_cycle: bool
) -> int:
    if has_cycle:
        return 0
    ordered, _ = _topo_sort(nodes, edges)
    depths = {node: 0 for node in nodes}
    successors: dict[str, list[str]] = {node: [] for node in nodes}
    for source, destination in edges:
        successors[source].append(destination)
    for node in ordered:
        for successor in successors[node]:
            depths[successor] = max(depths[successor], depths[node] + 1)
    return depths.get(target, 0)


def _topo_sort(nodes: set[str], edges: list[tuple[str, str]]) -> tuple[list[str], bool]:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    indegree: dict[str, int] = {node: 0 for node in nodes}

    for source, target in set(edges):
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1

    heap = [node for node in nodes if indegree[node] == 0]
    heapq.heapify(heap)

    ordered: list[str] = []
    while heap:
        node = heapq.heappop(heap)
        ordered.append(node)

        for neighbor in sorted(adjacency[node]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                heapq.heappush(heap, neighbor)

    if len(ordered) == len(nodes):
        return ordered, False

    unresolved = sorted(node for node in nodes if node not in set(ordered))
    return ordered + unresolved, True


def _sort_graph_edges(edges: list[tuple[str, str]], ordered_nodes: list[str]) -> list[tuple[str, str]]:
    index_lookup = {node: idx for idx, node in enumerate(ordered_nodes)}
    return sorted(
        set(edges),
        key=lambda edge: (
            index_lookup.get(edge[0], len(ordered_nodes)),
            index_lookup.get(edge[1], len(ordered_nodes)),
            edge[0],
            edge[1],
        ),
    )
