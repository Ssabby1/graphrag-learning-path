from __future__ import annotations

import heapq
import math
import re
from collections import defaultdict
from typing import Any


MASTERED_HINTS = ["已经学过", "学过", "掌握", "会了", "已掌握", "already know", "learned", "mastered", "know"]
TARGET_HINTS = ["想学", "学习", "想了解", "want to learn", "want to study", "learn", "study"]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())


def _embed(text: str, dimension: int = 256) -> list[float]:
    vector = [0.0] * dimension
    for token in _tokens(text):
        vector[hash(token) % dimension] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return vector if norm == 0 else [value / norm for value in vector]


class Stage0VectorStore:
    def __init__(self, docs: list[dict[str, Any]], dimension: int = 256) -> None:
        self.docs = docs
        self.vectors = [_embed(doc.get("text", ""), dimension) for doc in docs]
        self.dimension = dimension

    def search(self, query: str, top_k: int = 8) -> list[dict[str, Any]]:
        query_vector = _embed(query, self.dimension)
        hits = []
        for doc, vector in zip(self.docs, self.vectors):
            hits.append(
                {
                    "concept_id": doc.get("concept_id", ""),
                    "text": doc.get("text", ""),
                    "score": sum(left * right for left, right in zip(query_vector, vector)),
                    "source": "vector",
                }
            )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[: max(1, top_k)]


def stage0_rerank(question: str, hits: list[dict[str, Any]], top_k: int = 6) -> list[dict[str, Any]]:
    query_tokens = set(_tokens(question))
    rescored = []
    for hit in hits:
        merged = dict(hit)
        overlap = len(query_tokens & set(_tokens(hit.get("text", ""))))
        merged["rerank_score"] = float(hit.get("score", 0.0)) + 0.05 * overlap
        rescored.append(merged)
    rescored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return rescored[: max(1, top_k)]


def stage0_interpret(question: str, corpus: list[dict[str, str]]) -> dict[str, Any]:
    lowered = question.lower()
    matches = []
    for item in corpus:
        concept_id = (item.get("concept_id") or "").strip()
        name = (item.get("name") or "").strip()
        if not concept_id:
            continue
        hit_index = None
        matched_text = ""
        for candidate in (concept_id.lower(), name.lower() if name else ""):
            if candidate and candidate in lowered:
                index = lowered.index(candidate)
                if hit_index is None or index < hit_index:
                    hit_index = index
                    matched_text = candidate
        if hit_index is None:
            continue
        context = lowered[max(0, hit_index - 18) : hit_index]
        last_mastered = max((context.rfind(hint) for hint in MASTERED_HINTS), default=-1)
        last_target = max((context.rfind(hint) for hint in TARGET_HINTS), default=-1)
        mastered_distance = len(context) - last_mastered if last_mastered >= 0 else None
        target_distance = len(context) - last_target if last_target >= 0 else None
        matches.append(
            {
                "concept_id": concept_id,
                "name": name,
                "index": hit_index,
                "match_length": len(matched_text),
                "target_distance": target_distance,
                "is_mastered": mastered_distance is not None
                and (target_distance is None or mastered_distance < target_distance),
            }
        )
    matches.sort(key=lambda item: (item["index"], item["concept_id"]))
    deduped = []
    seen = set()
    for item in matches:
        if item["concept_id"] not in seen:
            seen.add(item["concept_id"])
            deduped.append(item)
    candidates = [item for item in deduped if not item["is_mastered"]] or deduped

    def priority(item: dict[str, Any]) -> tuple[Any, ...]:
        distance = item.get("target_distance")
        return (
            1 if distance is not None else 0,
            -distance if distance is not None else float("-inf"),
            item.get("match_length", 0),
            len(item.get("name") or ""),
            -item.get("index", 0),
            item.get("concept_id") or "",
        )

    target_match = max(candidates, key=priority) if candidates else None
    target = target_match["concept_id"] if target_match else None
    mastered = list(dict.fromkeys(item["concept_id"] for item in deduped if item["is_mastered"]))
    summary = "未能稳定识别目标知识点，请手动选择后继续。"
    if target or mastered:
        parts = []
        if target:
            parts.append(f"目标知识点识别为 {target}")
        if mastered:
            parts.append(f"已掌握知识点识别为 {', '.join(mastered)}")
        summary = "；".join(parts)
    return {
        "target_concept_id": target,
        "mastered_concepts": mastered,
        "matched_concepts": [item["concept_id"] for item in deduped],
        "summary": summary,
        "interpretation_source": "fallback",
    }


