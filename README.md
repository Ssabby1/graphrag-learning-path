<p align="right">
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">Chinese</a>
</p>

# GraphRAG Learning Path

A GraphRAG system for learning path recommendation.

This project combines knowledge graph retrieval, prerequisite-aware path reasoning, and grounded LLM explanation generation to produce explainable learning guidance for a target concept. Instead of responding from prompts alone, the system retrieves graph evidence, plans a valid concept path, and returns structured outputs with citations and runtime metadata.

## Overview

GraphRAG Learning Path is an end-to-end AI application project that demonstrates how to connect symbolic graph structure with natural-language generation in a practical product workflow.

The system focuses on the full GraphRAG loop:

- retrieve evidence from a knowledge graph
- reason over prerequisite structure
- generate grounded natural-language explanations
- return machine-friendly outputs for inspection and evaluation

## Core Capabilities

- Knowledge graph retrieval over concepts and prerequisite relations stored in Neo4j
- Prerequisite-aware path planning with deterministic topological ordering
- GraphRAG query endpoint with structured fields: `answer`, `path`, `evidence`, `citations`, `meta`
- Grounded explanation generation with fallback behavior when LLM support is unavailable
- Interactive Vue frontend for concept search, path visualization, and bilingual exploration
- Automated API and service tests covering retrieval, planning, and response contracts

## Tech Stack

### AI / Retrieval

- GraphRAG
- Knowledge Graph Retrieval
- Hybrid Retrieval
- Reciprocal Rank Fusion (RRF)
- Reranking
- Grounded LLM Explanation
- Structured Evidence and Citation Outputs

### Backend

- Python
- FastAPI
- Neo4j
- NetworkX
- LangChain Core

### Frontend

- Vue 3
- Vite
- ECharts

### Testing

- Pytest
- HTTPX

## Pipeline

`retrieve -> reason -> generate -> inspect`

1. Retrieve graph evidence relevant to the target concept.
2. Reason over prerequisite dependencies to build a valid learning path.
3. Generate a grounded explanation from retrieved evidence and planned path.
4. Return structured outputs so the result can be inspected by both humans and downstream systems.

## Example Output Contract

The `/graphrag/query` endpoint returns a structured response designed for explainability:

```json
{
  "answer": "Grounded recommendation text",
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

## Quick Start

### Backend

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe run.py
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`

## 2-Min Demo Flow

1. Open the GraphRAG query view in the frontend.
2. Search and select a target concept.
3. Add mastered concepts or enter a natural-language learning question.
4. Generate the learning path.
5. Generate the grounded explanation.
6. Show the returned `path`, `evidence`, `citations`, and `meta` fields together with the graph view.

## What This Project Demonstrates

- Designing a GraphRAG pipeline around structured retrieval and reasoning, not just prompt orchestration
- Combining symbolic graph structure with natural-language explanation generation
- Building explainable AI outputs with evidence and citation fields
- Turning an AI workflow into a usable full-stack application with test coverage

## Repository Notes

This public repository contains the shareable project code and supporting documentation. Some original research materials, full datasets, and local development assets are intentionally excluded.

## Technical Docs

- `docs/architecture.md`
- `docs/api.md`
- `docs/data_model.md`
