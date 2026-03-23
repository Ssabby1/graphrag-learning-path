# 数据模型说明

## 节点类型
- Course
- Chapter
- Concept

## 关系类型
- (Course)-[:HAS_CHAPTER]->(Chapter)
- (Chapter)-[:HAS_CONCEPT]->(Concept)
- (Concept)-[:PREREQUISITE_OF]->(Concept)

## Concept 建议字段
- concept_id: string（唯一）
- name: string
- description: string
- difficulty: int (1-5)
- resource_url: string（可选）
