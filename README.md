# Job GraphRAG Version

This is `graduate_design_graphrag`, the job-oriented evolution branch.

## Primary Objective
Turn the project into a portfolio-grade GraphRAG system with clear pipeline boundaries and measurable quality.

## Current Foundation
- Knowledge graph in Neo4j
- FastAPI retrieval APIs
- Path planning with deterministic topo-sort
- LLM explanation layer with fallback
- GraphRAG query endpoint with structured contract:
  - `answer`
  - `path`
  - `evidence`
  - `citations`
  - `meta`

## Quick Start
1. Start backend:
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe run.py
```
2. Start frontend:
```powershell
cd frontend
npm install
npm run dev
```
3. Open browser: `http://127.0.0.1:5173`

## 2-Min Interview Demo
1. Open the `GraphRAG Query Demo` panel in the UI.
2. Use:
   - `question`: `How should I learn C003?`
   - `target_concept_id`: `C003`
   - `mastered_concepts`: `C001`
3. Click `Run GraphRAG Query`.
4. Show output sections:
   - `answer`: final grounded response
   - `path`: ordered learning sequence
   - `evidence`: prerequisite concepts
   - `citations`: traceable concept-level references
   - `meta`: runtime signal (`has_cycle`, `model`, `source`)
5. Point to the graph rendering area to show path visualization consistency.

## API Example
```bash
curl -X POST http://127.0.0.1:8000/graphrag/query \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How should I learn C003?\",\"target_concept_id\":\"C003\",\"mastered_concepts\":[\"C001\"]}"
```

## What to Highlight in Interviews
- We separated retrieval/path logic from generation logic (`path_service` vs `explanation_service`).
- The GraphRAG endpoint returns both answer text and machine-friendly evidence/citations.
- The service supports fallback behavior when LLM is unavailable.
- The contract is covered by API tests, so iteration stays safe.

## What to Read First
1. VERSION_SCOPE.md
2. PROJECT_STATUS.md
3. PROJECT_STATUS_CN.md
4. GRAPHRAG_ROADMAP.md
5. Æô¶¯ÎÄµµ.txt

## Note
Any root docs outside the active whitelist should be treated as historical unless revalidated.
