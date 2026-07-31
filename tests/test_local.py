"""OCR sidecar seam against the stub server: contract prompt honored, JSON parsed,
R-class fingerprint stamped, typed degradation; the :8092 embedding seam refuses."""

import json
from pathlib import Path

import pytest

from conftest import STUB_OCR_TEXT, fresh_dir, make_png
from local import EmbedSidecar, OcrSidecar, RungGate

LOCK = json.loads((Path(__file__).parent.parent / "scriptorium.lock").read_text("utf-8"))


def test_ocr_roundtrip_and_fingerprint(ocr_stub):
    png = fresh_dir("localocr") / "t.png"
    make_png(png, "hello")
    side = OcrSidecar()
    assert side.ensure(launch=False)              # attach via env override
    res = side.ocr_image(png)
    side.close()
    assert res["text"] == STUB_OCR_TEXT
    assert res["confidence_hint"] == 0.9
    fp = res["fp"]
    assert fp["model_blake2b256"] == LOCK["sidecars"]["ocr"]["model_blake2b256"]
    assert fp["mmproj_blake2b256"] == LOCK["sidecars"]["ocr"]["mmproj_blake2b256"]
    assert fp["prompt_blake2b128"] == LOCK["prompts"]["ocr_contract_v0"]["blake2b128"]


def test_prompts_are_the_frozen_contracts():
    """Every prompt on disk is byte-for-byte the one the lock pins."""
    import canon
    for name, spec in LOCK["prompts"].items():
        data = (Path(__file__).parent.parent / spec["file"].replace("\\\\", "\\")).read_bytes()
        assert canon.blake2b128_hex(data) == spec["blake2b128"], \
            f"prompt {name} drifted from its lock pin"
    ocr = (Path(__file__).parent.parent / "prompts" / "ocr_contract_v0.txt").read_text("utf-8")
    for required in ("verbatim", "reading order", "[table]", "[handwritten]",
                     "⟨?", "json", "confidence_hint"):
        assert required in ocr, f"frozen OCR contract lost clause: {required}"


def test_ocr_shape_degradation(ocr_stub):
    ocr_stub.mode = "raw"
    png = fresh_dir("localocr2") / "t.png"
    make_png(png, "hello")
    side = OcrSidecar()
    res = side.ocr_image(png)
    side.close()
    assert res["note"] == "ocr_json_parse_failed"
    assert "plain words" in res["text"]


def test_ocr_down_and_no_launch(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_OCR_URL", "http://127.0.0.1:9")
    side = OcrSidecar()
    assert side.ensure(launch=True) is False      # env override forbids launching
    side.close()


def test_embedding_seam_is_gated():
    with pytest.raises(RungGate, match="S2"):
        EmbedSidecar().embed(["x"])
