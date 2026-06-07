"""HITL review logic: load working doc, apply confirm/correct edits, persist, and feed
corrections back as reusable canonical-vocab mappings.

The working copy is reviewed/<doc_id>.json once any edit exists, else raw/<doc_id>.json,
so review is resumable and never mutates the raw extraction. A canonical-key correction is
written to vocab_overrides.json - the concrete "feedback improves the pipeline" loop: the
next extraction picks the mapping up via vocab.load_overrides().
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .pipeline import derive_value
from .schema import Document, Field
from .store import (
    list_doc_ids,
    load_raw,
    load_reviewed,
    reviewed_exists,
    save_reviewed,
)
from .vocab import load_overrides

OVERRIDES_PATH = "vocab_overrides.json"


def working_doc(doc_id: str, out_root: str = "outputs") -> Document:
    """Reviewed copy if it exists, else the raw extraction."""
    if reviewed_exists(doc_id, out_root):
        return load_reviewed(doc_id, out_root)
    return load_raw(doc_id, out_root)


def summarize(doc: Document) -> dict:
    return {
        "doc_id": doc.doc_id,
        "doc_type": doc.doc_type,
        "fields": len(doc.fields),
        "reviewed": sum(1 for f in doc.fields if f.review_status != "unreviewed"),
        "low_conf": sum(1 for f in doc.fields if f.confidence < 0.8),
        "mapped": sum(1 for f in doc.fields if f.canonical_key),
    }


def list_summaries(out_root: str = "outputs") -> list[dict]:
    return [summarize(working_doc(d, out_root)) for d in list_doc_ids(out_root)]


def _add_override(label: str, key: str, path: str = OVERRIDES_PATH) -> None:
    overrides = load_overrides(path)
    overrides[label] = key
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(overrides, fh, indent=2, ensure_ascii=False)


def apply_field_edit(
    doc_id: str,
    field_id: str,
    action: str,  # "confirm" | "correct"
    value_raw: str | None = None,
    unit: str | None = None,
    canonical_key: str | None = None,
    out_root: str = "outputs",
) -> Field:
    doc = working_doc(doc_id, out_root)
    field = next((f for f in doc.fields if f.id == field_id), None)
    if field is None:
        raise KeyError(f"field '{field_id}' not in '{doc_id}'")

    now = datetime.now(timezone.utc).isoformat()

    if action == "confirm":
        field.review_status = "confirmed"
        field.reviewed_at = now
    elif action == "correct":
        # None = field omitted -> leave unchanged; "" = explicitly cleared.
        new_value = field.value_raw if value_raw is None else value_raw
        new_unit = field.unit if unit is None else (unit or None)
        new_key = field.canonical_key if canonical_key is None else (canonical_key or None)
        # capture the pre-correction value once
        if field.original_value_raw is None and new_value != field.value_raw:
            field.original_value_raw = field.value_raw
        key_changed = new_key != field.canonical_key

        field.value_raw = new_value
        field.unit = new_unit
        field.value_normalized, field.value_si, field.unit_si = derive_value(new_value, new_unit)
        field.canonical_key = new_key
        field.mapping_uncertain = new_key is None
        field.review_status = "corrected"
        field.reviewed_at = now

        if key_changed and new_key:
            _add_override(field.label_verbatim, new_key)
    else:
        raise ValueError(f"unknown action '{action}'")

    save_reviewed(doc, out_root)
    return field
