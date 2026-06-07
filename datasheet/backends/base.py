"""The swap point: every extraction backend implements this interface.

Pass 1 (verbatim harvest) is the only provider-specific step. Real adapters
(native-PDF Claude/Gemini, OpenAI-compatible Kimi/GPT) and the keyless fixture
backend all return the same Pass1Output, so Pass 2 / store / UI / eval are shared.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..render import PageRender
from ..schema import Pass1Output


class ExtractionBackend(ABC):
    name: str = "base"

    @abstractmethod
    def extract(
        self, doc_id: str, pdf_path: str, pages: list[PageRender]
    ) -> Pass1Output:
        """Return the verbatim Pass-1 harvest for one document.

        Implementations may use pdf_path directly (native-PDF providers) or the
        rendered page images in `pages` (image-only providers / fixtures).
        """
        raise NotImplementedError
