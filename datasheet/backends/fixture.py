"""Fixture / replay backend - lets the whole pipeline run with ZERO API keys.

Loads a recorded Pass-1 harvest from fixtures/<doc_id>.pass1.json. For Phase 1 the
fixtures are hand-authored dev data: they prove the plumbing (render -> normalize ->
store -> UI -> eval) is deterministic and end-to-end. They do NOT prove extraction
quality - that requires a real provider key (see PLAN.md SS8). When a key lands, the
real adapters can write their responses here to record new fixtures.
"""

from __future__ import annotations

import json
import os

from ..render import PageRender
from ..schema import Pass1Output
from .base import ExtractionBackend


class FixtureBackend(ExtractionBackend):
    name = "fixture"

    def __init__(self, fixtures_dir: str):
        self.fixtures_dir = fixtures_dir

    def extract(
        self, doc_id: str, pdf_path: str, pages: list[PageRender]
    ) -> Pass1Output:
        path = os.path.join(self.fixtures_dir, f"{doc_id}.pass1.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No fixture for '{doc_id}' at {path}. "
                f"Hand-author one, or wire a real backend once an API key is available."
            )
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return Pass1Output.model_validate(data)
