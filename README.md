# Datasheet Extraction

Turn messy engineering **process datasheets** (PDF) into clean, **queryable, cited** data - with a
human-in-the-loop review screen to correct what the model gets wrong, and a feedback loop that learns
from each correction.

It runs **with no API key out of the box** (a fixture/replay backend stands in for the model), so you
can try the whole thing - extract, review, evaluate, cost - in a couple of minutes.

> Built for the Raven backend assignment. Deeper docs: [`WRITEUP.md`](WRITEUP.md) (architecture,
> trade-offs, evaluation, cost) and [`docs/PLAN.md`](docs/PLAN.md) (the full plan). The original
> assignment brief is at the bottom of this file.

---

## Quickstart (no API key)

```bash
# 1. Create a virtualenv and install deps (Python 3.12)
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt      # Windows
# source venv/bin/activate && pip install -r requirements.txt  # macOS / Linux

# 2. Extract the sample datasheets -> outputs/raw/<doc_id>.json
python cli.py extract pdfs/pds-P300228.pdf pdfs/pds-P600173.pdf pdfs/pds-P718.pdf

# 3. Open the review UI to inspect / correct fields
python cli.py review            # then visit http://127.0.0.1:8000

# 4. See the eval metrics, the cost report, and the feedback loop in action
python cli.py eval
python cli.py cost
python cli.py feedback-demo
```

That's it - no key, no cloud, no setup beyond `pip install`. The extractor replays hand-authored
fixtures so the full pipeline (and the review UI) works offline.

---

## Commands

| Command | What it does |
|---|---|
| `python cli.py extract <pdf...>` | Render -> extract -> normalize -> `outputs/raw/<doc_id>.json` (+ artifacts) |
| `python cli.py review` | Launch the HITL review UI (field-first, confidence-sorted, citations inline) |
| `python cli.py eval` | Partial-correctness metrics vs the gold set (+ hallucination) |
| `python cli.py cost` | Per-doc cost from provider token usage (+ price table) |
| `python cli.py feedback-demo` | Show a measurable eval gain from one correction (keyless) |

---

## Repo structure

```
README.md            you are here
WRITEUP.md           architecture / trade-offs / evaluation / cost (the write-up)
requirements.txt     dependencies
.env.example         copy to .env to add a provider key (optional)
cli.py               command-line entry point
datasheet/           the library: schema, render, backends, pipeline, vocab, units,
                       review, evaluate, cost, web (FastAPI UI)
pdfs/                input datasheets (pds-P300228 / P600173 / P718 / P818)
fixtures/            hand-authored Pass-1 fixtures for keyless runs (P818 intentionally absent)
eval/gold/           query-anchored gold labels for the eval
outputs/             raw extractions (committed as samples) + reviewed + artifacts (ignored)
docs/PLAN.md         the full build plan
```

---

## Using a real model provider (optional)

The whole system is **provider-neutral**: the model sits behind one `ExtractionBackend` interface, so
swapping in a real model is a config change, not a rewrite. Today the default is the keyless fixture
backend; wiring a live adapter is the remaining step (see Status below).

To prepare for a real provider:

```bash
cp .env.example .env
```

Then open `.env` and fill in **one** key (you only need one):

```
GEMINI_API_KEY=...          # Google Gemini (strong native PDF)
# ANTHROPIC_API_KEY=...     # Claude (native PDF, strong reasoning)
# MOONSHOT_API_KEY=...      # Kimi K2.6 (cheapest; OpenAI-compatible)
# OPENAI_API_KEY=...        # GPT (verifier-only; pricey)
```

`.env` is gitignored and never committed. Which provider becomes the default is decided by the
eval (accuracy vs cost on these documents), not on paper.

---

## How it works (in one breath)

`PDF -> page images + text (PyMuPDF) -> Pass 1 verbatim harvest (the swappable backend) -> Pass 2
normalize (canonical key, SI units, footnote qualifiers, grounding, confidence) -> JSON store ->
review UI / eval / cost`. Provenance (page + verbatim snippet, grounded against the text layer) is
attached to every field. Corrections in the UI persist and feed back as vocab overrides, so the next
extraction improves. Full detail in [`WRITEUP.md`](WRITEUP.md).

---

## Status & limitations (honest)

- All five build phases are complete and run **keyless** on fixtures.
- The fixture-based eval validates the **pipeline and deterministic normalization**, not model
  *reading* accuracy - that needs a real adapter + key.
- `pds-P818` is a **sealed holdout** (never used for tuning); its cold-run generalization number is
  pending a real backend.
- Real per-doc cost is pending a provider's reported token usage (the cost command shows the price
  table + estimates today).

---

## Assignment brief (original)

Extract structured fields from a process datasheet so they can power search, technical bid
evaluation, and more. **Build:** (1) an extraction pipeline that ingests a datasheet PDF and produces
structured fields with citations; (2) a HITL feedback loop - a web interface to review/correct
extractions and explain how feedback improves the pipeline. **Schema:** define your own, but generic
enough for a wide variety of fields and use cases, balancing flexibility with queryability and
provenance. **Logistics:** 24h; any stack; submit as a private fork shared with the evaluator, with a
recorded demo and a write-up (architecture, trade-offs, evaluation and cost metrics, future work).
**Evaluation:** extraction quality (accuracy, coverage); reliability and cost (cost per doc, failure
modes); human-in-the-loop (how feedback is used, ergonomics); communication. **Not looking for:**
authentication, deployment, fancy UI beyond ergonomics for the HITL interface.
