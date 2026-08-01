"""Session-jsonl extractor (tape generation v2, manifest opt-in): voices kept,
envelope/thinking/tool traffic dropped, true content years recovered,
default-raw behavior preserved."""

import json

from conftest import fresh_dir
from intake import extract_session_text, run_intake, sniff_session_jsonl
from tape import Tape, verify_tape

SESSION_LINES = [
    {"type": "summary", "summary": "Planning the tape format"},
    {"type": "user", "timestamp": "2025-03-14T09:00:00Z",
     "message": {"role": "user", "content": "please build the hash chain"}},
    {"type": "assistant", "timestamp": "2025-03-14T09:00:30Z",
     "message": {"role": "assistant", "content": [
         {"type": "thinking", "thinking": "SECRET-REASONING must not surface"},
         {"type": "text", "text": "Building the blake2b chain now."},
         {"type": "tool_use", "name": "Write",
          "input": {"content": "TOOL-INPUT-NOISE " * 50}}]}},
    {"type": "user", "timestamp": "2025-03-14T09:01:00Z",
     "message": {"role": "user", "content": [
         {"type": "tool_result", "tool_use_id": "x",
          "content": [{"type": "text", "text": "TOOL-RESULT-DUMP " * 80}]},
         {"type": "text", "text": "looks good, continue"}]}},
    {"type": "file-history-snapshot", "snapshot": {"big": "blob"}},
]


def write_session(path, lines=SESSION_LINES, garbage_at=None):
    out = [json.dumps(ln) for ln in lines]
    if garbage_at is not None:
        out.insert(garbage_at, "{torn json line")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def test_extract_keeps_voices_drops_envelope(tmp_path):
    p = tmp_path / "s.jsonl"
    write_session(p, garbage_at=2)
    text, year, bad = extract_session_text(p.read_bytes())
    assert "SUMMARY: Planning the tape format" in text
    assert "USER: please build the hash chain" in text
    assert "ASSISTANT: Building the blake2b chain now." in text
    assert "USER: looks good, continue" in text
    assert "SECRET-REASONING" not in text          # thinking dropped
    assert "TOOL-INPUT-NOISE" not in text          # tool_use dropped
    assert "TOOL-RESULT-DUMP" not in text          # tool_result dropped
    assert year == 2025 and bad == 1


def test_sniff_session_vs_other_jsonl():
    session_head = "\n".join(json.dumps(ln) for ln in SESSION_LINES).encode()
    journal_head = b'{"ts": "2026-01-01", "event": "batch_done"}\n' * 3
    assert sniff_session_jsonl(session_head)
    assert not sniff_session_jsonl(journal_head)


def plant(arch, sessions_option):
    files = arch / "files"
    files.mkdir(parents=True)
    write_session(files / "abc.jsonl")
    (files / "journal.jsonl").write_text(
        '{"ts": "2026-01-01", "event": "x"}\n' * 40, encoding="utf-8")
    opt = f"options:\n  sessions: {sessions_option}\n" if sessions_option else ""
    (arch / "manifest.yaml").write_text(
        "roots:\n  - path: files\n    label: logs\n" + opt, encoding="utf-8")


def load_docs(arch):
    tape = Tape.open(arch)
    docs = {r["body"]["path"]: r["body"] for r in tape.iter_records(kinds=("doc",))}
    texts = {}
    for r in tape.iter_records(kinds=("text",)):
        texts.setdefault(r["body"]["doc_id"], []).append(r["body"])
    tape.close()
    return docs, texts


def test_intake_extracts_sessions_when_opted_in():
    arch = fresh_dir("sess-extract")
    plant(arch, "extract")
    report = run_intake(arch, quiet=True)
    assert report.completeness_pct == 100.0
    docs, texts = load_docs(arch)
    s = docs["abc.jsonl"]
    assert s["modality"] == "session"
    assert s["extractor"]["extractor"] == "session-jsonl-v1"
    assert s["year"] == 2025                        # content year beats 2026 mtime
    body = texts[s["doc_id"]][0]["text"]
    assert "USER: please build the hash chain" in body
    assert "TOOL-RESULT-DUMP" not in body
    assert docs["journal.jsonl"]["modality"] == "text"   # non-session stays raw
    assert verify_tape(arch).ok


def test_intake_default_stays_raw():
    arch = fresh_dir("sess-raw")
    plant(arch, None)
    run_intake(arch, quiet=True)
    docs, texts = load_docs(arch)
    s = docs["abc.jsonl"]
    assert s["modality"] == "text"                  # v1 behavior untouched
    body = texts[s["doc_id"]][0]["text"]
    assert "TOOL-RESULT-DUMP" in body               # raw envelope taped verbatim