def _topological_sort(nodes: set[str], edges: list[tuple[str, str]]) -> tuple[list[str], bool]:
    adjacency = {node: set() for node in nodes}
    indegree = {node: 0 for node in nodes}
    for source, target in set(edges):
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
    heap = [node for node in nodes if indegree[node] == 0]
    heapq.heapify(heap)
    ordered = []
    while heap:
        node = heapq.heappop(heap)
        ordered.append(node)
        for neighbor in sorted(adjacency[node]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                heapq.heappush(heap, neighbor)
    unresolved = sorted(nodes - set(ordered))
    return ordered + unresolved, bool(unresolved)


def stage0_recommend(target: str, mastered: list[str], repo: Any) -> dict[str, Any]:
    mastered_set = set(mastered)
    if target in mastered_set:
        return {
            "target_concept_id": target,
            "path": [],
            "evidence": [f"{target} already in mastered_concepts"],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept already mastered"],
            "explanation": "目标知识点已掌握，无需额外学习路径。",
        }
    subgraph = repo.get_prerequisite_subgraph(target)
    if not subgraph.get("target_exists", False):
        return {
            "target_concept_id": target,
            "path": [],
            "evidence": [],
            "graph_nodes": [],
            "graph_edges": [],
            "reasoning_steps": ["Target concept is not found in the graph"],
            "explanation": "目标知识点不存在，无法生成学习路径。",
        }
    raw_nodes = set(subgraph.get("node_ids", [])) | {target}
    raw_edges = [tuple(edge) for edge in subgraph.get("edges", []) if edge[0] in raw_nodes and edge[1] in raw_nodes]
    required = (raw_nodes - mastered_set) | {target}
    filtered_edges = [edge for edge in raw_edges if edge[0] in required and edge[1] in required]
    path, has_cycle = _topological_sort(required, filtered_edges)
    if target in path:
        path = [node for node in path if node != target] + [target]
    graph_nodes, _ = _topological_sort(raw_nodes, raw_edges)
    if target in graph_nodes:
        graph_nodes = [node for node in graph_nodes if node != target] + [target]
    positions = {node: index for index, node in enumerate(graph_nodes)}
    graph_edges = sorted(set(raw_edges), key=lambda edge: (positions[edge[0]], positions[edge[1]], edge))
    return {
        "target_concept_id": target,
        "path": path,
        "evidence": [node for node in path if node != target],
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "reasoning_steps": [
            "Retrieve prerequisite closure for the target concept",
            "Filter out mastered concepts from candidate nodes",
            "Apply deterministic topological sort on prerequisite graph",
        ],
        "explanation": "检测到疑似环路，已使用稳定回退顺序输出待学习节点。"
        if has_cycle
        else "已基于前驱闭包和拓扑排序生成学习路径。",
        "has_cycle": has_cycle,
        "explanation_source": "fallback",
    }


def _rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            if item_id:
                scores[item_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def stage0_hybrid(question: str, corpus: list[dict[str, str]], graph_ids: list[str]) -> list[dict[str, Any]]:
    docs = [
        {"concept_id": row["concept_id"], "text": f"{row['concept_id']} {row['name']} {row['description']}".strip()}
        for row in corpus
    ]
    vector_hits = Stage0VectorStore(docs).search(question, top_k=8)
    graph_rank = list(dict.fromkeys(graph_ids))
    vector_rank = [hit["concept_id"] for hit in vector_hits]
    by_id = {doc["concept_id"]: doc for doc in docs}
    hits = []
    for concept_id, score in _rrf([graph_rank, vector_rank]):
        source = "graph+vector"
        if concept_id not in vector_rank:
            source = "graph"
        elif concept_id not in graph_rank:
            source = "vector"
        hits.append({"concept_id": concept_id, "text": by_id.get(concept_id, {}).get("text", concept_id), "score": score, "source": source})
    return stage0_rerank(question, hits, top_k=6)


def stage0_answer(question: str, path: list[str], explanation: str, hits: list[dict[str, Any]]) -> str:
    preview = ", ".join(hit.get("concept_id", "") for hit in hits[:5]) or "none"
    path_text = " -> ".join(path) if path else "No additional path needed"
    return (
        f"Question: {question}\nPath: {path_text}\nEvidence concepts: {preview}\n"
        f"Explanation: {explanation}\nAnswer:"
    )


def stage0_query(question: str, target: str, mastered: list[str], repo: Any) -> dict[str, Any]:
    path_result = stage0_recommend(target, mastered, repo)
    graph_ids = list(dict.fromkeys([*path_result.get("path", []), *path_result.get("evidence", [])]))
    hits = stage0_hybrid(question, repo.get_concept_corpus(), graph_ids)
    return {
        "answer": stage0_answer(question, path_result.get("path", []), path_result.get("explanation", ""), hits),
        "path": path_result.get("path", []),
        "evidence": path_result.get("evidence", []),
        "citations": [
            {
                "concept_id": hit["concept_id"],
                "kind": "concept",
                "score": float(hit.get("rerank_score", hit.get("score", 0.0))),
                "source": hit.get("source", "unknown"),
            }
            for hit in hits
        ],
        "meta": {
            "has_cycle": bool(path_result.get("has_cycle", False)),
            "source": "path_service+hybrid_retrieval",
            "model": "template-grounded-answer",
            "retrieval_strategy": "graph+vector+rrf+rerank",
            "vector_backend": "hashing-fallback",
            "fusion": "rrf",
            "reranker": "token-overlap",
        },
    }

