# Datasheet Extraction

Generic, provider-neutral extraction of structured, **cited** fields from heterogeneous process
datasheets (PDF) into a queryable schema, with a human-in-the-loop (HITL) review loop.

Built for the Raven backend assignment. See [`PLAN.md`](PLAN.md) for the full plan,
[`DECISIONS.md`](DECISIONS.md) for the decision trail, and [`WRITEUP.md`](WRITEUP.md) for the
architecture/eval/cost write-up. The original assignment brief is at the bottom of this file.

## Key ideas

- **Vision-first, single generic extractor** - forced by the inputs: one datasheet is a flattened
  scan with no text layer, and the four docs span unrelated templates, two languages, and metric
  vs imperial units. So there are **no per-template parsers**.
- **Schema-open harvest** - Pass 1 extracts whatever labelled fields exist (key-value pairs,
  checkboxes, footnotes, multi-case tables, title block), never a fixed pump-field list, so it
  generalizes to unseen layouts.
- **Provider-neutral, key-independent** - the model sits behind an `ExtractionBackend` interface.
  The whole system runs **with no API key** via a fixture/replay backend; a real adapter
  (Claude / Gemini / Kimi) drops in when a key is available.
- **Provenance on every field** - model-emitted page + verbatim snippet, verified against the PDF
  text layer where one exists (grounding).
- **Feedback loop** - corrections persist and a corrected canonical-key mapping is fed back as a
  vocab override, so the next extraction improves.

## Pipeline

```
PDF -> PyMuPDF page images + text -> ExtractionBackend (Pass 1, verbatim harvest)
    -> Pass 2 normalize (canonical key, SI units, confidence, grounding)
    -> JSON store -> review UI / eval / cost
```

## Setup

Requires Python 3.12. A virtualenv with all dependencies is included; or install fresh:

```bash
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

No API key is needed to run everything below - the default backend replays fixtures.
To wire a real provider later, copy `.env.example` to `.env` and add one key.

## Usage

```bash
# Extract one or more PDFs -> outputs/raw/<doc_id>.json (+ artifacts under outputs/artifacts/)
python cli.py extract pds-P300228.pdf pds-P600173.pdf pds-P718.pdf

# Launch the HITL review UI (field-first, confidence-sorted, citation + page image inline)
python cli.py review            # http://127.0.0.1:8000

# Evaluate against the gold set (partial-correctness metrics + hallucination)
python cli.py eval

# Cost per document (provider-reported token usage; price table)
python cli.py cost

# Demonstrate a measurable eval gain from one HITL correction (keyless)
python cli.py feedback-demo
```

Example `extract` output:

```
[extract] pds-P300228 via fixture backend ...
  9 fields, 5 notes, 8 grounded, 9 canonical-mapped -> outputs/raw/pds-P300228.json
```

## Outputs

```
outputs/raw/<doc_id>.json        extraction result (committed as samples)
outputs/reviewed/<doc_id>.json   after human review
outputs/artifacts/<doc_id>/      page images, text, pass-1 / final (gitignored)
```

## Schema (per field)

Flat field-list (EAV) model: `id`, `type`, `canonical_key` (controlled vocab, nullable so unknown
fields are preserved), `label_verbatim`, `value_raw`, `value_normalized`, `unit`, `unit_si`,
`value_si`, `qualifiers` (footnote-resolved), `case` (multi-case tables), `citation`
(page + snippet + grounding), `confidence`, `review_status`. See [`PLAN.md`](PLAN.md) sec 5.

## Status

All five build phases are complete and run **keyless** on fixtures. Real model accuracy, the P818
cold-run (a sealed holdout, never used for tuning), and real per-doc cost are wired but pending an
API key.

## Repo layout

```
datasheet/          core library (schema, render, backends, pipeline, vocab, units, review, eval, cost, web)
cli.py              extract | review | eval | cost | feedback-demo
fixtures/           hand-authored Pass-1 fixtures (keyless dev) - P818 intentionally absent
eval/gold/          query-anchored gold labels (P300228/P600173/P718)
outputs/            extraction + review outputs
PLAN.md DECISIONS.md WRITEUP.md
```

---

## Assignment brief (original)

A large part of working at Raven is to extract knowledge and insights from a factory plant's
documentation. Extract structured fields from a process datasheet; these can power search, technical
bid evaluation, and more.

**What to build:** (1) an extraction pipeline that ingests a datasheet PDF and produces structured
fields with citations; (2) a HITL feedback loop - a web interface to review/correct extractions and
explain how feedback improves the pipeline.

**Output schema:** define your own, but it must be generic enough for a wide variety of fields and
use cases, balancing flexibility with queryability and provenance.

**Logistics:** 24h; any tools/stack; submit as a private fork shared with the evaluator, with a
recorded demo and a write-up (architecture, trade-offs, evaluation and cost metrics, future
improvements).

**Evaluation:** extraction quality (accuracy, coverage); reliability and cost (cost per doc, failure
modes); human-in-the-loop (how feedback is used, ergonomics); communication. Not looking for: auth,
deployment, fancy UI.
