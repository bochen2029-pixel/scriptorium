"""S1 units (no API): defect mutations, deterministic scoring, stratified
sampling, the YAML dumper round-trip — plus an end-to-end mini `discover` +
`freeze` against a content-routed stub (the S1 pipeline with zero real calls)."""

import asyncio
import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from cards import CardV0, Claim, Entity
from conftest import fresh_dir
from discover import (
    RecRow,
    compare_cards,
    dump_yaml,
    mutate,
    pack_batches,
    run_discover,
    run_freeze,
    stratified_sample,
)
from manifest import parse_yamlite
from tape import Tape

REPO = Path(__file__).parent.parent


# -- units ------------------------------------------------------------------

def test_mutations_deterministic_and_typed():
    text = ("Cortex is the memory organ. Cortex holds the tape. In 2024 the "
            "Cortex design moved 1500 lines. Cortex stays local.")
    m1 = mutate(text, "entity_swap")
    assert m1 == mutate(text, "entity_swap")            # deterministic
    assert "Zorbell" in m1[0] and m1[0].count("Cortex") == 1
    m2 = mutate(text, "negation_flip")
    assert " is not " in m2[0]
    m3 = mutate(text, "year_shift")
    assert "2031" in m3[0]
    m4 = mutate(text, "number_scale")
    assert "15000" in m4[0]
    assert mutate("no caps here at all", "entity_swap") is None


def test_compare_cards_math():
    ref = CardV0(entities=[Entity(name="Cortex"), Entity(name="Tape")],
                 claims=[Claim(subject="op", predicate="pinned", polarity=1)],
                 topics=["sovereignty"])
    same = compare_cards(ref, ref.model_copy(deep=True))
    assert same["score"] == 1.0
    disjoint = compare_cards(ref, CardV0(entities=[Entity(name="Other")],
                                         claims=[], topics=["misc"]))
    assert disjoint["entities"] == 0.0 and disjoint["score"] < 0.4
    empty_both = compare_cards(CardV0(), CardV0())
    assert empty_both["score"] == 1.0                    # nothing to miss


def test_stratified_sample_deterministic_and_proportional():
    rows = [RecRow(doc_id=f"d{i}", seq=0, tokens=500, chars=2000,
                   year=2024 + (i % 2), project=f"proj{i % 3}")
            for i in range(60)]
    s1 = stratified_sample(rows, 6000, seed=7)
    s2 = stratified_sample(rows, 6000, seed=7)
    assert [(r.doc_id, r.seq) for r in s1] == [(r.doc_id, r.seq) for r in s2]
    cells = {(r.year, r.project) for r in s1}
    assert len(cells) == 6                               # every cell got a voice
    total = sum(r.tokens for r in s1)
    assert 5000 <= total <= 9000                         # near budget


def test_pack_batches_respects_budget():
    rows = [RecRow(doc_id=f"d{i}", seq=0, tokens=400, chars=1600) for i in range(50)]
    batches = pack_batches(rows, max_tokens=1000)
    assert sum(len(b) for b in batches) == 50
    assert all(sum(r.tokens for r in b) <= 1000 for b in batches)


def test_dump_yaml_roundtrips_through_yamlite():
    obj = {"schema": 1, "status": "proposed", "scoring": {"bar": 0.55,
           "runs": [0.81, 0.83], "stable": True},
           "summary": 'multi word: with "quotes" and\nnewlines',
           "projects": [{"name": "cortex", "note": "memory: organ"},
                        {"name": "everywhere", "note": ""}],
           "empty_list": [], "nothing": None}
    text = dump_yaml(obj) + "\n"
    back = parse_yamlite(text)
    assert back["scoring"]["runs"] == [0.81, 0.83]
    assert back["scoring"]["stable"] is True
    assert back["summary"] == obj["summary"]
    assert back["projects"][0] == {"name": "cortex", "note": "memory: organ"}
    assert back["empty_list"] == [] and back["nothing"] is None


# -- end-to-end against a content-routed stub -------------------------------

CANNED_CARD = {"entities": [{"name": "Cortex", "kind": "project", "aliases": []}],
               "claims": [{"subject": "operator", "predicate": "built",
                           "object": "Cortex", "polarity": 1, "confidence": 0.9,
                           "time": "2024", "span": {"start": 0, "end": 20}}],
               "quotes": [], "topics": ["memory"],
               "style": {"voice": "log", "language": "en"},
               "retelling_candidates": [], "notes": None}
