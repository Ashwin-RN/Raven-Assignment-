"""Datasheet extraction CLI.

    python cli.py extract pds-P300228.pdf          # render -> backend -> normalize -> JSON
    python cli.py extract *.pdf --backend fixture
    python cli.py review                            # Phase 4
    python cli.py eval                              # Phase 5
    python cli.py cost                              # Phase 5

Phase 1: only `extract` (fixture backend) is wired end-to-end. The rest are stubs.
"""

from __future__ import annotations

import os

import click

from datasheet.backends import FixtureBackend
from datasheet.pipeline import extract_document
from datasheet.store import save_raw

OUT_ROOT = "outputs"
FIXTURES_DIR = "fixtures"


def _doc_id(pdf_path: str) -> str:
    return os.path.splitext(os.path.basename(pdf_path))[0]


@click.group()
def cli() -> None:
    """Generic, provider-neutral datasheet field extraction."""


@cli.command()
@click.argument("pdfs", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--backend", default="fixture", type=click.Choice(["fixture"]),
              help="Extraction backend (real adapters wired when an API key is available).")
@click.option("--out", "out_root", default=OUT_ROOT, help="Output root directory.")
def extract(pdfs: tuple[str, ...], backend: str, out_root: str) -> None:
    """Extract one or more datasheet PDFs to structured JSON."""
    if backend == "fixture":
        be = FixtureBackend(FIXTURES_DIR)
    else:  # pragma: no cover - only fixture exists in Phase 1
        raise click.ClickException(f"Backend '{backend}' not wired yet.")

    artifacts_dir = os.path.join(out_root, "artifacts")
    failures = 0
    for pdf in pdfs:
        doc_id = _doc_id(pdf)
        click.echo(f"[extract] {doc_id} via {backend} backend ...")
        try:
            doc = extract_document(doc_id, pdf, be, artifacts_dir)
        except FileNotFoundError as exc:
            click.secho(f"  skipped: {exc}", fg="yellow")
            failures += 1
            continue
        path = save_raw(doc, out_root)
        grounded = sum(1 for f in doc.fields if f.citation.text_layer_match)
        mapped = sum(1 for f in doc.fields if f.canonical_key)
        click.echo(
            f"  {len(doc.fields)} fields, {len(doc.notes)} notes, "
            f"{grounded} grounded, {mapped} canonical-mapped -> {path}"
        )
    if failures:
        raise SystemExit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
def review(host: str, port: int) -> None:
    """Launch the HITL review UI (FastAPI)."""
    import uvicorn

    click.echo(f"review UI -> http://{host}:{port}")
    uvicorn.run("datasheet.web.app:app", host=host, port=port, reload=False)


@cli.command(name="eval")
@click.option("--source", default="raw", type=click.Choice(["raw", "reviewed"]),
              help="Score raw extractions or human-reviewed outputs.")
def eval_(source: str) -> None:
    """Run the eval harness (partial-correctness metrics vs the gold set)."""
    from tabulate import tabulate

    from datasheet.evaluate import AXES, evaluate_all

    r = evaluate_all(source=source)
    rows = []
    for d in r["per_doc"]:
        c, n = d["counts"], d["n"]
        h = d["hallucination"]
        hall = "n/a (scan)" if h["rate"] is None else f"{h['ungrounded']}/{h['checkable']}"
        rows.append([d["doc_id"], n, *[f"{c[a]}/{n}" for a in AXES], hall])
    agg, tot = r["agg"], r["total"]
    rows.append(["OVERALL", tot, *[f"{agg[a]}/{tot}" for a in AXES], ""])
    click.echo(tabulate(rows, headers=["doc", "gold", *AXES, "ungrounded"], tablefmt="github"))
    if tot:
        click.echo(
            f"\ncoverage={agg['label_found'] / tot:.0%}  "
            f"value_acc={agg['value_correct'] / tot:.0%}  "
            f"key_acc={agg['key_correct'] / tot:.0%}  "
            f"(source={source})"
        )
    click.echo("\nP818: cold-run pending - sealed holdout, needs a real backend + API key.")


@cli.command()
def cost() -> None:
    """Report cost per document from provider-reported token usage."""
    from tabulate import tabulate

    from datasheet.cost import PRICING, cost_for_doc
    from datasheet.store import list_doc_ids, load_raw

    rows = []
    for did in list_doc_ids():
        c = cost_for_doc(load_raw(did))
        rows.append([
            did, c.get("model", "-"), c.get("input_tokens", "-"),
            c.get("output_tokens", "-"),
            "-" if c["usd"] is None else f"${c['usd']}", c["status"],
        ])
    click.echo(tabulate(rows, headers=["doc", "model", "in_tok", "out_tok", "usd", "status"],
                        tablefmt="github"))
    click.echo("\nIndicative pricing (USD per 1M tokens, in / out):")
    for m, (i, o) in PRICING.items():
        click.echo(f"  {m:18} {i:>5} / {o}")
    click.echo("\nReal per-doc cost appears once a provider key is wired (fixtures carry no usage).")


@cli.command(name="feedback-demo")
def feedback_demo() -> None:
    """Demonstrate a measurable eval gain from one HITL correction (keyless)."""
    import json

    from datasheet.backends import FixtureBackend
    from datasheet.evaluate import load_gold, score_doc
    from datasheet.pipeline import extract_document
    from datasheet.store import save_raw

    ovr = "vocab_overrides.json"
    be = FixtureBackend(FIXTURES_DIR)
    art = os.path.join(OUT_ROOT, "artifacts")
    backup = open(ovr).read() if os.path.exists(ovr) else None
    gold = load_gold("pds-P718")

    def run() -> dict:
        d = extract_document("pds-P718", os.path.join("pdfs", "pds-P718.pdf"), be, art)
        save_raw(d)
        return score_doc(d, gold)

    try:
        if os.path.exists(ovr):
            os.remove(ovr)
        base = run()
        b = next(x for x in base["details"] if x["match"] == "Auto-ignition")
        click.echo(f"baseline : Auto-ignition key_correct={b.get('key')} (mapped to '{b.get('got_key')}'), "
                   f"overall key_acc={base['counts']['key_correct']}/{base['n']}")

        with open(ovr, "w", encoding="utf-8") as fh:
            json.dump({"Auto-ignition temperature": "fluid.autoignition_temperature"}, fh)
        click.echo("correction: human maps 'Auto-ignition temperature' -> fluid.autoignition_temperature")

        after = run()
        a = next(x for x in after["details"] if x["match"] == "Auto-ignition")
        click.echo(f"after fix : Auto-ignition key_correct={a.get('key')} (mapped to '{a.get('got_key')}'), "
                   f"overall key_acc={after['counts']['key_correct']}/{after['n']}")
        delta = after["counts"]["key_correct"] - base["counts"]["key_correct"]
        click.echo(f"\nDELTA key_correct: +{delta}  (one correction -> reusable vocab override -> pipeline improves)")
    finally:
        if backup is not None:
            with open(ovr, "w", encoding="utf-8") as fh:
                fh.write(backup)
        elif os.path.exists(ovr):
            os.remove(ovr)
        run()  # restore clean raw
        click.echo("(state restored)")


if __name__ == "__main__":
    cli()
