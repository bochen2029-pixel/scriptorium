"""The Tape: append-only, hash-chained JSONL truth layer (spec section 3).

Layout under an *archive root* (operator-chosen, never inside C:\\scriptorium):

    <archive_root>/
      manifest.yaml
      tape/segments/seg-000001.jsonl ...
      tape/tape.lock
      runs/<run_id>/journal.jsonl        (driver checkpoints; not part of the chain)

Each segment line is one record:

    {"i": int, "kind": "doc|text|journal|contact", "ts": iso-utc, "body": {...}, "h": hex32}

"h" = blake2b-128 over ascii(prev_h) || CANON-JSON(record minus "h"); genesis prev "0"*32.

tape.lock is a JSON checkpoint (atomic replace); the segments are the truth. Boot
reconciles the two:
  - complete, verifying lines beyond the lock's acknowledged tail -> rolled forward
    (they were fsync'd but the crash landed before the lock update);
  - a final line that fails to parse or verify -> torn tail -> truncated (at most one
    line, by contract) and journaled as a `tape_repair` record;
  - any failure before the final line -> TapeCorruption; no repair is attempted.

Appends are batched: append_many() writes all lines in one os.write, fsyncs, then
checkpoints the lock. A crash can therefore lose only an unacknowledged tail, which
resume re-derives (intake commits one file per batch, doc record last).
"""

from __future__ import annotations

import io
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from canon import GENESIS, chain_hash

KINDS = ("doc", "text", "journal", "contact")
SEGMENT_MAX_BYTES_DEFAULT = 64 * 1024 * 1024


class TapeError(Exception):
    pass


class TapeCorruption(TapeError):
    """The chain fails somewhere torn-tail repair is not allowed to touch."""


@dataclass
class VerifyReport:
    ok: bool
    count: int
    head: str
    segments: int
    error: str | None = None
    bad_index: int | None = None

    def summary(self) -> str:
        if self.ok:
            return f"tape OK: {self.count} records, {self.segments} segments, head {self.head}"
        return f"tape CORRUPT at record {self.bad_index}: {self.error}"


@dataclass
class _Segment:
    name: str
    first_i: int
    count: int
    tail_h: str
    bytes: int

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "first_i": self.first_i, "count": self.count,
                "tail_h": self.tail_h, "bytes": self.bytes}