CANNED_ONTOLOGY = {"persons": [{"name": "Jin", "note": "correspondent"}],
                   "projects": [{"name": "Cortex", "note": "memory organ"}],
                   "themes": [{"name": "memory", "note": "recurring"}],
                   "genres": [{"name": "log", "note": "most of corpus"}],
                   "stance_axes": [], "recurring_stories": [], "style_notes": []}


class _P1Stub(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = req["messages"][-1]["content"]
        if user.startswith("Warm-up"):
            content = "ready"
        elif "CHUNK:" in user[:400]:          # bare (P1) or doc-header-prefixed (P2)
            content = json.dumps(CANNED_CARD)
        elif user.startswith("[{"):
            content = json.dumps({**CANNED_ONTOLOGY,
                                  "summary": "a small planted archive"})
        elif user.startswith("ONTOLOGY:"):
            content = json.dumps({"rubric_md": "# rubric v1\nExtract cards.",
                                  "prior_md": "# prior\nVoice first."})
        elif user.startswith("ASSIGNMENT:"):
            content = "## golden synthesis\n\nquoted [doc x | seq 0] gloss."
        else:
            content = json.dumps(CANNED_ONTOLOGY)        # induction batches
        body = json.dumps({"model": "deepseek-v4-flash-0731",
                           "usage": {"prompt_tokens": 1000,
                                     "prompt_cache_hit_tokens": 500,
                                     "prompt_cache_miss_tokens": 500,
                                     "completion_tokens": 200},
                           "choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def p1_stub():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _P1Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def mini_archive() -> Path:
    arch = fresh_dir("discover-mini")
    (arch / "files").mkdir()
    (arch / "manifest.yaml").write_text(
        "archive: mini\nroots:\n  - path: files\n    label: notes\n", "utf-8")
    tape = Tape.open(arch)
    for i in range(12):
        body_text = (
            f"Cortex note {i}. Cortex is the memory organ and Cortex holds "
            f"the tape. In 2024 the Cortex design moved 1500 lines. " * 30)
        doc_id = f"doc{i:02d}" + "0" * 26
        tape.append("text", {"doc_id": doc_id, "seq": 0, "text": body_text,
                             "chars": len(body_text),
                             "meta": {"unit": 0, "source": "file",
                                      "tokens_est": 900}})
        tape.append("doc", {"doc_id": doc_id, "root": "r", "path": f"proj{i % 2}/n{i}.md",
                            "source": "notes", "content_b2": f"c{i}", "size": 1,
                            "mtime": "2024-01-01T00:00:00+00:00",
                            "year": 2024 + (i % 2), "modality": "text",
                            "extractor": {}, "n_texts": 1,
                            "chars": len(body_text), "tokens_est": 900,
                            "notes": [], "minhash": None})
    tape.close()
    return arch


def test_discover_freeze_end_to_end(p1_stub, monkeypatch, tmp_path):
    import discover as dm

    # sandbox the code-dir so freeze mutates a COPY of scriptorium.lock
    sandbox = tmp_path / "code"
    sandbox.mkdir()
    shutil.copy(REPO / "scriptorium.lock", sandbox / "scriptorium.lock")
    shutil.copytree(REPO / "prompts", sandbox / "prompts")
    monkeypatch.setattr(dm, "CODE_DIR", sandbox)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    arch = mini_archive()
    meta = asyncio.run(run_discover(
        arch, usd_cap=5.0, sample_tokens=50_000, goldens_n=6, defects_n=2,
        concurrency=4, base_url=p1_stub))

    charter = arch / "charter"
    for f in ("ontology.yaml", "rubric_P2.md", "prior.md", "charter.yaml"):
        assert (charter / f).exists()
    assert meta["scoring"]["stable"] is True
    assert meta["scoring"]["runs"] == [1.0, 1.0]         # stub echoes references
    parsed = parse_yamlite((charter / "charter.yaml").read_text("utf-8"))
    assert parsed["status"] == "proposed"
    shards = sorted((charter / "goldens" / "shards").glob("shard-*.json"))
    assert len(shards) == 6
    defects = [json.loads(s.read_text("utf-8"))["defect"] for s in shards]
    assert sum(1 for d in defects if d) == 2
    assert len(list((charter / "goldens" / "syntheses").glob("*.md"))) == 3

    lock = run_freeze(arch)
    assert (charter / "charter.lock").exists()
    assert len(lock["fingerprints"]) == 4 + 6 + 3
    slock = json.loads((sandbox / "scriptorium.lock").read_text("utf-8"))
    row = slock["charters"][arch.name]         # one row per archive, never
    assert row["status"] == "frozen"           # overwritten by another freeze
    assert row["root_fingerprint"] == lock["root_fingerprint"]
    assert "charter" not in slock              # legacy single block retired
    assert parse_yamlite((charter / "charter.yaml").read_text("utf-8"))["status"] == "frozen"

    with pytest.raises(SystemExit, match="already exists"):
        run_freeze(arch)
    with pytest.raises(SystemExit, match="FROZEN"):
        asyncio.run(run_discover(arch, base_url=p1_stub))


def test_freeze_refuses_unstable(monkeypatch, tmp_path):
    import discover as dm
    sandbox = tmp_path / "code"
    sandbox.mkdir()
    shutil.copy(REPO / "scriptorium.lock", sandbox / "scriptorium.lock")
    monkeypatch.setattr(dm, "CODE_DIR", sandbox)

    arch = fresh_dir("discover-unstable")
    (arch / "manifest.yaml").write_text("roots:\n  - path: files\n", "utf-8")
    (arch / "files").mkdir()
    charter = arch / "charter"
    charter.mkdir()
    (charter / "charter.yaml").write_text(
        dump_yaml({"schema": 1, "status": "proposed",
                   "scoring": {"bar": 0.55, "runs": [0.9, 0.2], "stable": False}})
        + "\n", "utf-8")
    with pytest.raises(SystemExit, match="falsifier NOT passed"):
        run_freeze(arch)


def _rep(mean, scores):
    return {"mean": mean, "shards": [{"id": f"s{i}", "score": v}
                                     for i, v in enumerate(scores)]}


def test_stability_is_noise_aware_not_corpus_size():
    """The S1 stability rule must ask 'same or different?', not 'big corpus?'.
    Regression-locked to the four real charter scorings measured 2026-09-01."""
    from discover import stability_verdict

    # identical runs: zero gap, zero variance -> same
    v = stability_verdict(_rep(0.70, [0.7] * 20), _rep(0.70, [0.7] * 20))
    assert v["same"] and v["gap"] == 0.0 and v["paired_n"] == 20

    # a real shift, tiny noise: every shard drops 0.30 -> NOT the same rubric
    v = stability_verdict(_rep(0.70, [0.7] * 20), _rep(0.40, [0.4] * 20))
    assert not v["same"] and v["gap"] == 0.3

    # small n, high per-shard variance, gap over the absolute epsilon but
    # inside the noise the shards themselves show -> same (the false positive
    # the fixed 0.05 epsilon produced on collection #2's 42-shard charter)
    a = [0.9, 0.2, 0.8, 0.3, 0.95, 0.15, 0.75, 0.35]
    b = [0.2, 0.9, 0.3, 0.8, 0.15, 0.95, 0.35, 0.10]
    v = stability_verdict(_rep(sum(a) / len(a), a), _rep(sum(b) / len(b), b))
    assert v["gap"] > 0.05 and v["paired_se"] > 0.05 and v["same"]

    # the absolute epsilon stays a FLOOR: a near-deterministic pair with a
    # sub-epsilon gap passes even though its SE is ~0
    v = stability_verdict(_rep(0.700, [0.70] * 30), _rep(0.710, [0.71] * 30))
    assert v["same"] and v["paired_se"] < 0.001 and v["tolerance"] == 0.05

    # degenerate: a single shared shard has no variance estimate -> epsilon only
    v = stability_verdict(_rep(0.7, [0.7]), _rep(0.9, [0.9]))
    assert v["paired_n"] == 1 and v["t"] is None and not v["same"]


def test_roster_key_never_clobbers_a_different_archive(tmp_path):
    from discover import _roster_key

    a = tmp_path / "x" / "archive"
    b = tmp_path / "y" / "archive"
    slock = {}
    assert _roster_key(slock, a) == "archive"
    slock["charters"] = {"archive": {"archive": str(a)}}
    assert _roster_key(slock, a) == "archive"               # same archive: same row
    other = _roster_key(slock, b)
    assert other.startswith("archive@") and len(other) == len("archive@") + 8
