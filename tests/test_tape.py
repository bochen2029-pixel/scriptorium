"""Tape falsifiers: chain integrity (b), torn-tail repair, crash roll-forward."""

import json
import shutil

import pytest

from canon import chain_hash
from tape import Tape, TapeCorruption, verify_tape


def make_tape(root, n=10):
    t = Tape.open(root)
    for k in range(n):
        t.append("journal", {"event": "test", "k": k})
    t.close()
    return t


def test_append_reopen_verify(tmp_path):
    make_tape(tmp_path / "a", n=10)
    t = Tape.open(tmp_path / "a")
    assert t.count == 10
    rep = t.verify()
    assert rep.ok, rep.summary()
    recs = list(t.iter_records())
    assert [r["i"] for r in recs] == list(range(10))
    t.close()


def test_append_many_batch(tmp_path):
    t = Tape.open(tmp_path / "a")
    recs = t.append_many([("text", {"seq": i, "text": "x" * 10}) for i in range(50)])
    assert len(recs) == 50
    t.append("doc", {"doc_id": "d1"})
    assert t.verify().ok
    t.close()


def test_falsifier_b_corrupt_one_byte(tmp_path):
    """Spec section 7 S0 falsifier (b): corrupt one byte in a copy, verify catches."""
    make_tape(tmp_path / "a", n=20)
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    seg = tmp_path / "b" / "tape" / "segments" / "seg-000001.jsonl"
    raw = bytearray(seg.read_bytes())
    # flip one byte inside a middle record's body (not the last line)
    target = raw.index(b'"k":5')
    raw[target + 4] ^= 0x01
    seg.write_bytes(bytes(raw))
    with pytest.raises(TapeCorruption):
        verify_tape(tmp_path / "b")


def test_corruption_in_older_segment_caught_by_full_verify(tmp_path):
    t = Tape.open(tmp_path / "a", segment_max_bytes=512)
    for k in range(30):
        t.append("journal", {"event": "test", "k": k})
    assert len(t.segments) > 2
    t.close()
    first = tmp_path / "a" / "tape" / "segments" / "seg-000001.jsonl"
    raw = bytearray(first.read_bytes())
    raw[raw.index(b'"k":1')] ^= 0x01
    first.write_bytes(bytes(raw))
    # boot only scans the tail, so open succeeds...
    t = Tape.open(tmp_path / "a")
    # ...but the full verify (the certificate-side check) catches it.
    rep = t.verify()
    assert not rep.ok
    assert rep.bad_index is not None
    t.close()


def test_torn_tail_truncated_and_reported(tmp_path):
    make_tape(tmp_path / "a", n=5)
    seg = tmp_path / "a" / "tape" / "segments" / "seg-000001.jsonl"
    with open(seg, "ab") as f:
        f.write(b'{"i":5,"kind":"journal","ts":"x","body":{"tr')  # torn write
    t = Tape.open(tmp_path / "a")
    assert t.count == 5
    assert len(t.repairs) == 1
    assert "torn tail" in t.repairs[0]
    assert t.verify().ok
    # tape is writable after repair
    t.append("journal", {"event": "after-repair"})
    assert t.verify().ok
    t.close()


def test_crash_between_fsync_and_lock_rolls_forward(tmp_path):
    t = make_tape(tmp_path / "a", n=3)
    head, count = t.head, t.count
    # hand-craft a valid record fsync'd to the segment but never acknowledged in the lock
    core = {"i": count, "kind": "journal", "ts": "2026-07-31T00:00:00.000+00:00",
            "body": {"event": "unacked"}}
    rec = {**core, "h": chain_hash(head, core)}
    seg = tmp_path / "a" / "tape" / "segments" / "seg-000001.jsonl"
    with open(seg, "ab") as f:
        f.write(json.dumps(rec, separators=(",", ":")).encode() + b"\n")
    t2 = Tape.open(tmp_path / "a")
    assert t2.count == count + 1          # rolled forward, not lost, not duplicated
    assert t2.head == rec["h"]
    assert t2.verify().ok
    assert not t2.repairs
    t2.close()


def test_corrupt_acknowledged_tail_refuses_repair(tmp_path):
    """A bad line inside the acknowledged region is corruption, never 'repaired'."""
    make_tape(tmp_path / "a", n=5)
    seg = tmp_path / "a" / "tape" / "segments" / "seg-000001.jsonl"
    raw = bytearray(seg.read_bytes())
    raw[raw.index(b'"k":4')] ^= 0x01      # last acked record
    seg.write_bytes(bytes(raw))
    with pytest.raises(TapeCorruption):
        Tape.open(tmp_path / "a")


def test_segment_roll_preserves_order_and_chain(tmp_path):
    t = Tape.open(tmp_path / "a", segment_max_bytes=256)
    for k in range(40):
        t.append("journal", {"event": "roll", "k": k})
    assert len(t.segments) >= 3
    assert [r["body"]["k"] for r in t.iter_records()] == list(range(40))
    assert t.verify().ok
    t.close()
    t2 = Tape.open(tmp_path / "a", segment_max_bytes=256)
    t2.append("journal", {"event": "again"})
    assert t2.verify().ok
    t2.close()
