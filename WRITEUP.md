# Datasheet Extraction - Write-up

> Filled in as the build progresses (see `PLAN.md` for the full plan and `DECISIONS.md` for the
> decision trail).

## 1. Overview

Generic, provider-neutral extraction of structured, cited fields from heterogeneous process
datasheets, with a human-in-the-loop review loop.

The guiding judgment call is to optimize for a reliable, explainable 24-hour submission: a stable
schema, inspectable provenance, deterministic artifacts, a review path, and measurable eval/cost
work. Model/provider breadth is useful only after that core is green.

## 2. Phase 1 Status

Phase 1 is finalized.

Verified on `pds-P300228.pdf` with no API key:

| Check | Result |
|---|---|
| Keyless CLI extraction | `python cli.py extract pds-P300228.pdf` writes `outputs/raw/pds-P300228.json` |
| Schema round trip | `load_raw("pds-P300228")` re-validates through the Pydantic `Document` model |
| Field/notes count | 9 fields, 5 notes |
| Grounding | 8 of 9 values match the PDF text layer; `[REDACTED]` correctly does not match |
| Footnote resolution | `P. ABS / BHP RATED` resolves `(4)` to the full vendor caveat |
| Stable ID | BHP field id is `pds-P300228:p1:p_abs_bhp_rated:0` |
| Redaction | `[REDACTED]` carries the `redacted` qualifier |
| Artifacts | `page-1.png`, `page-2.png`, `page-1.txt`, `page-2.txt`, `pass1.json`, `final.json` |

Phase 1 proves pipeline correctness and artifact quality, not model extraction accuracy. Real
accuracy/cost numbers begin once a real Pass 1 adapter runs against the PDFs.

## 3. Architecture

Current Phase 1 architecture:

```text
PDF -> PyMuPDF page images/text -> ExtractionBackend -> Pass1Output
    -> deterministic normalize/grounding -> Document JSON -> raw store/artifacts
```

The key boundary is `ExtractionBackend`: fixture/replay, native-PDF providers, and image-based
providers all return the same `Pass1Output`. This keeps downstream normalization, storage, review,
eval, and cost reporting shared.

## 4. Schema

The schema is a flat field-list model. Each field keeps the literal `label_verbatim`, `value_raw`,
unit, page/snippet provenance, grounding result, confidence, review status, and a deterministic ID.
Canonical keys are intentionally nullable so unknown fields are preserved instead of dropped.

Phase 1 includes the stable data contract. Phase 3 adds canonical-key mapping, real confidence
calibration, and unit normalization.

## 5. Extraction Strategy

Pass 1 is schema-open: harvest generic document primitives such as label-value pairs, title-block
fields, checkboxes, notes, footnotes, and table cells. It must not be a fixed pump-field parser.

In Phase 1, Pass 1 is a fixture so the rest of the system can be verified keylessly. Phase 2 turns
that fixture contract into the real provider-independent prompt and structured JSON contract.

## 6. HITL Feedback Loop

_Phase 4 - field-first review sorted by confidence; corrections -> gold set + canonical-vocab
mappings / Pass-2 exemplars; measurable before/after delta._

## 7. Evaluation

_Phase 5 - query-anchored gold set on P300228/P600173/P718; partial-correctness metrics; P818 cold
run._

## 8. Cost

_Phase 5 - provider-reported usage per doc; per-provider pricing table; caching / model-tier
levers._

## 9. Failure Modes

Known risks to track through eval and review:

- Hallucinated values or snippets
- Dropped fields and low recall
- Checkbox misreads
- Footnote misattribution
- Gauge vs absolute pressure confusion
- Redacted-field hallucination
- Digit/unit misreads
- Multi-case table misalignment

## 10. Future Work

- Local OCR/VLM backend
- SI unit conversion
- Canonical-vocab routing by `doc_type`
- Bounding-box citations
- Split extraction and normalization confidence
