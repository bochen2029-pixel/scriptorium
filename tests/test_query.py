"""Read-only catalog window: FTS hits joined to cards, quotes shown ONLY with
code-derived spans, fabrications withheld, terminal control bytes neutered."""

import json
import sqlite3

import pytest

from conftest import fresh_dir
from query import QueryError, render, render_summary, search, summary
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
    # malformed FTS5 is no longer a refusal: it is matched as one literal
    # phrase (and labelled so) — a typed refusal is reserved for input that
    # cannot even be phrased
    rep = search(arch2, 'AND OR "')
    assert rep["matched_as"] == "phrase" and rep["n"] == 0


def test_no_match_is_an_empty_report_not_an_error():
    arch = fresh_dir("query-nomatch")
    make_catalog(arch, quotes=[])
    rep = search(arch, "zzzznotpresent")
    assert rep["n"] == 0 and rep["hits"] == []
    assert "no chunk in this catalog matches" in render(rep)


def test_summary_counts_dedupes_and_flags_mixed_reads():
    """The aggregate view: a resumed catalog can carry a key twice — count it
    once — and a catalog read by two models or under two charters must say so."""
    arch = fresh_dir("query-summary")
    make_catalog(arch, quotes=[{"text": "The negatives are forever.",
                                "start": 0, "end": 26}])
    cards_p = arch / "catalog" / "cards" / "cards.jsonl"
    row = json.loads(cards_p.read_text("utf-8").splitlines()[0])
    row["fp"] = {"model": "deepseek-v4-flash", "charter_root": "root-a"}
    other = json.loads(json.dumps(row))
    other["seq"] = 1
    other["fp"] = {"model": "some-other-model", "charter_root": "root-b"}
    with open(cards_p, "w", encoding="utf-8") as f:
        for r in (row, row, other):                  # row twice = resume overlap
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (arch / "catalog" / "cards" / "quarantine.jsonl").write_text(
        json.dumps({"doc_id": DOC, "seq": 9,
                    "reason": "worker_output_invalid: boom"}) + "\n", "utf-8")

    s = summary(arch)
    assert s["cards"] == 2 and s["quarantined"] == 1     # duplicate counted once
    assert s["quotes"] == 2 and s["claims"] == 2
    assert s["quotes_per_card"] == 1.0
    assert s["topics"] == [("fence", 2)]
    assert s["entity_kinds"] == {"other": 2}
    assert s["quarantine_reasons"] == [("worker_output_invalid", 1)]
    # an absent vectors table is UNKNOWN, never 0 — no sentinel may reach a
    # derived number (a -1 once made "2 cards" report 3 missing vectors)
    assert s["index"]["chunks"] == 1 and s["index"]["vectors"] is None
    assert s["vectors_missing"] is None

    out = render_summary(s)
    assert "WARNING mixed reader models" in out
    assert "WARNING mixed charter roots" in out
    assert "? vectors" in out and "lack a vector" not in out


def test_summary_refuses_without_cards():
    arch = fresh_dir("query-summary-empty")
    make_catalog(arch, quotes=[])
    (arch / "catalog" / "cards" / "cards.jsonl").unlink()
    with pytest.raises(QueryError, match="no cards"):
        summary(arch)


def test_fts_syntax_in_plain_terms_falls_back_to_a_literal_phrase():
    """FTS5 reads `a-b` as a column filter and `--` as NOT; an operator typing
    a hyphenated name must get a match, and be told it was matched literally."""
    arch = fresh_dir("query-phrase")
    make_catalog(arch, quotes=[])
    rep = search(arch, "fence-certifies")            # would be "no such column"
    assert rep["n"] == 1 and rep["matched_as"] == "phrase"
    assert "matched as ONE literal phrase" in render(rep)
    ok = search(arch, "fence AND certifies")
    assert ok["n"] == 1 and ok["matched_as"] == "expression"
    # even a lone quote is phrase-able (measured): an empty phrase, zero hits,
    # never a crash — the typed "bad query" refusal is defensive depth only
    lone = search(arch, '"')
    assert lone["matched_as"] == "phrase" and lone["n"] == 0


def test_report_keeps_exact_tape_bytes_and_render_normalizes():
    """--json consumers must get text == tape[start:end]; only render()
    collapses whitespace and strips control bytes for the console."""
    rep = {"terms": "x", "matched_as": "expression", "n": 1, "hits": [{
        "doc_id": "d" * 32, "seq": 0, "project": "P", "year": 2026,
        "path": "a.md", "rank": -1.0, "snippet": "s", "carded": True,
        "verbatim": [{"start": 0, "end": 11, "method": "find",
                      "text": "one\ntwo\x1b[0m"}],
        "unlocated_quotes": 0,
        "reading": {"topics": [], "entities": [], "claims": []}}]}
    out = render(rep)
    assert 'VERBATIM [0:11] "one two"' in out           # normalized for display
    assert rep["hits"][0]["verbatim"][0]["text"] == "one\ntwo\x1b[0m"   # untouched
