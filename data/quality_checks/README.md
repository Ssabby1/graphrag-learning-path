# Relationship Evidence Quality Check

The chapter-level prerequisite relationships were curated from course materials
and then consolidated deterministically into the 190-node
graph. The integration pipeline maps local IDs, merges duplicate evidence, checks
data integrity, and removes structural cycles; it does not invent prerequisite
relationships.

An additional AI-assisted pedagogical plausibility check of 50 high-connectivity
relationships is available in
[`AI_PLAUSIBILITY_CHECK.md`](AI_PLAUSIBILITY_CHECK.md). It is a supplementary
quality-control artifact and does not replace the original project curation.

The full graph and source material remain local. The public repository ships a
small synthetic bilingual sample so that the complete GraphRAG contract can be
reproduced without redistributing course content.
