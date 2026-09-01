"""query.py — read-only inspection of a finished catalog (no LLM, no API).

The catalogs P2 leaves on disk are currently only inspectable with sqlite3 and
a text editor. This is the smallest honest window onto them: full-text search
over the indexed chunks, joined to the cards that were read from those chunks,
with every displayed quote FENCE-CHECKED and its span DERIVED by
`spancheck.locate` — never taken from the model.

This is NOT the S4 `ask` rung. `ask` is demo-grade *cited retrieval over the
finished codex*: it needs the Map, the Atlas and a synthesizing model. This
command answers only what the catalog literally records, with receipts:

    scriptorium.cmd query <archive_root> "fence AND spans" [--limit 5]

Two registers, kept apart the way the P5 renderer must keep them:
  VERBATIM — quotes located in the Tape by code (start:end are real offsets)
  READING  — the model's typed claims/topics/entities, clearly labelled as a
             reading, never as the source's own words.
A quote that cannot be located is not shown as verbatim at all; it is counted
and named as unlocated, so the window can never launder a fabrication.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from discover import fetch_texts
from spancheck import locate

# archives carry terminal captures: ANSI colour and control bytes are part of
# the Tape's honest bytes, but they must never reach a console verbatim (they
# would repaint the operator's terminal and could hide text)
_CTRL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|[\x00-\x08\x0b-\x1f\x7f]")


def _display(s: str) -> str:
    return _CTRL.sub("", (s or "").replace("\n", " ").replace("\t", " "))


class QueryError(Exception):
    pass


def _cards_by_key(root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    p = root / "catalog" / "cards" / "cards.jsonl"
    out: dict[tuple[str, int], dict[str, Any]] = {}
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                out[(row["doc_id"], row["seq"])] = row      # last write wins
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def search(archive_root: str | Path, terms: str, limit: int = 5,
           snippet_chars: int = 240) -> dict[str, Any]:
    """FTS5 over the indexed chunks -> the cards read from them, with
    code-verified verbatim spans."""
    root = Path(archive_root)
    db_path = root / "catalog" / "index.sqlite"
    if not db_path.exists():
        raise QueryError(f"no catalog index at {db_path} — run `read` first")
    if not terms.strip():
        raise QueryError("empty query")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            rows = db.execute(
                "SELECT m.doc_id, m.seq, bm25(chunks_fts) AS rank,"
                "       snippet(chunks_fts, 0, '[', ']', ' ... ', 12) AS snip "
                "FROM chunks_fts f JOIN fts_map m ON m.fts_rowid = f.rowid "
                "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                (terms, limit)).fetchall()
        except sqlite3.OperationalError as e:      # malformed FTS expression
            raise QueryError(f"bad query {terms!r}: {e}") from e
        meta = {}
        for doc_id, seq, _r, _s in rows:
            got = db.execute("SELECT project, year, path FROM chunks "
                             "WHERE doc_id=? AND seq=?", (doc_id, seq)).fetchone()
            meta[(doc_id, seq)] = got or ("?", 0, "?")
    finally:
        db.close()

    cards = _cards_by_key(root)
    keys = [(d, s) for d, s, _r, _sn in rows]
    texts = fetch_texts(root, set(keys)) if keys else {}

    hits = []
    for (doc_id, seq), (_d, _s, rank, snip) in zip(keys, rows, strict=True):
        project, year, path = meta[(doc_id, seq)]
        text = texts.get((doc_id, seq))
        row = cards.get((doc_id, seq))
        card = (row or {}).get("card", {})
        verbatim, unlocated = [], 0
        for q in card.get("quotes", []):
            qt = (q.get("text") or "").strip()
            if not qt:
                continue
            found = locate(text, qt) if text is not None else None
            if found is None:
                unlocated += 1
                continue
            start, end, method = found
            verbatim.append({"start": start, "end": end, "method": method,
                             "text": _display(text[start:end]),
                             "speaker": _display(q.get("speaker") or "")[:60]})
        hits.append({
            "doc_id": doc_id, "seq": seq, "project": project, "year": year,
            "path": path, "rank": round(rank, 4),
            "snippet": _display(snip)[:snippet_chars],
            "carded": row is not None,
            "verbatim": verbatim, "unlocated_quotes": unlocated,
            "reading": {
                "topics": [_display(t) for t in card.get("topics", [])],
                "entities": [_display(e.get("name") or "")
                             for e in card.get("entities", [])],
                "claims": [_display(f"{c.get('subject')} {c.get('predicate')} "
                                    f"{c.get('object') or ''}").strip()
                           for c in card.get("claims", [])],
            } if row is not None else None,
        })
    return {"terms": terms, "hits": hits, "n": len(hits)}


def render(report: dict[str, Any]) -> str:
    """Plain-text, two registers kept visibly apart."""
    out = [f'query: {report["terms"]}  ({report["n"]} hit'
           f'{"" if report["n"] == 1 else "s"})']
    if not report["hits"]:
        out.append("  (no chunk in this catalog matches)")
    for h in report["hits"]:
        out.append("")
        out.append(f'  {h["project"]} / {h["year"]} / {h["path"]}'
                   f'  [{h["doc_id"][:10]}:{h["seq"]}]')
        out.append(f'    match: {h["snippet"]}')
        if not h["carded"]:
            out.append("    (chunk indexed but not carded — no reading yet)")
            continue
        for v in h["verbatim"]:
            who = f'{v["speaker"]}: ' if v["speaker"] else ""
            out.append(f'    VERBATIM [{v["start"]}:{v["end"]}] {who}"{v["text"]}"')
        if h["unlocated_quotes"]:
            out.append(f'    ({h["unlocated_quotes"]} quoted line'
                       f'{"" if h["unlocated_quotes"] == 1 else "s"} could NOT be '
                       f'located in the Tape — withheld, never shown as verbatim)')
        r = h["reading"]
        if r["topics"]:
            out.append(f'    READING topics: {", ".join(r["topics"][:8])}')
        if r["entities"]:
            out.append(f'    READING entities: {", ".join(x for x in r["entities"][:8] if x)}')
        for c in r["claims"][:3]:
            out.append(f"    READING claim: {c}")
    return "\n".join(out)
