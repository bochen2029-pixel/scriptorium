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

import re
import sqlite3
from pathlib import Path
from typing import Any

from catalog import CardsReader, iter_rows
from spancheck import locate
from textindex import TextReader

# archives carry terminal captures: ANSI colour and control bytes are part of
# the Tape's honest bytes, but they must never reach a console verbatim (they
# would repaint the operator's terminal and could hide text)
_CTRL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|[\x00-\x08\x0b-\x1f\x7f]")


def _display(s: str) -> str:
    return _CTRL.sub("", (s or "").replace("\n", " ").replace("\t", " "))


class QueryError(Exception):
    pass


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
    sql = ("SELECT m.doc_id, m.seq, bm25(chunks_fts) AS rank,"
           "       snippet(chunks_fts, 0, '[', ']', ' ... ', 12) AS snip "
           "FROM chunks_fts f JOIN fts_map m ON m.fts_rowid = f.rowid "
           "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?")
    matched_as = "expression"
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            rows = db.execute(sql, (terms, limit)).fetchall()
        except sqlite3.OperationalError as first:
            # FTS5 reads a hyphen as NOT and `a-b` as a column filter, so an
            # ordinary term like C--FERRYMAN or fence-check "fails". Retry the
            # whole input as ONE literal phrase and say so in the report.
            phrase = '"' + terms.replace('"', '""') + '"'
            try:
                rows = db.execute(sql, (phrase, limit)).fetchall()
                matched_as = "phrase"
            except sqlite3.OperationalError:
                raise QueryError(f"bad query {terms!r}: {first}") from first
        meta = {}
        for doc_id, seq, _r, _s in rows:
            got = db.execute("SELECT project, year, path FROM chunks "
                             "WHERE doc_id=? AND seq=?", (doc_id, seq)).fetchone()
            meta[(doc_id, seq)] = got or ("?", 0, "?")
    finally:
        db.close()

    keys = [(d, s) for d, s, _r, _sn in rows]
    with CardsReader(root) as cr:          # seeks, not a whole-catalog parse
        cards = cr.get_many(keys)
    with TextReader(root) as tr:           # seeks, not a tape pass
        texts = tr.get_many(keys) if keys else {}

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
    return {"terms": terms, "matched_as": matched_as, "hits": hits, "n": len(hits)}


