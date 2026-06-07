"""PDF -> page images + text layer, using PyMuPDF.

The text layer is unreliable across these datasheets (P600173 page 1 is a flattened
scan with 0 characters), so it is used only for grounding/debugging - never as the
primary extraction path. Page images are what the vision backends consume.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class PageRender:
    page_no: int  # 1-based
    image_path: str
    text: str  # text-layer text ("" for scanned pages)


def render_pages(pdf_path: str, out_dir: str, dpi: int = 200) -> list[PageRender]:
    """Render each page to a PNG and pull its text layer.

    Artifacts land in out_dir/page-{n}.png. Returns one PageRender per page.
    """
    os.makedirs(out_dir, exist_ok=True)
    pages: list[PageRender] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            image_path = os.path.join(out_dir, f"page-{i}.png")
            pix.save(image_path)
            text = page.get_text() or ""
            with open(
                os.path.join(out_dir, f"page-{i}.txt"), "w", encoding="utf-8"
            ) as fh:
                fh.write(text)
            pages.append(PageRender(page_no=i, image_path=image_path, text=text))
    return pages
