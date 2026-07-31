"""Subprocess seams to the organ family — fixed paths from scriptorium.lock,
never imported (spec section 0: organ discipline; enforced by test_import_graph).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

CODE_DIR = Path(__file__).parent


class OrganUnavailable(RuntimeError):
    """Typed: callers turn this into a quarantine reason, never a silent drop."""


@cache
def load_lock() -> dict[str, Any]:
    return json.loads((CODE_DIR / "scriptorium.lock").read_text("utf-8"))


def _run(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def _organ_script(name: str) -> Path:
    p = Path(load_lock()["organs"][name]["path"])
    if not p.exists():
        raise OrganUnavailable(f"organ {name} missing at pinned path {p}")
    return p


# -- everything: discovery cross-check ------------------------------------

def everything_list(root: Path, limit: int = 1_000_000) -> list[str] | None:
    """Paths under root per the Everything index, or None when unavailable.
    Used as a reconciliation cross-check, never as the sole discovery (fresh
    files can lag the index by ~1s; os.walk is the ground truth of now)."""
    try:
        script = _organ_script("everything")
        cp = _run([sys.executable, str(script), "--in", str(root), "-n", str(limit), "file:"],
                  timeout=120)
    except (OrganUnavailable, subprocess.TimeoutExpired, OSError):
        return None
    if cp.returncode != 0:
        return None
    return [ln.strip() for ln in cp.stdout.splitlines() if ln.strip()]


# -- chunker: token census cross-check ------------------------------------

_TOK_RE = re.compile(r"(?:tiktoken\[[^\]]*\]\s*=|heuristic\s*~)\s*([\d,]+)\s*tokens")


def estimate_tokens_organ(file: Path, timeout: float = 300) -> int:
    lock = load_lock()
    script = Path(lock["organs"]["chunker"]["estimate_tokens"])
    if not script.exists():
        raise OrganUnavailable(f"estimate_tokens.py missing at {script}")
    cp = _run([sys.executable, str(script), str(file)], timeout=timeout)
    if cp.returncode != 0:
        raise OrganUnavailable(f"estimate_tokens failed on {file}: {cp.stderr[:200]}")
    hits = _TOK_RE.findall(cp.stdout)
    if not hits:
        raise OrganUnavailable(f"estimate_tokens output unparsable for {file}")
    return int(hits[0].replace(",", ""))


# -- imguard: image preflight (before every vision call) -------------------

def imguard_ready(image: Path, timeout: float = 300) -> dict[str, Any]:
    """Run the preflight; return the per-file result dict (view_path is what OCR sees)."""
    script = _organ_script("imguard")
    cp = _run([sys.executable, str(script), "--json", str(image)], timeout=timeout)
    if cp.returncode != 0:
        raise OrganUnavailable(f"imguard failed on {image}: {cp.stderr[:200]}")
    data = json.loads(cp.stdout)
    results = data.get("results", [])
    if not results:
        raise OrganUnavailable(f"imguard returned no result for {image}")
    res = results[0]
    if res.get("status") != "ok" or not res.get("view_path"):
        raise OrganUnavailable(f"imguard status {res.get('status')!r} for {image}")
    return res


# -- earshot: ASR slow lane -------------------------------------------------

class AsrResult:
    def __init__(self, kind: str, text: str = "", detail: str = ""):
        self.kind = kind          # ok | no_speech | unavailable | timeout | error
        self.text = text
        self.detail = detail


def earshot_transcribe(av: Path, timeout: float = 3600) -> AsrResult:
    """stdout is only the transcript (earshot's contract); exit codes are typed:
    0 ok, 2 dependency missing, 3 timeout, 4 no speech."""
    try:
        script = _organ_script("earshot")
    except OrganUnavailable as e:
        return AsrResult("unavailable", detail=str(e))
    try:
        cp = _run([sys.executable, str(script), str(av)], timeout=timeout)
    except subprocess.TimeoutExpired:
        return AsrResult("timeout", detail=f"driver timeout {timeout}s")
    if cp.returncode == 0:
        return AsrResult("ok", text=cp.stdout)
    if cp.returncode == 4:
        return AsrResult("no_speech", detail=cp.stderr.strip()[-200:])
    if cp.returncode == 2:
        return AsrResult("unavailable", detail=cp.stderr.strip()[-200:])
    if cp.returncode == 3:
        return AsrResult("timeout", detail=cp.stderr.strip()[-200:])
    return AsrResult("error", detail=f"exit {cp.returncode}: {cp.stderr.strip()[-200:]}")


def earshot_available() -> bool:
    try:
        script = _organ_script("earshot")
    except OrganUnavailable:
        return False
    try:
        cp = _run([sys.executable, str(script), "--check"], timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        return False
    out = cp.stdout + cp.stderr
    wc_lines = [ln for ln in out.splitlines() if "whisper-cli" in ln]
    return bool(wc_lines) and ".exe" in wc_lines[0].lower() and "ggml" in out
