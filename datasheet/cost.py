"""Cost reporting from provider-reported token usage.

Token counts are provider-specific (especially for image/PDF input), so we never assume a
shared count - each adapter records its own `usage` on the Document. When real usage is
present we price it; with the fixture backend there is no usage, so we report that honestly
and show the price table for reference.

Expected usage shape on doc.usage when a real adapter runs:
    {"model": "...", "input_tokens": N, "output_tokens": M,
     "cache_read_input_tokens": K (optional)}
"""

from __future__ import annotations

from .schema import Document

# USD per 1M tokens: (input, output). Indicative - confirm at adapter-wiring time.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "kimi-k2.6": (0.95, 4.0),       # cached input ~0.16
    "gpt-5.5": (5.0, 30.0),
    # gemini: confirm current rate when key obtained
}


def cost_for_doc(doc: Document) -> dict:
    u = doc.usage or {}
    model = u.get("model")
    inp = u.get("input_tokens")
    out = u.get("output_tokens")
    if model is None or inp is None or out is None:
        return {"doc_id": doc.doc_id, "status": "no real usage (fixture)", "usd": None}
    price = PRICING.get(model)
    if price is None:
        return {"doc_id": doc.doc_id, "status": f"unknown model '{model}'", "usd": None}
    usd = inp / 1e6 * price[0] + out / 1e6 * price[1]
    return {
        "doc_id": doc.doc_id,
        "model": model,
        "input_tokens": inp,
        "output_tokens": out,
        "usd": round(usd, 4),
        "status": "ok",
    }
