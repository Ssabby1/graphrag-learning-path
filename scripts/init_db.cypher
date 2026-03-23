// 约束与索引（示例）
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept)
REQUIRE c.concept_id IS UNIQUE;
