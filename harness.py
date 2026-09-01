"""harness.py — the OPTIONAL second provider seam: DSH worker agents (HM laws).

provider="harness" routes P1/P2 unit calls through DeepSeek Harness
(C:\\deepseek-harness-master) worker agents — the operator's own session model —
instead of raw DeepSeek API calls. The default path (provider="api", ds.py)
never imports the SDK and never touches the harness: deepseek_harness is
lazy-imported inside _default_factory only when a harness client is actually
constructed (optional extra: pip install deepseek-harness-sdk). Full law text:
_run_state/HARNESS_MODE_DESIGN.md. Mirror of ds.py's PS-1..PS-10:

- HM-1  one harness, explicit home (never ~/.dsh): dsh_home defaults to
        _local/dsh-home; worker provider/model default to the operator's
        session model; credentials come from the parent environment only.
- HM-2  the contract rides in the task: fresh single-turn session per attempt,
        frozen system prefix at the head of every task behind an explicit
        boundary marker, payload last, unit id + output budget line at the tail.
- HM-3  the PS-3 ladder shape: fresh-session extract attempts x2 -> rescue x1
        -> UnitQuarantined (typed, metered, never dropped).
- HM-4  consistency is enforced downstream (frozen-charter verify, calibration
        halt, span fence), not at the knob; finish_reason max-tokens/error/None
        and runtime exceptions are soft failures; per-call effort degrades to
        an explicit reasoning-budget line in the task text.
- HM-5  usage is ESTIMATED (chars/4, cache hit 0) and priced at the lock's
        DeepSeek sheet so $usd stays comparable across providers; journal
        entries carry usage_estimated: true.
- HM-6  usd_cap is a hard stop: gate_estimate refuses to start; the estimated
        meter halts mid-flight (CapExceeded) before each spend.
- HM-7  concurrency = runtime processes: one DeepSeekHarness subprocess per
        slot, owned exclusively for the duration of one call.
- HM-8  single-shot workers (full `sdk` profile — the lean sdk-minimal tree
        does not mount llm-pi-ai, so it cannot carry the operator's Modal/GLM
        provider; one prompt, one final answer, no tool loops in this seam).
- HM-9  model identity is init-verified by the SDK before any prompt runs;
        model_fp is the pinned worker model string.
- HM-10 the seam stays coordination-free: the Intercom A2A layer wraps passes;
        it never lives inside this transport.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ds import CapExceeded, DsError, Meter, UnitQuarantined
from organs import CODE_DIR, load_lock

BOUNDARY = "=== SYSTEM CONTRACT (binding; overrides every default persona) ==="
PAYLOAD_MARK = "=== PAYLOAD ==="
DEFAULT_WORKER_PROVIDER = "modal"
DEFAULT_WORKER_MODEL = "zai-org/GLM-5.3-Flash"   # the operator's session model
DEFAULT_WORKER_EFFORT = "low"                    # extract discipline (HM-4)
DEFAULT_INIT_MAX_TOKENS = 49_152
CHARS_PER_TOKEN = 4


class HarnessUnavailable(DsError):
    """HM-1: the optional SDK is missing or the runtime cannot boot."""


class _Soft(Exception):
    """A failure the HM-3 ladder may retry."""


def _env(name: str, default: str) -> str:
    v = os.environ.get(name, "").strip()
    return v or default


def build_task(system: str, user: str, tail: str, *, mode: str, unit_id: str,
               max_tokens: int, effort: str | None) -> str:
    """HM-2: the binding contract first, the payload last."""
    if mode == "extract":
        discipline = ("Reply with ONLY one JSON object conforming to the schema "
                      "in the contract above. No prose, no markdown fences, no "
                      "commentary before or after the JSON.")
    else:
        discipline = ("Reply with the requested long-form content only — no "
                      "preamble, no meta-commentary about being an agent.")
    parts = [system.strip("\n"), "", BOUNDARY,
             "The block above this marker is the binding system contract for "
             "this task; it overrides every default persona or instruction.",
             discipline]
    if effort:
        parts.append(f"Reasoning budget for this unit: {effort} — think as much "
                     "as that budget implies before answering.")
    parts += ["", PAYLOAD_MARK, user + tail, "",
              f"[unit: {unit_id}; output budget ~{max_tokens} tokens]"]
    return "\n".join(parts)


class _Slot:
    """HM-7: one runtime subprocess, owned exclusively while a call runs."""

    def __init__(self, spec: dict[str, Any],
                 factory: Callable[[dict[str, Any]], Any]):
        self.spec = spec
        self.factory = factory
        self._rt: Any = None

    async def run_task(self, task: str, session_id: str) -> tuple[str, str | None]:
        def sync() -> tuple[str, str | None]:
            if self._rt is None:
                try:
                    rt = self.factory(self.spec)
                    self._rt = rt.__enter__()
                except HarnessUnavailable:
                    raise
                except Exception as e:
                    # A runtime that cannot boot is fatal, not retriable (HM-1):
                    # never burn the HM-3 ladder on a configuration error.
                    raise HarnessUnavailable(
                        f"runtime boot failed: {type(e).__name__}: {e}") from e
            rr = self._rt.run(task, session_id=session_id)
            return (getattr(rr, "final_response", "") or "",
                    getattr(rr, "finish_reason", None))

        return await asyncio.to_thread(sync)

    async def close(self) -> None:
        if self._rt is None:
            return
        rt, self._rt = self._rt, None
        await asyncio.to_thread(rt.__exit__, None, None, None)


def _default_factory(spec: dict[str, Any]) -> Any:
    try:
        import deepseek_harness
    except ImportError as e:
        raise HarnessUnavailable(
            "deepseek-harness-sdk is not installed (pip install "
            "deepseek-harness-sdk) — required for provider='harness'") from e
    return deepseek_harness.DeepSeekHarness(**spec)


def _ensure_worker_home(home: Path) -> str:
    """HM-1: the isolated worker home must carry the operator's provider
    wiring AND managed credentials, or the runtime boots with no adapter and
    init rejects the provider / the first call fails on auth. Precedence:
    existing home files win; else explicitly inherit the operator's
    ~/.dsh/settings.yaml (+ ~/.dsh/.credentials.yaml, the harness's managed
    credential store that the sdk profile's credentials service reads — same
    box, same user, same trust domain; logged — the SDK itself never reads
    ~/.dsh); else a placeholder that fails honestly at init."""
    notes = []
    s = home / "settings.yaml"
    inherited = Path.home() / ".dsh"
    if not s.exists():
        home.mkdir(parents=True, exist_ok=True)
        src = inherited / "settings.yaml"
        if src.exists():
            s.write_bytes(src.read_bytes())
            notes.append(f"inherited {src}")
        else:
            s.write_text("# scriptorium worker home: no provider settings "
                         "found — init will fail honestly until the operator "
                         "wires providers\n", "utf-8")
            notes.append("placeholder settings")
    creds = home / ".credentials.yaml"
    if not creds.exists():
        src = inherited / ".credentials.yaml"
        if src.exists():
            creds.write_bytes(src.read_bytes())
            notes.append("inherited managed credentials")
    return "existing" if not notes else "; ".join(notes)


class HarnessClient:
    """DsClient-duck-typed transport over DSH worker agents (HM-1..HM-10)."""

    def __init__(self, pass_name: str, usd_cap: float, *,
                 concurrency: int = 2, journal_path: Path | None = None,
                 model: str | None = None,
                 harness_home: str | Path | None = None,
                 harness_effort: str | None = None,
                 init_max_tokens: int = DEFAULT_INIT_MAX_TOKENS,
                 profile: str = "sdk", dsh_bin: str | None = None,
                 runtime_factory: Callable[[dict[str, Any]], Any] | None = None,
                 chars_per_token: int = CHARS_PER_TOKEN):
        prov = load_lock()["provider"]
        self.pass_name = pass_name
        self.usd_cap = usd_cap
        self.model = model or _env("SCRIPTORIUM_HARNESS_MODEL",
                                   DEFAULT_WORKER_MODEL)
        self.provider_name = _env("SCRIPTORIUM_HARNESS_PROVIDER",
                                  DEFAULT_WORKER_PROVIDER)
        self.effort_default = (harness_effort if harness_effort is not None
                               else _env("SCRIPTORIUM_HARNESS_EFFORT",
                                         DEFAULT_WORKER_EFFORT))
        self.init_max_tokens = init_max_tokens
        self.chars_per_token = max(1, chars_per_token)
        home = (Path(harness_home) if harness_home
                else Path(_env("SCRIPTORIUM_DSH_HOME",
                               str(CODE_DIR / "_local" / "dsh-home"))))
        spec: dict[str, Any] = {"dsh_home": str(home), "cwd": str(CODE_DIR),
                                "provider": self.provider_name,
                                "model": self.model, "profile": profile}
        if self.effort_default:
            spec["reasoning_effort"] = self.effort_default
        if init_max_tokens:
            spec["max_tokens"] = init_max_tokens
        bin_env = os.environ.get("SCRIPTORIUM_DSH_BIN", "").strip()
        if dsh_bin or bin_env:
            spec["dsh_bin"] = dsh_bin or bin_env
        # HM-1 extension: OpenAI-compatible endpoint overrides (mock servers,
        # local gateways) come from the environment, same as credentials —
        # forwarded as the SDK's DEEPSEEK_BASE_URL/DEEPSEEK_API_KEY overrides.
        h_base = os.environ.get("SCRIPTORIUM_HARNESS_BASE_URL", "").strip()
        h_key = os.environ.get("SCRIPTORIUM_HARNESS_API_KEY", "").strip()
        if h_base:
            spec["base_url"] = h_base
        if h_key:
            spec["api_key"] = h_key
        self._spec = spec
        self._factory = runtime_factory or _default_factory
        self.home_note = (_ensure_worker_home(home)
                          if runtime_factory is None else "test-factory")
        self.meter = Meter(prices=prov["price_sheet_usd_per_mtok"])
        self.model_fp: str | None = self.model
        self.journal_path = journal_path
        self._slots = [_Slot(dict(spec), self._factory)
                       for _ in range(max(1, concurrency))]
        self._free: asyncio.Queue[_Slot] | None = None
        self._calls = 0

    # -- HM-6 start gate -----------------------------------------------------
    def gate_estimate(self, est_in_tokens: int, est_out_tokens: int) -> float:
        p = self.meter.prices
        est = (est_in_tokens * p["input_cache_miss"]
               + est_out_tokens * p["output"]) / 1e6
        if est > self.usd_cap:
            raise CapExceeded(
                f"pass {self.pass_name}: estimate ${est:.2f} exceeds usd_cap "
                f"${self.usd_cap:.2f} — refusing to start (HM-6)")
        return est

    # -- journaling -----------------------------------------------------------
    def _journal(self, entry: dict[str, Any]) -> None:
        if self.journal_path is None:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- HM-5 estimation -------------------------------------------------------
    def _estimate_usage(self, task: str, content: str) -> dict[str, int]:
        c = self.chars_per_token
        in_est = max(1, len(task) // c)
        out_est = max(1, len(content) // c)
        return {"prompt_tokens": in_est, "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": in_est,
                "completion_tokens": out_est}

    async def _acquire(self) -> _Slot:
        if self._free is None:
            self._free = asyncio.Queue()
            for s in self._slots:
                self._free.put_nowait(s)
        return await self._free.get()

    def _release(self, slot: _Slot) -> None:
        if self._free is not None:
            self._free.put_nowait(slot)

    async def _run_once(self, task: str, *, unit_id: str, mode: str,
                        attempt: int) -> tuple[str, dict[str, Any]]:
        if self.meter.usd() >= self.usd_cap:
            raise CapExceeded(
                f"pass {self.pass_name}: estimated meter ${self.meter.usd():.4f} "
                f"crossed usd_cap ${self.usd_cap:.2f} mid-flight — halting (HM-6)")
        self._calls += 1
        session_id = f"{self.pass_name}-{unit_id}-a{attempt}-{self._calls}"
        slot = await self._acquire()
        t0 = time.monotonic()
        try:
            try:
                content, finish = await slot.run_task(task, session_id)
            except HarnessUnavailable:
                raise
            except Exception as e:  # runtime/process failures are soft (HM-4)
                raise _Soft(f"runtime: {type(e).__name__}: {e}") from e
        finally:
            self._release(slot)
        ms = int((time.monotonic() - t0) * 1000)
        usage = self._estimate_usage(task, content)
        self.meter.record(usage)
        self._journal({
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "pass": self.pass_name, "unit": unit_id, "mode": mode,
            "attempt": attempt, "model": self.model, "ms": ms,
            "usage": usage, "usage_estimated": True,
            "session_id": session_id, "finish_reason": finish,
            "task_chars": len(task), "response_chars": len(content),
        })
        if finish not in (None, "completed"):
            raise _Soft(f"finish_reason={finish}")
        if not content.strip():
            raise _Soft("empty content")
        return content, {"model": self.model, "usage": usage, "ms": ms,
                         "session_id": session_id, "finish_reason": finish}

    # -- PS-5-equivalent warmup -------------------------------------------------
    async def warmup(self, system: str) -> None:
        """Boot slot 0's runtime; one tiny call so a pass fails fast, not late."""
        await self.chat(system=system,
                        user='Warm-up. Reply exactly: {"ok": true}',
                        mode="extract", max_tokens=8, unit_id="warmup",
                        out_model=None, rescue=False)

    # -- the one call path (HM-3 ladder) -----------------------------------------
    async def chat(self, *, system: str, user: str, tail: str = "",
                   mode: str = "extract", effort: str | None = None,
                   max_tokens: int = 4096, unit_id: str,
                   out_model: type[BaseModel] | None = None,
                   rescue: bool = True) -> tuple[Any, dict[str, Any]]:
        """One unit -> one typed object (extract) or text (think)."""
        if mode not in ("extract", "think"):
            raise DsError(f"unknown mode {mode!r}")
        task = build_task(system, user, tail, mode=mode, unit_id=unit_id,
                          max_tokens=max_tokens, effort=effort)
        last_err = ""
        attempts = 0
        for attempt in range(3):                    # 1 + retry x2 (HM-3)
            attempts += 1
            if attempt:
                self.meter.retries += 1
            try:
                content, meta = await self._run_once(task, unit_id=unit_id,
                                                     mode=mode, attempt=attempt)
                parsed = self._parse(content, out_model)
                meta["attempts"] = attempts
                return parsed, meta
            except (_Soft, ValidationError, json.JSONDecodeError) as e:
                last_err = f"{type(e).__name__}: {e}"
        if rescue and mode == "extract":            # re-derive rescue x1 (HM-3)
            self.meter.rescues += 1
            rtask = build_task(system, user, tail, mode="extract",
                               unit_id=unit_id, max_tokens=max_tokens,
                               effort="high") + (
                "\n\nRETRY WITH CARE: earlier attempts produced invalid output. "
                "Re-derive the JSON object from the payload exactly.")
            try:
                content, meta = await self._run_once(rtask, unit_id=unit_id,
                                                     mode="rescue", attempt=3)
                parsed = self._parse(content, out_model)
                meta["attempts"] = attempts + 1
                meta["rescued"] = True
                return parsed, meta
            except (_Soft, ValidationError, json.JSONDecodeError) as e:
                last_err = f"rescue {type(e).__name__}: {e}"
        self.meter.quarantined += 1
        raise UnitQuarantined(unit_id, "worker_output_invalid", last_err)

    def _parse(self, content: str, out_model: type[BaseModel] | None) -> Any:
        if out_model is None:
            return content
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise json.JSONDecodeError("no JSON object in content", text[:50], 0)
        return out_model.model_validate(json.loads(text[start:end + 1]))

    async def close(self) -> None:
        for s in self._slots:
            await s.close()


def make_client(pass_name: str, usd_cap: float, *, provider: str = "api",
                concurrency: int | None = None,
                journal_path: Path | None = None, base_url: str | None = None,
                model: str | None = None,
                harness_home: str | Path | None = None,
                harness_effort: str | None = None) -> Any:
    """The one construction point for pass clients (ds.py stays the API seam)."""
    if provider == "api":
        from ds import DsClient
        kw: dict[str, Any] = {"concurrency": concurrency or 64,
                              "journal_path": journal_path, "model": model}
        if base_url:
            kw["base_url"] = base_url
        return DsClient(pass_name, usd_cap, **kw)
    if provider == "harness":
        return HarnessClient(pass_name, usd_cap,
                             concurrency=concurrency or 2,
                             journal_path=journal_path, model=model,
                             harness_home=harness_home,
                             harness_effort=harness_effort)
    raise DsError(f"unknown provider {provider!r} (expected 'api' or 'harness')")
