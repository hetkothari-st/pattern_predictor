"""Parse Bulkowski's *Encyclopedia of Chart Patterns* into structured guidance.

Usage:
    python -m app.knowledge.ingest_book \
        --pdf "C:\\Users\\ST269\\Downloads\\dokumen.pub_encyclopedia-of-chart-patterns-3nbsped-1119739721-9781119739722.pdf" \
        --out app/knowledge/patterns.yaml \
        [--chroma data/chroma]

What it does:
  1. pdfplumber → page text.
  2. Heuristic chapter split: looks for "Chapter N — <Pattern Name>" headers.
  3. Maps detected chapter names to our canonical pattern keys via PATTERN_ALIASES.
  4. Extracts the per-pattern statistics paragraph (success rate / measure rule /
     throwback %) using regex against the phrasing Bulkowski uses consistently.
  5. Writes the result merged into the existing patterns.yaml (so seeded fields
     remain a fallback for anything the parser missed).
  6. Optionally embeds chapter chunks into a Chroma collection for prose RAG.

This is a *best-effort* parser. After it runs, the user should spot-check
patterns.yaml against the book and correct any mis-extracted numbers — the
guidance card explicitly cites these figures to the trader.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

# Map free-text chapter titles to our internal canonical pattern keys.
PATTERN_ALIASES: dict[str, str] = {
    "head-and-shoulders top": "head_and_shoulders",
    "head-and-shoulders tops": "head_and_shoulders",
    "head-and-shoulders bottom": "inverse_head_and_shoulders",
    "head-and-shoulders bottoms": "inverse_head_and_shoulders",
    "double top": "double_top",
    "double tops": "double_top",
    "double bottom": "double_bottom",
    "double bottoms": "double_bottom",
    "triangles, ascending": "ascending_triangle",
    "ascending triangle": "ascending_triangle",
    "triangles, descending": "descending_triangle",
    "descending triangle": "descending_triangle",
    "triangles, symmetrical": "symmetric_triangle",
    "symmetrical triangle": "symmetric_triangle",
    "rising wedge": "rising_wedge",
    "falling wedge": "falling_wedge",
    "flags": "bull_flag",
    "flags, high and tight": "bull_flag",
    "pennants": "bull_pennant",
    "cup with handle": "cup_with_handle",
    "cup-with-handle": "cup_with_handle",
}

PAT_SUCCESS = re.compile(r"(success(?: rate)?|reliability)\D{0,15}(\d{1,3})\s*%", re.I)
PAT_AVG_MOVE = re.compile(r"average (?:rise|decline|move)\D{0,15}(\d{1,3})\s*%", re.I)
PAT_THROWBACK = re.compile(r"(throwback|pullback)\D{0,15}(\d{1,3})\s*%", re.I)
PAT_CHAPTER = re.compile(r"^\s*(?:chapter\s+\d+[:\.\s-]+|)([A-Z][A-Za-z,\-\s]{4,60})\s*$", re.M)


def parse_pdf_to_chapters(pdf_path: Path) -> list[tuple[str, str]]:
    """Return list of (chapter_title, body_text)."""
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "pdfplumber is required. Install with: pip install -e '.[knowledge]'"
        ) from exc

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for p in pdf.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pages.append("")
    text = "\n".join(pages)

    # Split on candidate chapter headings.
    chapters: list[tuple[str, str]] = []
    last_idx = 0
    last_title = "preface"
    for m in PAT_CHAPTER.finditer(text):
        title = m.group(1).strip().lower()
        if title not in PATTERN_ALIASES:
            continue
        chapters.append((last_title, text[last_idx : m.start()]))
        last_title = title
        last_idx = m.end()
    chapters.append((last_title, text[last_idx:]))
    return [(t, body) for t, body in chapters if t in PATTERN_ALIASES]


def extract_stats(body: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = PAT_SUCCESS.search(body)
    if m:
        out["success_rate"] = int(m.group(2)) / 100.0
    m = PAT_AVG_MOVE.search(body)
    if m:
        out["avg_move"] = int(m.group(1)) / 100.0
    m = PAT_THROWBACK.search(body)
    if m:
        out["throwback_pct"] = int(m.group(2)) / 100.0
    # First couple of sentences as a summary.
    sentences = re.split(r"(?<=[.!?])\s+", body.strip())
    if sentences:
        out["summary"] = " ".join(sentences[:2]).strip()[:400]
        out["source_quote"] = sentences[min(2, len(sentences) - 1)][:300]
    return out


def merge_yaml(out_path: Path, updates: dict[str, dict[str, Any]]) -> None:
    existing: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        existing = yaml.safe_load(out_path.read_text()) or {}
    for key, fields in updates.items():
        prev = existing.get(key, {})
        prev.update(fields)
        existing[key] = prev
    out_path.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True))


def maybe_index_chroma(chapters: list[tuple[str, str]], chroma_path: Path) -> None:
    try:
        import chromadb  # type: ignore
        from chromadb.utils.embedding_functions import (  # type: ignore
            SentenceTransformerEmbeddingFunction,
        )
    except ImportError:
        print("Chroma not installed; skipping vector index. (`pip install -e '.[knowledge]'`)")
        return
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    coll = client.get_or_create_collection(
        name="bulkowski",
        embedding_function=SentenceTransformerEmbeddingFunction(),
    )
    ids, docs, metas = [], [], []
    for i, (title, body) in enumerate(chapters):
        for j in range(0, len(body), 1500):
            chunk = body[j : j + 1500]
            if not chunk.strip():
                continue
            ids.append(f"{title}-{i}-{j}")
            docs.append(chunk)
            metas.append({"pattern": PATTERN_ALIASES[title]})
    if ids:
        coll.upsert(ids=ids, documents=docs, metadatas=metas)
        print(f"Indexed {len(ids)} chunks into {chroma_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to the Encyclopedia of Chart Patterns PDF")
    ap.add_argument("--out", default="app/knowledge/patterns.yaml")
    ap.add_argument("--chroma", default=None, help="Optional path for Chroma index")
    args = ap.parse_args()

    pdf = Path(args.pdf).expanduser()
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    print(f"Parsing {pdf} ...")
    chapters = parse_pdf_to_chapters(pdf)
    print(f"Found {len(chapters)} mappable chapters.")

    updates: dict[str, dict[str, Any]] = {}
    for title, body in chapters:
        key = PATTERN_ALIASES[title]
        stats = extract_stats(body)
        if stats:
            updates[key] = stats
    print(f"Extracted stats/summary for {len(updates)} patterns.")
    merge_yaml(Path(args.out), updates)
    print(f"Merged into {args.out}.")

    if args.chroma:
        maybe_index_chroma(chapters, Path(args.chroma))


if __name__ == "__main__":
    main()
