"""Local sidecars (spec section 2) — the sovereign floor. Pixels never leave the box.

OCR/VISION on :8091: attach-or-launch `llama-server -m Qwen3.5-9B-Q5_K_M.gguf
--mmproj mmproj-F16.gguf`. The OCR contract prompt is frozen at
prompts/ocr_contract_v0.txt (hash pinned in scriptorium.lock); every OCR output
carries R-class provenance with the extractor fingerprint (gguf + mmproj hashes).

EMBEDDINGS on :8092: an S2 seam, deliberately stubbed here — wiring it now would
be leaving the rung.

Env override SCRIPTORIUM_OCR_URL points the seam at any OpenAI-compatible
endpoint (tests use a local stub; sovereignty holds either way because the
default is localhost and intake never sends pixels through ds.py).
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from organs import CODE_DIR, load_lock


class OcrUnavailable(RuntimeError):
    pass


class OcrFailed(RuntimeError):
    pass


class RungGate(NotImplementedError):
    pass


def _prompt_text() -> str:
    rel = load_lock()["prompts"]["ocr_contract_v0"]["file"]
    return (CODE_DIR / rel).read_text("utf-8")


class OcrSidecar:
    """Attach to a running llama-server on the pinned port, or launch one."""

    def __init__(self) -> None:
        cfg = load_lock()["sidecars"]["ocr"]
        self.cfg = cfg
        self.url = os.environ.get("SCRIPTORIUM_OCR_URL",
                                  f"http://127.0.0.1:{cfg['port']}").rstrip("/")
        self.prompt = _prompt_text()
        self._client = httpx.Client(timeout=httpx.Timeout(600.0, connect=5.0))
        self._launched: subprocess.Popen | None = None

    # -- lifecycle --------------------------------------------------------
    def healthy(self) -> bool:
        try:
            return self._client.get(f"{self.url}/health").status_code == 200
        except httpx.HTTPError:
            return False

    def ensure(self, launch: bool = True) -> bool:
        """True when a healthy server answers on the seam; launch if allowed."""
        if self.healthy():
            return True
        if not launch or os.environ.get("SCRIPTORIUM_OCR_URL"):
            return False
        exe, model, mmproj = Path(self.cfg["exe"]), Path(self.cfg["model"]), Path(self.cfg["mmproj"])
        if not (exe.exists() and model.exists() and mmproj.exists()):
            return False
        log_dir = CODE_DIR / "_local"
        log_dir.mkdir(exist_ok=True)
        log = open(log_dir / f"ocr-{self.cfg['port']}.log", "ab")
        args = [str(exe), "-m", str(model), "--mmproj", str(mmproj),
                *self.cfg.get("launch_args", [])]
        self._launched = subprocess.Popen(
            args, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        deadline = time.monotonic() + self.cfg.get("health_timeout_s", 300)
        while time.monotonic() < deadline:
            if self.healthy():
                return True
            if self._launched.poll() is not None:
                return False                      # died during load; log has the story
            time.sleep(2.0)
        return False

    def fingerprint(self) -> dict[str, Any]:
        return {
            "extractor": "qwen3.5-9b-ocr",
            "server": "llama-server",
            "url": self.url,
            "model_file": Path(self.cfg["model"]).name,
            "model_blake2b256": self.cfg["model_blake2b256"],
            "mmproj_file": Path(self.cfg["mmproj"]).name,
            "mmproj_blake2b256": self.cfg["mmproj_blake2b256"],
            "prompt": "ocr_contract_v0",
            "prompt_blake2b128": load_lock()["prompts"]["ocr_contract_v0"]["blake2b128"],
        }

    # -- the call ---------------------------------------------------------
    def ocr_image(self, png_path: str | Path) -> dict[str, Any]:
        """One image -> {text, regions, confidence_hint, fp}. Retries once; a
        JSON-shaped failure degrades to raw text with a typed note, never a guess."""
        b64 = base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
        payload = {
            "model": "qwen3.5-9b",
            "temperature": 0,
            "max_tokens": 8192,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
        }
        last_err: Exception | None = None
        for _attempt in range(2):
            try:
                r = self._client.post(f"{self.url}/v1/chat/completions", json=payload)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return self._parse(content)
            except (httpx.HTTPError, KeyError, IndexError) as e:
                last_err = e
        raise OcrFailed(f"OCR call failed after retry: {last_err}")

    def _parse(self, content: str) -> dict[str, Any]:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict) and isinstance(obj.get("text"), str):
                    return {"text": obj["text"],
                            "regions": obj.get("regions") or [],
                            "confidence_hint": obj.get("confidence_hint"),
                            "fp": self.fingerprint()}
            except json.JSONDecodeError:
                pass
        # typed degradation: the words still count; the shape failure is recorded
        return {"text": content.strip(), "regions": [],
                "confidence_hint": None, "fp": self.fingerprint(),
                "note": "ocr_json_parse_failed"}

    def close(self) -> None:
        self._client.close()


class EmbedSidecar:
    """The :8092 seam, stubbed by design at S0 (spec section 7: S2 wires it)."""

    def __init__(self) -> None:
        self.cfg = load_lock()["sidecars"]["embedding"]

    def embed(self, texts: list[str]) -> None:
        raise RungGate(
            f"embedding sidecar (:{self.cfg['port']}) is {self.cfg['status']}; "
            "rung S2 wires it — this build is S0")
