"""Harness-mode seam under test (HM-2/3/5/6/7/1 against a fake runtime factory;
the default api path and the S0 dependency closure stay untouched). No SDK, no
node, no network here — the DeepSeekHarness subprocess is always faked."""

import asyncio
import json
import time
from pathlib import Path

import pytest
from pydantic import BaseModel

import harness
from ds import CapExceeded, DsClient, DsError, UnitQuarantined
from harness import HarnessClient, HarnessUnavailable, build_task, make_client

LOCK = json.loads((Path(__file__).parent.parent / "scriptorium.lock").read_text("utf-8"))
PRICES = LOCK["provider"]["price_sheet_usd_per_mtok"]


class TinyOut(BaseModel):
    answer: str


class FakeRunResult:
    def __init__(self, final_response: str, finish_reason: str | None = "completed",
                 events: list | None = None):
        self.final_response = final_response
        self.finish_reason = finish_reason
        self.events = events or []


class FakeRuntime:
    """The DeepSeekHarness surface the transport actually touches."""

    def __init__(self, script: list[dict], calls: list[dict], tag: int, spec: dict):
        self.script = script          # shared queue across slots
        self.calls = calls            # shared call log
        self.tag = tag
        self.spec = spec

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, task: str, session_id: str | None = None) -> FakeRunResult:
        self.calls.append({"task": task, "session_id": session_id, "tag": self.tag})
        spec = (self.script.pop(0) if self.script
                else {"content": '{"answer": "ok"}'})
        if spec.get("raise"):
            raise RuntimeError(spec["raise"])
        if spec.get("sleep"):
            time.sleep(spec["sleep"])
        return FakeRunResult(spec.get("content", '{"answer": "ok"}'),
                             spec.get("finish_reason", "completed"),
                             spec.get("events"))


def make_factory(script: list[dict], calls: list[dict], rts: list[FakeRuntime]):
    def factory(spec: dict) -> FakeRuntime:
        rt = FakeRuntime(script, calls, len(rts), spec)
        rts.append(rt)
        return rt
    return factory


def client(factory, cap: float = 5.0, concurrency: int = 2, **kw) -> HarnessClient:
    kw.setdefault("backoff", (0, 0))       # instant ladder in tests
    return HarnessClient("test-pass", cap, concurrency=concurrency,
                         runtime_factory=factory, **kw)


def run(coro):
    return asyncio.run(coro)


