import heapq

from app.repositories.graph_repository import GraphRepository
from app.services.explanation_service import get_fallback_reasoning_and_explanation


def recommend_path(target_concept_id: str, mastered_concepts: list[str], repo: GraphRepository) -> dict:
    mastered_set = set(mastered_concepts)

    if target_concept_id in mastered_set:
        return {
            "target_concept_id": target_concept_id,
            "path": [],
            "evidence": [f"{target_concept_id} already in mastered_concepts"],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept already mastered"],
            "explanation": "目标知识点已掌握，无需额外学习路径。",
        }

    subgraph = repo.get_prerequisite_subgraph(target_concept_id=target_concept_id)
    if not subgraph.get("target_exists", False):
        return {
            "target_concept_id": target_concept_id,
            "path": [],
            "evidence": [],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept is not found in the graph"],
            "explanation": "目标知识点不存在，无法生成学习路径。",
        }

    raw_nodes = set(subgraph.get("node_ids", []))
    raw_nodes.add(target_concept_id)
    raw_edges = [
        (source, target)
        for source, target in subgraph.get("edges", [])
        if source in raw_nodes and target in raw_nodes
    ]

    required_nodes = {node for node in raw_nodes if node not in mastered_set}
    required_nodes.add(target_concept_id)

    filtered_edges = [
        (source, target)
        for source, target in raw_edges
        if source in required_nodes and target in required_nodes
    ]

    ordered_path, has_cycle = _topo_sort(required_nodes, filtered_edges)
    if target_concept_id in ordered_path:
        ordered_path = [node for node in ordered_path if node != target_concept_id] + [target_concept_id]

    missing_prerequisites = [node for node in ordered_path if node != target_concept_id]
    graph_nodes, _ = _topo_sort(raw_nodes, raw_edges)
    if target_concept_id in graph_nodes:
        graph_nodes = [node for node in graph_nodes if node != target_concept_id] + [target_concept_id]

    graph_edges = _sort_graph_edges(raw_edges, graph_nodes)
    reasoning_steps, explanation = get_fallback_reasoning_and_explanation(has_cycle)

    return {
        "target_concept_id": target_concept_id,
        "path": ordered_path,
        "evidence": missing_prerequisites,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "reasoning_steps": reasoning_steps,
        "explanation": explanation,
        "has_cycle": has_cycle,
        "explanation_source": "fallback",
    }


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
