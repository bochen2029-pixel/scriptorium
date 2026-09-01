"""The tape text-offset sidecar: a derived, append-aware, regenerable index
that makes chunk reads seek-sized instead of loading the corpus into RAM."""

import json
import unicodedata

from conftest import fresh_dir
from tape import Tape
from textindex import TextIndex, TextReader


def chunk_text(i: int, prefix: str = "chunk") -> str:
    """Defined ONCE and used by both the writer and the assertions: the reader
    must return exactly the bytes the Tape stored, so a test that retypes the
    literal can drift by Unicode normalization alone (it did: an editor
    recomposed cafe+U+0301 into U+00E9 and the comparison broke while the
    index was perfectly correct)."""
    return unicodedata.normalize("NFD", f"{prefix} number {i} — café 中文")


def add_text(tape, doc_id, seq, text):
    tape.append("text", {"doc_id": doc_id, "seq": seq, "text": text,
                         "chars": len(text), "meta": {"unit": seq}})


def build(arch, n=5, prefix="chunk"):
    tape = Tape.open(arch)
    for i in range(n):
        add_text(tape, f"d{i:031d}", 0, chunk_text(i, prefix))
        tape.append("journal", {"event": "noise", "i": i})   # interleaved kinds
    tape.close()


def test_index_serves_exact_text_and_refuses_unknown_keys():
    arch = fresh_dir("textindex-basic")
    build(arch, n=4)
    with TextReader(arch) as r:
        assert r.stats["indexed"] == 4 and r.stats["added"] == 4
        for i in range(4):
            got = r.get(f"d{i:031d}", 0)
            assert got == chunk_text(i)                    # bytes intact
        assert r.get("d" + "9" * 31, 0) is None               # unknown doc
        assert r.get(f"d{0:031d}", 7) is None                 # unknown seq
        many = r.get_many([(f"d{i:031d}", 0) for i in range(4)]
                          + [("ghost", 0)])
        assert len(many) == 4 and ("ghost", 0) not in many


def test_index_is_append_aware_not_rebuilt():
    """The tape only grows: a second ensure() indexes ONLY the new records."""
    arch = fresh_dir("textindex-append")
    build(arch, n=3)
    idx = TextIndex(arch)
    first = idx.ensure()
    again = idx.ensure()
    idx.close()
    assert first["added"] == 3
    assert again["added"] == 0 and again["indexed"] == 3

    tape = Tape.open(arch)                     # append two more records
    add_text(tape, "d" + "a" * 31, 0, "late arrival one")
    add_text(tape, "d" + "b" * 31, 0, "late arrival two")
    tape.close()

    with TextReader(arch) as r:
        assert r.stats["added"] == 2 and r.stats["indexed"] == 5
        assert r.get("d" + "b" * 31, 0) == "late arrival two"
        assert r.get(f"d{0:031d}", 0) == chunk_text(0)   # old rows intact


def test_index_matches_fetch_texts_exactly():
    """Same answers as the load-everything path it replaces."""
    from discover import fetch_texts

    arch = fresh_dir("textindex-parity")
    build(arch, n=6)
    keys = {(f"d{i:031d}", 0) for i in range(6)}
    eager = fetch_texts(arch, keys)
    with TextReader(arch) as r:
        lazy = r.get_many(keys)
    assert lazy == eager and len(lazy) == 6


def test_stale_offset_is_refused_never_guessed():
    """If an offset points at the wrong record the reader must return None,
    not hand back some other chunk's text."""
    arch = fresh_dir("textindex-stale")
    build(arch, n=3)
    idx = TextIndex(arch)
    idx.ensure()
    good = idx.db.execute("SELECT seg, off FROM offsets WHERE doc_id=?",
                          (f"d{0:031d}",)).fetchone()
    other = idx.db.execute("SELECT off FROM offsets WHERE doc_id=?",
                           (f"d{2:031d}",)).fetchone()
    idx.db.execute("UPDATE offsets SET off=? WHERE doc_id=?",
                   (other[0], f"d{0:031d}"))       # point doc0 at doc2's record
    idx.db.commit()
    idx.close()

    with TextReader(arch) as r:
        assert r.get(f"d{0:031d}", 0) is None       # refuses the mismatch
        assert r.get(f"d{2:031d}", 0) == chunk_text(2)
    assert good[0]


def test_index_is_regenerable_from_the_tape():
    """It is a cache: delete it and the same answers come back."""
    arch = fresh_dir("textindex-regen")
    build(arch, n=3)
    with TextReader(arch) as r:
        before = r.get_many([(f"d{i:031d}", 0) for i in range(3)])
    (arch / "tape" / "text_offsets.sqlite").unlink()
    with TextReader(arch) as r:
        assert r.stats["added"] == 3               # rebuilt from one pass
        assert r.get_many([(f"d{i:031d}", 0) for i in range(3)]) == before


def test_torn_tail_beyond_the_checkpoint_is_not_indexed():
    """tape.lock's count is the truth: bytes past it are a killed writer's
    leftovers and must never become servable records."""
    arch = fresh_dir("textindex-torn")
    build(arch, n=2)
    seg = next((arch / "tape" / "segments").glob("seg-*.jsonl"))
    with open(seg, "a", encoding="utf-8") as f:     # append an unaccounted line
        f.write(json.dumps({"kind": "text", "body": {
            "doc_id": "d" + "f" * 31, "seq": 0, "text": "ghost record"}}) + "\n")

    with TextReader(arch) as r:
        assert r.get("d" + "f" * 31, 0) is None
        assert r.stats["indexed"] == 2
