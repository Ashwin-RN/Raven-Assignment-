# Decision Log

This file captures the decision trail behind the implementation. It is written for the
founder/evaluator conversation: each choice ties back to an observed constraint, a trade-off,
and a concrete artifact.

## Phase 1 - Foundation

### Decision: Build a provider-neutral extraction contract first

Constraint:
The final provider key is not guaranteed yet, and the assignment allows any stack. The system
still needs to be buildable, testable, and demoable before a model adapter is available.

Choice:
Define `Pass1Output` as the backend contract and make every backend return the same raw,
verbatim harvest shape.

Trade-off:
This adds a small interface layer up front, but it keeps Pass 2, storage, review, eval, and cost
logic independent of Claude, Gemini, Kimi, or OpenAI.

Evidence:
`datasheet/backends/base.py`, `datasheet/backends/fixture.py`, and `datasheet/schema.py`.

### Decision: Use a fixture/replay backend in Phase 1

Constraint:
No API key is required to prove pipeline plumbing, schema validation, artifact persistence, or UI
integration points.

Choice:
Hand-author a Pass 1 fixture for `pds-P300228` and replay it through the same pipeline a real
backend will use.

Trade-off:
Fixtures do not prove extraction accuracy. They prove deterministic end-to-end behavior and give
downstream phases a stable contract.

Evidence:
`fixtures/pds-P300228.pass1.json` extracts to schema-valid `outputs/raw/pds-P300228.json`.

### Decision: Keep Phase 1 normalization deterministic

Constraint:
Phase 1 should verify the pipeline without depending on model behavior.

Choice:
Implement deterministic ID assignment, numeric parsing, footnote resolution, redaction handling,
and grounding. Defer canonical-key mapping, real confidence calibration, and SI conversion.

Trade-off:
The output is not semantically complete yet, but it is stable and auditable. The deferred work is
now isolated behind the Phase 2/3 contract.

Evidence:
`datasheet/pipeline.py` assigns `pds-P300228:p1:p_abs_bhp_rated:0`, resolves note `(4)`, sets
`case=design`, and keeps redacted fields as `[REDACTED]`.

### Decision: Use JSON files instead of a database

Constraint:
The assignment has four PDFs and values inspectability over production infrastructure.

Choice:
Persist raw and reviewed documents as JSON, with intermediate artifacts under
`outputs/artifacts/<doc_id>/`.

Trade-off:
JSON is not a multi-user production store, but it is easy to diff, inspect, demo, and validate.

Evidence:
`datasheet/store.py`, `outputs/raw/pds-P300228.json`, and
`outputs/artifacts/pds-P300228/final.json`.

### Decision: Build provenance ourselves

Constraint:
Provider-native citations are not portable across model vendors and may conflict with structured
outputs or image inputs.

Choice:
Require every Pass 1 field to include `page` and `snippet`, then verify values against the PDF
text layer where available.

Trade-off:
This does not provide pixel-accurate bounding boxes in Phase 1. It does provide backend-agnostic,
inspectable provenance that works across native-PDF and image-based adapters.

Evidence:
`Citation` includes `page`, `snippet`, `source_backend`, and `text_layer_match`; Phase 1 grounds
8 of 9 values from `pds-P300228`, with `[REDACTED]` correctly ungrounded.

### Decision: Use PyMuPDF rendering and text extraction as artifacts, not the primary extractor

Constraint:
At least one provided PDF has no reliable text layer, so text-only extraction would fail.

Choice:
Render every page to PNG and persist the text layer for grounding/debugging only.

Trade-off:
Rendering adds artifact volume, but it gives vision backends a common input path and makes
failures inspectable.

Evidence:
`outputs/artifacts/pds-P300228/page-1.png`, `page-2.png`, `page-1.txt`, and `page-2.txt`.

## Phase 2 - Generic Pass 1 Contract

### Decision: Keep Pass 1 schema-open instead of template-specific

Constraint:
The assignment evaluates generalization across heterogeneous datasheets, and the inputs already
include materially different layouts: bilingual metric forms, a scanned form, and an imperial
multi-case form.

Choice:
Use one generic Pass 1 contract for document primitives: label-value pairs, title-block fields,
checkboxes, notes, footnotes, and table cells. Do not branch on `doc_id`, `doc_type`, language, or
template.

Trade-off:
The model must do more layout reasoning, and Pass 2 must normalize a wider range of labels. In
exchange, the implementation avoids brittle custom parsers and can preserve fields from unseen
layouts.

