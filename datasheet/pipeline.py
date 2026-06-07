"""Orchestration: render -> Pass 1 (backend) -> Pass 2 (normalize) -> Document.

Phase 1 note: Pass 2 here is a deterministic PASSTHROUGH + grounding. It assigns
stable ids, parses numerics, resolves footnote markers from the notes table, and runs
the text-layer grounding check. Real canonical-key mapping + confidence modelling is
Phase 3 (and may use a cheap LLM). Keeping it deterministic now means the pipeline is
fully testable with no key.
"""

from __future__ import annotations

import json
import os
import re

from .backends.base import ExtractionBackend
from .render import PageRender, render_pages
from .schema import Citation, Document, Field, Note, Pass1Output
from .units import to_si
from .vocab import load_overrides, map_label


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return s[:40] or "field"


def _parse_number(value_raw: str):
    """Parse value_raw to float only when the WHOLE token is numeric.

    The Pass-1 contract keeps units in a separate field, so a numeric field's value_raw
    is just the number. Strings like 'SS 304', 'Single Seal Plan 11', or '415/3/50' are
    NOT numbers and must return None - otherwise value_normalized gets a spurious
    304 / 11 / 415 that would corrupt any numeric query or aggregation.
    """
    s = value_raw.strip().replace(",", ".").replace(" ", "")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return float(s)
    return None


def derive_value(value_raw: str, unit: str | None):
    """Shared Pass-2 numeric derivation: (value_normalized, value_si, unit_si).

    Single source of truth used by both extraction (normalize) and HITL corrections
    (review.apply_field_edit), so the two never drift.
    """
    value_normalized = _parse_number(value_raw)
    value_si, unit_si = to_si(value_normalized, unit)
    return value_normalized, value_si, unit_si


def _resolve_qualifiers(markers: list[str], notes: list[Note]) -> list[str]:
    """Map footnote markers like '(4)' to the note text they reference."""
    by_marker = {n.marker: n.text for n in notes}
    out: list[str] = []
    for m in markers:
        text = by_marker.get(m)
        if text:
            out.append(text)
    return out


def _ground(value_raw: str, page_text: str) -> bool | None:
    """text_layer_match: is value_raw present in the page's text layer?

    Returns None when there is no text layer (scanned page) -> grounding unavailable.
    """
    if not page_text.strip():
        return None
    needle = value_raw.strip()
    return needle in page_text or needle.replace(" ", "") in page_text.replace(" ", "")


def calibrate_confidence(
    base: float | None, grounding: bool | None, is_redacted: bool = False
) -> float:
    """Compose value-reading confidence from backend self-report + grounding signal.

    Transparent and explainable (rubric: failure modes). Grounding only adjusts when a
    text layer exists (True -> small boost, False -> penalty); on scans (None) it is
    left untouched. Redacted values keep their (certain) backend confidence.
    """
    c = base if base is not None else 0.6
    if is_redacted:
        return round(c, 3)
    if grounding is True:
        c = min(1.0, c + 0.1)
    elif grounding is False:
        c = max(0.0, c - 0.3)
    return round(c, 3)


def normalize(
    doc_id: str,
    p1: Pass1Output,
    page_texts: dict[int, str],
    source_pages: int,
    source_backend: str,
    overrides: dict[str, str] | None = None,
) -> Document:
    fields: list[Field] = []
    seen: dict[str, int] = {}  # slug -> running index, for deterministic ids
    for rf in p1.fields:
        slug = _slug(rf.label_verbatim)
        idx = seen.get(slug, 0)
        seen[slug] = idx + 1
        fid = f"{doc_id}:p{rf.page}:{slug}:{idx}"

        qualifiers = _resolve_qualifiers(rf.footnote_markers, p1.notes)
        is_redacted = rf.value_raw.strip() == "[REDACTED]"
        if is_redacted:
            qualifiers = [*qualifiers, "redacted"]
        match = _ground(rf.value_raw, page_texts.get(rf.page, ""))

        value_normalized, value_si, unit_si = derive_value(rf.value_raw, rf.unit)
        canonical_key, mapping_uncertain = map_label(rf.label_verbatim, overrides)
        confidence = calibrate_confidence(rf.confidence, match, is_redacted)

        fields.append(
            Field(
                id=fid,
                type=rf.type,
                canonical_key=canonical_key,
                label_verbatim=rf.label_verbatim,
                value_raw=rf.value_raw,
                value_normalized=value_normalized,
                unit=rf.unit,
                unit_si=unit_si,
                value_si=value_si,
                qualifiers=qualifiers,
                case=rf.case,
                citation=Citation(
                    page=rf.page,
                    snippet=rf.snippet,
                    source_backend=source_backend,
                    text_layer_match=match,
                ),
                confidence=confidence,
                mapping_uncertain=mapping_uncertain,
            )
        )
    return Document(
        doc_id=doc_id,
        doc_type=p1.doc_type,
        language=p1.language,
        source_pages=source_pages,
        fields=fields,
        notes=p1.notes,
        usage=p1.usage,
    )


def extract_document(
    doc_id: str,
    pdf_path: str,
    backend: ExtractionBackend,
    artifacts_dir: str,
) -> Document:
    """Full pipeline for one PDF. Persists artifacts at every stage."""
    doc_art = os.path.join(artifacts_dir, doc_id)
    os.makedirs(doc_art, exist_ok=True)

    pages: list[PageRender] = render_pages(pdf_path, doc_art)
    page_texts = {p.page_no: p.text for p in pages}

    p1 = backend.extract(doc_id, pdf_path, pages)
    _dump(os.path.join(doc_art, "pass1.json"), p1)

    doc = normalize(
        doc_id,
        p1,
        page_texts,
        source_pages=len(pages),
        source_backend=backend.name,
        overrides=load_overrides(),
    )
    _dump(os.path.join(doc_art, "final.json"), doc)
    return doc


def _dump(path: str, model) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(model.model_dump(), fh, indent=2, ensure_ascii=False)