def test_hm2_bundle_contract_first_payload_last():
    script, calls, rts = [], [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        out, meta = await c.chat(system="SYS CONTRACT", user="PAYLOAD BODY",
                                 tail="\n[id:7]", mode="extract", unit_id="u1",
                                 out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "ok"
    task = calls[0]["task"]
    assert (task.index("SYS CONTRACT") < task.index(harness.BOUNDARY)
            < task.index(harness.PAYLOAD_MARK) < task.index("PAYLOAD BODY"))
    assert task.endswith("[unit: u1; output budget ~4096 tokens]")
    assert calls[0]["session_id"].startswith("test-pass-u1-a0-")
    assert meta["session_id"] == calls[0]["session_id"]
    assert meta["finish_reason"] == "completed"


def test_hm2_extract_demand_and_spec_in_task():
    task = build_task("RUBRIC TEXT", "CHUNK", "\n[id:1]", mode="extract",
                      unit_id="u2", max_tokens=6000, effort=None)
    assert "ONLY one JSON object" in task
    assert "RUBRIC TEXT" in task and "CHUNK" in task and "[id:1]" in task
    think = build_task("R", "U", "", mode="think", unit_id="t1",
                       max_tokens=24000, effort="high")
    assert "Reasoning budget for this unit: high" in think
    assert "long-form content only" in think


def test_hm3_ladder_retry_then_rescue_fresh_sessions():
    script = [{"content": "not json"}, {"content": "still not"},
              {"content": "{broken"}, {"content": '{"answer": "saved"}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        out, meta = await c.chat(system="S", user="U", mode="extract",
                                 unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "saved"
    assert meta["attempts"] == 4 and meta["rescued"] is True
    assert c.meter.retries == 2 and c.meter.rescues == 1
    assert len(calls) == 4
    sids = [k["session_id"] for k in calls]
    assert len(set(sids)) == 4                       # fresh session per attempt
    assert "RETRY WITH CARE" in calls[3]["task"]     # rescue is re-derive framing


def test_hm3_quarantine_is_typed():
    script = [{"content": "junk"}] * 4
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        try:
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u9", out_model=TinyOut)
        except UnitQuarantined as e:
            await c.close()
            return e
        raise AssertionError("expected UnitQuarantined")

    err = run(go())
    assert err.unit_id == "u9" and err.reason == "worker_output_invalid"
    assert c.meter.quarantined == 1


def test_think_mode_returns_text_with_effort_hint():
    script = [{"content": "long-form prose"}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        out, _ = await c.chat(system="S", user="U", mode="think",
                              effort="high", max_tokens=24_000, unit_id="t1")
        await c.close()
        return out, calls

    out, calls = run(go())
    assert out == "long-form prose"
    assert "Reasoning budget for this unit: high" in calls[0]["task"]


def test_hm4_maxtokens_finish_reason_is_soft():
    script = [{"content": '{"answer": "x"}', "finish_reason": "max-tokens"},
              {"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        out, meta = await c.chat(system="S", user="U", mode="extract",
                                 unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "ok" and meta["attempts"] == 2
    assert c.meter.retries == 1


def test_finish_failure_surfaces_in_journal_and_quarantine(tmp_path):
    """A provider failure message (e.g. Modal 429) must be readable in the
    journal and the quarantine detail — never only in the session store."""
    ev = [{"type": "turn/end",
           "data": {"reason": {"kind": "error",
                               "failure": {"message": "429 Plan credits "
                                           "cannot be applied"}}}}]
    script = [{"finish_reason": "error", "content": "", "events": ev}] * 4
    calls, rts = [], []
    jp = tmp_path / "j.jsonl"
    c = client(make_factory(script, calls, rts), journal_path=jp)

    async def go():
        try:
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u1", out_model=TinyOut)
        except UnitQuarantined as e:
            await c.close()
            return e
        raise AssertionError("expected UnitQuarantined")

    err = run(go())
    assert "429 Plan credits" in err.detail
    entry = json.loads(jp.read_text("utf-8").splitlines()[0])
    assert entry["finish_failure"].startswith("429 Plan credits")


def test_hm4_error_finish_reason_and_runtime_exception_are_soft():
    script = [{"finish_reason": "error", "content": "partial"},
              {"raise": "boom"},
              {"content": '{"answer": "third"}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        out, meta = await c.chat(system="S", user="U", mode="extract",
                                 unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "third" and meta["attempts"] == 3


def test_hm6_gate_refuses_to_start():
    calls, rts = [], []
    c = client(make_factory([], calls, rts), cap=1.0)
    with pytest.raises(CapExceeded, match="refusing to start"):
        c.gate_estimate(est_in_tokens=50_000_000, est_out_tokens=10_000_000)
    run(c.close())


def test_hm6_halts_midflight_on_estimated_meter():
    calls, rts = [], []
    c = client(make_factory([], calls, rts), cap=1e-6)   # absurdly small

    async def go():
        out, _ = await c.chat(system="S", user="U", mode="extract",
                              unit_id="u1", out_model=TinyOut)
        with pytest.raises(CapExceeded, match="mid-flight"):
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u2", out_model=TinyOut)
        await c.close()
        return out

    assert run(go()).answer == "ok"
    assert c.meter.usd() > 1e-6


def test_hm5_meter_estimation_math_at_pinned_prices():
    script = [{"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        await c.chat(system="S" * 40, user="U" * 60, mode="extract",
                     unit_id="u1", out_model=TinyOut)
        await c.close()

    run(go())
    task_len = len(calls[0]["task"])
    in_est = task_len // c.chars_per_token
    out_est = len('{"answer": "ok"}') // c.chars_per_token
    assert c.meter.in_hit == 0 and c.meter.in_miss == in_est
    assert c.meter.out_tokens == out_est
    want = (in_est * PRICES["input_cache_miss"]
            + out_est * PRICES["output"]) / 1e6
    assert abs(c.meter.usd() - want) < 1e-12
    assert c.meter.snapshot()["hit_rate"] == 0.0


def test_warmup_boots_one_runtime_fail_fast():
    script = [{"content": '{"ok": true}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts))

    async def go():
        await c.warmup("FROZEN PREFIX")
        await c.close()

    run(go())
    assert calls[0]["task"].startswith("FROZEN PREFIX")
    assert calls[0]["session_id"].startswith("test-pass-warmup-")
    assert len(rts) == 1                              # exactly one runtime booted


def test_hm7_concurrent_calls_use_distinct_slots():
    script = [{"sleep": 0.05, "content": '{"answer": "a"}'},
              {"sleep": 0.05, "content": '{"answer": "b"}'}]
    calls, rts = [], []
    c = client(make_factory(script, calls, rts), concurrency=2)

    async def go():
        r = await asyncio.gather(
            c.chat(system="S", user="U", mode="extract", unit_id="u1",
                   out_model=TinyOut),
            c.chat(system="S", user="U", mode="extract", unit_id="u2",
                   out_model=TinyOut))
        await c.close()
        return r

    (a, _), (b, _) = run(go())
    assert {a.answer, b.answer} == {"a", "b"}
    assert len(rts) == 2                              # two runtimes, no sharing
    assert len({k["tag"] for k in calls}) == 2
    assert len({k["session_id"] for k in calls}) == 2


def test_hm1_runtime_boot_failure_is_fatal_not_retried():
    calls, rts = [], []

    def broken(spec):
        raise RuntimeError("no node.exe")

    c = client(make_factory([], calls, rts))
    c._factory = broken                               # simulate boot failure
    c._slots = [harness._Slot(dict(c._spec), broken)]

    async def go():
        try:
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u1", out_model=TinyOut)
        except HarnessUnavailable as e:
            await c.close()
            return e
        raise AssertionError("expected HarnessUnavailable")

    err = run(go())
    assert "runtime boot failed" in str(err)
    assert len(calls) == 0                            # never reached a worker


def test_hm1_sdk_missing_is_typed():
    calls, rts = [], []
    c = client(make_factory([], calls, rts))

    def no_sdk(spec):
        raise HarnessUnavailable("deepseek-harness-sdk is not installed")

    c._factory = no_sdk
    c._slots = [harness._Slot(dict(c._spec), no_sdk)]

    async def go():
        try:
            await c.warmup("P")
        except HarnessUnavailable as e:
            await c.close()
            return e
        raise AssertionError("expected HarnessUnavailable")

    assert "not installed" in str(run(go()))


def test_hm2_session_ids_globally_fresh_across_clients():
    """The session store persists across runs; two clients (two processes,
    two reruns) must never mint the same session id for the same unit —
    an on-disk id rerun errors instantly (measured live)."""
    ids = []
    for _ in range(2):
        script = [{"content": '{"answer": "ok"}'}]
        calls, rts = [], []
        c = client(make_factory(script, calls, rts))

        async def go(c=c, calls=calls):
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u1", out_model=TinyOut)
            await c.close()
            return calls[0]["session_id"]

        ids.append(run(go()))
    assert ids[0] != ids[1]
    assert all(i.startswith("test-pass-u1-a0-") for i in ids)


def test_make_client_dispatch():
    with pytest.raises(DsError, match="unknown provider"):
        make_client("p", 1.0, provider="nope")
    c = HarnessClient("p", 1.0, runtime_factory=make_factory([], [], []))
    assert c.provider_name and c.model_fp == c.model
    run(c.close())


def test_make_client_api_path_returns_dsclient(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    c = make_client("p", 1.0, provider="api", concurrency=8,
                    base_url="http://127.0.0.1:9")
    assert isinstance(c, DsClient)
    run(c.close())


def test_hm2v2_persona_patch_mode(tmp_path):
    """system_persona promotes the frozen prefix to the real system role: a
    Cordis patch file lands beside the journal, the spec carries it, and tasks
    shrink to discipline + payload + unit line (no duplicated prefix)."""
    script = [{"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    jp = tmp_path / "ds_calls.jsonl"
    c = client(make_factory(script, calls, rts), journal_path=jp,
               system_persona="FROZEN SYS PREFIX")

    async def go():
        await c.chat(system="FROZEN SYS PREFIX", user="PAYLOAD BODY",
                     tail="\n[id:7]", mode="extract", unit_id="u1",
                     out_model=TinyOut)
        await c.close()

    run(go())
    patch = tmp_path / harness.PERSONA_PATCH_NAME
    assert patch.exists()
    body = patch.read_text("utf-8")
    assert "- id: system-prompt" in body
    assert "includeHarnessIdentity: false" in body
    assert "includeRuntimeContext: false" in body
    # the persona ships with the END-OF-CONTRACT boundary appended (foreign
    # plugin sections follow the persona in the composed system role), and
    # every tool row is unmounted for single-shot workers (HM-8)
    assert json.dumps("FROZEN SYS PREFIX" + harness.PERSONA_END) in body
    for row in harness.WORKER_DISABLED_ROWS:
        assert f"- id: {row}\n  disabled: true" in body
    assert rts[0].spec["patches"] == (str(patch),)
    task = calls[0]["task"]
    assert harness.BOUNDARY not in task and "FROZEN SYS PREFIX" not in task
    assert harness.PAYLOAD_MARK not in task
    assert task.startswith("Reply with ONLY one JSON object")
    assert "PAYLOAD BODY" in task
    assert task.endswith("[unit: u1; output budget ~4096 tokens]")
    entry = json.loads(jp.read_text("utf-8").splitlines()[-1])
    assert entry["system_role"] == "patch"


def test_hm2v2_persona_pins_one_prefix_per_pass(tmp_path):
    calls, rts = [], []
    c = client(make_factory([], calls, rts),
               journal_path=tmp_path / "j.jsonl", system_persona="THE PREFIX")

    async def go():
        with pytest.raises(DsError, match="ONE frozen system prefix"):
            await c.chat(system="A DIFFERENT PREFIX", user="U", mode="extract",
                         unit_id="u1", out_model=TinyOut)
        await c.close()

    run(go())
    assert calls == []                               # refused before any spend


def test_hm2v2_intask_killswitch(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_HARNESS_INTASK", "1")
    script = [{"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    jp = tmp_path / "j.jsonl"
    c = client(make_factory(script, calls, rts), journal_path=jp,
               system_persona="FROZEN SYS")

    async def go():
        await c.chat(system="ANY SYS", user="U", mode="extract",
                     unit_id="u1", out_model=TinyOut)
        await c.close()

    run(go())
    assert c.system_role == "in-task"
    assert "patches" not in rts[0].spec
    assert harness.BOUNDARY in calls[0]["task"]      # v1 bundle shape intact
    entry = json.loads(jp.read_text("utf-8").splitlines()[-1])
    assert entry["system_role"] == "in-task"


def test_hm2v2_braced_prefix_refused(tmp_path):
    with pytest.raises(DsError, match="strict"):
        client(make_factory([], [], []), journal_path=tmp_path / "j.jsonl",
               system_persona="prefix with {{template}} braces")


def test_hm2v2_estimator_counts_persona(tmp_path):
    """HM-5: the persona reaches the model as system role every call — the
    estimated meter must count it or harness-$ undercuts api-$ comparability."""
    script = [{"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    persona = "P" * 400
    c = client(make_factory(script, calls, rts),
               journal_path=tmp_path / "j.jsonl", system_persona=persona)

    async def go():
        await c.chat(system=persona, user="U" * 60, mode="extract",
                     unit_id="u1", out_model=TinyOut)
        await c.close()

    run(go())
    task_len = len(calls[0]["task"])
    sent = len(persona) + len(harness.PERSONA_END)   # what the system role carries
    assert c.meter.in_miss == (task_len + sent) // c.chars_per_token


def test_write_persona_patch_roundtrip(tmp_path):
    """Arbitrary rubric text survives the JSON-escaped YAML scalar exactly
    (with the END-OF-CONTRACT boundary appended)."""
    nasty = 'quotes " and \\backslash\\ and\nnewlines\tand tabs — μñicode: 你好'
    p = harness.write_persona_patch(nasty, tmp_path / "persona.patch.yml")
    line = next(ln for ln in p.read_text("utf-8").splitlines()
                if ln.strip().startswith("persona: "))
    assert json.loads(line.split("persona: ", 1)[1]) == nasty + harness.PERSONA_END


def test_journal_records_estimated_usage(tmp_path):
    script = [{"content": '{"answer": "ok"}'}]
    calls, rts = [], []
    jp = tmp_path / "ds_calls.jsonl"
    c = client(make_factory(script, calls, rts), journal_path=jp)

    async def go():
        await c.chat(system="S", user="U", mode="extract",
                     unit_id="u1", out_model=TinyOut)
        await c.close()

    run(go())
    entry = json.loads(jp.read_text("utf-8").splitlines()[-1])
    assert entry["usage_estimated"] is True
    assert entry["unit"] == "u1" and entry["session_id"]
    assert entry["finish_reason"] == "completed"


def test_ensure_worker_home_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home",
                        lambda: tmp_path / "fakehome")
    home = tmp_path / "home"
    # no source anywhere -> honest placeholder (credentials source absent too)
    assert harness._ensure_worker_home(home) == "placeholder settings"
    # an existing home settings file always wins
    (home / "settings.yaml").write_text("a: 1", encoding="utf-8")
    assert harness._ensure_worker_home(home) == "existing"
    # otherwise the operator's ~/.dsh settings + managed credentials are
    # inherited explicitly (same box, same user, same trust domain)
    home2 = tmp_path / "home2"
    src = tmp_path / "fakehome" / ".dsh"
    src.mkdir(parents=True)
    (src / "settings.yaml").write_text("llm-pi-ai:\n  providers: {}\n",
                                       encoding="utf-8")
    (src / ".credentials.yaml").write_text("version: 1\n", encoding="utf-8")
    note = harness._ensure_worker_home(home2)
    assert "inherited" in note and "credentials" in note
    assert "llm-pi-ai" in (home2 / "settings.yaml").read_text("utf-8")
    assert (home2 / ".credentials.yaml").exists()