@dataclass
class Tape:
    root: Path                      # archive root
    head: str = GENESIS
    count: int = 0
    segments: list[_Segment] = field(default_factory=list)
    segment_max_bytes: int = SEGMENT_MAX_BYTES_DEFAULT
    repairs: list[str] = field(default_factory=list)   # boot-repair notes, journaled by caller
    _fh: io.BufferedWriter | None = None

    # -- paths ------------------------------------------------------------
    @property
    def tape_dir(self) -> Path:
        return self.root / "tape"

    @property
    def seg_dir(self) -> Path:
        return self.tape_dir / "segments"

    @property
    def lock_path(self) -> Path:
        return self.tape_dir / "tape.lock"

    def _seg_path(self, name: str) -> Path:
        return self.seg_dir / name

    # -- open / boot ------------------------------------------------------
    @classmethod
    def open(cls, archive_root: str | Path,
             segment_max_bytes: int = SEGMENT_MAX_BYTES_DEFAULT) -> Tape:
        t = cls(root=Path(archive_root), segment_max_bytes=segment_max_bytes)
        t.seg_dir.mkdir(parents=True, exist_ok=True)
        t._load_lock()
        t._boot_reconcile()
        return t

    def _load_lock(self) -> None:
        if not self.lock_path.exists():
            return
        data = json.loads(self.lock_path.read_text("utf-8"))
        self.head = data["head"]
        self.count = data["count"]
        self.segments = [_Segment(**s) for s in data["segments"]]
        self.segment_max_bytes = data.get("segment_max_bytes", self.segment_max_bytes)

    def _boot_reconcile(self) -> None:
        """Verify the tail of the tape against the lock; roll forward or repair."""
        on_disk = sorted(p.name for p in self.seg_dir.glob("seg-*.jsonl"))
        known = [s.name for s in self.segments]
        if known != on_disk[: len(known)]:
            raise TapeCorruption(
                f"segment files {on_disk} do not extend the lock's list {known}")
        # Segments to scan: the last acknowledged one (its tail may have grown or torn)
        # plus any segment files the lock has never seen.
        scan: list[str] = ([known[-1]] if known else []) + on_disk[len(known):]
        for idx, name in enumerate(scan):
            is_last_file = idx == len(scan) - 1
            self._scan_segment(name, is_last_file)

    def _scan_segment(self, name: str, is_last_file: bool) -> None:
        """Verify one segment from its lock-acknowledged prefix to its physical end."""
        path = self._seg_path(name)
        seg = next((s for s in self.segments if s.name == name), None)
        if seg is None:
            prev_seg_tail = self.segments[-1].tail_h if self.segments else GENESIS
            seg = _Segment(name=name, first_i=self.count, count=0,
                           tail_h=prev_seg_tail, bytes=0)
            self.segments.append(seg)
        acked_lines = seg.count
        raw = path.read_bytes()
        lines = raw.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()          # trailing newline -> empty final element
        if len(lines) < acked_lines:
            raise TapeCorruption(
                f"{name}: {len(lines)} lines on disk < {acked_lines} acknowledged")
        # Recompute the chain across the acknowledged prefix (cheap: last segment only).
        prev = self._prev_of_segment(seg)
        offset = 0
        for n, line in enumerate(lines):
            beyond_ack = n >= acked_lines
            rec, err = self._parse_verify(line, prev, expect_i=seg.first_i + n)
            if rec is None:
                last_line = n == len(lines) - 1
                if beyond_ack and last_line and is_last_file:
                    # Torn tail: truncate this one line, journal the repair.
                    with open(path, "r+b") as f:
                        f.truncate(offset)
                        f.flush()
                        os.fsync(f.fileno())
                    self.repairs.append(
                        f"torn tail truncated: {name} line {n} ({len(line)} bytes): {err}")
                    break
                raise TapeCorruption(f"{name} line {n}: {err}")
            prev = rec["h"]
            offset += len(line) + 1
            if beyond_ack:      # fsync'd but unacknowledged -> roll forward
                seg.count += 1
                seg.tail_h = rec["h"]
                seg.bytes = offset
                self.count = seg.first_i + seg.count
                self.head = rec["h"]
        if seg.count == 0 and seg.bytes == 0:
            seg.bytes = 0
        self._write_lock()

    def _prev_of_segment(self, seg: _Segment) -> str:
        i = self.segments.index(seg)
        return self.segments[i - 1].tail_h if i > 0 else GENESIS

    @staticmethod
    def _parse_verify(line: bytes, prev: str, expect_i: int
                      ) -> tuple[dict[str, Any] | None, str | None]:
        try:
            rec = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return None, f"unparseable: {e}"
        if not isinstance(rec, dict) or "h" not in rec:
            return None, "not a record object"
        h = rec.get("h")
        body = {k: v for k, v in rec.items() if k != "h"}
        try:
            want = chain_hash(prev, body)
        except Exception as e:                      # noqa: BLE001 - typed into report
            return None, f"unhashable: {e}"
        if h != want:
            return None, f"hash mismatch (stored {h}, computed {want})"
        if rec.get("i") != expect_i:
            return None, f"index mismatch (stored {rec.get('i')}, expected {expect_i})"
        return rec, None

    # -- append -----------------------------------------------------------
    def append(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.append_many([(kind, body)])[0]

    def append_many(self, items: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """Append records as one write + one fsync + one lock checkpoint."""
        if not items:
            return []
        recs: list[dict[str, Any]] = []
        blob = bytearray()
        prev = self.head
        i = self.count
        ts = datetime.now(UTC).isoformat(timespec="milliseconds")
        for kind, body in items:
            if kind not in KINDS:
                raise TapeError(f"unknown record kind {kind!r}")
            core = {"i": i, "kind": kind, "ts": ts, "body": body}
            h = chain_hash(prev, core)
            rec = {**core, "h": h}
            line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
            blob += line.encode("utf-8") + b"\n"
            recs.append(rec)
            prev = h
            i += 1
        seg = self._writable_segment()
        fh = self._open_segment(seg)
        fh.write(bytes(blob))
        fh.flush()
        os.fsync(fh.fileno())
        seg.count += len(recs)
        seg.tail_h = recs[-1]["h"]
        seg.bytes += len(blob)
        self.count = i
        self.head = prev
        self._write_lock()
        return recs

    def _writable_segment(self) -> _Segment:
        if self.segments and self.segments[-1].bytes < self.segment_max_bytes:
            return self.segments[-1]
        if self._fh:
            self._fh.close()
            self._fh = None
        name = f"seg-{len(self.segments) + 1:06d}.jsonl"
        seg = _Segment(name=name, first_i=self.count, count=0,
                       tail_h=self.head, bytes=0)
        self.segments.append(seg)
        self._seg_path(name).touch()
        return seg

    def _open_segment(self, seg: _Segment) -> io.BufferedWriter:
        if self._fh is None or Path(self._fh.name).name != seg.name:
            if self._fh:
                self._fh.close()
            self._fh = open(self._seg_path(seg.name), "ab")
        return self._fh

    def _write_lock(self) -> None:
        data = {"head": self.head, "count": self.count,
                "segment_max_bytes": self.segment_max_bytes,
                "segments": [s.to_json() for s in self.segments]}
        tmp = self.lock_path.with_suffix(".lock.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        # Windows: replace is denied while a concurrent reader (e.g. `status`)
        # holds the destination open without FILE_SHARE_DELETE. Transient — retry
        # bounded, then let the real error through.
        for attempt in range(40):
            try:
                os.replace(tmp, self.lock_path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    # -- read / verify ----------------------------------------------------
    def iter_records(self, kinds: tuple[str, ...] | None = None) -> Iterator[dict[str, Any]]:
        """Stream records in order (no hash re-verification; use verify() for that)."""
        for seg in self.segments:
            with open(self._seg_path(seg.name), "rb") as f:
                for n, line in enumerate(f):
                    if n >= seg.count:
                        break
                    rec = json.loads(line.decode("utf-8"))
                    if kinds is None or rec["kind"] in kinds:
                        yield rec

    def verify(self) -> VerifyReport:
        """Recompute the whole chain from genesis; the falsifier-(b) gate."""
        prev = GENESIS
        n_total = 0
        for seg in self.segments:
            with open(self._seg_path(seg.name), "rb") as f:
                for n, line in enumerate(f):
                    if n >= seg.count:
                        break
                    rec, err = self._parse_verify(line.rstrip(b"\n"), prev, expect_i=n_total)
                    if rec is None:
                        return VerifyReport(ok=False, count=n_total, head=prev,
                                            segments=len(self.segments),
                                            error=err, bad_index=n_total)
                    prev = rec["h"]
                    n_total += 1
        ok = n_total == self.count and prev == self.head
        err = None if ok else (
            f"lock disagrees with chain: lock count={self.count} head={self.head}, "
            f"chain count={n_total} head={prev}")
        return VerifyReport(ok=ok, count=n_total, head=prev,
                            segments=len(self.segments), error=err,
                            bad_index=None if ok else n_total)


def verify_tape(archive_root: str | Path) -> VerifyReport:
    """Module-level convenience: open (with boot reconcile) and fully verify."""
    t = Tape.open(archive_root)
    try:
        return t.verify()
    finally:
        t.close()
