# GraphRAG Phase Roadmap (Strategic View)

## 1. Program Objective
Build a GraphRAG system for course learning-path recommendation that is retrievable, explainable, measurable, and deployable.

Core capability goals:
1. Graph-based knowledge organization (structured prerequisites)
2. Hybrid retrieval (graph + vector + keyword)
3. Evidence-grounded generation (explainable output)
4. Production-ready services (stable APIs, tests, monitoring, deployment)

---

## 2. Target Architecture
- Backend: FastAPI
- Graph store: Neo4j
- Vector capability: Neo4j Vector Index or external vector store (FAISS/Chroma)
- Keyword retrieval: BM25/inverted index
- Frontend: Vue 3 + ECharts
- Offline/ops pipeline: Python scripts (data, indexing, evaluation)

---

## 3. Phase Plan

## Phase A: Data and Knowledge Modeling
Goal: establish a high-quality, maintainable graph data foundation.

Key work:
1. Define a unified data model
- Entities: Course / Chapter / Concept
- Relations: PREREQUISITE_OF plus extensible relation types
- Evidence attributes: evidence_text / source / confidence

2. Build data processing pipeline
- Standardization of source data
- Deduplication, alias normalization, relation-direction validation
- Import and incremental update strategy

3. Add data quality gates
- Cycle detection, self-loop detection, duplicate-edge detection
- Required-field completeness checks
- Automated quality report generation

Outputs:
- Stable graph schema and import contract
- Reusable validation workflow
- Versioned and traceable data snapshots

---

## Phase B: Retrieval and Indexing
Goal: deliver scalable GraphRAG retrieval capabilities.

Key work:
1. Chunk design
- Concept chunks (description, chapter, aliases)
- Relation-evidence chunks (edge semantics + evidence text)
- Standard metadata (concept_id, edge_id, confidence)

2. Index construction
- Graph index: Neo4j constraints and indexes
- Vector index: embeddings + ANN index
- Keyword index: BM25/inverted index

3. Hybrid retrieval strategy
- Graph recall: prerequisite subgraph expansion
- Vector recall: semantic nearest neighbors
- Keyword recall: exact terminology hits
- Fusion/reranking: weighted score + rule-based rerank

Outputs:
- Rebuildable multi-index system
- Online hybrid retrieval service
- Tunable recall/ranking knobs

---

## Phase C: Reasoning and Generation
Goal: produce evidence-driven and auditable recommendations.

Key work:
1. Recommendation reasoning flow
- Input normalization (target concept, mastered set, optional goal)
- Candidate path generation
- Evidence bundle freezing before generation

2. Prompt engineering
- System constraints: role, boundaries, anti-hallucination rules
- Structured input template: path candidates + evidence table
- Structured output template: path/evidence/reasoning/explanation/confidence

3. Output control and fallback
- Fact checks against graph edges/nodes
- Explicit uncertainty handling when evidence is weak
- Template fallback rewrite for invalid generations

Outputs:
- Stable and auditable model responses
- Standardized explainability fields
- Hallucination control mechanisms

---

## Phase D: Service Layer (FastAPI)
Goal: expose stable, testable, and well-documented APIs.

Key work:
1. FastAPI service design
- Route domains: health / graph / concept / recommend / admin
- Pydantic request-response contracts
- Dependency injection for config, DB, retrievers, generators

2. Core API surface
- `GET /health`
- `GET /graph/overview`
- `GET /concept/{concept_id}`
- `POST /path/recommend`
- `POST /admin/index/rebuild` (ops/admin)

3. Engineering robustness
- Unified error codes and exception handling
- Request logs and latency metrics
- Concurrency, timeout, and retry policies

Outputs:
- Deployable FastAPI backend
- OpenAPI docs and stable contracts
- Reliable runtime behavior

---

## Phase E: Frontend Productization
Goal: turn retrieval and reasoning into a user-understandable product flow.

Key work:
1. Interaction flow
- Target concept and learning-state input
- Path visualization with graph highlighting
- Side-by-side evidence and explanation panels

2. Explainability UX
- Step cards for path sequence
- Per-step evidence traceability
- Confidence and alternative path display

3. Usability hardening
- Error fallback UX
- History and comparison views
- Responsive behavior for desktop/mobile

Outputs:
- End-to-end demo-ready frontend
- Explainable and reviewable recommendation display

---

## Phase F: Evaluation, Optimization, and Operations
Goal: establish measurable improvement loops and stable operations.

Key work:
1. Retrieval evaluation
- Recall@K, MRR, nDCG
- Contribution analysis by graph/vector/keyword branches

2. Generation evaluation
- Factual grounding rate (evidence traceability)
- Explanation quality (clarity/completeness)
- Hallucination and fallback rates

3. Operations
- Scheduled/manual data refresh workflow
- Index rebuild workflow
- Logging, alerting, and performance monitoring

Outputs:
- Continuous optimization metric system
- Operational stability mechanisms
- Versioned release process

---

## 4. Milestone View
1. M1: graph data foundation + quality gates
2. M2: hybrid retrieval + tunable ranking
3. M3: evidence-grounded generation + explainable API
4. M4: FastAPI serviceization + frontend integration
5. M5: evaluation loop + deployment handoff

---

## 5. Decision Principles
1. Usability before complexity: close a working loop first
2. Explainability before score chasing: evidence traceability first
3. Stability before expansion: lock contracts and quality gates early
4. Replaceable components: model/vector/retrieval should stay pluggable

---

## 6. One-line Summary
Drive this GraphRAG program in six layers: data foundation -> retrieval core -> generation engine -> FastAPI services -> frontend productization -> evaluation and operations, with explicit outputs and acceptance criteria at each phase.
