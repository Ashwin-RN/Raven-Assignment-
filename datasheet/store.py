"""JSON persistence. No SQLite - JSON files are enough for 4 docs and easy to diff/demo.

Layout:
  outputs/raw/<doc_id>.json        extraction output
  outputs/reviewed/<doc_id>.json   after human review (Phase 4)
  outputs/artifacts/<doc_id>/...   per-stage artifacts (images, text, pass1, final)
"""

from __future__ import annotations

import json
import os

from .schema import Document


def save_raw(doc: Document, out_root: str = "outputs") -> str:
    path = os.path.join(out_root, "raw", f"{doc.doc_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc.model_dump(), fh, indent=2, ensure_ascii=False)
    return path


def load_raw(doc_id: str, out_root: str = "outputs") -> Document:
    path = os.path.join(out_root, "raw", f"{doc_id}.json")
    with open(path, encoding="utf-8") as fh:
        return Document.model_validate(json.load(fh))


def _reviewed_path(doc_id: str, out_root: str) -> str:
    return os.path.join(out_root, "reviewed", f"{doc_id}.json")


def reviewed_exists(doc_id: str, out_root: str = "outputs") -> bool:
    return os.path.exists(_reviewed_path(doc_id, out_root))


def save_reviewed(doc: Document, out_root: str = "outputs") -> str:
    path = _reviewed_path(doc.doc_id, out_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc.model_dump(), fh, indent=2, ensure_ascii=False)
    return path


def load_reviewed(doc_id: str, out_root: str = "outputs") -> Document:
    with open(_reviewed_path(doc_id, out_root), encoding="utf-8") as fh:
        return Document.model_validate(json.load(fh))


def list_doc_ids(out_root: str = "outputs") -> list[str]:
    raw_dir = os.path.join(out_root, "raw")
    if not os.path.isdir(raw_dir):
        return []
    return sorted(f[:-5] for f in os.listdir(raw_dir) if f.endswith(".json"))
