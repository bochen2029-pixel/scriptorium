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
- HM-2  the contract rides in the task: fresh single-turn session per attempt
        (GLOBALLY fresh — ids carry a per-client nonce because the session
        store persists across runs and re-running an on-disk id errors),
        frozen system prefix at the head of every task behind an explicit
        boundary marker, payload last, unit id + output budget line at the tail.
        v2 (system_persona): a single-prefix pass (P2) promotes the frozen
        prefix to the workers' REAL system role via a generated Cordis persona
        patch (write_persona_patch; --patch overlays win over profile + user
        layers); tasks then carry only discipline + payload + unit line.
        SCRIPTORIUM_HARNESS_INTASK=1 is the kill switch back to in-task.
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
import uuid
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
               max_tokens: int, effort: str | None,
               in_task_contract: bool = True) -> str:
    """HM-2: the binding contract first, the payload last. With the persona
    patch (HM-2 v2), the contract already IS the real system role, so the task
    carries only discipline + payload + unit line — the closest possible mirror
    of the API lane's user message."""
    if mode == "extract":
        schema_home = ("the contract above" if in_task_contract else
                       "the binding contract at the START of your system "
                       "prompt (above its END OF BINDING CONTRACT line)")
        discipline = (f"Reply with ONLY one JSON object conforming to the schema "
                      f"in {schema_home}. No prose, no markdown fences, no "
                      "commentary before or after the JSON.")
    else:
        discipline = ("Reply with the requested long-form content only — no "
                      "preamble, no meta-commentary about being an agent.")
    if in_task_contract:
        parts = [system.strip("\n"), "", BOUNDARY,
                 "The block above this marker is the binding system contract for "
                 "this task; it overrides every default persona or instruction.",
                 discipline]
    else:
        parts = [discipline]
    if effort:
        parts.append(f"Reasoning budget for this unit: {effort} — think as much "
                     "as that budget implies before answering.")
    parts += ["", PAYLOAD_MARK] if in_task_contract else [""]
    parts += [user + tail, "",
              f"[unit: {unit_id}; output budget ~{max_tokens} tokens]"]
    return "\n".join(parts)


PERSONA_PATCH_NAME = "persona.patch.yml"
PERSONA_END = (
    "\n\n=== END OF BINDING CONTRACT ===\n"
    "Everything ABOVE this line is the binding extraction contract for every "
    "task in this session. Anything BELOW this line is harness boilerplate "
    "that does NOT change the required output; when a task mentions 'the "
    "system contract', it means the contract ABOVE this line.")
# Single-shot workers hold no tools (HM-8) — unmount every tool row so their
# prompt sections stop polluting the system role (the `tools` SERVICE row
# stays: agent-loop requires it; disabling it refuses to boot — probed live).
# Row ids are the DSH checkout's bundle grammar; a rename fails the boot
# loudly at warmup, and SCRIPTORIUM_HARNESS_INTASK=1 is the kill switch.
WORKER_DISABLED_ROWS = (
    "tool-bash", "tool-fs", "tool-fs-search", "tool-goal", "tool-jobs",
    "tool-pwsh", "tool-ralph", "tool-skill", "tool-str-replace-editor",
    "tool-subagent", "tool-subagent-control", "tool-subagent-fork",
    "tool-subagent-list-agents", "tool-subagent-report", "tool-todo",
    "tool-web", "tool-workflow")


