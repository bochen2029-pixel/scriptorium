"""ds.py — the ONE provider seam (spec section 1, laws PS-1..PS-10).

Every DeepSeek API call in this organ goes through DsClient; there is no other
API call-site (section 8 refusal; local.py talks only to localhost sidecars).

- PS-1  one model: deepseek-v4-flash at api.deepseek.com; base_url/model are
        constructor overrides so the seam can point anywhere OpenAI-compatible.
- PS-2  two modes: extract (thinking disabled, temperature 0, JSON) vs think
        (thinking on, reasoning_effort low/high/max; determinism knobs not sent
        — thinking mode silently ignores them). reasoning_content goes to the
        call journal: working paper, never a citable artifact.
- PS-3  JSON verified client-side by pydantic; ladder: same call x2 ->
        thinking-enabled rescue x1 -> UnitQuarantined (typed, never dropped).
- PS-4  cache shaping is the CALLER's layout (frozen system prefix, volatile
        tail last); the meter reads prompt_cache_hit/miss_tokens per call and
        reports the realized hit rate.
- PS-5  warmup(): one serial call to cache a frozen prefix before fan-out.
- PS-6  AimdGate: bounded concurrency, halve on 429/5xx, +64/min recovery.
- PS-7  is_peak_beijing() + surcharge note at pass start.
- PS-8  usd_cap is a hard stop: gate() refuses to start a pass whose estimate
        exceeds cap; chat() raises CapExceeded mid-flight the moment the meter
        crosses it (checkpoint-clean: callers checkpoint, then stop).
- PS-9  the model version string the API returns is the fingerprint; a mid-pass
        change raises ModelChanged (halt + operator decision).
- PS-10 single-shot workers only; no tool loops in this seam.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from organs import CODE_DIR, load_lock


class DsError(Exception):
    pass


class CapExceeded(DsError):
    """PS-8: the budget is a hard stop, at start or mid-flight."""


class ModelChanged(DsError):
    """PS-9: the API's reported model version changed mid-pass."""


class UnitQuarantined(DsError):
    def __init__(self, unit_id: str, reason: str, detail: str = ""):
        super().__init__(f"{unit_id}: {reason}: {detail[:200]}")
        self.unit_id = unit_id
        self.reason = reason
        self.detail = detail


