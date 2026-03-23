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
            "reasoning_steps": ["Target concept already mastered"],
            "explanation": "目标知识点已掌握，无需额外学习路径。",
        }

    subgraph = repo.get_prerequisite_subgraph(target_concept_id=target_concept_id)
    if not subgraph.get("target_exists", False):
        return {
            "target_concept_id": target_concept_id,
            "path": [],
            "evidence": [],
            "reasoning_steps": ["Target concept is not found in the graph"],
            "explanation": "目标知识点不存在，无法生成学习路径。",
        }

    raw_nodes = set(subgraph.get("node_ids", []))
    required_nodes = {node for node in raw_nodes if node not in mastered_set}
    required_nodes.add(target_concept_id)

    raw_edges = subgraph.get("edges", [])
    filtered_edges = [
        (source, target)
        for source, target in raw_edges
        if source in required_nodes and target in required_nodes
    ]

    ordered_path, has_cycle = _topo_sort(required_nodes, filtered_edges)
    if target_concept_id in ordered_path:
        ordered_path = [node for node in ordered_path if node != target_concept_id] + [target_concept_id]

    missing_prerequisites = [node for node in ordered_path if node != target_concept_id]
    reasoning_steps, explanation = get_fallback_reasoning_and_explanation(has_cycle)

    return {
        "target_concept_id": target_concept_id,
        "path": ordered_path,
        "evidence": missing_prerequisites,
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
