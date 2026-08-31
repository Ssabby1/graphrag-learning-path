# Offline evaluation

This directory freezes the pre-refactor baseline before the roadmap replaces graph traversal, retrieval, evidence, and answer generation.

## Dataset contracts

All datasets use JSON Lines (`.jsonl`): one independent UTF-8 JSON object per line.

- `target_resolver.jsonl`: multilingual target resolution, ambiguity, and rejection cases. `acceptable_target_ids` contains every accepted answer; `should_reject` makes negative cases explicit.
- `path_planner.jsonl`: target/mastered inputs plus independently reviewable required and forbidden concepts. `review_status` distinguishes structural fixtures from human teaching review.
- `evidence_retriever.jsonl`: a fixed path and relationship-level relevance labels. Evidence IDs use `prereq:{from_id}:{to_id}`.
- `answer_generator.jsonl`: fixed path and Evidence Pack input so generator behavior is measured without upstream retrieval errors.

The initial files are deliberately small, versioned contracts—not claims of statistical significance. Human teaching review remains pending unless a case explicitly says `human_verified`.

## Reproduce the frozen baseline

From the repository root:

```bash
PYTHONHASHSEED=0 python -m evals.runner
```

The runner prefers ignored full local CSVs when present and otherwise falls back to `data/seed/`. It never calls an LLM, downloads a model, or requires Neo4j. It writes JSON and Markdown reports plus representative service-level API samples under `evals/reports/`, and records the dataset profile and hashes.

The stage-0 report is expected to expose current limitations. In particular, relationship evidence and structured answers are reported as unsupported rather than inferred or fabricated.

## Reproduce the stage-2 retrieval report on macOS

Use a fresh Python 3.13 virtual environment; do not reuse the old Windows environment:

```bash
/opt/homebrew/bin/python3.13 -m venv backend/.venv-macos-embeddings
backend/.venv-macos-embeddings/bin/python -m pip install -r backend/requirements-embeddings.txt
HF_HOME="$PWD/backend/.cache/huggingface" PYTHONPATH="$PWD" \
  backend/.venv-macos-embeddings/bin/python evals/stage2_runner.py --allow-download
```

The first run downloads the configured multilingual model and builds separate concept and relationship caches. Later runs can omit `--allow-download` and must report cache hits. Both model and embedding caches live below the ignored `backend/.cache/` directory. The runner records model ID, dimensions, corpus hashes, threshold provenance, per-language metrics, failures, and P50/P95 latency.
