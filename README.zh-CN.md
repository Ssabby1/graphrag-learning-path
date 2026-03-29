<p align="right">
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">Chinese</a>
</p>

# GraphRAG Learning Path

一个 GraphRAG 学习路径推荐系统。

该项目结合知识图谱检索、先修约束路径推理，以及基于证据的 LLM 解释生成，为目标知识点提供可解释的学习建议。它不是只靠提示词直接生成答案，而是先从图谱中检索证据、规划有效路径，再返回带有引用和运行元数据的结构化结果。

## 项目概览

GraphRAG Learning Path 是一个端到端 AI 应用项目，目标是展示如何把符号化图结构与自然语言生成结合到实际产品流程中。

系统重点覆盖完整的 GraphRAG 闭环：

- 从知识图谱中检索证据
- 基于先修结构进行路径推理
- 生成有依据的自然语言解释
- 返回便于检查和评估的结构化输出

## 核心能力

- 基于 Neo4j 对知识点与先修关系进行知识图谱检索
- 基于确定性拓扑排序的先修约束路径规划
- 提供结构化 GraphRAG 查询接口，返回 `answer`、`path`、`evidence`、`citations`、`meta`
- 在 LLM 不可用时保留 fallback 行为的解释生成能力
- 提供支持中英双语交互的 Vue 前端，可进行知识点搜索、路径展示与图谱可视化
- 使用自动化测试覆盖检索、规划与响应契约

## 技术栈

### AI / 检索增强能力

- GraphRAG
- 知识图谱检索
- 混合检索（Hybrid Retrieval）
- RRF 融合排序（Reciprocal Rank Fusion）
- 重排序（Reranking）
- 基于证据的 LLM 解释生成
- 结构化证据与引用输出

### 后端

- Python
- FastAPI
- Neo4j
- NetworkX
- LangChain Core

### 前端

- Vue 3
- Vite
- ECharts

### 测试

- Pytest
- HTTPX

## 流程概览

`retrieve -> reason -> generate -> inspect`

1. 检索与目标知识点相关的图谱证据。
2. 基于先修依赖关系推理出有效学习路径。
3. 根据检索证据和规划结果生成 grounded explanation。
4. 返回结构化输出，便于人工检查和系统评估。

## 输出结构示例

`/graphrag/query` 接口返回一个面向可解释性的结构化响应：

```json
{
  "answer": "基于证据的推荐说明",
  "path": ["C001", "C002", "C003"],
  "evidence": ["C001 is a prerequisite of C002"],
  "citations": [
    {
      "concept_id": "C001",
      "kind": "concept",
      "source": "graph"
    }
  ],
  "meta": {
    "source": "fallback",
    "model": "disabled"
  }
}
```

## 快速启动

### 后端

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe run.py
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`

## 2 分钟演示流程

1. 打开前端中的 GraphRAG 查询视图。
2. 搜索并选择目标知识点。
3. 添加已掌握知识点，或直接输入自然语言学习问题。
4. 生成学习路径。
5. 生成 grounded explanation。
6. 结合图谱视图展示 `path`、`evidence`、`citations` 和 `meta` 字段。

## 这个项目体现了什么

- 不只是做提示词调用，而是围绕结构化检索与推理设计 GraphRAG 流程
- 将符号化知识图谱与自然语言解释生成结合起来
- 通过 evidence 和 citation 字段增强 AI 输出的可追溯性与可解释性
- 将 AI 工作流落地为可交互、可测试的全栈应用

## 仓库说明

本公开仓库包含可共享的项目代码与相关文档，未包含完整研究材料、全量数据与本地开发资产。

## 技术文档

- `docs/architecture.md`
- `docs/api.md`
- `docs/data_model.md`
