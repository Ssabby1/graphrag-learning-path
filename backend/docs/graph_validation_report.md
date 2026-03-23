# Neo4j Graph Validation Report

- Generated at: `2026-03-13 13:31:09`
- URI: `bolt://127.0.0.1:7687`
- Database: `neo4j`
- Sample size: `20`
- Max cycle depth: `12`
- Overall result: `FAIL`

## Schema Check

- Expected `Concept` label and `PREREQUISITE_OF` relationship type were not both found.
- Found labels: `['Course', 'KnowledgePoint']`
- Found relationship types: `['BELONGS_TO', 'PREREQUISITE']`
- Conclusion: graph data may not be imported into this database yet.

## Summary Metrics

- Concept nodes: `0`
- Total nodes: `6`
- Total relations: `6`
- PREREQUISITE_OF relations: `0`
- Missing concept_id: `0`
- Duplicate concept_id groups: `0`
- Duplicate PREREQUISITE_OF pairs: `0`
- PREREQUISITE_OF self loops: `0`
- Concepts without HAS_CONCEPT parent: `0`
- Fully isolated concepts: `0`
- Cycle path matches (<= depth 12): `0`

## Hard-Fail Checks

- `has_expected_schema`: `FAIL`
- `cycle_example_count`: `PASS`
- `duplicate_prerequisite_pair_count`: `PASS`
- `self_loop_count`: `PASS`
- `concept_missing_id_count`: `PASS`
- `duplicate_concept_id_count`: `PASS`

## Relation Type Distribution

| relation_type | count |
| --- | ---: |
| BELONGS_TO | 4 |
| PREREQUISITE | 2 |

## Duplicate PREREQUISITE_OF Examples

- none

## Cycle Examples

- none

## Sampled Target Prerequisite Counts

| target_concept_id | target_name | prerequisite_count |
| --- | --- | ---: |

> Manual check suggestion: randomly pick 20 PREREQUISITE_OF rows and verify against source material.
