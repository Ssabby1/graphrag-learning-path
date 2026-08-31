# API 接口说明

## 1. 接口概览

后端采用 FastAPI 实现，默认启动后可通过 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

当前核心接口包括：

- `GET /health`
- `GET /graph/overview`
- `GET /concept/{concept_id}`
- `GET /concepts`
- `POST /path/recommend`
- `POST /path/explain`
- `POST /planner/interpret`
- `POST /state/update`
- `POST /graphrag/query`

## 2. 健康检查

### GET `/health`

用于检查后端服务是否正常启动。

响应示例：

```json
{
  "status": "ok",
  "service": "kg-learning-path-backend"
}
```

## 3. 图谱查询接口

### GET `/graph/overview`

返回图谱统计信息。

响应字段：

- `course_count`
- `chapter_count`
- `concept_count`
- `prerequisite_rel_count`

### GET `/concept/{concept_id}`

返回某个知识点的详细信息。

响应字段：

- `concept_id`
- `name`
- `description`
- `chapter_id`
- `chapter_name`
- `prerequisites`
- `successors`

### GET `/concepts`

返回概念语料列表，供前端搜索和 planner/retrieval 使用。

查询参数：

- `limit`：最多返回多少条概念，默认 `2000`

## 4. 路径推荐接口

### POST `/path/recommend`

根据目标知识点和已掌握知识点生成推荐学习路径。

路径由完整 `PREREQUISITE_OF` 祖先闭包决定，不再设置固定 8 层查询上限。默认把已掌握节点及其全部祖先从待学习路径中跳过，但这些节点仍保留在 `graph_nodes` / `graph_edges` 图上下文中。

请求示例：

```json
{
  "target_concept_id": "C010",
  "mastered_concepts": ["C001", "C002"]
}
```

响应字段：

- `target_concept_id`
- `path`
- `evidence`
- `graph_nodes`
- `graph_edges`
- `reasoning_steps`
- `explanation`
- `has_cycle`
- `truncated`：图安全限制是否触发；为 `true` 时路径不得视为完整
- `max_depth`：目标在当前先修闭包中的最长祖先深度
- `meta`：节点/边数量、省略数量、缓存策略和数据集哈希
- `explanation_source`

`meta` 结构示例：

```json
{
  "has_cycle": false,
  "truncated": false,
  "max_depth": 16,
  "node_count": 42,
  "edge_count": 87,
  "omitted_node_count": 0,
  "omitted_edge_count": 0,
  "skipped_mastered_count": 0,
  "planner_strategy": "cached_graph_ancestor_closure",
  "dataset_hash": "sha256..."
}
```

### POST `/path/explain`

对已有路径结果进行解释生成。

请求字段：

- `target_concept_id`
- `path`
- `evidence`
- `has_cycle`

## 5. 自然语言请求解析接口

### POST `/planner/interpret`

把自然语言学习请求解析成结构化目标信息。

请求示例：

```json
{
  "question": "我已经学过逻辑门，想继续学习组合逻辑电路"
}
```

响应字段：

- `target_concept_id`
- `mastered_concepts`
- `matched_concepts`
- `summary`
- `interpretation_source`

## 6. GraphRAG 查询接口

### POST `/graphrag/query`

这是当前项目最核心的接口，用于执行完整的 GraphRAG 查询流程。

请求示例：

```json
{
  "question": "我想学习时序逻辑，应该先补哪些知识？",
  "target_concept_id": "C021",
  "mastered_concepts": ["C001", "C005"]
}
```

响应字段：

- `answer`：最终自然语言回答
- `path`：推荐学习路径
- `evidence`：图谱证据
- `citations`：引用列表
- `meta`：元信息，包括检索与生成策略说明

响应示例：

```json
{
  "answer": "建议先学习组合逻辑基础，再进入时序逻辑相关内容。",
  "path": ["C005", "C010", "C021"],
  "evidence": ["C010 is a prerequisite of C021"],
  "citations": [
    {
      "concept_id": "C010",
      "kind": "concept",
      "score": 0.92,
      "source": "graph"
    }
  ],
  "meta": {
    "has_cycle": false,
    "truncated": false,
    "max_depth": 2,
    "planner_strategy": "cached_graph_ancestor_closure",
    "dataset_hash": "sha256...",
    "source": "path_service+hybrid_retrieval",
    "model": "template-grounded-answer",
    "retrieval_strategy": "graph+vector+rrf+rerank",
    "vector_backend": "fallback",
    "fusion": "rrf",
    "reranker": "heuristic"
  }
}
```

## 7. 状态更新接口

### POST `/state/update`

该接口目前仍是占位实现，用于预留用户学习状态更新能力。

它可以作为后续扩展点，在论文中说明系统具备个性化学习状态跟踪的发展空间。
