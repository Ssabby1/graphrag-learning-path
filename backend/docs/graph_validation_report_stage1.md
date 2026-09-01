# Graph Validation Report

- Generated at: `2026-08-30 20:30:00`
- Concepts CSV: `章节数据/数据汇总/outputs/fixed/concepts_all.csv`
- Relations CSV: `章节数据/数据汇总/outputs/fixed/relations_all.csv`
- Sample size: `20`
- Cycle validation: `full graph (unbounded)`
- Depth reporting threshold: `8`
- Overall result: `PASS`

## Summary Metrics

- Concept nodes: `190`
- Total nodes: `190`
- Total relations: `827`
- PREREQUISITE_OF relations: `409`
- Missing concept_id: `0`
- Duplicate concept_id groups: `0`
- Duplicate PREREQUISITE_OF pairs: `0`
- PREREQUISITE_OF self loops: `0`
- Concepts without HAS_CONCEPT parent: `not_available_in_csv_profile`
- Fully isolated concepts: `not_available_in_csv_profile`
- Full DAG check: `PASS`
- Cycle examples found: `0`
- Longest prerequisite path (edges): `16`
- Targets deeper than 8: `48`
- Dataset hash (SHA-256): `b679cc2133f4531fc023e65fd7ae1ecf76ce67aa8fdfd227a79ac9b98501b264`
- Independent oracle closure matches: `190` / `190`
- Structural Closure Recall: `1514` / `1514` = `100.0%`
- Relationship evidence_text present: `409` / `409`
- Relationship source_images present: `409` / `409`
- Relationship confidence_max present: `409` / `409`
- Relationship provenance: `project_curated_input`

## Ancestor Closure Statistics

- target_count: `190`
- total_ancestor_references: `1514`
- min_ancestors: `0`
- max_ancestors: `51`
- average_ancestors: `7.968`

## Prerequisite Depth Distribution

| depth_edges | target_count |
| ---: | ---: |
| 0 | 35 |
| 1 | 11 |
| 2 | 8 |
| 3 | 16 |
| 4 | 20 |
| 5 | 9 |
| 6 | 3 |
| 7 | 12 |
| 8 | 28 |
| 9 | 13 |
| 10 | 6 |
| 11 | 3 |
| 12 | 13 |
| 13 | 4 |
| 14 | 5 |
| 15 | 3 |
| 16 | 1 |

## Hard-Fail Checks

- `has_expected_schema`: `PASS`
- `full_dag_check`: `PASS`
- `duplicate_prerequisite_pair_count`: `PASS`
- `self_loop_count`: `PASS`
- `concept_missing_id_count`: `PASS`
- `duplicate_concept_id_count`: `PASS`

## Relation Type Distribution

| relation_type | count |
| --- | ---: |
| PREREQUISITE_OF | 409 |
| RELATED_TO | 299 |
| CONTAINS | 119 |

## Duplicate PREREQUISITE_OF Examples

- none

## Cycle Examples

- none

## Deterministic Target Prerequisite Sample

| target_concept_id | target_name | prerequisite_count | max_depth |
| --- | --- | ---: | ---: |
| G000001 | 数字逻辑基础 | 0 | 0 |
| G000002 | 逻辑门电路 | 2 | 2 |
| G000003 | 异步时序电路 | 41 | 16 |
| G000004 | 逻辑代数基础 | 1 | 1 |
| G000005 | 数字逻辑系统 | 2 | 2 |
| G000006 | 逻辑变量 | 6 | 5 |
| G000007 | 八进制 | 0 | 0 |
| G000008 | 十六进制 | 0 | 0 |
| G000009 | 二进制 | 1 | 1 |
| G000010 | 计数体制 | 3 | 3 |
| G000011 | 十进制 | 0 | 0 |
| G000012 | 逻辑代数的基本概念 | 5 | 4 |
| G000013 | 计算机系统 | 3 | 3 |
| G000014 | 加法器 | 4 | 4 |
| G000015 | 寄存器 | 17 | 12 |
| G000016 | 计数器 | 17 | 12 |
| G000017 | 分立元件逻辑门电路 | 13 | 9 |
| G000018 | 数字逻辑及数字电路 | 4 | 4 |
| G000019 | 数制与码制 | 0 | 0 |
| G000020 | 数制之间的转换 | 0 | 0 |

> Chapter-level prerequisite relationships were curated from course materials; structural validation and AI-assisted plausibility checks are reported separately.