Evidence:
`pds-P300228`, `pds-P600173`, and `pds-P718` all extract through the same render -> backend ->
normalize -> store code path. The Phase 2 audit found no document/template conditional logic in
`datasheet/` or `cli.py`.

### Decision: Export the Pass 1 contract as JSON Schema

Constraint:
The real provider is still configurable, but every provider adapter needs the same structured
output target.

Choice:
Expose the Pydantic `Pass1Output` contract as JSON Schema via `pass1_json_schema()`, including
shared definitions for `RawField` and `Note`.

Trade-off:
Provider-specific JSON-mode syntax still belongs in each adapter, but the semantic contract is
owned by the application rather than scattered through prompts.

Evidence:
Phase 2 verified that `pass1_json_schema()` generates a clean provider-ready JSON Schema.

### Decision: Treat scanned-page grounding as unavailable, not failed

Constraint:
`pds-P600173` has no useful text layer, so a deterministic text-layer match cannot validate values
from that document.

Choice:
Set `citation.text_layer_match = None` when page text is empty. Reserve `False` for pages that have
a text layer but do not contain the claimed value.

Trade-off:
The system cannot prove grounding deterministically on scans in Phase 2. It avoids the worse
failure mode of reporting false negatives or false positives as evidence.

Evidence:
`pds-P600173` extracts 11 fields with grounding unavailable (`None`) rather than pretending the
scan was text-grounded.

### Decision: Use `case` for repeated operating conditions

Constraint:
Some datasheets repeat the same engineering field under different operating conditions, especially
multi-case tables.

Choice:
Represent the operating condition as field-level `case` metadata instead of creating
template-specific table schemas.

Trade-off:
Downstream queries must filter by `case` when the same canonical key appears multiple times. The
schema remains generic and can represent new cases without code changes.

Evidence:
`pds-P718` extracts 15 fields with cases including `normal`, `minimum`, `design`, and
`off-spec_to_pgo`, including off-spec table cells, without custom parser logic.

### Decision: Preserve P818 as a cold holdout

Constraint:
The final evaluation needs evidence that the system was not tuned to every provided layout.

Choice:
Do not create a fixture for `pds-P818` during Phases 1-2. Let fixture extraction fail loudly if
someone tries to use it before the cold run.

Trade-off:
The fixture-backed development set is smaller, but the final holdout story remains credible.

Evidence:
Phase 2 audit confirmed `pds-P818` fails with the informative "No fixture for 'pds-P818'" error.

## Phase 3 - Deterministic Pass 2

### Decision: Keep Pass 2 deterministic and keyless

Constraint:
The pipeline needs queryable fields before a real provider key is available, and the normalized
output must be reproducible for eval and HITL development.

Choice:
Implement canonical-key mapping, SI-ish unit conversion, and confidence calibration as deterministic
Python logic in Pass 2.

Trade-off:
The first vocabulary is limited to known pump-datasheet terms from the dev set. It is transparent,
testable, and can later be augmented by HITL overrides or a cheap model behind the same interface.

Evidence:
Phase 3 maps 9/9 fields for `pds-P300228`, 11/11 for `pds-P600173`, and 15/15 for `pds-P718`
without API calls.

### Decision: Use controlled vocabulary with graceful fallback

Constraint:
Users need queryable fields, but unseen datasheets may contain labels not yet represented in the
canonical vocabulary.

Choice:
Map known labels to `canonical_key` by generic label aliases. If no alias matches, keep the field,
set `canonical_key = null`, and mark `mapping_uncertain = true`.

Trade-off:
100% canonical coverage on the dev fixtures is expected because the vocabulary was built from those
documents. Real coverage is measured on `pds-P818` and future unseen documents.

Evidence:
The dev set has 35/35 mapped fields and zero unmapped fields. The code path has no `doc_id`,
`doc_type`, language, or template branching.

### Decision: Preserve gauge/absolute pressure semantics during unit normalization

Constraint:
Gauge and absolute pressures are semantically different in engineering datasheets and should not be
merged silently.

Choice:
Convert pressure values to bar while preserving suffixes such as `bar g` and `bar a`.

Trade-off:
This is a best-effort SI-ish normalization, not a full dimensional-analysis library. It covers the
unit families present in the assignment while preserving the original unit separately.

Evidence:
`3.98 kg/cm2 g` converts to `3.903 bar g`, and `174.5 psig` converts to `12.0314 bar g`.

### Decision: Calibrate confidence from observable evidence

Constraint:
The system should expose uncertainty without pretending scans can be deterministically grounded.

Choice:
Start with backend-reported confidence, boost values that match a text layer, penalize values that
fail on a text-layer page, leave scanned pages unchanged, and keep redacted sentinels certain.

