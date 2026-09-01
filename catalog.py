"""catalog.py — the catalog's files, in one place.

The P2 catalog is a few append-only artifacts under <archive>/catalog/cards/:
cards.jsonl (one row per read chunk), quarantine.jsonl (typed refusals), and
the derived sidecars written beside them. Six call sites used to parse
cards.jsonl with six ideas of what a torn line or a duplicated key means.
This module is the one definition:

- iter_rows(path): tolerant JSONL — a torn tail (a killed writer) or a foreign
  line is skipped, never fatal; every yielded row carries doc_id + seq.
- CardStore: the writer (fsync'd batches; heals a torn tail before appending
  so a killed batch can never glue itself onto the next one) and the resume
  law's done_keys.
- CardsReader: random access by (doc_id, seq) through a derived, append-aware
  offset index, so fetching ten cards from a 27,000-card catalog is a handful
  of seeks, not a 135 MB parse. Last write wins for a duplicated key (a
  --retry-quarantined rerun supersedes) — the same verdict a full scan gives.
  Derived and regenerable; a stale offset is detected on read (the row's own
  key is checked) and the index rebuilt once, never trusted blindly.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

OFFSETS_NAME = "cards_offsets.sqlite"


def iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Every parseable keyed row of a catalog JSONL, in file order."""
    if not path.exists():
        return
    with open(path, "rb") as f:
        for line in f:
            try:
                row = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue                  # torn tail / foreign line: skip
            if isinstance(row, dict) and "doc_id" in row and "seq" in row:
                yield row


class CardStore:
    """Append-only cards + quarantine JSONL with fsync'd batch writes."""

    def __init__(self, cards_dir: Path):
        cards_dir.mkdir(parents=True, exist_ok=True)
        self.cards_path = cards_dir / "cards.jsonl"
        self.quar_path = cards_dir / "quarantine.jsonl"

    def done_keys(self, *, include_quarantined: bool = True) -> set[tuple[str, int]]:
        """Resume law: skip keys already present. include_quarantined=False is
        the --retry-quarantined mode — quarantined keys become todo again; a
        key later appearing in BOTH files means resolved-on-retry (cards.jsonl
        wins; quarantine.jsonl is append-only history)."""
        paths = ((self.cards_path, self.quar_path) if include_quarantined
                 else (self.cards_path,))
        return {(row["doc_id"], row["seq"]) for p in paths for row in iter_rows(p)}

    def append_batch(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        blob = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        with open(path, "ab") as f:
            # A killed writer can leave a partial last line. Appending straight
            # after it would glue this batch's first row onto the garbage and
            # lose a paid card; terminate the torn line first so it stays its
            # own skippable line and every new row is intact.
            if f.tell() and not _ends_with_newline(path):
                f.write(b"\n")
            f.write(blob.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())


def _ends_with_newline(path: Path) -> bool:
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) == b"\n"


class CardsReader:
    """Offset-indexed random access over cards.jsonl (derived sidecar)."""

    def __init__(self, archive_root: str | Path):
        self.root = Path(archive_root)
        self.path = self.root / "catalog" / "cards" / "cards.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path.parent / OFFSETS_NAME)
        self.db.executescript(
            "PRAGMA journal_mode=WAL;"
            "CREATE TABLE IF NOT EXISTS offsets("
            " doc_id TEXT, seq INT, off INT, PRIMARY KEY(doc_id, seq));"
            "CREATE TABLE IF NOT EXISTS progress("
            " id INT PRIMARY KEY, bytes INT, size INT);")
        self._fh: Any = None
        self.stats = self._ensure()

    # -- build ---------------------------------------------------------------
    def _ensure(self) -> dict[str, int]:
        if not self.path.exists():
            return {"indexed": 0, "added": 0}
        size = self.path.stat().st_size
        row = self.db.execute("SELECT bytes, size FROM progress WHERE id=1").fetchone()
        done = row[0] if row else 0
        if row and size < row[1]:
            # the file shrank: it was rewritten, not appended — start over
            self.db.execute("DELETE FROM offsets")
            done = 0
        added = 0
        with open(self.path, "rb") as f:
            f.seek(done)
            off = done
            while True:
                line = f.readline()        # readline keeps offsets exact
                if not line:
                    break
                complete = line.endswith(b"\n")
                try:
                    rec = json.loads(line.decode("utf-8"))
                    self.db.execute(
                        "INSERT OR REPLACE INTO offsets VALUES(?,?,?)",
                        (rec["doc_id"], rec["seq"], off))
                    added += 1
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
                    pass                   # torn or foreign line: skip
                if not complete:
                    # A final line without its newline is indexed if it parses
                    # (iter_rows yields it too — the two parsers must agree)
                    # but progress stays BEFORE it, so a writer completing or
                    # healing that line gets it re-indexed next time.
                    break
                off += len(line)
        self.db.execute("INSERT OR REPLACE INTO progress VALUES(1,?,?)", (off, size))
        self.db.commit()
        n = self.db.execute("SELECT COUNT(*) FROM offsets").fetchone()[0]
        return {"indexed": n, "added": added}

    def _rebuild(self) -> None:
        self.db.execute("DELETE FROM offsets")
        self.db.execute("DELETE FROM progress")
        self.db.commit()
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self.stats = self._ensure()

    # -- read ----------------------------------------------------------------
    def _read_at(self, off: int) -> dict[str, Any] | None:
        if self._fh is None:
            if not self.path.exists():
                return None
            self._fh = open(self.path, "rb")
        self._fh.seek(off)
        line = self._fh.readline()
        if not line:
            return None
        try:
            rec = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return rec if isinstance(rec, dict) else None

    def get(self, doc_id: str, seq: int) -> dict[str, Any] | None:
        for attempt in (0, 1):
            row = self.db.execute(
                "SELECT off FROM offsets WHERE doc_id=? AND seq=?",
                (doc_id, seq)).fetchone()
            if row is None:
                return None
            rec = self._read_at(row[0])
            if rec is not None and rec.get("doc_id") == doc_id and rec.get("seq") == seq:
                return rec
            if attempt == 0:
                self._rebuild()            # stale offset: the file was rewritten
        return None

    def get_many(self, keys: Iterable[tuple[str, int]]
                 ) -> dict[tuple[str, int], dict[str, Any]]:
        out: dict[tuple[str, int], dict[str, Any]] = {}
        for doc_id, seq in keys:
            rec = self.get(doc_id, seq)
            if rec is not None:
                out[(doc_id, seq)] = rec
        return out

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self.db.commit()
        self.db.close()

    def __enter__(self) -> CardsReader:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
