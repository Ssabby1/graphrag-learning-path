# Relationship Evidence Review

The full 190-node graph is private, so its review ledger is generated under the ignored `output/` directory and is not published with source excerpts.

Generate a deterministic queue of 50 high-connectivity prerequisite relationships:

```bash
python scripts/build_relationship_review_queue.py \
  --concepts-csv "章节数据/数据汇总/outputs/fixed/concepts_all.csv" \
  --relations-csv "章节数据/数据汇总/outputs/fixed/relations_all.csv" \
  --output output/relationship_review_queue.csv \
  --limit 50
```

For every row, compare the direction and claim against the listed source image, then set `review_status` to one of:

- `human_verified`: the source supports the prerequisite direction and wording;
- `rejected`: the relationship should not be used;
- `needs_revision`: the relation may be valid but its direction or evidence text needs correction;
- `pending`: no human decision has been recorded.

Fill `reviewer`, ISO-8601 `reviewed_at`, and `review_notes`. Re-running the command preserves those decision fields by stable `evidence_id`. Machine-generated queues and AI suggestions do not count as human verification.