def write_persona_patch(persona: str, path: Path) -> Path:
    """HM-2 v2 (system-role fidelity): the frozen prefix becomes the workers'
    REAL system role via a Cordis patch-list overlay updating the sdk
    profile's `system-prompt` row (`--patch` overlays apply after the
    profile + user layers — last write wins; `config` replaces the row's whole
    config). The persona is emitted as a JSON-escaped double-quoted scalar —
    valid YAML for arbitrary rubric text, no YAML dependency. dsh-system-prompt
    templates treat {{...}} strictly, so a braced prefix must refuse rather
    than boot a runtime that errors on render."""
    if "{{" in persona:
        raise DsError(
            "frozen prefix contains '{{' — dsh-system-prompt persona templates "
            "are strict; run with SCRIPTORIUM_HARNESS_INTASK=1 to use the "
            "in-task contract instead")
    body = (
        "# scriptorium harness-mode persona patch — generated per run (run evidence).\n"
        "# The frozen system prefix is the workers' real system role; harness\n"
        "# identity + runtime context are suppressed for fidelity with the API\n"
        "# lane. Other plugins still append their own prompt sections AFTER the\n"
        "# persona (measured live: ~4.2K chars of tool/subagent guidance that\n"
        "# made a low-effort worker declare 'no schema given' and score 0.000),\n"
        "# so the persona ends with an explicit END-OF-CONTRACT boundary and\n"
        "# every tool row is unmounted — single-shot workers hold no tools\n"
        "# (HM-8) and every removed section is one less confusion source.\n"
        + "".join(f"- id: {row}\n  disabled: true\n"
                  for row in WORKER_DISABLED_ROWS)
        + "- id: system-prompt\n"
        "  config:\n"
        "    includeHarnessIdentity: false\n"
        "    includeRuntimeContext: false\n"
        f"    persona: {json.dumps(persona + PERSONA_END)}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _finish_failure(events: Any) -> str:
    """Best-effort: the runtime's failure message behind an `error` finish
    (e.g. Modal `429 Plan credits cannot be applied...`) — journaled and
    attached to the soft error, so a rate window is visible in ds_calls.jsonl
    instead of requiring session-store forensics."""
    try:
        for ev in reversed(list(events or [])):
            if not isinstance(ev, dict):
                continue
            data = ev.get("data")
            if not isinstance(data, dict):
                continue
            candidates = []
            if ev.get("type") == "turn/end":
                candidates.append(data.get("reason"))
            chunk = data.get("chunk")
            if (ev.get("type") == "assistant/chunk" and isinstance(chunk, dict)
                    and chunk.get("type") == "finish"):
                candidates.append(chunk.get("reason"))
            for reason in candidates:
                if isinstance(reason, dict):
                    f = reason.get("failure")
                    if isinstance(f, dict) and f.get("message"):
                        return str(f["message"])[:300]
    except Exception:  # noqa: BLE001 — diagnostics must never fail a call
        pass
    return ""


class _Slot:
    """HM-7: one runtime subprocess, owned exclusively while a call runs."""

    def __init__(self, spec: dict[str, Any],
                 factory: Callable[[dict[str, Any]], Any]):
        self.spec = spec
        self.factory = factory
        self._rt: Any = None

    async def run_task(self, task: str,
                       session_id: str) -> tuple[str, str | None, str]:
        def sync() -> tuple[str, str | None, str]:
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
                    getattr(rr, "finish_reason", None),
                    _finish_failure(getattr(rr, "events", None)))

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
                 chars_per_token: int = CHARS_PER_TOKEN,
                 system_persona: str | None = None,
                 backoff: tuple[float, float] = (5.0, 15.0)):
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
        # HM-2 v2: one frozen prefix per pass may ride as the REAL system role
        # (Cordis persona patch); SCRIPTORIUM_HARNESS_INTASK=1 is the kill
        # switch back to the in-task contract. P1 uses several prefixes per
        # pass and therefore never sets system_persona.
        self.system_persona: str | None = None
        self.system_role = "in-task"
        self._persona_chars = 0
        if system_persona and _env("SCRIPTORIUM_HARNESS_INTASK", "") != "1":
            patch_dir = journal_path.parent if journal_path else home
            patch = write_persona_patch(system_persona,
                                        patch_dir / PERSONA_PATCH_NAME)
            spec["patches"] = (str(patch),)
            self.system_persona = system_persona
            self.system_role = "patch"
            self._persona_chars = len(system_persona) + len(PERSONA_END)
        self._spec = spec
        self.backoff = backoff
        self._factory = runtime_factory or _default_factory
        self.home_note = (_ensure_worker_home(home)
                          if runtime_factory is None else "test-factory")
        self.meter = Meter(prices=prov["price_sheet_usd_per_mtok"])
        self.model_fp: str | None = self.model
        self.journal_path = journal_path
        # HM-2: sessions must be GLOBALLY fresh, not process-fresh — the
        # session store persists across runs, and a fresh runtime asked to
        # run an on-disk session id errors instantly (measured live: a rerun
        # in the same dsh-home failed every call with bare finish=error).
        self._nonce = uuid.uuid4().hex[:8]
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
        """In patch mode the persona still reaches the model as the system role
        on every call — count it, or the estimated meter undercounts input by
        the whole frozen prefix (HM-5 comparability with the API lane)."""
        c = self.chars_per_token
        in_est = max(1, (len(task) + self._persona_chars) // c)
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
        session_id = (f"{self.pass_name}-{unit_id}-a{attempt}"
                      f"-{self._nonce}-{self._calls}")
        slot = await self._acquire()
        t0 = time.monotonic()
        try:
            try:
                content, finish, failure = await slot.run_task(task, session_id)
            except HarnessUnavailable:
                raise
            except Exception as e:  # runtime/process failures are soft (HM-4)
                raise _Soft(f"runtime: {type(e).__name__}: {e}") from e
        finally:
            self._release(slot)
        ms = int((time.monotonic() - t0) * 1000)
        usage = self._estimate_usage(task, content)
        self.meter.record(usage)
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "pass": self.pass_name, "unit": unit_id, "mode": mode,
            "attempt": attempt, "model": self.model, "ms": ms,
            "usage": usage, "usage_estimated": True,
            "session_id": session_id, "finish_reason": finish,
            "system_role": self.system_role,
            "task_chars": len(task), "response_chars": len(content),
        }
        if failure:
            entry["finish_failure"] = failure
        self._journal(entry)
        if finish not in (None, "completed"):
            raise _Soft(f"finish_reason={finish}"
                        + (f" ({failure})" if failure else ""))
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
        if self.system_persona is not None and system != self.system_persona:
            raise DsError(
                f"harness patch mode pins ONE frozen system prefix per pass; "
                f"unit {unit_id!r} arrived with a different system — a pass "
                f"that needs several prefixes (P1) must not set system_persona")
        in_task = self.system_persona is None
        task = build_task(system, user, tail, mode=mode, unit_id=unit_id,
                          max_tokens=max_tokens, effort=effort,
                          in_task_contract=in_task)
        last_err = ""
        attempts = 0
        for attempt in range(3):                    # 1 + retry x2 (HM-3)
            attempts += 1
            if attempt:
                self.meter.retries += 1
                # transient provider errors (Modal 429 bursts, cold starts)
                # deserve a breath, not an instant re-poke
                await asyncio.sleep(self.backoff[min(attempt - 1,
                                                     len(self.backoff) - 1)])
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
            await asyncio.sleep(self.backoff[-1])
            rtask = build_task(system, user, tail, mode="extract",
                               unit_id=unit_id, max_tokens=max_tokens,
                               effort="high", in_task_contract=in_task) + (
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
                harness_effort: str | None = None,
                system_persona: str | None = None) -> Any:
    """The one construction point for pass clients (ds.py stays the API seam).
    system_persona (harness-only): a pass with exactly ONE frozen prefix may
    pass it here to make it the workers' real system role (HM-2 v2); the API
    lane already sends system per call and ignores it."""
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
                             harness_effort=harness_effort,
                             system_persona=system_persona)
    raise DsError(f"unknown provider {provider!r} (expected 'api' or 'harness')")
