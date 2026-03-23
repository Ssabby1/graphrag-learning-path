# GraphRAG Roadmap (Job Version)

Updated: 2026-03-17

## Goal
Implement a clean GraphRAG pipeline:
`ingest -> retrieve -> augment -> generate -> evaluate`

## Phase 1 (Now)
- Introduce `backend/app/graphrag/` module layout
- Add `/graphrag/query` endpoint
- Standard response contract: answer, path, evidence, citations, meta

## Phase 2
- Evidence packing strategy (subgraph -> grounded context)
- Structured generation constraints
- Citation binding to concept_id / relation edges

## Phase 3
- Evaluation harness:
  - path validity
  - evidence coverage
  - redundancy
  - answer-grounding consistency

## Phase 4
- Production polish:
  - cache
  - observability
  - failure fallback tiers
