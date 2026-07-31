"""Provider-seam laws under test (PS-2/3/6/8/9 against a scripted stub server;
the meter against the pinned price sheet). No real API is touched here."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from pydantic import BaseModel

from ds import AimdGate, CapExceeded, DsClient, Meter, ModelChanged, UnitQuarantined

LOCK = json.loads((Path(__file__).parent.parent / "scriptorium.lock").read_text("utf-8"))
PRICES = LOCK["provider"]["price_sheet_usd_per_mtok"]

USAGE_DEFAULT = {"prompt_tokens": 100, "prompt_cache_hit_tokens": 0,
                 "prompt_cache_miss_tokens": 100, "completion_tokens": 20}


class TinyOut(BaseModel):
    answer: str


class _DsStub(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        with self.server.lock:
            self.server.requests.append(req)
            spec = (self.server.script.pop(0) if self.server.script
                    else {"content": '{"answer": "ok"}'})
        status = spec.get("status", 200)
        if status != 200:
            body = b'{"error": "scripted failure"}'
        else:
            msg = {"content": spec.get("content", '{"answer": "ok"}')}
            if "reasoning" in spec:
                msg["reasoning_content"] = spec["reasoning"]
            body = json.dumps({
                "model": spec.get("model", "deepseek-v4-flash-0731"),
                "usage": spec.get("usage", USAGE_DEFAULT),
                "choices": [{"message": msg}],
            }).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def ds_stub():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _DsStub)
    srv.script, srv.requests, srv.lock = [], [], threading.Lock()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.url = f"http://127.0.0.1:{srv.server_port}"
    yield srv
    srv.shutdown()


def client(stub, cap=5.0, **kw):
    return DsClient("test-pass", cap, base_url=stub.url, api_key="sk-test",
                    concurrency=kw.pop("concurrency", 8), **kw)


def run(coro):
    return asyncio.run(coro)


def test_meter_math_at_pinned_prices():
    m = Meter(prices=PRICES)
    m.record({"prompt_cache_hit_tokens": 1000, "prompt_cache_miss_tokens": 9000,
              "completion_tokens": 500,
              "completion_tokens_details": {"reasoning_tokens": 100}})
    assert m.in_hit == 1000 and m.in_miss == 9000
    assert m.reasoning_tokens == 100
    want = (9000 * PRICES["input_cache_miss"] + 1000 * PRICES["input_cache_hit"]
            + 500 * PRICES["output"]) / 1e6
    assert abs(m.usd() - want) < 1e-12
    assert m.hit_rate() == 0.1


def test_extract_payload_shape(ds_stub):
    c = client(ds_stub)

    async def go():
        out, meta = await c.chat(system="SYS", user="U", tail="\n[id:1]",
                                 mode="extract", unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "ok"
    req = ds_stub.requests[0]
    assert req["thinking"] == {"type": "disabled"}          # PS-2 extract
    assert req["temperature"] == 0
    assert req["response_format"] == {"type": "json_object"}
    assert req["messages"][0] == {"role": "system", "content": "SYS"}
    assert req["messages"][1]["content"].endswith("[id:1]")  # volatile tail LAST


def test_think_payload_shape(ds_stub):
    ds_stub.script = [{"content": "long-form prose", "reasoning": "chain..."}]
    c = client(ds_stub, journal_path=Path(__file__).parent.parent
               / "_testdata" / "dsjournal" / "j.jsonl")

    async def go():
        out, _ = await c.chat(system="SYS", user="U", mode="think",
                              effort="high", unit_id="t1")
        await c.close()
        return out

    assert run(go()) == "long-form prose"
    req = ds_stub.requests[0]
    assert req["reasoning_effort"] == "high"                 # PS-2 think
    assert "temperature" not in req and "thinking" not in req
    lines = (Path(__file__).parent.parent / "_testdata" / "dsjournal" / "j.jsonl"
             ).read_text("utf-8").splitlines()
    assert json.loads(lines[-1])["reasoning_content"] == "chain..."  # journaled


def test_ps3_ladder_retry_then_rescue(ds_stub):
    ds_stub.script = [{"content": "not json"}, {"content": "still not"},
                      {"content": "{broken"}, {"content": '{"answer": "saved"}'}]
    c = client(ds_stub)

    async def go():
        out, meta = await c.chat(system="S", user="U", mode="extract",
                                 unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "saved"
    assert meta["attempts"] == 4 and meta["rescued"] is True
    assert c.meter.retries == 2 and c.meter.rescues == 1
    rescue_req = ds_stub.requests[3]
    assert "thinking" not in rescue_req and rescue_req["reasoning_effort"] == "low"


def test_ps3_quarantine_is_typed(ds_stub):
    ds_stub.script = [{"content": "junk"}] * 4
    c = client(ds_stub)

    async def go():
        with pytest.raises(UnitQuarantined) as ei:
            await c.chat(system="S", user="U", mode="extract",
                         unit_id="u9", out_model=TinyOut)
        await c.close()
        return ei.value

    err = run(go())
    assert err.unit_id == "u9" and err.reason == "worker_output_invalid"
    assert c.meter.quarantined == 1


def test_ps6_backoff_and_aimd(ds_stub):
    ds_stub.script = [{"status": 429}, {"status": 500},
                      {"content": '{"answer": "ok"}'}]
    c = client(ds_stub, concurrency=8)

    async def go():
        out, _ = await c.chat(system="S", user="U", mode="extract",
                              unit_id="u1", out_model=TinyOut)
        await c.close()
        return out

    assert run(go()).answer == "ok"
    assert c.gate.target < 8                                  # halved (twice)


def test_ps8_refuses_to_start(ds_stub):
    c = client(ds_stub, cap=1.0)
    with pytest.raises(CapExceeded, match="refusing to start"):
        c.gate_estimate(est_in_tokens=50_000_000, est_out_tokens=10_000_000)
    run(c.close())


def test_ps8_halts_midflight(ds_stub):
    big_usage = {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 8_000_000,
                 "completion_tokens": 0}
    ds_stub.script = [{"usage": big_usage}]
    c = client(ds_stub, cap=1.0)

    async def go():
        await c.chat(system="S", user="U", mode="extract", unit_id="u1",
                     out_model=TinyOut)
        with pytest.raises(CapExceeded, match="mid-flight"):
            await c.chat(system="S", user="U", mode="extract", unit_id="u2",
                         out_model=TinyOut)
        await c.close()

    run(go())
    assert c.meter.usd() > 1.0


def test_ps9_model_change_halts(ds_stub):
    ds_stub.script = [{"model": "deepseek-v4-flash-0731"},
                      {"model": "deepseek-v4-flash-0899"}]
    c = client(ds_stub)

    async def go():
        await c.chat(system="S", user="U", mode="extract", unit_id="u1",
                     out_model=TinyOut)
        with pytest.raises(ModelChanged):
            await c.chat(system="S", user="U", mode="extract", unit_id="u2",
                         out_model=TinyOut)
        await c.close()

    run(go())


def test_empty_content_is_retried(ds_stub):
    ds_stub.script = [{"content": ""}, {"content": '{"answer": "second"}'}]
    c = client(ds_stub)

    async def go():
        out, meta = await c.chat(system="S", user="U", mode="extract",
                                 unit_id="u1", out_model=TinyOut)
        await c.close()
        return out, meta

    out, meta = run(go())
    assert out.answer == "second" and meta["attempts"] == 2


def test_reasoning_exhaustion_escalates_max_tokens(ds_stub):
    """Empty content + completion_tokens ~ max_tokens = reasoning ate the output
    budget; the ladder must escalate, not repeat the doomed call."""
    exhausted = {"prompt_tokens": 100, "prompt_cache_hit_tokens": 0,
                 "prompt_cache_miss_tokens": 100, "completion_tokens": 4000,
                 "completion_tokens_details": {"reasoning_tokens": 4000}}
    ds_stub.script = [{"content": "", "usage": exhausted},
                      {"content": "long-form prose"}]
    c = client(ds_stub)

    async def go():
        out, _ = await c.chat(system="S", user="U", mode="think", effort="high",
                              max_tokens=4000, unit_id="t1")
        await c.close()
        return out

    assert run(go()) == "long-form prose"
    assert ds_stub.requests[0]["max_tokens"] == 4000
    assert ds_stub.requests[1]["max_tokens"] == 12000     # 3x escalation


def test_ps5_warmup_shape(ds_stub):
    c = client(ds_stub)

    async def go():
        await c.warmup("FROZEN PREFIX")
        await c.close()

    run(go())
    req = ds_stub.requests[0]
    assert req["messages"][0]["content"] == "FROZEN PREFIX"
    assert req["max_tokens"] == 8 and "response_format" not in req


def test_aimd_reward_recovers_64_per_min():
    now = [0.0]
    g = AimdGate(start=64, cap=2400, clock=lambda: now[0])
    g.punish()
    assert g.target == 32
    now[0] += 30.0
    g.reward()
    assert g.target == pytest.approx(64.0)                    # +64/min * 30s


def test_env_loader_does_not_override(monkeypatch, tmp_path):
    import ds as ds_mod
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=from-file\nOTHER=x\n",
                                   encoding="utf-8")
    monkeypatch.setattr(ds_mod, "CODE_DIR", tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    monkeypatch.delenv("OTHER", raising=False)
    ds_mod.load_env()
    import os
    assert os.environ["DEEPSEEK_API_KEY"] == "from-env"       # existing wins
    assert os.environ["OTHER"] == "x"
