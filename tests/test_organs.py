"""Live organ seams (fast, read-only calls against the real fixed-path organs)."""

from pathlib import Path

from conftest import fresh_dir, make_png
from organs import earshot_available, estimate_tokens_organ, everything_list, imguard_ready


def test_estimate_tokens_organ_parses():
    n = estimate_tokens_organ(Path(r"C:\chunker\README.md"))
    assert 500 < n < 5000


def test_imguard_ready_roundtrip():
    png = fresh_dir("organprobe") / "probe.png"
    make_png(png, "organ probe")
    res = imguard_ready(png)
    assert res["status"] == "ok"
    assert Path(res["view_path"]).exists()


def test_everything_list_shape():
    res = everything_list(Path(r"C:\chunker"))
    assert res is None or (isinstance(res, list)
                           and all(isinstance(p, str) for p in res))


def test_earshot_available_returns_bool():
    assert earshot_available() in (True, False)
