"""S2 falsifiers (no real API): end-to-end read under a frozen charter against
the content-routed stub; resume with zero dupes/gaps; calibration-drift halt
(drilled); tampered-charter refusal; embedding index build."""

import asyncio
import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from test_discover import _P1Stub, mini_archive

from discover import run_discover, run_freeze
from read import run_read

REPO = Path(__file__).parent.parent


class _EmbedStub(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self._reply(b'{"status":"ok"}')

    def do_POST(self):  # noqa: N802
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n = len(req["input"])
        body = json.dumps({"model": "stub-embed",
                           "data": [{"index": i, "embedding": [0.5] * 8}
                                    for i in range(n)]}).encode()
        self._reply(body)

    def _reply(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def stubs(monkeypatch, tmp_path):
    """P1 stub (chat) + embed stub, plus a sandboxed CODE_DIR for freeze."""
    p1 = ThreadingHTTPServer(("127.0.0.1", 0), _P1Stub)
    threading.Thread(target=p1.serve_forever, daemon=True).start()
    emb = ThreadingHTTPServer(("127.0.0.1", 0), _EmbedStub)
    threading.Thread(target=emb.serve_forever, daemon=True).start()
    monkeypatch.setenv("SCRIPTORIUM_EMBED_URL", f"http://127.0.0.1:{emb.server_port}")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    import discover as dm
    sandbox = tmp_path / "code"
    sandbox.mkdir()
    shutil.copy(REPO / "scriptorium.lock", sandbox / "scriptorium.lock")
    shutil.copytree(REPO / "prompts", sandbox / "prompts")
    monkeypatch.setattr(dm, "CODE_DIR", sandbox)
    yield f"http://127.0.0.1:{p1.server_port}"
    p1.shutdown()
    emb.shutdown()


def frozen_mini(stub_url: str) -> Path:
    arch = mini_archive()
    asyncio.run(run_discover(arch, usd_cap=5.0, sample_tokens=50_000,
                             goldens_n=6, defects_n=2, concurrency=4,
                             base_url=stub_url))
    run_freeze(arch)
    return arch


def read_cards(arch: Path) -> list[dict]:
    p = arch / "catalog" / "cards" / "cards.jsonl"
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()] if p.exists() else []


def test_read_end_to_end_with_index(stubs):
    arch = frozen_mini(stubs)
    report = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs,
                                  batch_size=4, calib_every=2))
    cards = read_cards(arch)
    assert report["cards"] == 12 and len(cards) == 12
    assert report["coverage_pct"] == 100.0
    keys = [(c["doc_id"], c["seq"]) for c in cards]
    assert len(keys) == len(set(keys))
    fp = cards[0]["fp"]
    assert fp["rubric_v"] == "r1" and fp["charter_root"]
    assert cards[0]["card"]["entities"][0]["name"] == "Cortex"   # stub canned card
    assert report["index"] == {"chunks": 12, "fts": 12, "vectors": 12}
    assert report["calibrations"], "calibration must have run at batch 0"


def test_read_resume_zero_dupes_zero_gaps(stubs):
    arch = frozen_mini(stubs)
    asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    n1 = len(read_cards(arch))

    # rerun: everything already read
    r2 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert r2.get("cards", 0) == 0 and len(read_cards(arch)) == n1

    # simulate a killed run: keep only the first 5 card rows, then resume
    p = arch / "catalog" / "cards" / "cards.jsonl"
    lines = p.read_text("utf-8").splitlines()
    p.write_text("\n".join(lines[:5]) + "\n", "utf-8")
    r3 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    cards = read_cards(arch)
    assert r3["cards"] == n1 - 5
    keys = [(c["doc_id"], c["seq"]) for c in cards]
    assert len(keys) == len(set(keys)) == n1                     # no dupes, no gaps


def test_calibration_drift_halts_checkpoint_clean(stubs, monkeypatch):
    arch = frozen_mini(stubs)
    monkeypatch.setenv("SCRIPTORIUM_TEST_FORCE_DRIFT", "1")
    with pytest.raises(SystemExit, match="CALIBRATION DRIFT"):
        asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    journal = (arch / "runs")
    halts = [json.loads(ln) for run in sorted(journal.iterdir())
             for ln in ((run / "journal.jsonl").read_text("utf-8").splitlines()
                        if (run / "journal.jsonl").exists() else [])
             if '"halt"' in ln]
    assert any(h.get("reason") == "calibration_drift" for h in halts)


def test_tampered_charter_refused(stubs):
    arch = frozen_mini(stubs)
    rubric = arch / "charter" / "rubric_P2.md"
    rubric.write_text(rubric.read_text("utf-8") + "\ntampered", "utf-8")
    with pytest.raises(SystemExit, match="fingerprint"):
        asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs))


def test_read_refuses_without_charter(stubs, monkeypatch):
    arch = mini_archive()
    with pytest.raises(SystemExit, match="no frozen charter"):
        asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs))
