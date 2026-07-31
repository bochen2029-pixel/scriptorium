"""Falsifier (a): planted corpus — zero silently dropped files. Every discovered
path terminates as doc / journal:dedup / journal:excluded / journal:quarantined.
Plus: span-coordinate integrity, OCR provenance, census + cross-check, rerun
idempotence."""

import json
from pathlib import Path

from conftest import STUB_OCR_TEXT, fresh_dir, plant_corpus
from intake import run_intake
from tape import Tape, verify_tape
from textnorm import canonical

LOCK = json.loads((Path(__file__).parent.parent / "scriptorium.lock").read_text("utf-8"))


def load_tape_maps(arch):
    tape = Tape.open(arch)
    docs, texts, journals = {}, {}, []
    for rec in tape.iter_records():
        b = rec["body"]
        if rec["kind"] == "doc":
            docs[b["path"]] = b
        elif rec["kind"] == "text":
            texts.setdefault(b["doc_id"], []).append(b)
        elif rec["kind"] == "journal":
            journals.append(b)
    tape.close()
    return docs, texts, journals


def test_planted_corpus_full_accounting(ocr_stub):
    arch = fresh_dir("planted")
    expected = plant_corpus(arch)
    report = run_intake(arch, quiet=True)

    # -- falsifier (a): completeness measured at 100, nothing unaccounted
    assert report.completeness_pct == 100.0, report.reconciliation
    assert report.reconciliation["unaccounted"] == []
    assert report.counts["done"] == 7
    assert report.counts["dedup"] == 1
    assert report.counts["excluded"] == 1
    assert report.counts["quarantined"] == 1

    docs, texts, journals = load_tape_maps(arch)
    for rel, want in expected.items():
        if want == "doc":
            assert rel in docs, f"{rel} missing its doc record"
        else:
            assert any(j.get("event") == want and j.get("path") == rel
                       for j in journals), f"{rel} not journaled as {want}"

    # -- exact dedup references the original
    dd = next(j for j in journals if j.get("event") == "dedup")
    assert dd["ref_doc_id"] == docs["notes/a.md"]["doc_id"]

    # -- near-dup flagged, kept, cross-referenced (never folded)
    flags = [j for j in journals if j.get("event") == "near_dup_flag"]
    assert any(f["doc_id"] == docs["notes/near_a.md"]["doc_id"]
               and f["other_doc_id"] == docs["notes/a.md"]["doc_id"]
               and f["jaccard_est"] >= 0.6 for f in flags), flags
    assert "notes/near_a.md" in docs          # kept as its own doc

    # -- span coordinate system: taped text reconstructs the canonical source
    a = docs["notes/a.md"]
    a_texts = sorted(texts[a["doc_id"]], key=lambda t: t["seq"])
    joined = "".join(t["text"] for t in a_texts)
    src = canonical((arch / "files/notes/a.md").read_text("utf-8"))
    assert joined == src
    assert all(t["chars"] == len(t["text"]) for t in a_texts)
    assert [t["seq"] for t in a_texts] == list(range(len(a_texts)))

    # -- pdf text layer
    c_texts = texts[docs["docs/c.pdf"]["doc_id"]]
    assert any("QUINCE" in t["text"] for t in c_texts)
    assert all(t["meta"]["source"] == "text-layer" for t in c_texts)

    # -- scanned pdf went through imguard -> stub OCR, R-class provenance stamped
    s_texts = texts[docs["docs/scan.pdf"]["doc_id"]]
    assert len(s_texts) == 1 and s_texts[0]["meta"]["source"] == "ocr"
    assert STUB_OCR_TEXT in s_texts[0]["text"]
    fp = s_texts[0]["meta"]["ocr"]["fp"]
    assert fp["model_blake2b256"] == LOCK["sidecars"]["ocr"]["model_blake2b256"]
    assert fp["prompt_blake2b128"] == LOCK["prompts"]["ocr_contract_v0"]["blake2b128"]

    # -- image OCR + docx extraction
    e_texts = texts[docs["img/e.png"]["doc_id"]]
    assert STUB_OCR_TEXT in e_texts[0]["text"]
    d_texts = texts[docs["docs/d.docx"]["doc_id"]]
    assert any("MARIGOLD" in t["text"] for t in d_texts)

    # -- census: planted years present; totals consistent; cross-check sane
    rows = report.contact_rows
    summary = rows[-1]
    assert summary["files"] == 7
    years = {r["year"] for r in rows if r["year"] is not None}
    assert years == {2019, 2020, 2021}
    assert summary["tokens_est"] == sum(r["tokens_est"] for r in rows[:-1])
    assert report.crosscheck["mean_ratio"] is not None
    assert 0.9 <= report.crosscheck["mean_ratio"] <= 1.1, report.crosscheck

    assert verify_tape(arch).ok


def test_rerun_is_idempotent(ocr_stub):
    arch = fresh_dir("planted-rerun")
    plant_corpus(arch)
    run_intake(arch, quiet=True)
    _, texts1, journals1 = load_tape_maps(arch)
    n_texts1 = sum(len(v) for v in texts1.values())

    report2 = run_intake(arch, quiet=True)
    assert report2.completeness_pct == 100.0
    assert report2.counts["done"] == 0
    assert report2.counts["skipped"] == 7

    docs2, texts2, journals2 = load_tape_maps(arch)
    assert len(docs2) == 7                                    # zero new docs
    assert sum(len(v) for v in texts2.values()) == n_texts1   # zero new texts
    for ev in ("excluded", "dedup", "quarantined", "near_dup_flag"):
        n1 = sum(1 for j in journals1 if j.get("event") == ev)
        n2 = sum(1 for j in journals2 if j.get("event") == ev)
        assert n1 == n2, f"journal {ev} duplicated on rerun: {n1} -> {n2}"
    assert verify_tape(arch).ok


def test_ocr_shape_degradation_is_typed(ocr_stub):
    """A sidecar that answers with non-JSON still yields the words + a typed note."""
    ocr_stub.mode = "raw"
    arch = fresh_dir("planted-rawocr")
    plant_corpus(arch)
    report = run_intake(arch, quiet=True)
    assert report.completeness_pct == 100.0
    docs, texts, _ = load_tape_maps(arch)
    s = texts[docs["docs/scan.pdf"]["doc_id"]][0]
    assert s["meta"]["ocr"]["note"] == "ocr_json_parse_failed"
    assert "plain words" in s["text"]


def test_ocr_unavailable_quarantines_typed(monkeypatch):
    """No sidecar, no launch -> image-bearing files quarantine typed, texts still land."""
    monkeypatch.setenv("SCRIPTORIUM_OCR_URL", "http://127.0.0.1:9")   # nothing there
    arch = fresh_dir("planted-noocr")
    plant_corpus(arch)
    report = run_intake(arch, launch_ocr=False, quiet=True)
    assert report.completeness_pct == 100.0                   # quarantine IS accounted
    reasons = dict(report.quarantined)
    assert reasons.get("docs/scan.pdf") == "ocr_unavailable"
    assert reasons.get("img/e.png") == "ocr_unavailable"
    docs, _, _ = load_tape_maps(arch)
    assert "notes/a.md" in docs and "docs/c.pdf" in docs
