# GraphRAG Learning Path

[![CI](https://github.com/Ssabby1/graphrag-learning-path/actions/workflows/ci.yml/badge.svg)](https://github.com/Ssabby1/graphrag-learning-path/actions/workflows/ci.yml)

[中文说明](README.zh-CN.md) · [Evaluation Summary](evals/reports/stage6_summary.md) · [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)

A multilingual, prerequisite-constrained GraphRAG system that combines complete prerequisite-graph reasoning, cross-lingual retrieval, relationship-level Evidence Packs, deterministic citation validation, and modular evaluation to produce explainable and traceable learning paths.

![English cross-language demo](docs/assets/cross-language-demo.gif)

## Why This Project Exists

A semantic match can suggest relevant concepts, but relevance alone cannot guarantee a valid learning order. This project separates the responsibilities that are often blended inside a RAG pipeline:

- the graph determines the complete prerequisite path;
- multilingual retrieval resolves a target and selects evidence, but never changes the path;
- every path relationship is retained in a complete Evidence Pack, while only a bounded, ranked subset is sent to the Answer Generator;
- the Answer Generator can cite only relationship IDs in that selected answer evidence;
- a deterministic validator removes unknown citations before the API responds.
- explicit `ok`, `already_mastered`, `not_found`, `truncated`, and `cycle` states prevent unsafe paths from becoming normal answers.

## Architecture

```mermaid
flowchart LR
    Q[English / Chinese / Mixed Query] --> R[Target Resolver]
    R -->|Resolved Concept ID| P[Path Planner]
    G[(Prerequisite Graph)] --> P
    P -->|Ordered Ancestor Closure| F[Full Path Evidence Pack]
    G -->|All Path Relationship IDs| F
    F -->|Complete Explanation Evidence| UI[Path + Why Recommended + Sources]
    F --> E[Ranked Answer Evidence Selector]
    E -->|Bounded Context| A[Answer Generator]
    A --> V[Citation Validator]
    V --> UI
```

The core contract is deliberately narrow:

```text
query → resolved target → explicit path status → complete relationship evidence
      → bounded answer evidence → grounded answer → validated citations
```

## Cross-Language Example

```text
Query:    What should I learn before studying Karnaugh maps?
Target:   卡诺图构成 / Karnaugh Map Construction (c_006)
Path:     Binary fundamentals → Truth tables → Boolean algebra
          → Minterms and maxterms → Karnaugh map construction
Evidence: Stable prerequisite relationship IDs from Evidence Pack 1.0
Answer:   English by default; Chinese can be selected explicitly
```

The public sample contains 15 synthetic, curated bilingual concepts and 18 relationship-level evidence records. The full local validation graph contains 190 Chinese concepts and 409 prerequisite relationships; it is not redistributed because its source material is not public.

## Measured Results

| Module | Primary Result | Scope |
| --- | ---: | --- |
| Target Resolver | Top-1 30/30; cross-language Top-1 10/10 | 36 directional fixtures |
| Path Planner | Closure recall 1514/1514; 0 structural violations | all 190 local targets |
| Evidence Retriever | Graph-scoped Recall@5 6/6; Citation Integrity 6/6 | 6 labelled fixtures |
| Answer Generator | Language match 6/6; invalid evidence IDs 0 | offline fallback + fake contract tests |
| GraphRAG Contract | 42 nodes / 107 edges fully evidenced; answer context 8 | deterministic regression fixture |

These are directional engineering evaluations, not claims of statistical generalisation. No external LLM was called for the versioned Answer Generator report: deterministic fallback claim lineage measured `0/6` unsupported claim templates, while real-model unsupported-claim rate and human faithfulness remain explicitly unmeasured. See the [four independent scorecards and feature ablation](evals/reports/stage6_summary.md).

Key decisions supported by the ablation:

- keep `intfloat/multilingual-e5-small` for multilingual retrieval;
- keep complete cached graph closure instead of depth-limited traversal;
- keep relationship retrieval constrained to the planned graph path;
- leave the evaluated CrossEncoder reranker disabled because it reduced overall and English Top-1 quality;
- always retain deterministic bilingual answer fallback and citation validation.

## Run the Public Sample

### macOS / Linux

Prerequisites: Python 3.11–3.13 and Node.js 18+. The public CSV graph mode does not require Docker or Java.

```bash
./setup.sh
./start-dev.sh
```

Stop the services with `./stop-dev.sh`.

The default is a lightweight, fully offline demo. It deliberately skips the optional model runtime and the UI labels retrieval as **Degraded Hashing**. To install `sentence-transformers` and explicitly download the approximately 470 MB multilingual E5 model, run `./setup.sh --embeddings`. Normal startup never downloads model weights.

### Windows PowerShell

The Windows scripts use the same public CSV sample by default, so a clean clone does not require Java, Docker, or a bundled Neo4j directory:

```powershell
.\setup.ps1
.\start-dev.ps1
```

Stop with `.\stop-dev.ps1`.

Use `.\setup.ps1 -Embeddings` to opt into the real multilingual E5 runtime and model download.

Open the frontend at <http://127.0.0.1:5173> and API docs at <http://127.0.0.1:8000/docs>.

For the full local graph, set `GRAPH_BACKEND=neo4j` and start Neo4j with `docker compose up -d neo4j` or your local installation. The Compose password is for development only; set `NEO4J_PASSWORD` to override it.

## Test and Reproduce Reports

```bash
cd backend
.venv-unix/bin/python -m pytest
cd ..
backend/.venv-unix/bin/python evals/graphrag_contract_runner.py
backend/.venv-unix/bin/python evals/stage5_answer_runner.py
backend/.venv-unix/bin/python evals/stage6_report.py
cd frontend
npm run build
```

The public end-to-end test runs the English question above through graph closure, evidence retrieval, Evidence Pack construction, bilingual fallback generation, and citation validation without Neo4j or a network call.

GitHub Actions runs the same offline backend suite, regenerates and validates the Stage 6 reports, audits and builds the frontend, checks Unix shell syntax, and performs a real clean-clone setup/start/API/frontend smoke test on Windows. CI never requires an LLM API key or downloads the optional embedding model.

## Repository Map

- `backend/app/graph/` — immutable graph snapshots and complete prerequisite closure.
- `backend/app/retrieval/` — multilingual concept and relationship retrieval, caches, fusion, and optional reranking.
- `backend/app/evidence/` — Evidence Pack construction and citation validation.
- `backend/app/services/` — target resolution, planning, GraphRAG orchestration, and answer generation.
- `frontend/` — English-first Vue interface with path, evidence, and graph inspection.
- `data/seed/` — public bilingual synthetic sample.
- `evals/` — versioned datasets, runners, JSON reports, Markdown scorecards, and ablations.

## Technology

FastAPI · Neo4j · Vue 3 · ECharts · multilingual E5 · optional CrossEncoder · deterministic structured fallback
