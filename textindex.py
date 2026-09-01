"""textindex.py — random access to the Tape's text records.

P2 currently loads every selected chunk's text into RAM before the first card
(`discover.fetch_texts`). That is fine for a slice and wrong for a corpus: the
full v2 tape is 172M tokens, so a whole-archive read would hold roughly a
gigabyte of Python strings for hours, and it pays a full tape pass before any
card is written.

This is the parked "tape kind-index sidecar", built: ONE pass records the byte
offset of every text record, and reads become seek + readline. Properties that
matter:

- DERIVED, never authoritative. It lives beside the tape as a regenerable
  cache; deleting it costs one pass. The segments stay the truth (S0 law), and
  nothing here writes to them.
- APPEND-AWARE. The Tape is append-only, so an existing index is extended from
  where it stopped rather than rebuilt; a segment that somehow SHRANK (a torn
  tail the tape itself repairs) invalidates only that segment's rows.
- BOUNDED. `TextReader.get_many` fetches exactly the keys a batch needs.
- HONEST. A key the index cannot serve returns None rather than an empty
  string, so callers can tell "not in this Tape" from "empty chunk".
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tape import Tape

INDEX_NAME = "text_offsets.sqlite"


class TextIndex:
    """Offset index over `text` records: (doc_id, seq) -> (segment, byte offset)."""

    def __init__(self, archive_root: str | Path):
        self.root = Path(archive_root)
        self.path = self.root / "tape" / INDEX_NAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(
            "PRAGMA journal_mode=WAL;"
            "CREATE TABLE IF NOT EXISTS offsets("
            " doc_id TEXT, seq INT, seg TEXT, off INT,"
            " PRIMARY KEY(doc_id, seq));"
            "CREATE TABLE IF NOT EXISTS progress("
            " seg TEXT PRIMARY KEY, lines INT, bytes INT);")

    # -- build ---------------------------------------------------------------
    def ensure(self) -> dict[str, Any]:
        """Index whatever is not indexed yet. Returns {indexed, added, segments}."""
        tape = Tape.open(self.root)
        added = 0
        try:
            for seg in tape.segments:
                seg_path = tape.tape_dir / "segments" / seg.name
                if not seg_path.exists():
                    continue
                row = self.db.execute(
                    "SELECT lines, bytes FROM progress WHERE seg=?",
                    (seg.name,)).fetchone()
                done_lines, done_bytes = row if row else (0, 0)
                if done_lines > seg.count:
                    # the segment lost records (a torn tail the tape repaired):
                    # this segment's rows are untrustworthy — redo just it
                    self.db.execute("DELETE FROM offsets WHERE seg=?", (seg.name,))
                    done_lines, done_bytes = 0, 0
                if done_lines >= seg.count:
                    continue
                added += self._index_segment(seg_path, seg.name, seg.count,
                                             done_lines, done_bytes)
        finally:
            tape.close()
        self.db.commit()
        n = self.db.execute("SELECT COUNT(*) FROM offsets").fetchone()[0]
        return {"indexed": n, "added": added,
                "segments": self.db.execute(
                    "SELECT COUNT(*) FROM progress").fetchone()[0]}

    def _index_segment(self, seg_path: Path, name: str, limit: int,
                       done_lines: int, done_bytes: int) -> int:
        added = 0
        with open(seg_path, "rb") as f:
            f.seek(done_bytes)
            n = done_lines
            off = done_bytes
            while n < limit:
                line = f.readline()          # readline keeps offsets exact;
                if not line:                 # `for line in f` buffers and lies
                    break
                try:
                    rec = json.loads(line.decode("utf-8"))
                    if rec.get("kind") == "text":
                        b = rec["body"]
                        self.db.execute(
                            "INSERT OR REPLACE INTO offsets VALUES(?,?,?,?)",
                            (b["doc_id"], b["seq"], name, off))
                        added += 1
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                    pass                     # torn/foreign line: skip, keep going
                off += len(line)
                n += 1
            self.db.execute(
                "INSERT OR REPLACE INTO progress VALUES(?,?,?)", (name, n, off))
        return added

    def close(self) -> None:
        self.db.commit()
        self.db.close()


class TextReader:
    """Bounded-memory text access: build (or extend) the index once, then read
    only the chunks a caller actually asks for."""

    def __init__(self, archive_root: str | Path):
        self.root = Path(archive_root)
        self.index = TextIndex(self.root)
        self.stats = self.index.ensure()
        self._segdir = self.root / "tape" / "segments"
        self._open: dict[str, Any] = {}

    def get(self, doc_id: str, seq: int) -> str | None:
        row = self.index.db.execute(
            "SELECT seg, off FROM offsets WHERE doc_id=? AND seq=?",
            (doc_id, seq)).fetchone()
        if row is None:
            return None
        seg, off = row
        f = self._open.get(seg)
        if f is None:
            p = self._segdir / seg
            if not p.exists():
                return None
            f = self._open[seg] = open(p, "rb")
        f.seek(off)
        line = f.readline()
        if not line:
            return None
        try:
            rec = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        body = rec.get("body") or {}
        if rec.get("kind") != "text" or body.get("doc_id") != doc_id \
                or body.get("seq") != seq:
            return None                      # stale offset: refuse, never guess
        return body.get("text")

    def get_many(self, keys: Iterable[tuple[str, int]]
                 ) -> dict[tuple[str, int], str]:
        out: dict[tuple[str, int], str] = {}
        for doc_id, seq in keys:
            text = self.get(doc_id, seq)
            if text is not None:
                out[(doc_id, seq)] = text
        return out

    def close(self) -> None:
        for f in self._open.values():
            f.close()
        self._open.clear()
        self.index.close()

    def __enter__(self) -> TextReader:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
