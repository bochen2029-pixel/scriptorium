"""The AV slow lane: real speech (Windows TTS) through the real earshot organ.
Skips honestly when a dependency is missing — the planted-corpus falsifier notes
what it couldn't generate rather than pretending."""

import pytest

from conftest import fresh_dir, make_silent_wav, make_tts_wav
from intake import run_intake
from organs import earshot_available
from tape import Tape, verify_tape

pytestmark = pytest.mark.skipif(not earshot_available(),
                                reason="earshot dependencies missing on this box")

SPOKEN = ("The quick brown fox jumps over the lazy dog. "
          "This is the scriptorium test recording.")


def load_docs_texts(arch):
    tape = Tape.open(arch)
    docs = {r["body"]["path"]: r["body"] for r in tape.iter_records(kinds=("doc",))}
    texts = {}
    for r in tape.iter_records(kinds=("text",)):
        texts.setdefault(r["body"]["doc_id"], []).append(r["body"])
    tape.close()
    return docs, texts


def test_av_lane_speech_and_silence():
    arch = fresh_dir("avlane")
    files = arch / "files"
    files.mkdir(parents=True)
    if not make_tts_wav(files / "hello.wav", SPOKEN):
        pytest.skip("Windows TTS unavailable — noted, not simulated")
    have_silence = make_silent_wav(files / "silence.wav")
    (arch / "manifest.yaml").write_text(
        "archive: avlane\nroots:\n  - path: files\n    label: recordings\n",
        encoding="utf-8")

    report = run_intake(arch, quiet=True)
    assert report.completeness_pct == 100.0

    docs, texts = load_docs_texts(arch)
    hello = docs["hello.wav"]
    assert hello["modality"] == "av"
    assert hello["extractor"]["extractor"] == "earshot"
    transcript = " ".join(t["text"] for t in texts[hello["doc_id"]]).lower()
    assert "quick brown fox" in transcript, transcript
    assert all(t["meta"]["source"] == "transcript" for t in texts[hello["doc_id"]])

    if have_silence:
        # whisper may hallucinate a token on digital silence (exit 0) or report
        # no-speech (exit 4); both are the ORGAN's call — we assert faithful
        # admission either way, never a drop.
        silence = docs["silence.wav"]
        if silence["n_texts"] == 0:
            assert "no_speech" in silence["notes"]
        else:
            assert silence["n_texts"] >= 1

    assert verify_tape(arch).ok


def test_no_speech_exit_is_admitted_empty(monkeypatch):
    """Deterministic unit for the earshot exit-4 path: doc admitted, zero texts,
    typed note — never a quarantine, never a drop."""
    import organs
    from organs import AsrResult
    monkeypatch.setattr(organs, "earshot_transcribe",
                        lambda path, timeout=3600: AsrResult("no_speech", detail="exit 4"))
    arch = fresh_dir("avlane-nospeech")
    files = arch / "files"
    files.mkdir(parents=True)
    (files / "quiet.wav").write_bytes(b"RIFF0000WAVEfmt ")   # never reaches whisper
    (arch / "manifest.yaml").write_text(
        "roots:\n  - path: files\n    label: recordings\n", encoding="utf-8")
    report = run_intake(arch, quiet=True)
    assert report.completeness_pct == 100.0
    docs, _ = load_docs_texts(arch)
    q = docs["quiet.wav"]
    assert q["n_texts"] == 0
    assert "no_speech" in q["notes"]
