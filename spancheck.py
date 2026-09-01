"""Span fence-check over P2 cards (the S2 gate's fence-checked-spans item;
P6's certify absorbs and extends this at S4). Deterministic, no LLM.

For every card quote: does tape_text[start:end] equal the quoted text?
  exact      — offsets and text both right (the fence's happy path)
  substring  — the words exist verbatim in the chunk, offsets wrong
  normalized — the words exist after whitespace collapsing (the model folds
               newlines/indentation inside quotes; words real, layout not)
  miss       — the quoted text is NOT in the chunk even normalized
               (fabrication or paraphrase-as-quote — the thing the fence
               exists to catch; these never ship as verbatim)
  no_offset  — the worker declined offsets (start=-1 per the contract's
               "use -1 rather than guessing"); presence-checked instead
Claim spans carry no text, so they are bounds-checked (0 <= start < end <= len).

A card whose chunk text cannot be fetched from the Tape is NOT scored: its
quotes would all read as fabrication and blame the model for a data problem
(wrong archive root, tape drift, a card from another catalog). Such cards are
counted in `cards_unfetchable` and excluded from every rate — the fence must
measure the reading, never the plumbing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from discover import fetch_texts

_WS = re.compile(r"\s+")


def _squash(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


def fence_check(archive_root: str | Path, limit: int | None = None) -> dict[str, Any]:
    root = Path(archive_root)
    cards_path = root / "catalog" / "cards" / "cards.jsonl"
    if not cards_path.exists():
        raise SystemExit(f"no cards at {cards_path} — run `read` first")
    rows: list[dict[str, Any]] = []
    with open(cards_path, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit:
        rows = rows[:limit]
    texts = fetch_texts(root, {(r["doc_id"], r["seq"]) for r in rows})

    q = {"exact": 0, "substring": 0, "normalized": 0, "miss": 0,
         "no_offset_hit": 0, "no_offset_norm": 0, "no_offset_miss": 0}
    c = {"valid": 0, "invalid": 0, "absent": 0}
    misses: list[dict[str, Any]] = []
    squashed: dict[tuple[str, int], str] = {}
    unfetchable: set[tuple[str, int]] = set()
    for row in rows:
        key = (row["doc_id"], row["seq"])
        text = texts.get(key)
        if text is None:
            unfetchable.add(key)          # plumbing, not fabrication — skip
            continue
        if key not in squashed:
            squashed[key] = _squash(text)
        sq_text = squashed[key]
        for quote in row["card"].get("quotes", []):
            qt = (quote.get("text") or "").strip()
            if not qt:
                continue
            start, end = quote.get("start", -1), quote.get("end", -1)
            if start < 0 or end <= start:
                if qt in text:
                    q["no_offset_hit"] += 1
                elif _squash(qt) in sq_text:
                    q["no_offset_norm"] += 1
                else:
                    q["no_offset_miss"] += 1
                    misses.append({"doc_id": row["doc_id"], "seq": row["seq"],
                                   "quote": qt[:80]})
                continue
            # offsets right = exact, whether or not the model included the
            # quote's surrounding whitespace in either the text or the span
            if text[start:end] == quote["text"] or text[start:end].strip() == qt:
                q["exact"] += 1
            elif qt in text:
                q["substring"] += 1
            elif _squash(qt) in sq_text:
                q["normalized"] += 1
            else:
                q["miss"] += 1
                misses.append({"doc_id": row["doc_id"], "seq": row["seq"],
                               "quote": qt[:80]})
        for claim in row["card"].get("claims", []):
            span = claim.get("span")
            if not span:
                c["absent"] += 1
                continue
            s, e = span.get("start", -1), span.get("end", -1)
            c["valid" if 0 <= s < e <= len(text) else "invalid"] += 1

    n_quotes = sum(q.values())
    verified = (q["exact"] + q["substring"] + q["normalized"]
                + q["no_offset_hit"] + q["no_offset_norm"])
    unlocated = q["miss"] + q["no_offset_miss"]
    return {
        "cards": len(rows) - len(unfetchable), "quotes": n_quotes, **q,
        "cards_unfetchable": len(unfetchable), "claims": c,
        "quote_verified_rate": round(verified / n_quotes, 4) if n_quotes else None,
        "quote_exact_rate": round(q["exact"] / n_quotes, 4) if n_quotes else None,
        "quote_unlocated_rate": round(unlocated / n_quotes, 4) if n_quotes else None,
        "sample_misses": misses[:10],
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(fence_check(sys.argv[1]), ensure_ascii=False, indent=1))