Trade-off:
This is a simple, explainable calibration rather than a statistically trained confidence model.
That is appropriate for the 24-hour scope and is easy to explain in review.

Evidence:
Grounded `pds-P718` values receive a small boost up to `1.0`; `pds-P600173` scan values keep their
fixture confidence with `text_layer_match = None`; `[REDACTED]` remains `1.0` even though it
correctly fails text grounding.

### Decision: Keep non-numeric values queryable but unconverted

Constraint:
Many useful datasheet fields are textual: fluid, service, material, redaction, and notes.

Choice:
Keep textual values in `value_raw` with canonical keys where possible, but leave `value_si` and
`unit_si` as `null` when there is no numeric conversion.

Trade-off:
The system does not fabricate numeric values for text fields. Queries can still use
`canonical_key`, `label_verbatim`, and `value_raw`.

Evidence:
Values such as `water + traces of VCM`, `RECYCLED WATER`, `CS / CS`, and `[REDACTED]` remain
preserved with no SI conversion.

## Phase 4 - Human-in-the-Loop Review

### Decision: Make the review UI field-first

Constraint:
Reviewer time should go to the fields most likely to need attention, not to browsing whole
documents in source order.

Choice:
List fields sorted by ascending confidence by default, with filters for review status, page, and
canonical key.

Trade-off:
This is less document-like than a page-first viewer, but it makes the workflow faster for
correction and aligns with the confidence signal produced by Pass 2.

Evidence:
`GET /doc/{doc_id}` returns a confidence-sorted field view, and Phase 4 audit verified filters for
status, page, and canonical key.

### Decision: Put citation context beside every editable field

Constraint:
The reviewer should not need to hunt through the original PDF to validate a value.

Choice:
Show the page number, snippet, grounding badge, and rendered page image inline for each field.

Trade-off:
The table is denser than a minimal form, but it makes review decisions auditable and fast. Pixel
bounding boxes remain future work.

Evidence:
`GET /doc/pds-P718` renders field rows with citation snippets, grounding indicators, and page image
links under `/artifacts/.../page-N.png`.

### Decision: Persist reviewed output separately from raw extraction

Constraint:
Human review must be resumable without destroying the original extraction artifact used for eval,
debugging, and audit.

Choice:
Load `outputs/reviewed/<doc_id>.json` when it exists, otherwise load `outputs/raw/<doc_id>.json`.
Save confirmations and corrections only to `reviewed/`.

Trade-off:
The working-document logic has to decide between raw and reviewed copies, but raw extraction remains
immutable after review.

Evidence:
Phase 4 audit confirmed a correction writes `reviewed/<doc_id>.json` and leaves
`raw/<doc_id>.json` unchanged.

### Decision: Use a small JSON API for review edits

Constraint:
The assignment does not need a complex frontend or multipart form handling, and the environment
should stay lightweight.

Choice:
Use FastAPI endpoints that accept JSON bodies for `confirm` and `correct` actions.

Trade-off:
This keeps the UI simple and avoids adding `python-multipart`. It is enough for the demo and easy
to test with Starlette's `TestClient`.

Evidence:
`POST /api/doc/{doc_id}/field/{field_id}` sets `confirmed` or `corrected`, updates corrected values,
and returns the updated field JSON.

### Decision: Turn corrections into reusable vocabulary overrides

Constraint:
The HITL requirement is stronger than an edit form; feedback should improve future extraction or
normalization behavior.

Choice:
When a human changes a field's `canonical_key`, persist a label-to-key mapping in
`vocab_overrides.json`. Pass 2 loads overrides before the base vocabulary on the next extraction.

Trade-off:
This is a deterministic label-level feedback loop, not model fine-tuning. It is appropriate for the
24-hour scope and gives a measurable before/after delta.

Evidence:
Phase 4 audit corrected one canonical key, verified the override was written, then re-extracted the
document and confirmed the new mapping was applied automatically.

### Decision: Verify the UI with TestClient instead of manual-only testing

Constraint:
The review UI needs to be demoable, but the core behavior should also be provable in a repeatable
keyless audit.

Choice:
Use FastAPI/Starlette `TestClient` to exercise `GET /`, `GET /doc/{id}`, filters, `POST correct`,
and `POST confirm` without starting a server.

Trade-off:
This does not replace a visual demo, but it verifies the server-side contract and persistence logic
deterministically.

Evidence:
Phase 4 audit verified the routes, raw-vs-reviewed persistence, feedback override, and cleanup with
no test pollution left in the workspace.

## Phase 5 - Evaluation and Cost

