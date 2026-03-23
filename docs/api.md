# API 文档（初版）

## GET /health
### 描述
服务健康检查。

### 响应
```json
{
  "status": "ok",
  "service": "kg-learning-path-backend"
}
```

## GET /graph/overview
### 描述
返回图谱概要统计（当前为占位实现）。

### 响应
```json
{
  "nodes": 0,
  "relations": 0,
  "course": "digital-logic"
}
```

## GET /concept/{id}
### 描述
返回知识点详情（当前为占位实现）。

## POST /path/recommend
### 描述
根据目标知识点与已掌握集合生成推荐路径。

### 请求体
```json
{
  "target_concept_id": "c_001",
  "mastered_concepts": ["c_000"]
}
```

### 响应（示例）
```json
{
  "target_concept_id": "c_001",
  "path": ["c_000", "c_001"],
  "explanations": [
    "c_001 依赖 c_000"
  ]
}
```
