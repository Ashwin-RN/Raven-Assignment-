"""Pass 1 prompt + JSON contract - the provider-independent extraction core.

This is the heart of the system: a schema-open verbatim harvester. It is deliberately
NOT a pump-field parser - it extracts whatever labelled fields exist, so it generalizes
to unseen templates and equipment types. The four sample docs are a validation set, not
a field list to hard-code.

The JSON contract is `Pass1Output` (see schema.py). Every real adapter (Claude/Gemini
native-PDF, Kimi/GPT OpenAI-compatible) passes `PASS1_SYSTEM_PROMPT` as the system
message and `pass1_json_schema()` to the provider's structured-output / JSON mode, then
validates the result back into `Pass1Output`.
"""

from __future__ import annotations

from .schema import Pass1Output

PASS1_SYSTEM_PROMPT = """\
You extract structured data from an engineering PROCESS DATASHEET (e.g. for a pump,
motor, vessel, or similar equipment). The document may be a scanned image, bilingual
(e.g. French/English), and use metric or imperial units. Return JSON only - no prose.

GOAL: harvest EVERY labelled field present on the pages, exactly as printed. Do not limit
yourself to a fixed list of fields, and do not invent fields that are not on the page.
Think of yourself as transcribing the form, not interpreting it.

For each field produce an object with:
- type: one of scalar | checkbox | table_cell | note | title_block | free_text
- label_verbatim: the field's printed label, EXACTLY as shown. If bilingual, keep both
  languages joined with " / " (e.g. "DEBIT Nominal / FLOW Nominal").
- value_raw: the printed value, EXACTLY as shown (keep the original digits and decimal
  separator). Do NOT convert units or normalize.
- unit: the printed unit as a separate string (e.g. "m3/h", "kg/cm2 g", "psig", "degF"),
  or null if none.
- footnote_markers: any reference markers attached to the value, e.g. ["(4)"], else [].
- case: for values that recur under different OPERATING CONDITIONS (multi-case tables /
  columns such as Normal / Maximum / Design / Off-spec), set the case label; else null.
- page: the 1-based page number you read it from.
- snippet: a short VERBATIM excerpt of the surrounding printed text you read the value
  from. This is the provenance and is REQUIRED for every field.
- confidence: your reading confidence from 0 to 1.

RULES:
- Checkboxes / option groups: emit type "checkbox", value_raw = the label of the SELECTED
  option (the ticked/filled box). If none is selected, value_raw = "".
- Footnotes / remarks: extract the numbered remarks/notes section SEPARATELY into the
  top-level `notes` array as {marker, text, page}. Still record the marker on the field's
  footnote_markers.
- Multi-case tables: emit one field per case, each with its `case` label, rather than
  collapsing them into one value.
- Title block (client, project, item, service, etc.): type "title_block". If a value is
  blacked out / redacted, set value_raw EXACTLY to "[REDACTED]" - never guess a name.
- Skip empty cells (do not emit fields with no value), unless the blank itself is
  meaningful (then say so in the snippet).
- Also report top-level `doc_type` (a short snake_case guess, e.g.
  "centrifugal_pump_datasheet") and `language` (e.g. ["fr","en"]).

Return a single JSON object matching the provided schema. JSON only.
"""


def pass1_json_schema() -> dict:
    """JSON Schema for the Pass-1 contract, for provider structured-output / JSON mode."""
    return Pass1Output.model_json_schema()


def build_user_prompt(doc_id: str, num_pages: int) -> str:
    """Per-document user message. The pages/PDF themselves are attached by the adapter."""
    return (
        f"Datasheet id: {doc_id} ({num_pages} page(s)). "
        f"Extract every labelled field per the system instructions. Return JSON only."
    )
