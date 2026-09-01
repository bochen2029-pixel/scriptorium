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


def test_retry_quarantined_rescues_key(stubs):
    """--retry-quarantined: a quarantined key becomes todo again; on success
    the key lives in BOTH files (cards win; quarantine.jsonl is history) and
    cards.jsonl still has zero dupes."""
    arch = frozen_mini(stubs)
    asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    cards = read_cards(arch)
    victim = (cards[0]["doc_id"], cards[0]["seq"])

    # simulate history: drop the victim's card, add a quarantine row for it
    cards_p = arch / "catalog" / "cards" / "cards.jsonl"
    quar_p = arch / "catalog" / "cards" / "quarantine.jsonl"
    keep = [json.dumps(c) for c in cards[1:]]
    cards_p.write_text("\n".join(keep) + "\n", "utf-8")
    quar_p.write_text(json.dumps({"doc_id": victim[0], "seq": victim[1],
                                  "reason": "worker_output_invalid",
                                  "run_id": "old"}) + "\n", "utf-8")

    # without the flag: quarantined counts as done — nothing to do
    r1 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert r1.get("cards", 0) == 0

    # with the flag: the key is re-read and lands as a card
    r2 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4,
                              retry_quarantined=True))
    assert r2["cards"] == 1
    keys = [(c["doc_id"], c["seq"]) for c in read_cards(arch)]
    assert len(keys) == len(set(keys)) == len(cards)
    assert victim in keys


def test_read_multi_driver_lease_partition(stubs, monkeypatch):
    """A2A chunk leases: a chunk claimed by a live co-driver is skipped without
    writing anything; the skip is reported honestly; a later resume (the other
    driver gone) completes the catalog with zero dupes and zero gaps."""
    from test_a2a import CP

    import a2a

    arch = frozen_mini(stubs)
    monkeypatch.setenv("SCRIPTORIUM_A2A", "1")
    lock = threading.Lock()
    refused: list[str] = []

    def runner(argv):
        if argv[0] == "join":
            return CP(0, "drv1\n")
        if argv[0] == "claim":
            resource = argv[argv.index("--resource") + 1]
            if ":p2:" in resource:
                with lock:                      # exactly one chunk is "theirs"
                    if not refused:
                        refused.append(resource)
                        return CP(3, "", "held by co-driver")
        return CP(0, "ok", "")

    monkeypatch.setattr(a2a.IntercomBridge, "_subprocess_runner",
                        staticmethod(runner))
    r1 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert r1["skipped_leased"] == 1 and r1["cards"] == 11
    assert len(refused) == 1
    assert len(read_cards(arch)) == 11
    assert r1["coverage_pct"] < 100.0           # honest per-driver coverage

    # the co-driver never wrote its card (crashed / was killed): resume with
    # the bus off picks up exactly the leased-away chunk — the resume law is
    # primary, leases only prevented CONCURRENT double-work
    monkeypatch.delenv("SCRIPTORIUM_A2A")
    r2 = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert r2["cards"] == 1
    cards = read_cards(arch)
    keys = [(c["doc_id"], c["seq"]) for c in cards]
    assert len(keys) == len(set(keys)) == 12    # no dupes, no gaps


def test_dry_run_preflights_without_spending(stubs, monkeypatch):
    """The preflight for an expensive read: verify the charter, select the
    slice, gate the budget, prove the tape readable — and make ZERO model
    calls, so nothing is spent and no card is written."""
    arch = frozen_mini(stubs)
    calls: list = []
    import ds

    real_request = ds.DsClient._request

    async def spy(self, body, **kw):
        calls.append(kw.get("unit_id"))
        return await real_request(self, body, **kw)

    monkeypatch.setattr(ds.DsClient, "_request", spy)

    rep = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs,
                               batch_size=4, dry_run=True))
    assert rep["dry_run"] is True
    assert rep["todo"] == 12 and rep["batches"] == 3
    assert rep["already_done"] == 0
    assert rep["charter_root"]
    assert rep["sampled_chunks_readable"] == "12/12"
    assert rep["est_realistic_usd"] <= rep["est_worst_case_usd"]
    assert calls == []                       # not one model call
    assert read_cards(arch) == []            # and not one card

    # the real read still works afterwards, unaffected
    real = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert real["cards"] == 12


def test_backfill_vectors_reaches_chunks_a_rerun_cannot(stubs):
    """A read that ran while :8092 was down leaves carded chunks with no
    vector — and a plain rerun can never fix them, because the resume law
    skips already-carded keys. The backfill is the only path, and it must be
    idempotent."""
    from read import backfill_vectors

    arch = frozen_mini(stubs)
    asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    db_path = arch / "catalog" / "index.sqlite"

    import sqlite3
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM vectors")                # simulate a sidecar-down read
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
    db.close()

    # a rerun does nothing: those chunks are carded, so they are not todo
    rerun = asyncio.run(run_read(arch, usd_cap=5.0, base_url=stubs, batch_size=4))
    assert rerun.get("cards", 0) == 0
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 0
    db.close()

    rep = backfill_vectors(arch)
    assert rep["missing"] == 12 and rep["added"] == 12
    assert rep["index"]["vectors"] == 12

    again = backfill_vectors(arch)                   # idempotent
    assert again["missing"] == 0 and again["added"] == 0