### Decision: Use a small query-anchored gold set

Constraint:
The assignment asks for extraction quality and coverage, but exhaustive labeling of dense
datasheets would consume the 24-hour budget and distract from system design.

Choice:
Label a targeted gold set for the development documents, focused on fields that support the
README's example queries and the main engineering use cases: fluid, flows, pressures, materials,
power, temperature, and related operating conditions.

Trade-off:
The eval is not a complete field-by-field benchmark. It is a focused acceptance test for the most
important query paths and a useful way to compare future real-provider runs.

Evidence:
Gold labels live under `eval/gold/` for `pds-P300228`, `pds-P600173`, and `pds-P718`, totaling 34
scored fields.

### Decision: Score partial correctness, not just pass/fail

Constraint:
A field can be partially useful: the label may be found while the unit, citation, or canonical key
is wrong. A single binary score would hide the failure mode.

Choice:
Score five axes per gold field: `label_found`, `value_correct`, `unit_correct`, `citation_valid`,
and `key_correct`.

Trade-off:
The metrics table is slightly wider, but it gives a clearer explanation of what is reliable and
what still needs improvement.

Evidence:
Fixture-backed eval reports 34/34 label coverage, 34/34 value correctness, 34/34 unit correctness,
34/34 citation validity, and 33/34 canonical-key correctness.

### Decision: Separate fixture-plumbing quality from real model-reading quality

Constraint:
Fixtures are hand-authored Pass 1 outputs. They are useful for verifying the pipeline, but they
cannot honestly measure whether a real model can read the PDFs.

Choice:
Report fixture eval as validation of schema, normalization, canonical mapping, grounding, review,
and eval plumbing. Keep real model accuracy and the P818 cold run explicitly key-gated.

Trade-off:
The current metrics are less impressive than pretending they are model accuracy, but the framing is
honest and defensible in an evaluator conversation.

Evidence:
CLI eval prints the fixture-backed metrics and separately states that `pds-P818` is a sealed cold
run pending a real backend and API key.

### Decision: Measure hallucination only where grounding is available

Constraint:
Text-layer grounding is deterministic on text-backed pages, unavailable on scans, and intentionally
false for redaction sentinels.

Choice:
Compute ungrounded-value counts only for fields whose pages have a text layer, excluding
`[REDACTED]`. Mark scanned documents as grounding unavailable instead of inventing a hallucination
rate.

Trade-off:
The scan does not get a hallucination number until a vision/OCR backend can provide independent
evidence. This avoids false precision.

Evidence:
Eval reports `0/8` ungrounded for `pds-P300228`, `0/16` for `pds-P718`, and `n/a (scan)` for
`pds-P600173`.

### Decision: Demonstrate feedback as a measurable eval delta

Constraint:
The HITL requirement asks how corrections improve the pipeline, not just whether a field can be
edited.

Choice:
Use a deliberate canonical-key miss (`Auto-ignition temperature` over-mapped to
`temperature.operating`) and show that one human correction writes a reusable override, then the
next extraction scores correctly.

Trade-off:
This demonstrates deterministic vocabulary improvement, not model fine-tuning. It is the right
scope for the assignment and produces a concrete before/after number.

Evidence:
`python cli.py feedback-demo` shows P718 key accuracy improving from 13/14 to 14/14, with
`DELTA key_correct: +1`, then restores clean state.

### Decision: Price only provider-reported usage

Constraint:
Token accounting differs across providers, especially for PDF/image inputs. Fixture runs have no
real model usage.

Choice:
Cost reporting reads `Document.usage` from real adapters and prices only provider-reported input
and output tokens. Fixture docs report `no real usage (fixture)` and show the indicative price table
only for reference.

Trade-off:
The cost command is structurally complete but cannot produce real dollars until an API key and real
adapter are used. It avoids fake cost numbers.

Evidence:
`python cli.py cost` lists all three fixture docs with no real usage and prints the provider price
table separately.

### Decision: Keep P818 key-gated instead of fabricating a cold-run fixture

Constraint:
The holdout is valuable only if it is not tuned through fixtures or hand-authored outputs.

Choice:
Do not create `fixtures/pds-P818.pass1.json`. Wire the eval/cost path so it can accept P818 once a
real backend exists, but leave the cold-run number empty until then.

Trade-off:
The current submission cannot claim a P818 accuracy number without a key. The generalization story
remains credible because the holdout has not been absorbed into fixture development.

Evidence:
Attempting fixture extraction for `pds-P818` fails because no fixture exists; the eval command
prints that the cold run is pending a real backend and API key.
