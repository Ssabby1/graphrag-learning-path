# Neo4j Graph Validation Report

- Generated at: `2026-03-13 13:32:27`
- URI: `bolt://127.0.0.1:7687`
- Database: `neo4j`
- Sample size: `20`
- Max cycle depth: `12`
- Overall result: `PASS`

## Summary Metrics

- Concept nodes: `190`
- Total nodes: `204`
- Total relations: `1179`
- PREREQUISITE_OF relations: `409`
- Missing concept_id: `0`
- Duplicate concept_id groups: `0`
- Duplicate PREREQUISITE_OF pairs: `0`
- PREREQUISITE_OF self loops: `0`
- Concepts without HAS_CONCEPT parent: `0`
- Fully isolated concepts: `0`
- Cycle path matches (<= depth 12): `0`

## Hard-Fail Checks

- `has_expected_schema`: `PASS`
- `cycle_example_count`: `PASS`
- `duplicate_prerequisite_pair_count`: `PASS`
- `self_loop_count`: `PASS`
- `concept_missing_id_count`: `PASS`
- `duplicate_concept_id_count`: `PASS`

## Relation Type Distribution

| relation_type | count |
| --- | ---: |
| PREREQUISITE_OF | 409 |
| HAS_CONCEPT | 341 |
| RELATED_TO | 299 |
| CONTAINS | 119 |
| HAS_CHAPTER | 9 |
| PREREQUISITE | 2 |

## Duplicate PREREQUISITE_OF Examples

- none

## Cycle Examples

- none

## Sampled Target Prerequisite Counts

| target_concept_id | target_name | prerequisite_count |
| --- | --- | ---: |
| G000140 | D到其他 | 24 |
| G000133 | 电平触发T触发器 | 17 |
| G000174 | 险象的判断 | 16 |
| G000076 | 最大项定义 | 10 |
| G000084 | 带无关项的逻辑函数化简 | 10 |
| G000087 | 逻辑或运算 | 9 |
| G000063 | 逻辑函数的表示方法 | 8 |
| G000069 | 逻辑(函数)表达式 | 8 |
| G000079 | 卡诺图构成 | 8 |
| G000167 | 二-十进制优先编码器74LS147 | 7 |
| G000042 | 二-十进制编码器 | 6 |
| G000012 | 逻辑代数的基本概念 | 5 |
| G000046 | 编码器 | 4 |
| G000048 | 同步时序逻辑电路的分析 | 4 |
| G000181 | 异步时序电路特点 | 1 |
| G000007 | 八进制 | 0 |
| G000038 | 格雷码 | 0 |
| G000126 | 卡诺图表示逻辑函数 | 0 |
| G000182 | 时序逻辑电路特点 | 0 |
| G000188 | 模拟电路基础 | 0 |

> Manual check suggestion: randomly pick 20 PREREQUISITE_OF rows and verify against source material.