def summary(archive_root: str | Path, top: int = 12) -> dict[str, Any]:
    """What is actually in this catalog — deterministic aggregation over
    cards.jsonl + quarantine.jsonl + index.sqlite. No LLM, no Tape pass.
    Answers the question a 13,000-card catalog otherwise can't: what did the
    reading find, where is it thin, and what refused to be read."""
    root = Path(archive_root)
    cards_dir = root / "catalog" / "cards"
    cards_path = cards_dir / "cards.jsonl"
    if not cards_path.exists():
        raise QueryError(f"no cards at {cards_path} — run `read` first")

    from collections import Counter
    projects: Counter[str] = Counter()
    years: Counter[int] = Counter()
    topics: Counter[str] = Counter()
    entities: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    models: Counter[str] = Counter()
    charter_roots: Counter[str] = Counter()
    n_cards = n_quotes = n_claims = 0
    keys: set[tuple[str, int]] = set()
    for row in iter_rows(cards_path):
        card = row.get("card")
        if not isinstance(card, dict):
            continue
        key = (row["doc_id"], row["seq"])
        if key in keys:
            continue                          # resume/rerun overlap: count once
        keys.add(key)
        n_cards += 1
        n_quotes += len(card.get("quotes", []))
        n_claims += len(card.get("claims", []))
        for t in card.get("topics", []):
            topics[_display(t)] += 1
        for e in card.get("entities", []):
            if e.get("name"):
                entities[_display(e["name"])] += 1
                kinds[e.get("kind") or "other"] += 1
        fp = row.get("fp") or {}
        if fp.get("model"):
            models[fp["model"]] += 1
        if fp.get("charter_root"):
            charter_roots[fp["charter_root"]] += 1

    quar: Counter[str] = Counter()
    n_quar = 0
    for row in iter_rows(cards_dir / "quarantine.jsonl"):
        n_quar += 1
        quar[str(row.get("reason", "?")).split(":")[0][:60]] += 1

    index: dict[str, int | None] = {}
    db_path = root / "catalog" / "index.sqlite"
    if db_path.exists():
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for name, q in (("chunks", "SELECT COUNT(*) FROM chunks"),
                            ("fts", "SELECT COUNT(*) FROM chunks_fts"),
                            ("vectors", "SELECT COUNT(*) FROM vectors")):
                try:
                    index[name] = db.execute(q).fetchone()[0]
                except sqlite3.Error:
                    index[name] = None      # absent table: unknown, NOT zero —
                                            # a sentinel must never reach a
                                            # derived number below
            for doc_id, seq in keys:
                got = db.execute("SELECT project, year FROM chunks "
                                 "WHERE doc_id=? AND seq=?",
                                 (doc_id, seq)).fetchone()
                if got:
                    projects[got[0] or "?"] += 1
                    years[got[1] or 0] += 1
        finally:
            db.close()

    return {
        "archive": str(root), "cards": n_cards, "quarantined": n_quar,
        "quotes": n_quotes, "claims": n_claims,
        "quotes_per_card": round(n_quotes / n_cards, 2) if n_cards else 0,
        "claims_per_card": round(n_claims / n_cards, 2) if n_cards else 0,
        "index": index,
        "vectors_missing": (max(0, n_cards - index["vectors"])
                            if isinstance(index.get("vectors"), int) else None),
        "models": dict(models), "charter_roots": dict(charter_roots),
        "projects": projects.most_common(top),
        "years": sorted(years.items()),
        "topics": topics.most_common(top),
        "entities": entities.most_common(top),
        "entity_kinds": dict(kinds),
        "quarantine_reasons": quar.most_common(top),
    }


def render_summary(s: dict[str, Any]) -> str:
    out = [f'catalog: {s["archive"]}',
           f'  {s["cards"]} cards, {s["quarantined"]} quarantined | '
           f'{s["quotes"]} quotes ({s["quotes_per_card"]}/card), '
           f'{s["claims"]} claims ({s["claims_per_card"]}/card)']
    if s["index"]:
        shown = ", ".join(f'{"?" if v is None else v} {k}'
                          for k, v in s["index"].items())
        out.append(f"  index: {shown}"
                   + (f' ({s["vectors_missing"]} cards lack a vector — '
                      f'backfillable)' if s["vectors_missing"] else ""))
    if len(s["models"]) > 1:
        out.append(f'  WARNING mixed reader models: {s["models"]}')
    elif s["models"]:
        out.append(f'  read by: {", ".join(s["models"])}')
    if len(s["charter_roots"]) > 1:
        out.append(f'  WARNING mixed charter roots: {list(s["charter_roots"])}')

    def row(label, pairs):
        if pairs:
            out.append(f"  {label}: " + ", ".join(f"{k} ({n})" for k, n in pairs))

    row("projects", s["projects"])
    row("years", [(str(y), n) for y, n in s["years"]])
    row("topics", s["topics"])
    row("entities", s["entities"])
    if s["entity_kinds"]:
        out.append("  entity kinds: " + ", ".join(
            f"{k} ({n})" for k, n in sorted(s["entity_kinds"].items(),
                                            key=lambda kv: -kv[1])))
    row("quarantine reasons", s["quarantine_reasons"])
    return "\n".join(out)


def render(report: dict[str, Any]) -> str:
    """Plain-text, two registers kept visibly apart."""
    out = [f'query: {report["terms"]}  ({report["n"]} hit'
           f'{"" if report["n"] == 1 else "s"})']
    if report.get("matched_as") == "phrase":
        out.append('  (matched as ONE literal phrase — the input had FTS5 '
                   'syntax; use AND / OR / NOT or "quotes" for expressions)')
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
