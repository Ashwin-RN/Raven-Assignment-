"""Pydantic models = the data contract everything else depends on.

Two layers:
  - Pass-1 raw harvest (what a backend returns): verbatim, provider-neutral.
  - Final document (after Pass-2 normalize): canonical keys, confidence, review state.

See PLAN.md SS5.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field as PydField

FieldType = Literal[
    "scalar", "checkbox", "table_cell", "note", "title_block", "free_text"
]
ReviewStatus = Literal["unreviewed", "confirmed", "corrected"]


# --------------------------------------------------------------------------- #
# Pass-1 raw harvest (backend output) - verbatim, provider-neutral
# --------------------------------------------------------------------------- #
class RawField(BaseModel):
    """One label-value pair exactly as it appears on the page."""

    type: FieldType = "scalar"
    label_verbatim: str
    value_raw: str
    unit: Optional[str] = None
    footnote_markers: list[str] = PydField(default_factory=list)  # e.g. ["(4)"]
    case: Optional[str] = None  # operating-condition tag for multi-case tables
    page: int
    snippet: str  # the surrounding verbatim text (our provenance)
    confidence: Optional[float] = None  # backend self-report, if any


class Note(BaseModel):
    marker: str  # e.g. "(4)"
    text: str
    page: int


class Pass1Output(BaseModel):
    """Everything a backend returns for one document."""

    doc_type: Optional[str] = None
    language: list[str] = PydField(default_factory=list)
    fields: list[RawField] = PydField(default_factory=list)
    notes: list[Note] = PydField(default_factory=list)
    usage: dict = PydField(default_factory=dict)  # provider-reported token usage


# --------------------------------------------------------------------------- #
# Final document (after Pass-2 normalize)
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    page: int
    snippet: str
    source_backend: str
    text_layer_match: Optional[bool] = None  # grounding result; None if no text layer


class Field(BaseModel):
    id: str  # deterministic: doc:p{page}:slug:index
    type: FieldType = "scalar"
    canonical_key: Optional[str] = None  # controlled vocab; None if unmapped
    label_verbatim: str
    value_raw: str
    value_normalized: Optional[float] = None
    unit: Optional[str] = None
    unit_si: Optional[str] = None
    value_si: Optional[float] = None  # value_normalized converted to unit_si
    qualifiers: list[str] = PydField(default_factory=list)
    case: Optional[str] = None
    citation: Citation
    confidence: float = 0.5
    mapping_uncertain: bool = False
    review_status: ReviewStatus = "unreviewed"
    original_value_raw: Optional[str] = None  # set on correction
    reviewed_at: Optional[str] = None


class Document(BaseModel):
    doc_id: str
    doc_type: Optional[str] = None
    language: list[str] = PydField(default_factory=list)
    source_pages: int = 0
    fields: list[Field] = PydField(default_factory=list)
    notes: list[Note] = PydField(default_factory=list)
    usage: dict = PydField(default_factory=dict)
