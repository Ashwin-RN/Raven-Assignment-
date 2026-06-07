"""FastAPI review UI.

Field-first HITL review: fields sorted by ascending confidence (shakiest first), filterable
by page / canonical_key / review status. Each field shows its citation (page + snippet) and
rendered page image inline, so the reviewer never hunts through the PDF. Confirm / Correct
persist to reviewed/<doc_id>.json; a canonical-key correction is fed back as a vocab override.

Edits use a small JSON API (no python-multipart dependency).
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..review import apply_field_edit, list_summaries, working_doc

OUT_ROOT = "outputs"
_TEMPLATES = os.path.join(os.path.dirname(__file__), "templates")

app = FastAPI(title="Datasheet Review")
templates = Jinja2Templates(directory=_TEMPLATES)

# serve rendered page images for inline citation context
os.makedirs(os.path.join(OUT_ROOT, "artifacts"), exist_ok=True)
app.mount(
    "/artifacts",
    StaticFiles(directory=os.path.join(OUT_ROOT, "artifacts")),
    name="artifacts",
)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"docs": list_summaries(OUT_ROOT)}
    )


@app.get("/doc/{doc_id}", response_class=HTMLResponse)
def doc_view(
    request: Request,
    doc_id: str,
    status: str = "all",
    key: str = "",
    page: int = 0,
    sort: str = "confidence",
):
    doc = working_doc(doc_id, OUT_ROOT)
    fields = list(doc.fields)
    if status != "all":
        fields = [f for f in fields if f.review_status == status]
    if key:
        fields = [f for f in fields if f.canonical_key and key.lower() in f.canonical_key.lower()]
    if page:
        fields = [f for f in fields if f.citation.page == page]
    if sort == "page":
        fields.sort(key=lambda f: (f.citation.page, f.id))
    else:  # confidence ascending - shakiest first
        fields.sort(key=lambda f: f.confidence)

    pages = sorted({f.citation.page for f in doc.fields})
    keys = sorted({f.canonical_key for f in doc.fields if f.canonical_key})
    return templates.TemplateResponse(
        request,
        "doc.html",
        {
            "doc": doc,
            "fields": fields,
            "pages": pages,
            "keys": keys,
            "filters": {"status": status, "key": key, "page": page, "sort": sort},
        },
    )


@app.post("/api/doc/{doc_id}/field/{field_id}")
async def edit_field(doc_id: str, field_id: str, request: Request):
    body = await request.json()
    try:
        field = apply_field_edit(
            doc_id,
            field_id,
            action=body.get("action", "confirm"),
            value_raw=body.get("value_raw"),
            unit=body.get("unit"),
            canonical_key=body.get("canonical_key"),
            out_root=OUT_ROOT,
        )
    except (KeyError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(field.model_dump())
