"""a2a.py — the Intercom A2A layer around scriptorium passes (opt-in).

SCRIPTORIUM_A2A=1 joins each P1/P2 pass to the local Intercom bus
(C:/Intercom; one SQLite broadcast.db — see _run_state/survey/intercom.md) so
passes are visible to other agents, mutually exclusive per archive+pass, and
audit-trailed in agent terms:

- join (kind=session, harness=dsh, lane=orchestrator-<pass>)
- claim the pass lease "scriptorium:<archive>:<pass>" (atomic CAS, TTL 900s):
  an explicit refusal (exit 3 = a live holder) stops the pass before any
  spend; ANY other bus failure degrades to a no-op with one stderr note —
  Intercom is coordination sugar, never a dependency (mirrors HM-10: the
  provider seam stays coordination-free; this module wraps passes).
- run_start / run_end / per-quarantine findings (bodies <= 4 KB per the
  Intercom spec), then release + leave in the exit path.
- per-chunk leases "scriptorium:<archive>:p2:<doc_id>:<seq>" (try_claim) so
  two drivers can co-work one catalog without dupes; the resume law (skip
  keys already in cards.jsonl) stays primary — leases only prevent
  CONCURRENT double-work and are never released (TTL is the janitor).
- driver identity is honest about which of the box's two harnesses is
  driving (claude-code or dsh; RATIFIED item 8).

Transport = one fresh subprocess per verb (organ discipline: the bus client
is a fixed-path tool, never imported). Forward slashes per the QUICKSTART
rule (Git Bash eats backslashes). Env: SCRIPTORIUM_A2A=1 enables; INTERCOM_PY
overrides the client path (default C:/Intercom/intercom.py).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

INTERCOM_PY = "C:/Intercom/intercom.py"
BODY_CAP = 4000
LEASE_TTL = 900


def _driver_identity() -> tuple[str, str]:
    """Which of the box's TWO harnesses is driving (RATIFIED item 8: only DSH
    and Claude Code exist here). Env overrides win; else the Claude Code env
    marker decides; else dsh."""
    h = os.environ.get("SCRIPTORIUM_DRIVER_HARNESS", "").strip()
    m = os.environ.get("SCRIPTORIUM_DRIVER_MODEL", "").strip()
    if not h:
        h = "claude-code" if os.environ.get("CLAUDECODE") else "dsh"
    if not m:
        m = ((os.environ.get("ANTHROPIC_MODEL", "").strip() or "claude")
             if h == "claude-code" else "dsh")
    return h, m


class A2ARefused(Exception):
    """The bus explicitly refused (exit 3: lease held by a live holder)."""


class _Soft(Exception):
    """Any other bus failure: coordination degrades to a no-op."""


def _note(msg: str) -> None:
    print(f"[a2a] {msg}", file=sys.stderr, flush=True)


def _enabled() -> bool:
    return os.environ.get("SCRIPTORIUM_A2A", "").strip() == "1"


class IntercomBridge:
    """The few verbs a pass needs, one subprocess each. `runner` is the single
    I/O point (tests inject a fake; production runs intercom.py)."""

    def __init__(self, project: str, lane: str, cli: str = INTERCOM_PY,
                 harness_name: str | None = None, model: str | None = None,
                 runner: Callable[[list[str]], Any] | None = None):
        self.project = project
        self.lane = lane
        self.cli = cli
        default_h, default_m = _driver_identity()
        self.harness_name = harness_name or default_h
        self.model = model or default_m
        self._runner = runner or self._subprocess_runner
        self.me: str | None = None
        self.resource: str | None = None

    @staticmethod
    def _subprocess_runner(argv: list[str]) -> Any:
        try:
            return subprocess.run([sys.executable, INTERCOM_PY, *argv],
                                  capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            return SimpleNamespace(returncode=1, stdout="",
                                   stderr=f"{type(e).__name__}: {e}")

    # -- the one I/O point -----------------------------------------------------
    def _cmd(self, *args: str) -> str:
        r = self._runner(list(args))
        code = getattr(r, "returncode", 0)
        err = (getattr(r, "stderr", "") or "").strip()
        if code == 3:
            raise A2ARefused(err[:200] or "refused")
        if code != 0:
            raise _Soft(f"exit {code}: {err[:200]}")
        return (getattr(r, "stdout", "") or "").strip()

    def _joined(self) -> str:
        if not self.me:
            raise _Soft("not joined")
        return self.me

    def join(self) -> str:
        out = self._cmd("join", "--harness", self.harness_name,
                        "--model", self.model,
                        "--project", self.project, "--kind", "session",
                        "--lane", self.lane)
        me = out.splitlines()[-1].strip() if out else ""
        if not me:
            raise _Soft("join produced no id")
        self.me = me
        return me

    def say(self, body: str, type_: str = "finding") -> None:
        self._cmd("say", "--me", self._joined(), "--project", self.project,
                  "--type", type_, body[:BODY_CAP])

    def claim(self, resource: str, ttl: int = LEASE_TTL) -> None:
        self._cmd("claim", "--me", self._joined(), "--resource", resource,
                  "--ttl", str(ttl))

    def pin_file(self, path: str, note_text: str) -> None:
        self._cmd("pin", "--me", self._joined(), "--file",
                  path.replace("\\", "/"), note_text[:BODY_CAP])

    def release(self, resource: str) -> None:
        self._cmd("release", "--me", self._joined(), "--resource", resource)

    def leave(self) -> None:
        self._cmd("leave", "--me", self._joined(), "--room", self.project)


def begin(pass_name: str, archive_name: str) -> IntercomBridge | None:
    """join + claim the pass lease. An explicit refusal (another live driver
    holds the pass) stops the pass via SystemExit; any soft failure returns
    None so the pass runs uncoordinated. Disabled (None) unless
    SCRIPTORIUM_A2A=1."""
    if not _enabled():
        return None
    cli = os.environ.get("INTERCOM_PY", "").strip() or INTERCOM_PY
    if not Path(cli).exists():
        _note(f"Intercom client not found at {cli} — pass runs WITHOUT A2A")
        return None
    resource = f"scriptorium:{archive_name}:{pass_name.lower()}"
    bridge = IntercomBridge(project=f"scriptorium-{archive_name}",
                            lane=f"orchestrator-{pass_name.lower()}", cli=cli)
    try:
        me = bridge.join()
        bridge.claim(resource)
    except A2ARefused as e:
        raise SystemExit(
            f"A2A: {resource} is held by another live driver — refusing to "
            f"double-run ({e}). If that driver is a ghost, steal the lease "
            f"with: intercom claim --steal-stale --resource {resource}") from e
    except _Soft as e:
        _note(f"bus unavailable ({e}) — pass runs WITHOUT A2A")
        return None
    bridge.resource = resource
    _note(f"joined as {me} (project {bridge.project}, lane {bridge.lane}, "
          f"lease {resource})")
    return bridge


def note(bridge: IntercomBridge | None, body: str) -> None:
    """Fire-and-forget finding; never raises."""
    if bridge is None:
        return
    try:
        bridge.say(body)
    except Exception as e:  # noqa: BLE001 — coordination must not fail a pass
        _note(f"say failed ({type(e).__name__}) — continuing")


def pin(bridge: IntercomBridge | None, path: Any, note_text: str) -> None:
    """Artifact-grain attestation (the honest resolution of 'worker
    attestation'): ONE pin at run end records the catalog's blake2b on the bus
    — a cryptographic receipt for the whole output. Card-grain attestation was
    evaluated and rejected: workers are single-shot calls (HM-8) so the driver
    would post ~1-3 subprocesses per card of pure chatter restating what
    cards.jsonl already is — the terminal, fsync'd record. Never raises."""
    if bridge is None:
        return
    try:
        bridge.pin_file(str(path), note_text)
    except Exception as e:  # noqa: BLE001 — coordination must not fail a pass
        _note(f"pin failed ({type(e).__name__}) — continuing")


def try_claim(bridge: IntercomBridge | None, resource: str,
              ttl: int = LEASE_TTL) -> bool:
    """Chunk-grain lease CAS for multi-DRIVER co-work (design doc, A2A item 2):
    True = ours to do (or the bus is down/disabled — coordination is sugar,
    never a dependency); False = a live driver holds it, skip without writing.
    Never released: a card/quarantine row is terminal once fsync'd (the resume
    law protects forever after), so the TTL is the janitor for crashed
    claimants and --steal-stale the manual override."""
    if bridge is None:
        return True
    try:
        bridge.claim(resource, ttl)
        return True
    except A2ARefused:
        return False
    except Exception as e:  # noqa: BLE001 — soft failures degrade to no-op
        _note(f"claim soft-failed ({type(e).__name__}: {e}) — proceeding "
              f"uncoordinated")
        return True


def end(bridge: IntercomBridge | None, summary: str) -> None:
    """run_end finding + release + leave; never raises."""
    if bridge is None:
        return
    try:
        bridge.say(f"run_end: {summary}")
    except Exception as e:  # noqa: BLE001
        _note(f"run_end say failed ({type(e).__name__})")
    if bridge.resource:
        try:
            bridge.release(bridge.resource)
        except Exception as e:  # noqa: BLE001 — TTL expiry is the backstop
            _note(f"release failed ({type(e).__name__}) — lease expires via TTL")
    try:
        bridge.leave()
    except Exception:  # noqa: BLE001
        pass
