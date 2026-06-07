# Datasheet Extraction - Write-up

Generic, provider-neutral extraction of structured, cited fields from heterogeneous process
datasheets, with a human-in-the-loop (HITL) review loop. This write-up is organised around the four
evaluation criteria. See [`docs/PLAN.md`](docs/PLAN.md) for the full plan.

## TL;DR

- One generic, schema-open extraction path handles all templates - **no per-template parsers**. The
  only document-specific code is CLI/demo/eval scaffolding (e.g. the feedback demo names P718), not
  extraction logic.
- Runs **end-to-end with no API key** via a fixture/replay backend; a real model adapter
  (Claude/Gemini/Kimi) drops in behind one interface when a key is available.
- Provenance on every field (model-emitted page + verbatim snippet, grounded against the text layer).
- HITL feedback is **measurable**: one canonical-key correction lifts P718 key accuracy 13/14 -> 14/14.
- Honest scope: the fixture-based eval validates the pipeline and the deterministic Pass 2, **not**
  model reading accuracy; real accuracy, the P818 cold-run, and true per-doc cost are key-gated.

---

## Demo

A short recorded walkthrough accompanies this submission (link/file provided with the submission).
It covers: `python cli.py extract` on the sample PDFs (keyless, fixture backend) -> the review UI
(`python cli.py review`) making a correction with citation + page image inline -> `python cli.py
feedback-demo` and `python cli.py eval` showing the measurable +1 key-accuracy delta and the metric
table.

---

## 1. Extraction quality (accuracy, coverage)

### What the inputs forced
Inspecting the four PDFs drove every major decision:
- **No reliable text layer** - `pds-P600173` page 1 is a flattened scan with 0 extractable
  characters. -> vision is the only common denominator.
- **Heterogeneous templates** - P300228/P600173 are a bilingual FR/EN form; P718/P818 are an
  unrelated row-numbered template. -> a single generic extractor, never per-template parsers.
- **Bilingual labels, mixed units** (kg/cm2 g, m3/h vs GPM, psig, degF, hp), **footnotes** that
  qualify values (`2.7 (4)` = "estimated, confirm with vendor"), **checkboxes**, **multi-case
  tables** (P718 off-spec column), and **redacted** title-block fields.

### Approach: schema-open harvest, then normalize
- **Pass 1 (the swappable extraction step)** harvests *every* labelled field as generic document
  primitives - key-value pairs, checkboxes, footnotes, multi-case rows, title block - emitting
  verbatim label, value, unit, footnote markers, `case`, page, and a verbatim snippet. It is never
  given a fixed field list, which is what lets it generalise to unseen layouts. **The Pass-1 prompt
  and JSON contract are implemented; the current backend replays hand-authored fixtures, so real
  model *reading* is key-gated** - a Claude/Gemini/Kimi adapter drops in behind the same interface.
- **Pass 2 (deterministic, shared)** maps the verbatim label to a controlled `canonical_key`,
  normalizes value + unit to SI (gauge vs absolute preserved), resolves footnote markers to
  qualifiers, runs the grounding check, and calibrates confidence.

### Schema (the graded centerpiece)
A flat field-list / EAV model: `canonical_key` (controlled vocab -> queryability) that is **nullable**
so unmapped fields are kept as free-form with full provenance (-> flexibility, nothing dropped). Each
field carries `value_raw` + `value_normalized` + `unit` + `unit_si` + `value_si`, `qualifiers`,
`case`, `citation` (page + snippet + grounding), `confidence`, and review state. Resolving the
generic-vs-queryable tension this way is the core schema decision.

### Coverage / accuracy (current, fixture-based)
Measured by `python cli.py eval` against a query-anchored gold set (P300228/P600173/P718, ~9-14
fields each, anchored on the README example queries). Partial-correctness per field - label found,
value, unit, citation, canonical key:

