"""Read-only catalog window: FTS hits joined to cards, quotes shown ONLY with
code-derived spans, fabrications withheld, terminal control bytes neutered."""

import json
import sqlite3

import pytest

from conftest import fresh_dir
from query import QueryError, render, search
from tape import Tape

TEXT = ("The negatives are forever. The fence certifies what the readers "
        "claim. Sovereignty means pixels never leave the box.")
DOC = "d" + "0" * 31


def make_catalog(arch, quotes, topics=("fence",), with_index=True):
    tape = Tape.open(arch)
    tape.append("text", {"doc_id": DOC, "seq": 0, "text": TEXT,
                         "chars": len(TEXT), "meta": {"unit": 0}})
    tape.append("doc", {"doc_id": DOC, "root": "r", "path": "notes/a.md",
                        "source": "s", "content_b2": "c", "size": 1,
                        "mtime": "2026-01-01T00:00:00+00:00", "year": 2026,
                        "modality": "text", "extractor": {}, "n_texts": 1,
                        "chars": len(TEXT), "tokens_est": 20, "notes": [],
                        "minhash": None})
    tape.close()
    cards_dir = arch / "catalog" / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "cards.jsonl").write_text(json.dumps({
        "doc_id": DOC, "seq": 0,
        "card": {"quotes": quotes, "topics": list(topics),
                 "entities": [{"name": "the fence"}],
                 "claims": [{"subject": "negatives", "predicate": "are",
                             "object": "forever"}]}}, ensure_ascii=False) + "\n",
        "utf-8")
    (arch / "manifest.yaml").write_text("roots:\n  - path: files\n", "utf-8")
    (arch / "files").mkdir()
    if with_index:
        db = sqlite3.connect(arch / "catalog" / "index.sqlite")
        db.executescript(
            "CREATE TABLE chunks(doc_id TEXT, seq INT, project TEXT, year INT,"
            " path TEXT, tokens INT, chars INT, PRIMARY KEY(doc_id, seq));"
            "CREATE VIRTUAL TABLE chunks_fts USING fts5(text);"
            "CREATE TABLE fts_map(fts_rowid INTEGER PRIMARY KEY, doc_id TEXT,"
            " seq INT, UNIQUE(doc_id, seq));")
        db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?,?)",
                   (DOC, 0, "PROJ", 2026, "notes/a.md", 20, len(TEXT)))
        cur = db.execute("INSERT INTO chunks_fts(text) VALUES(?)", (TEXT,))
        db.execute("INSERT INTO fts_map VALUES(?,?,?)", (cur.lastrowid, DOC, 0))
        db.commit()
        db.close()


def test_search_joins_fts_to_cards_with_derived_spans():
    arch = fresh_dir("query-basic")
    make_catalog(arch, quotes=[
        {"text": "The negatives are forever.", "start": 900, "end": 950},  # junk offsets
        {"text": "fence   certifies", "start": -1, "end": -1},             # reflowed
    ])
    rep = search(arch, "negatives")
    assert rep["n"] == 1
    hit = rep["hits"][0]
    assert hit["project"] == "PROJ" and hit["path"] == "notes/a.md"
    assert hit["carded"] and hit["unlocated_quotes"] == 0
    # spans are DERIVED: they index the real Tape text, not the model's numbers
    assert [(v["start"], v["end"]) for v in hit["verbatim"]] == [(0, 26), (31, 46)]
    assert all(TEXT[v["start"]:v["end"]] == v["text"] for v in hit["verbatim"])
    assert hit["reading"]["topics"] == ["fence"]
    assert "negatives are forever" in hit["reading"]["claims"][0]


def test_fabricated_quote_is_withheld_never_rendered():
    arch = fresh_dir("query-fabrication")
    make_catalog(arch, quotes=[
        {"text": "The negatives are forever.", "start": 0, "end": 26},
        {"text": "the archive shall be destroyed at dawn", "start": 0, "end": 38},
    ])
    rep = search(arch, "negatives")
    hit = rep["hits"][0]
    assert len(hit["verbatim"]) == 1 and hit["unlocated_quotes"] == 1
    out = render(rep)
    assert "destroyed at dawn" not in out          # never shown as verbatim
    assert "could NOT be located" in out           # but never silently dropped


def test_control_bytes_are_neutered_for_display():
    """Terminal captures are honest Tape bytes; they must not repaint the
    operator's console or hide text when rendered."""
    arch = fresh_dir("query-ansi")
    make_catalog(arch, quotes=[], topics=["\x1b[32;1mgreen\x1b[0m\ttopic"])
    out = render(search(arch, "negatives"))
    assert "\x1b" not in out and "\t" not in out
    assert "green" in out and "topic" in out


def test_uncarded_chunk_is_labelled_not_invented():
    arch = fresh_dir("query-uncarded")
    make_catalog(arch, quotes=[])
    (arch / "catalog" / "cards" / "cards.jsonl").write_text("", "utf-8")
    rep = search(arch, "sovereignty")
    assert rep["hits"][0]["carded"] is False
    assert rep["hits"][0]["reading"] is None
    assert "not carded" in render(rep)


def test_refusals_are_typed():
    arch = fresh_dir("query-refuse")
    make_catalog(arch, quotes=[], with_index=False)
    with pytest.raises(QueryError, match="no catalog index"):
        search(arch, "anything")

    arch2 = fresh_dir("query-refuse2")
    make_catalog(arch2, quotes=[])
    with pytest.raises(QueryError, match="empty query"):
        search(arch2, "   ")
    with pytest.raises(QueryError, match="bad query"):
        search(arch2, 'AND OR "')


def test_no_match_is_an_empty_report_not_an_error():
    arch = fresh_dir("query-nomatch")
    make_catalog(arch, quotes=[])
    rep = search(arch, "zzzznotpresent")
    assert rep["n"] == 0 and rep["hits"] == []
    assert "no chunk in this catalog matches" in render(rep)
