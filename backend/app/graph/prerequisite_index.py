from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

from app.graph.graph_snapshot import GraphSnapshot


@dataclass(frozen=True)
class ClosureResult:
    target_exists: bool
    node_ids: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    has_cycle: bool
    truncated: bool
    max_depth: int
    omitted_node_count: int
    omitted_edge_count: int
    content_hash: str


class PrerequisiteGraphIndex:
    """Deterministic in-memory index for complete prerequisite reasoning."""

    def __init__(self, snapshot: GraphSnapshot) -> None:
        self.snapshot = snapshot
        self.concept_ids = frozenset(snapshot.concept_ids)
        self.edges = snapshot.prerequisite_edges
        self.forward: dict[str, tuple[str, ...]] = {node: () for node in snapshot.concept_ids}
        self.reverse: dict[str, tuple[str, ...]] = {node: () for node in snapshot.concept_ids}
        forward_sets = {node: set() for node in snapshot.concept_ids}
        reverse_sets = {node: set() for node in snapshot.concept_ids}
        for source, target in self.edges:
            forward_sets[source].add(target)
            reverse_sets[target].add(source)
        self.forward = {node: tuple(sorted(neighbors)) for node, neighbors in forward_sets.items()}
        self.reverse = {node: tuple(sorted(neighbors)) for node, neighbors in reverse_sets.items()}

    def ancestors(self, target: str) -> set[str]:
        if target not in self.concept_ids:
            return set()
        found: set[str] = set()
        queue = deque([target])
        while queue:
            node = queue.popleft()
            for predecessor in self.reverse[node]:
                if predecessor not in found:
                    found.add(predecessor)
                    queue.append(predecessor)
        return found

    def closure(self, target: str, max_nodes: int, max_edges: int) -> ClosureResult:
        if target not in self.concept_ids:
            return ClosureResult(False, (), (), False, False, 0, 0, 0, self.snapshot.content_hash)

        complete_nodes = self.ancestors(target) | {target}
        complete_edges = tuple(
            edge for edge in self.edges if edge[0] in complete_nodes and edge[1] in complete_nodes
        )
        selected_nodes = set(sorted(complete_nodes)[:max_nodes])
        selected_nodes.add(target)
        if len(selected_nodes) > max_nodes:
            removable = sorted(selected_nodes - {target}, reverse=True)
            selected_nodes.remove(removable[0])
        selected_edges = tuple(
            edge for edge in complete_edges if edge[0] in selected_nodes and edge[1] in selected_nodes
        )
        if len(selected_edges) > max_edges:
            selected_edges = selected_edges[:max_edges]

        ordered, has_cycle = self.topological_sort(selected_nodes, selected_edges)
        max_depth = self.max_depth(selected_nodes, selected_edges, target, has_cycle)
        omitted_nodes = len(complete_nodes - selected_nodes)
        omitted_edges = len(complete_edges) - len(selected_edges)
        return ClosureResult(
            True,
            tuple(ordered),
            selected_edges,
            has_cycle,
            omitted_nodes > 0 or omitted_edges > 0,
            max_depth,
            omitted_nodes,
            omitted_edges,
            self.snapshot.content_hash,
        )

    @staticmethod
    def topological_sort(
        nodes: set[str], edges: tuple[tuple[str, str], ...] | list[tuple[str, str]]
    ) -> tuple[list[str], bool]:
        adjacency = {node: set() for node in nodes}
        indegree = {node: 0 for node in nodes}
        for source, target in set(edges):
            if source in nodes and target in nodes and target not in adjacency[source]:
                adjacency[source].add(target)
                indegree[target] += 1
        heap = [node for node, degree in indegree.items() if degree == 0]
        heapq.heapify(heap)
        ordered: list[str] = []
        while heap:
            node = heapq.heappop(heap)
            ordered.append(node)
            for neighbor in sorted(adjacency[node]):
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    heapq.heappush(heap, neighbor)
        unresolved = sorted(nodes - set(ordered))
        return ordered + unresolved, bool(unresolved)

    @staticmethod
    def max_depth(
        nodes: set[str],
        edges: tuple[tuple[str, str], ...] | list[tuple[str, str]],
        target: str,
        has_cycle: bool,
    ) -> int:
        if not nodes or target not in nodes:
            return 0
        reverse = {node: set() for node in nodes}
        for source, destination in edges:
            if source in nodes and destination in nodes:
                reverse[destination].add(source)
        if has_cycle:
            distances = {target: 0}
            queue = deque([target])
            while queue:
                node = queue.popleft()
                for predecessor in sorted(reverse[node]):
                    if predecessor not in distances:
                        distances[predecessor] = distances[node] + 1
                        queue.append(predecessor)
            return max(distances.values(), default=0)

        ordered, _ = PrerequisiteGraphIndex.topological_sort(nodes, edges)
        depth = {node: 0 for node in nodes}
        for node in ordered:
            for successor_source, successor in edges:
                if successor_source == node:
                    depth[successor] = max(depth[successor], depth[node] + 1)
        return depth.get(target, 0)
