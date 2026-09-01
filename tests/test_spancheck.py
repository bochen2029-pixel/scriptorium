"""The span fence: exact / substring / miss / no-offset classification, and
the DERIVED-span artifact (model offsets are never trusted)."""

import json

from conftest import fresh_dir
from spancheck import derive_spans, fence_check, locate
from tape import Tape

TEXT = "The negatives are forever. The fence certifies what the readers claim."


def make_catalog(arch, quotes, claims=()):
    tape = Tape.open(arch)
    doc_id = "d" + "0" * 31
    tape.append("text", {"doc_id": doc_id, "seq": 0, "text": TEXT,
                         "chars": len(TEXT), "meta": {"unit": 0}})
    tape.append("doc", {"doc_id": doc_id, "root": "r", "path": "a.md",
                        "source": "s", "content_b2": "c", "size": 1,
                        "mtime": "2026-01-01T00:00:00+00:00", "year": 2026,
                        "modality": "text", "extractor": {}, "n_texts": 1,
                        "chars": len(TEXT), "tokens_est": 20, "notes": [],
                        "minhash": None})
    tape.close()
    cards_dir = arch / "catalog" / "cards"
    cards_dir.mkdir(parents=True)
    row = {"doc_id": doc_id, "seq": 0,
           "card": {"quotes": quotes, "claims": list(claims)}}
    (cards_dir / "cards.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n", "utf-8")
    (arch / "manifest.yaml").write_text("roots:\n  - path: files\n", "utf-8")
    (arch / "files").mkdir()


def test_fence_classification():
    arch = fresh_dir("spancheck")
    make_catalog(arch, quotes=[
        {"text": "The negatives are forever.", "start": 0, "end": 26},   # exact
        {"text": "fence certifies", "start": 0, "end": 15},              # substring
        {"text": "words never written anywhere", "start": 5, "end": 33}, # miss
        {"text": "the readers claim", "start": -1, "end": -1},           # no-offset hit
        {"text": "fabricated quote", "start": -1, "end": -1},            # no-offset miss
    ], claims=[
        {"subject": "x", "predicate": "y", "span": {"start": 0, "end": 26}},
        {"subject": "x", "predicate": "y", "span": {"start": 60, "end": 999}},
        {"subject": "x", "predicate": "y", "span": None},
    ])
    rep = fence_check(arch)
    assert rep["exact"] == 1 and rep["substring"] == 1 and rep["miss"] == 1
    assert rep["no_offset_hit"] == 1 and rep["no_offset_miss"] == 1
    assert rep["claims"] == {"valid": 1, "invalid": 1, "absent": 1}
    assert rep["quote_verified_rate"] == 0.6
    assert len(rep["sample_misses"]) == 2
    assert rep["cards_unfetchable"] == 0


def test_exact_when_offsets_include_whitespace():
    """Right offsets + a padded quote is still exact — not a substring
    downgrade (the exact rate is a headline fence number)."""
    arch = fresh_dir("spancheck-ws")
    make_catalog(arch, quotes=[
        {"text": " The negatives are forever. ", "start": 0, "end": 27},
    ])
    rep = fence_check(arch)
    assert rep["exact"] == 1 and rep["substring"] == 0


def test_locate_derives_spans_and_refuses_fabrication():
    text = "Alpha beta.\nThe fence   certifies\n  what readers claim."
    assert locate(text, "Alpha beta.") == (0, 11, "find")
    # a reflowed quote: words real, layout not -> derived from the raw text
    start, end, method = locate(text, "The fence certifies what readers claim.")
    assert method == "whitespace"
    assert text[start:end] == "The fence   certifies\n  what readers claim."
    assert locate(text, "never written here") is None    # no coordinates ever
    assert locate(text, "   ") is None


def test_derive_spans_writes_located_only(tmp_path):
    """The sidecar carries derived spans for located quotes ONLY — an
    unlocated quote simply has no row, so it cannot render as verbatim."""
    arch = fresh_dir("spancheck-derive")
    make_catalog(arch, quotes=[
        {"text": "The negatives are forever.", "start": 999, "end": 1050},  # junk offsets
        {"text": "fence   certifies", "start": -1, "end": -1},              # reflowed
        {"text": "invented entirely", "start": 3, "end": 20},               # fabrication
    ])
    stats = derive_spans(arch)
    assert stats["quotes"] == 3 and stats["located"] == 2
    assert stats["unlocated"] == 1 and stats["located_rate"] == 0.6667
    rows = [json.loads(x) for x in
            (arch / "catalog" / "cards" / "spans.jsonl").read_text("utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["start"] == 0 and rows[0]["text"] == "The negatives are forever."
    assert rows[0]["method"] == "find" and rows[0]["quote"] == 0
    assert rows[1]["quote"] == 1 and "certifies" in rows[1]["text"]
    assert all(TEXT[r["start"]:r["end"]] == r["text"] for r in rows)   # spans are true


def test_unfetchable_chunk_is_not_fabrication():
    """A card whose chunk is not in this Tape must not be scored as miss —
    that would blame the model for a wrong-archive/tape-drift problem."""
    arch = fresh_dir("spancheck-missing")
    make_catalog(arch, quotes=[{"text": "The negatives are forever.",
                                "start": 0, "end": 26}])
    cards_p = arch / "catalog" / "cards" / "cards.jsonl"
    row = json.loads(cards_p.read_text("utf-8").splitlines()[0])
    ghost = dict(row, doc_id="d" + "9" * 31)      # a key no tape record has
    with open(cards_p, "a", encoding="utf-8") as f:
        f.write(json.dumps(ghost, ensure_ascii=False) + "\n")

    rep = fence_check(arch)
    assert rep["cards_unfetchable"] == 1
    assert rep["cards"] == 1                       # only the real card scored
    assert rep["quotes"] == 1 and rep["exact"] == 1
    assert rep["miss"] == 0                        # the ghost never counted
    assert rep["quote_verified_rate"] == 1.0


def test_keyed_row_without_a_card_is_skipped_not_fatal():
    arch = fresh_dir("spancheck-nocard")
    make_catalog(arch, quotes=[{"text": "The negatives are forever.",
                                "start": 0, "end": 26}])
    cards_p = arch / "catalog" / "cards" / "cards.jsonl"
    with open(cards_p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"doc_id": "d" + "0" * 31, "seq": 0,
                            "note": "hand repair, no card"}) + "\n")
    rep = fence_check(arch)
    assert rep["cards"] == 1 and rep["exact"] == 1     # the real card only
    assert derive_spans(arch)["located"] == 1