| metric | result |
|---|---|
| coverage (label found) | 34/34 (100%) |
| value correct | 34/34 (100%) |
| unit correct | 34/34 (100%) |
| citation valid | 34/34 (100%) |
| canonical key correct | 33/34 (97%) |
| hallucination (text-layer pages) | 0 ungrounded; scan = grounding-unavailable |

**Honest reading of these numbers:** value/unit/citation = 100% reflects that the harness and the
deterministic Pass 2 are correct *given correct Pass-1 input* - the fixtures are hand-authored, so
this validates plumbing, not model reading accuracy. `key_acc` = 97% genuinely measures the canonical
mapper (gold keys are independent of the vocab); the one miss is the generic `temperature` alias
over-matching "Auto-ignition temperature" - a real, instructive gap.

---

## 2. Reliability and cost (cost per doc, failure modes)

### Reliability
- **Provenance + grounding:** every value carries page + verbatim snippet; where a text layer exists
  we string-match the value against it (`text_layer_match`), so a fabricated value surfaces as
  ungrounded. On scans grounding is reported unavailable rather than faked.
- **Validation (implemented) + repair (planned):** Pass-1/Pass-2 output is validated against the
  Pydantic schema (the fixture backend validates on load). For a real adapter - where model JSON can
  be malformed - the planned path is one repair attempt (re-prompt with the validation error), then
  fail with the raw artifact rather than emit garbage. This isn't exercised yet because fixtures are
  pre-validated.
- **Inspectable artifacts:** page images, raw text, Pass-1 and final JSON are persisted per doc.

### Failure modes tracked (and how they're handled)
| failure mode | mitigation |
|---|---|
| hallucinated value | text-layer grounding -> low confidence / flag |
| dropped field (coverage gap) | schema-open harvest maximises recall; coverage measured |
| redacted field guessed as a name | explicit `[REDACTED]` sentinel + `redacted` qualifier |
| gauge vs absolute pressure merged | preserved in `unit_si` (`bar g` vs `bar a`) |
| spurious numeric from a text value ("SS 304") | value parsed only when the *entire* string is numeric (`re.fullmatch`), so "SS 304" -> `value_normalized = None` (not 304) |
| footnote caveat lost | markers resolved to note text in `qualifiers` |
| multi-case values collide | each value tagged with its `case` |
| canonical key over/mis-mapped | flagged `mapping_uncertain`; correctable via HITL |

### Cost per doc
Token counts are provider-specific (especially for image/PDF input), so each adapter records its own
`usage`. Today, on the fixture backend, `python cli.py cost` reports the per-provider **price table
and "no real usage" per doc** - real per-doc cost requires a provider's reported token usage. The
numbers below are **estimates** from the token methodology (2-3 pages, output ~3-4k structured tokens
dominating, schema/instruction prefix cached), not measured runs:

| provider | est. cost/doc |
|---|---|
| Claude Opus 4.8 ($5/$25 per 1M) | ~$0.10-0.20 |
| Claude Sonnet 4.6 ($3/$15) | ~$0.05-0.08 |
| Kimi K2.6 (~$0.95/$4) | a few cents |
| Pass 0/2 on Haiku 4.5 ($1/$5) | ~$0.01-0.02 |

Levers: prompt caching of the schema/instruction prefix, model tier per pass, batch APIs for eval
runs. Real measured numbers are populated the moment a provider key is wired (fixtures carry no
usage) - this is the confirmation step, not a missing design.

---

## 3. Human-in-the-loop (how feedback improves results, ergonomics)

### Ergonomics
A lightweight FastAPI + Jinja2 UI (`python cli.py review`). It is **field-first**: all fields across
a doc sorted by ascending confidence (shakiest first), filterable by page / canonical key / review
status. Each row shows the value, SI value, qualifiers, and the **citation snippet + grounding badge
+ rendered page image inline**, so the reviewer never hunts through the PDF. Confirm / Correct write
to `outputs/reviewed/<doc>.json`, leaving the raw extraction intact and review resumable.