def load_env() -> None:
    """Tiny .env loader (stdlib; python-dotenv is not in the dependency law).
    Existing process env wins."""
    p = CODE_DIR / ".env"
    if not p.exists():
        return
    for line in p.read_text("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def is_peak_beijing(now_utc: datetime | None = None) -> bool:
    """PS-7. Beijing is UTC+8, no DST."""
    now = now_utc or datetime.now(UTC)
    hm = (now.hour + 8) % 24 * 60 + now.minute
    for a, b in load_lock()["provider"]["peak_windows_beijing"]:
        a_m = int(a[:2]) * 60 + int(a[3:])
        b_m = int(b[:2]) * 60 + int(b[3:])
        if a_m <= hm < b_m:
            return True
    return False


@dataclass
class Meter:
    """PS-8: computed from usage fields at the pinned price sheet."""
    prices: dict[str, float]
    calls: int = 0
    retries: int = 0
    rescues: int = 0
    quarantined: int = 0
    in_miss: int = 0
    in_hit: int = 0
    out_tokens: int = 0
    reasoning_tokens: int = 0

    def record(self, usage: dict[str, Any]) -> None:
        self.calls += 1
        self.in_hit += usage.get("prompt_cache_hit_tokens", 0) or 0
        miss = usage.get("prompt_cache_miss_tokens")
        if miss is None:  # fall back: whole prompt was a miss
            miss = (usage.get("prompt_tokens", 0) or 0) - (usage.get("prompt_cache_hit_tokens", 0) or 0)
        self.in_miss += max(miss, 0)
        self.out_tokens += usage.get("completion_tokens", 0) or 0
        det = usage.get("completion_tokens_details") or {}
        self.reasoning_tokens += det.get("reasoning_tokens", 0) or 0

    def usd(self) -> float:
        return (self.in_miss * self.prices["input_cache_miss"]
                + self.in_hit * self.prices["input_cache_hit"]
                + self.out_tokens * self.prices["output"]) / 1e6

    def hit_rate(self) -> float:
        tot = self.in_hit + self.in_miss
        return self.in_hit / tot if tot else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {"calls": self.calls, "retries": self.retries, "rescues": self.rescues,
                "quarantined": self.quarantined, "in_miss": self.in_miss,
                "in_hit": self.in_hit, "out": self.out_tokens,
                "reasoning": self.reasoning_tokens,
                "hit_rate": round(self.hit_rate(), 4), "usd": round(self.usd(), 6)}


class AimdGate:
    """PS-6: additive-increase (+64/min toward cap) / multiplicative-decrease
    (halve on 429/5xx) concurrency gate."""

    def __init__(self, start: int, cap: int, clock=time.monotonic):
        self.target = float(start)
        self.cap = cap
        self.active = 0
        self._clock = clock
        self._last_inc = clock()
        self._cond: asyncio.Condition | None = None

    def _cond_lazy(self) -> asyncio.Condition:
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    @property
    def effective(self) -> int:
        return max(1, int(self.target))

    async def __aenter__(self):
        cond = self._cond_lazy()
        async with cond:
            while self.active >= self.effective:
                await cond.wait()
            self.active += 1

    async def __aexit__(self, *exc):
        cond = self._cond_lazy()
        async with cond:
            self.active -= 1
            cond.notify_all()

    def punish(self) -> None:
        self.target = max(1.0, self.target / 2)
        self._last_inc = self._clock()

    def reward(self) -> None:
        now = self._clock()
        self.target = min(float(self.cap), self.target + 64.0 * (now - self._last_inc) / 60.0)
        self._last_inc = now


class DsClient:
    def __init__(self, pass_name: str, usd_cap: float, *,
                 concurrency: int = 64, journal_path: Path | None = None,
                 base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None):
        load_env()
        prov = load_lock()["provider"]
        self.pass_name = pass_name
        self.usd_cap = usd_cap
        self.base_url = (base_url or prov["base_url"]).rstrip("/")
        self.model = model or prov["model"]
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise DsError("DEEPSEEK_API_KEY missing (put it in C:\\scriptorium\\.env)")
        self.meter = Meter(prices=prov["price_sheet_usd_per_mtok"])
        self.gate = AimdGate(start=concurrency,
                             cap=min(prov.get("concurrency_limit", 2500), 2400))
        self.journal_path = journal_path
        self.model_fp: str | None = None
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(900.0, connect=15.0),
            headers={"Authorization": f"Bearer {self.api_key}"})

    # -- PS-8 start gate ---------------------------------------------------
    def gate_estimate(self, est_in_tokens: int, est_out_tokens: int) -> float:
        p = self.meter.prices
        est = (est_in_tokens * p["input_cache_miss"]
               + est_out_tokens * p["output"]) / 1e6
        if est > self.usd_cap:
            raise CapExceeded(
                f"pass {self.pass_name}: estimate ${est:.2f} exceeds usd_cap "
                f"${self.usd_cap:.2f} — refusing to start (PS-8)")
        if is_peak_beijing():
            print(f"NOTE (PS-7): inside a Beijing peak window — announced pricing "
                  f"would surcharge this pass toward ${est * 2:.2f}")
        return est

    # -- journaling --------------------------------------------------------
    def _journal(self, entry: dict[str, Any]) -> None:
        if self.journal_path is None:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- PS-5 warmup -------------------------------------------------------
    async def warmup(self, system: str) -> None:
        """One serial call so the frozen prefix is cached before fan-out."""
        await self._request({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": "Warm-up. Reply: ready"}],
            "max_tokens": 8,
            "thinking": {"type": "disabled"},
            "temperature": 0,
        }, unit_id="warmup", mode="warmup", attempt=0)

    # -- the one call path -------------------------------------------------
    async def chat(self, *, system: str, user: str, tail: str = "",
                   mode: str = "extract", effort: str | None = None,
                   max_tokens: int = 4096, unit_id: str,
                   out_model: type[BaseModel] | None = None,
                   rescue: bool = True) -> tuple[Any, dict[str, Any]]:
        """One unit -> one typed object (extract) or text (think). PS-3 ladder
        inside; transport retries with AIMD backoff; cap checked before spend."""
        if mode not in ("extract", "think"):
            raise DsError(f"unknown mode {mode!r}")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user + tail}],
            "max_tokens": max_tokens,
        }
        if mode == "extract":
            body["thinking"] = {"type": "disabled"}
            body["temperature"] = 0
            if out_model is not None:
                body["response_format"] = {"type": "json_object"}
        else:
            if effort:
                body["reasoning_effort"] = effort

        last_err = ""
        attempts = 0
        for attempt in range(3):                      # 1 + retry x2 (PS-3)
            attempts += 1
            if attempt:
                self.meter.retries += 1
            try:
                content, meta = await self._request(body, unit_id=unit_id,
                                                    mode=mode, attempt=attempt)
                parsed = self._parse(content, out_model)
                meta["attempts"] = attempts
                return parsed, meta
            except (_SoftFailure, ValidationError, json.JSONDecodeError) as e:
                last_err = f"{type(e).__name__}: {e}"
                # Adaptive ladder: reasoning ate the whole output budget -> the
                # identical retry is doomed; escalate max_tokens instead.
                used = getattr(e, "usage", {}).get("completion_tokens", 0)
                if used and used >= 0.85 * body["max_tokens"]:
                    body["max_tokens"] = min(body["max_tokens"] * 3, 131_072)
        if rescue and mode == "extract":              # thinking-enabled rescue x1
            self.meter.rescues += 1
            rescue_body = {k: v for k, v in body.items()
                           if k not in ("thinking", "temperature")}
            rescue_body["reasoning_effort"] = "low"
            try:
                content, meta = await self._request(rescue_body, unit_id=unit_id,
                                                    mode="rescue", attempt=3)
                parsed = self._parse(content, out_model)
                meta["attempts"] = attempts + 1
                meta["rescued"] = True
                return parsed, meta
            except (_SoftFailure, ValidationError, json.JSONDecodeError) as e:
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

    async def _request(self, body: dict[str, Any], *, unit_id: str,
                       mode: str, attempt: int) -> tuple[str, dict[str, Any]]:
        if self.meter.usd() >= self.usd_cap:
            raise CapExceeded(
                f"pass {self.pass_name}: meter ${self.meter.usd():.4f} crossed "
                f"usd_cap ${self.usd_cap:.2f} mid-flight — halting (PS-8)")
        backoff = 1.0
        for transport_try in range(7):
            transport_err: httpx.HTTPError | None = None
            async with self.gate:
                t0 = time.monotonic()
                try:
                    r = await self._client.post(f"{self.base_url}/chat/completions",
                                                json=body)
                except httpx.HTTPError as e:
                    self.gate.punish()
                    if transport_try == 6:
                        raise _SoftFailure(f"transport: {e}") from e
                    transport_err = e
                else:
                    ms = int((time.monotonic() - t0) * 1000)
            if transport_err is not None:
                # back off OUTSIDE the gate: a sleeping retry must not hold a
                # concurrency slot, or a network wobble starves healthy calls
                # (the 429/5xx path below already sleeps outside)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            if r.status_code in (429,) or r.status_code >= 500:
                self.gate.punish()
                if transport_try == 6:
                    raise _SoftFailure(f"HTTP {r.status_code} after retries")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            if r.status_code != 200:
                raise _SoftFailure(f"HTTP {r.status_code}: {r.text[:200]}")
            self.gate.reward()
            data = r.json()
            model_seen = data.get("model", "")
            if not self.model_fp:
                # only a REAL name becomes the fingerprint: a response that
                # omits `model` must not pin "" and make the next honest
                # answer look like a mid-pass model change (PS-9 false halt)
                self.model_fp = model_seen or None
            elif model_seen and model_seen != self.model_fp:
                raise ModelChanged(
                    f"model fingerprint changed mid-pass: {self.model_fp!r} -> "
                    f"{model_seen!r} — halt + operator decision (PS-9)")
            usage = data.get("usage", {}) or {}
            self.meter.record(usage)
            msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
            content = msg.get("content") or ""
            self._journal({
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "pass": self.pass_name, "unit": unit_id, "mode": mode,
                "attempt": attempt, "model": model_seen, "ms": ms,
                "usage": usage,
                "reasoning_content": msg.get("reasoning_content"),
            })
            if not content.strip():
                raise _SoftFailure("empty content (documented failure mode)", usage=usage)
            return content, {"model": model_seen, "usage": usage, "ms": ms}
        raise _SoftFailure("unreachable")

    async def close(self) -> None:
        await self._client.aclose()


class _SoftFailure(Exception):
    """A failure the PS-3 ladder may retry."""

    def __init__(self, msg: str, usage: dict[str, Any] | None = None):
        super().__init__(msg)
        self.usage = usage or {}
