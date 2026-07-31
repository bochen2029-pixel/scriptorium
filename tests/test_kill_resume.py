"""Falsifier (c): kill the intake mid-run (real subprocess, hard TerminateProcess),
rerun, assert zero duplicate records and zero gaps. Plus a deterministic unit test
of partial-doc continuation (texts on tape, doc record missing)."""

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import fresh_dir, varied_sentences, wait_for
from intake import doc_id_for, run_intake
from models import TextBody
from tape import Tape, verify_tape
from textnorm import canonical, split_blocks

REPO = Path(__file__).parent.parent
N_FILES = 300


def plant_many(arch: Path, n: int = N_FILES) -> None:
    files = arch / "files"
    files.mkdir(parents=True)
    for i in range(n):
        # distinct numbering per file: near-dup flagging must stay quiet here
        (files / f"note-{i:04d}.txt").write_text(
            f"Note {i}.\n" + varied_sentences(6, f"salt{i}", start=i * 100) + "\n",
            encoding="utf-8")
    (arch / "manifest.yaml").write_text(
        "archive: killres\nroots:\n  - path: files\n    label: notes\n",
        encoding="utf-8")


def tape_count(arch: Path) -> int:
    lock = arch / "tape" / "tape.lock"
    if not lock.exists():
        return 0
    try:
        return json.loads(lock.read_text("utf-8"))["count"]
    except (json.JSONDecodeError, KeyError, OSError):
        return 0


def assert_no_dupes_no_gaps(arch: Path, expect_docs: int) -> None:
    tape = Tape.open(arch)
    doc_ids: list[str] = []
    seqs: dict[str, list[int]] = {}
    for rec in tape.iter_records():
        b = rec["body"]
        if rec["kind"] == "doc":
            doc_ids.append(b["doc_id"])
        elif rec["kind"] == "text":
            seqs.setdefault(b["doc_id"], []).append(b["seq"])
    tape.close()
    assert len(doc_ids) == len(set(doc_ids)) == expect_docs, \
        f"duplicate or missing docs: {len(doc_ids)} records, {len(set(doc_ids))} unique"
    for did, ss in seqs.items():
        assert sorted(ss) == list(range(len(ss))), f"seq gap/dupe in {did}: {sorted(ss)}"


def test_falsifier_c_kill_and_resume():
    arch = fresh_dir("killres")
    plant_many(arch)

    env = {**os.environ,
           "SCRIPTORIUM_TEST_SLEEP_PER_FILE": "0.01",
           "SCRIPTORIUM_OCR_URL": "http://127.0.0.1:9"}
    child_log = arch / "child.log"
    with open(child_log, "wb") as logf:
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "scriptorium.py"), "intake", str(arch), "--quiet"],
            cwd=REPO, env=env, stdout=logf, stderr=logf)
        try:
            # let it commit a meaningful prefix, then kill it hard mid-flight
            staged = wait_for(lambda: tape_count(arch) >= 60, timeout=90)
        finally:
            alive = proc.poll() is None
            proc.kill()                 # ALWAYS kill: an orphan would corrupt reruns
            proc.wait(timeout=30)
    assert staged, (
        f"intake never reached 60 records (alive at timeout: {alive}); child said:\n"
        + child_log.read_text("utf-8", errors="replace")[-2000:])

    n_before = tape_count(arch)
    assert 0 < n_before, "kill landed before any progress"
    t = Tape.open(arch)
    docs_before = sum(1 for _ in t.iter_records(kinds=("doc",)))
    t.close()
    assert docs_before < N_FILES, "process finished before the kill — test is vacuous"

    report = run_intake(arch, quiet=True)          # the resume
    assert report.completeness_pct == 100.0
    assert report.counts["done"] + report.counts["skipped"] == N_FILES
    assert report.counts["done"] > 0 and report.counts["skipped"] > 0

    assert_no_dupes_no_gaps(arch, expect_docs=N_FILES)
    assert verify_tape(arch).ok


def test_partial_doc_continuation_deterministic():
    """Texts fsync'd, doc record lost: rerun continues units, no dupes, no gaps."""
    arch = fresh_dir("partialdoc")
    files = arch / "files"
    files.mkdir(parents=True)
    big = "\n".join(varied_sentences(40, f"part{i}") for i in range(12)) + "\n"
    (files / "big.txt").write_text(big, encoding="utf-8")
    (arch / "manifest.yaml").write_text(
        "roots:\n  - path: files\n    label: notes\n", encoding="utf-8")

    canon_text = canonical(big)
    blocks = split_blocks(canon_text)
    assert len(blocks) >= 2, "fixture must span multiple blocks"

    from intake import hash_file
    content = hash_file(files / "big.txt")
    did = doc_id_for(files.as_posix(), "big.txt", content)

    # simulate the crash artifact: first block taped, doc record never written
    tape = Tape.open(arch)
    tape.append("text", TextBody(doc_id=did, seq=0, text=blocks[0],
                                 chars=len(blocks[0]),
                                 meta={"unit": 0, "source": "file",
                                       "tokens_est": 10}).model_dump())
    tape.close()

    report = run_intake(arch, quiet=True)
    assert report.completeness_pct == 100.0

    tape = Tape.open(arch)
    texts = [r["body"] for r in tape.iter_records(kinds=("text",))]
    docs = [r["body"] for r in tape.iter_records(kinds=("doc",))]
    tape.close()
    assert len(docs) == 1 and docs[0]["doc_id"] == did
    assert docs[0]["n_texts"] == len(blocks)
    assert "resumed" in docs[0]["notes"]
    assert [t["seq"] for t in texts] == list(range(len(blocks)))
    assert "".join(t["text"] for t in texts) == canon_text     # zero gaps in content
    assert verify_tape(arch).ok