### Feedback that measurably improves the pipeline
This is demonstrated, not just described (`python cli.py feedback-demo`): a corrected canonical-key
mapping is persisted as a **vocab override**, and the next extraction picks it up automatically.

```
baseline : Auto-ignition -> temperature.operating (wrong), key_acc 13/14
correction: human maps "Auto-ignition temperature" -> fluid.autoignition_temperature
after fix : Auto-ignition -> fluid.autoignition_temperature (correct), key_acc 14/14
DELTA: +1
```

Corrections also flow into the gold set (each is a labelled example) and can seed few-shot exemplars
for the model passes - so feedback improves both the deterministic mapper now and the model prompts
when a backend is wired.

---

## 4. Communication / engineering judgment

- **Provider-neutral by design** (`ExtractionBackend` interface): the project had no API key, so the
  entire system was built and verified keyless on a fixture/replay backend, with a real adapter as a
  drop-in. Model choice is a config decided by an A/B eval, not on paper.
- **Generalisation is designed and guarded (not yet measured):** the code has no per-template
  branching (grep-verified) and three dev templates pass through one contract; `pds-P818` is reserved
  as a sealed cold-eval holdout - never used for prompt, schema, or gold tuning - so a true
  generalisation number awaits the cold run on a real backend.
- **Scope discipline:** JSON store (no DB), no auth/deploy/fancy UI, local OCR/VLM left as future
  work - matching the brief's "not looking for" list.

---

## 5. Architecture summary

```
PDF -> PyMuPDF page images + text  ->  ExtractionBackend (Pass 1: verbatim harvest)
                                          fixture | Claude/Gemini | OpenAI-compatible (Kimi/GPT)
    -> Pass 2 normalize (canonical key, SI units, qualifiers, grounding, confidence)
    -> JSON store  ->  review UI (HITL)  |  eval harness  |  cost report
                         corrections -> vocab overrides -> next extraction improves
```

Modules: `schema` (data contract), `render`, `backends/*`, `prompts` (Pass-1 prompt + JSON contract),
`pipeline` (orchestration + Pass 2), `vocab` / `units` (canonicalisation), `store`, `review`,
`evaluate`, `cost`, `web` (UI).

---

## 6. Trade-offs

- **Vision LLM vs classical OCR/layout:** classical parsing can't survive the scanned page, bilingual
  labels, footnotes, or unseen templates; an LLM handles all of these but costs tokens and can
  hallucinate - mitigated by grounding + confidence + HITL.
- **Native citations vs self-built provenance:** provider-native citations are incompatible with
  structured outputs and unsupported on images, so provenance is model-emitted page+snippet verified
  by grounding - which is also backend-agnostic.
- **Controlled vocab vs free-form keys:** a controlled `canonical_key` gives queryability; nullable +
  free-form fallback preserves flexibility so nothing is dropped.
- **Deterministic Pass 2 now vs LLM Pass 2 later:** deterministic mapping is testable with no key and
  fast; an LLM mapper can replace it behind the same signature for better coverage on unseen labels.

---

## 7. Future improvements

- Wire a real provider adapter (Claude or Gemini native-PDF; Kimi via OpenAI-compatible) - the only
  real code remaining; run the **P818 cold-run** and populate real accuracy + cost.
- LLM-assisted Pass 2 for canonical mapping on unseen labels (the deterministic vocab has gaps by
  design - e.g. the auto-ignition over-map).
- Tighten over-broad vocab aliases (`tension`/`number`/`item`) so mapping doesn't depend on ordering;
  more specific gold anchoring in the eval matcher.
- Bounding-box citations, SI conversions for more unit families, canonical-vocab routing by doc_type,
  split extraction vs normalization confidence, an open-source local OCR/VLM backend for the
  cost/accuracy comparison table.
