"""Controlled canonical-key vocabulary + label -> key mapping (Pass 2).

Generic keyword matching applied uniformly to every document - NOT per-template logic.
A label maps to a canonical_key if any of its (bilingual) alias substrings appears in the
printed label. Unmapped labels keep canonical_key=None and are flagged mapping_uncertain,
so nothing is dropped - queryability degrades gracefully, flexibility is preserved.

HITL corrections (Phase 4) extend this by writing label->key overrides, checked first.
This deterministic mapper is the keyless starter; a cheap LLM can replace/augment it later
behind the same map_label() signature.

Order matters: more specific aliases come before generic ones.
"""

from __future__ import annotations

import json
import os

# (canonical_key, [alias substrings, lowercased])
CANONICAL_VOCAB: list[tuple[str, list[str]]] = [
    # flow (specific cases before generic)
    ("flow.maximum", ["flow maxi", "debit maxi", "maximum flow", "flow max"]),
    ("flow.minimum", ["minimum flow", "flow mini", "min flow"]),
    ("flow.design", ["design flow"]),
    ("flow.total", ["total flow"]),
    ("flow.nominal", ["flow nominal", "debit nominal", "normal flow"]),
    # pressure
    ("pressure.discharge", ["discharge press", "press. refoulement", "refoulement"]),
    ("pressure.suction", ["suction press", "pression aspiration", "aspiration"]),
    ("pressure.differential", ["differential press", "press. differentielle"]),
    # head / npsh
    ("head.differential", ["differential head", "hauteur mano", "hauteur"]),
    ("npsh.required", ["npsh requis", "req'd npsh", "required npsh", "npsh required"]),
    ("npsh.available", ["npsh disponible", "available npsh", "npsh available"]),
    # power / efficiency / speed
    ("power.shaft.rated", ["bhp rated", "p. abs", "p.abs", "puiss. abs", "abs. roue"]),
    ("power.shaft.normal", ["normal shaft power", "shaft power"]),
    ("efficiency.pump", ["rendt", "rendement", "efficiency"]),
    ("speed.rpm", ["rpm", "tr/min"]),
    # fluid properties
    ("density.operating", ["density", "masse vol"]),
    ("viscosity.operating", ["viscosity", "viscosite"]),
    ("vapor_pressure.operating", ["vapor pressure", "tension de vapeur"]),
    ("temperature.design", ["design temp"]),
    ("temperature.operating", ["pumping temp", "temp. de ref", "temperature"]),
    ("corrosion_erosion", ["corrosion", "erosion"]),
    # materials / seal (combined before single)
    ("material.casing_impeller", ["material of construction", "casing / impeller"]),
    ("material.impeller", ["impeller", "roue"]),
    ("material.casing", ["inner case", "casing", "corps"]),
    ("seal.type", ["mechanical seal", "garniture mecanique", "seal"]),
    # motor
    ("motor.voltage", ["volts/phases", "volts", "tension"]),
    ("motor.protection", ["protection", "ip5", "ip6"]),
    # identification / title block
    ("fluid.name", ["liquid", "product", "fluid"]),
    ("equipment.service", ["service", "fonction"]),
    ("units.count", ["n of units", "quantite necessaire", "number"]),
    ("client.name", ["client", "customer"]),
    ("project.name", ["project", "nom du projet"]),
    ("item.number", ["item", "repere"]),
]


def map_label(label: str, overrides: dict[str, str] | None = None) -> tuple[str | None, bool]:
    """Return (canonical_key, mapping_uncertain).

    overrides: optional {label_verbatim -> canonical_key} from HITL corrections,
    matched case-insensitively and checked before the base vocabulary.
    """
    norm = label.strip().lower()
    if overrides:
        for k, v in overrides.items():
            if k.strip().lower() == norm:
                return v, False
    for key, patterns in CANONICAL_VOCAB:
        if any(p in norm for p in patterns):
            return key, False
    return None, True


def load_overrides(path: str = "vocab_overrides.json") -> dict[str, str]:
    """Load HITL-learned label->canonical_key overrides if the file exists."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}
