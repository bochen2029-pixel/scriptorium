"""catalog.py: the one tolerant cards.jsonl parser, the writer that heals a
torn tail, and the offset-indexed reader (seeks, not whole-catalog parses)."""

import json

from catalog import CardsReader, CardStore, iter_rows
from conftest import fresh_dir


def row(i, seq=0, tag="a"):
    return {"doc_id": f"d{i:031d}", "seq": seq, "card": {"topics": [tag]}}


def test_iter_rows_skips_torn_and_foreign_lines(tmp_path):
    p = tmp_path / "cards.jsonl"
    p.write_text(json.dumps(row(1)) + "\n"
                 + "not json at all\n"
                 + json.dumps({"no": "key"}) + "\n"
                 + json.dumps(row(2)) + "\n"
                 + '{"doc_id": "torn', "utf-8")            # killed writer
    got = list(iter_rows(p))
    assert [r["doc_id"][-1] for r in got] == ["1", "2"]
    assert list(iter_rows(tmp_path / "absent.jsonl")) == []


def test_store_heals_a_torn_tail_before_appending(tmp_path):
    """A killed batch's partial line must never glue the next batch's first
    row onto itself and lose a paid card."""
    store = CardStore(tmp_path / "cards")
    store.append_batch(store.cards_path, [row(1)])
    with open(store.cards_path, "ab") as f:
        f.write(b'{"doc_id": "d-torn", "seq": 0, "card": {')   # mid-write kill
    store.append_batch(store.cards_path, [row(2), row(3)])
    keys = {r["doc_id"][-1] for r in iter_rows(store.cards_path)}
    assert keys == {"1", "2", "3"}                              # nothing lost
    assert store.done_keys() == {(row(i)["doc_id"], 0) for i in (1, 2, 3)}


def test_reader_seeks_and_matches_a_full_scan(tmp_path):
    arch = fresh_dir("catalog-reader")
    store = CardStore(arch / "catalog" / "cards")
    store.append_batch(store.cards_path, [row(i) for i in range(50)])
    with CardsReader(arch) as r:
        assert r.stats == {"indexed": 50, "added": 50}
        assert r.get(row(7)["doc_id"], 0)["card"]["topics"] == ["a"]
        assert r.get(row(7)["doc_id"], 9) is None
        assert r.get("d" + "9" * 31, 0) is None
        many = r.get_many([(row(i)["doc_id"], 0) for i in (3, 44)] + [("ghost", 0)])
        assert set(many) == {(row(3)["doc_id"], 0), (row(44)["doc_id"], 0)}
    scan = {(x["doc_id"], x["seq"]): x for x in iter_rows(store.cards_path)}
    with CardsReader(arch) as r:
        assert r.get_many(scan.keys()) == scan


def test_reader_is_append_aware_and_last_write_wins(tmp_path):
    arch = fresh_dir("catalog-append")
    store = CardStore(arch / "catalog" / "cards")
    store.append_batch(store.cards_path, [row(1), row(2)])
    with CardsReader(arch) as r:
        assert r.stats["added"] == 2
    # a --retry-quarantined rerun appends a NEWER card for the same key
    store.append_batch(store.cards_path, [row(3), row(1, tag="retried")])
    with CardsReader(arch) as r:
        assert r.stats["added"] == 2 and r.stats["indexed"] == 3
        assert r.get(row(1)["doc_id"], 0)["card"]["topics"] == ["retried"]


def test_reader_detects_a_rewritten_file_and_rebuilds(tmp_path):
    """The catalog is append-only by law, but tests and hand repairs rewrite
    it in place; a stale offset must be caught by the row's own key, never
    served as some other card."""
    arch = fresh_dir("catalog-rewrite")
    p = arch / "catalog" / "cards" / "cards.jsonl"
    store = CardStore(p.parent)
    store.append_batch(p, [row(1), row(2), row(3)])
    with CardsReader(arch) as r:
        assert r.get(row(3)["doc_id"], 0) is not None
    # same-size rewrite that reorders rows: offsets now point at wrong keys
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n"
                         for x in (row(3), row(1), row(2))), "utf-8")
    with CardsReader(arch) as r:
        got = r.get(row(3)["doc_id"], 0)
        assert got is not None and got["doc_id"] == row(3)["doc_id"]
    # shrink: rows removed -> rebuilt, removed key gone
    p.write_text(json.dumps(row(2)) + "\n", "utf-8")
    with CardsReader(arch) as r:
        assert r.get(row(1)["doc_id"], 0) is None
        assert r.get(row(2)["doc_id"], 0) is not None
        assert r.stats["indexed"] == 1
