"""Eval harness: partial-correctness metrics against a query-anchored gold set.

Gold entries anchor on a label substring (+ optional case) so matching is independent of
the canonical_key - that lets us score canonical_key correctness separately from coverage.
Per gold field we score five axes: label_found (coverage), value_correct, unit_correct,
citation_valid, key_correct. Denominator is the gold count, so a missed field fails every
axis (end-to-end correctness).

Hallucination is measured separately over ALL fields: on pages with a text layer, the rate
of values that could not be grounded; on scanned pages grounding is unavailable (excluded).

P818 is intentionally absent (no fixture, sealed) - its cold-run number is key-gated.
"""

from __future__ import annotations

import json
import os

from .schema import Document, Field
from .store import list_doc_ids
from .review import working_doc

GOLD_DIR = os.path.join("eval", "gold")


def load_gold(doc_id: str) -> list[dict]:
    path = os.path.join(GOLD_DIR, f"{doc_id}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _val_eq(expected: str, actual) -> bool:
    e = str(expected).strip().lower()
    a = str(actual).strip().lower()
    if e == a:
        return True
    try:
        return abs(float(e.replace(",", ".")) - float(a.replace(",", "."))) < 1e-9
    except ValueError:
        return False


def _unit_eq(expected, actual) -> bool:
    if not expected and not actual:
        return True
    if not expected or not actual:
        return False
    return expected.strip().lower() == actual.strip().lower()


def _match(entry: dict, fields: list[Field]) -> Field | None:
    sub = entry["match"].lower()
    case = entry.get("case")
    for f in fields:
        if sub in f.label_verbatim.lower() and (case is None or f.case == case):
            return f
    return None


AXES = ["label_found", "value_correct", "unit_correct", "citation_valid", "key_correct"]


def score_doc(doc: Document, gold: list[dict]) -> dict:
    counts = {a: 0 for a in AXES}
    details = []
    for entry in gold:
        f = _match(entry, doc.fields)
        row = {"match": entry["match"], "case": entry.get("case")}
        if f is None:
            row["status"] = "MISSED"
            details.append(row)
            continue
        counts["label_found"] += 1
        value_ok = _val_eq(entry["value"], f.value_raw)
        unit_ok = _unit_eq(entry.get("unit"), f.unit)
        cite_ok = f.citation.page == entry["page"] and bool(f.citation.snippet.strip())
        key_ok = f.canonical_key == entry.get("canonical_key")
        counts["value_correct"] += value_ok
        counts["unit_correct"] += unit_ok
        counts["citation_valid"] += cite_ok
        counts["key_correct"] += key_ok
        row.update(
            status="found", value=value_ok, unit=unit_ok, cite=cite_ok, key=key_ok,
            got_key=f.canonical_key,
        )
        details.append(row)
    return {"doc_id": doc.doc_id, "n": len(gold), "counts": counts, "details": details}


def hallucination(doc: Document) -> dict:
    # exclude redaction sentinels: they are intentionally absent from the text layer,
    # so they are not hallucinations and must not inflate the ungrounded rate.
    checkable = [
        f for f in doc.fields
        if f.citation.text_layer_match is not None and f.value_raw.strip() != "[REDACTED]"
    ]
    ungrounded = [f for f in checkable if f.citation.text_layer_match is False]
    return {
        "checkable": len(checkable),
        "ungrounded": len(ungrounded),
        "rate": (len(ungrounded) / len(checkable)) if checkable else None,
    }


def evaluate_all(source: str = "raw", out_root: str = "outputs") -> dict:
    per_doc = []
    agg = {a: 0 for a in AXES}
    total = 0
    for doc_id in list_doc_ids(out_root):
        gold = load_gold(doc_id)
        if not gold:
            continue
        doc = working_doc(doc_id, out_root) if source == "reviewed" else _load(doc_id, out_root)
        res = score_doc(doc, gold)
        res["hallucination"] = hallucination(doc)
        per_doc.append(res)
        total += res["n"]
        for a in AXES:
            agg[a] += res["counts"][a]
    return {"per_doc": per_doc, "total": total, "agg": agg}


def _load(doc_id: str, out_root: str) -> Document:
    from .store import load_raw
    return load_raw(doc_id, out_root)
