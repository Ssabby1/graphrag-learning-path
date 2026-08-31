from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


CONCEPT_CORPUS_SCHEMA_VERSION = "concept-v1"
EVIDENCE_CORPUS_SCHEMA_VERSION = "evidence-v1"


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = value.split("|")
    elif isinstance(value, Iterable):
        values = value
    else:
        values = [value]
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _line(label: str, value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        rendered = "、".join(_list(value))
    else:
        rendered = str(value or "").strip()
    return f"{label}：{rendered}"


def build_concept_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents = []
    for row in sorted(rows, key=lambda item: str(item.get("concept_id") or "")):
        concept_id = str(row.get("concept_id") or "").strip()
        if not concept_id:
            continue
        aliases = _list(row.get("aliases", row.get("alias")))
        aliases_en = _list(row.get("aliases_en"))
        chapters = _list(row.get("source_chapters"))
        predecessors = _list(row.get("predecessor_names"))
        successors = _list(row.get("successor_names"))
        text = "\n".join(
            [
                _line("知识点", row.get("name")),
                _line("编号", concept_id),
                _line("别名", aliases),
                _line("英文名称", row.get("name_en")),
                _line("英文别名", aliases_en),
                _line("章节", chapters),
                _line("难度", row.get("difficulty")),
                _line("描述", row.get("description")),
                _line("英文描述", row.get("description_en")),
                _line("直接前置知识", predecessors),
                _line("直接后继知识", successors),
            ]
        )
        documents.append(
            {
                "id": concept_id,
                "concept_id": concept_id,
                "text": text,
                "metadata": {
                    "name": str(row.get("name") or ""),
                    "name_en": str(row.get("name_en") or ""),
                    "aliases": aliases,
                    "aliases_en": aliases_en,
                    "source_chapters": chapters,
                    "predecessor_names": predecessors,
                    "successor_names": successors,
                    "schema_version": CONCEPT_CORPUS_SCHEMA_VERSION,
                },
            }
        )
    return documents


def evidence_id(relation_type: str, from_id: str, to_id: str) -> str:
    prefix = "prereq" if relation_type == "PREREQUISITE_OF" else "related"
    return f"{prefix}:{from_id}:{to_id}"


def build_evidence_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents = []
    normalized = sorted(
        rows,
        key=lambda item: (
            str(item.get("relation_type") or ""),
            str(item.get("from_concept_id") or ""),
            str(item.get("to_concept_id") or ""),
        ),
    )
    for row in normalized:
        relation_type = str(row.get("relation_type") or "").strip().upper()
        from_id = str(row.get("from_concept_id") or "").strip()
        to_id = str(row.get("to_concept_id") or "").strip()
        if relation_type not in {"PREREQUISITE_OF", "RELATED_TO"} or not from_id or not to_id:
            continue
        item_id = evidence_id(relation_type, from_id, to_id)
        chapters = _list(row.get("source_chapters"))
        text = "\n".join(
            [
                _line("证据编号", item_id),
                _line("前置知识点", f"{row.get('from_name', '')} ({from_id})"),
                _line("关系", relation_type),
                _line("后置知识点", f"{row.get('to_name', '')} ({to_id})"),
                _line("证据文本", row.get("evidence_text")),
                _line("章节", chapters),
                _line("抽取置信度", row.get("confidence_max")),
            ]
        )
        documents.append(
            {
                "id": item_id,
                "evidence_id": item_id,
                "text": text,
                "metadata": {
                    **row,
                    "source_chapters": chapters,
                    "schema_version": EVIDENCE_CORPUS_SCHEMA_VERSION,
                },
            }
        )
    return documents


def corpus_hash(documents: list[dict[str, Any]]) -> str:
    canonical = [
        {"id": document.get("id"), "text": document.get("text", "")}
        for document in sorted(documents, key=lambda item: str(item.get("id") or ""))
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
