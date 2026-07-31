"""Planted-corpus builders + the OCR stub server.

Test archive roots live under C:\\scriptorium\\_testdata (gitignored, kickoff
section 2). Corpora are deterministic fixture trees; the stub OCR server lets
image/scanned-PDF routing run end-to-end without a 6 GB model in the loop
(the real :8091 sidecar is exercised by the S0 live demo instead).
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import zipfile
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import fitz
import pytest

TESTDATA = Path(__file__).parent.parent / "_testdata"

STUB_OCR_TEXT = "STUB OCR TEXT with an uncertainty mark ⟨?maybe⟩ and no guesses."


def fresh_dir(name: str) -> Path:
    p = TESTDATA / name
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def varied_sentences(n: int = 30, salt: str = "brown", start: int = 0) -> str:
    return "\n".join(
        f"On day {i} the {salt} fox jumped over dog {i} and retold story {i} "
        f"with slightly different details in the {salt} evening light."
        for i in range(start, start + n))


def make_docx(path: Path, paragraphs: list[str]) -> None:
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


def make_text_pdf(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 90 + 20 * i), line, fontsize=12)
    doc.save(path)
    doc.close()


def make_scanned_pdf(path: Path, text: str) -> None:
    """A page whose words exist only as pixels: render text, re-embed as image."""
    src = fitz.open()
    p = src.new_page()
    p.insert_text((72, 120), text, fontsize=16)
    pix = p.get_pixmap(dpi=120)
    src.close()
    dst = fitz.open()
    page = dst.new_page(width=595, height=842)
    page.insert_image(page.rect, pixmap=pix)
    dst.save(path)
    dst.close()


def make_png(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=500, height=200)
    page.insert_text((30, 90), text, fontsize=13)
    page.get_pixmap(dpi=110).save(path)
    doc.close()


def set_year(path: Path, year: int) -> None:
    t = datetime(year, 6, 15, 12, 0, 0, tzinfo=UTC).timestamp()
    os.utime(path, (t, t))


def plant_corpus(arch: Path) -> dict[str, str]:
    """Build the deterministic S0 fixture tree; return {relpath: expected-state}."""
    files = arch / "files"
    for sub in ("notes", "docs", "img", "junk"):
        (files / sub).mkdir(parents=True)

    a_text = "# Alpha notes\n\n" + varied_sentences(30, "brown") + "\n"
    (files / "notes/a.md").write_text(a_text, encoding="utf-8")
    # near-dup = the retelling with added detail (flag-and-keep, never fold)
    (files / "notes/near_a.md").write_text(
        a_text + varied_sentences(5, "grey") + "\n", encoding="utf-8")
    (files / "notes/dup_of_a.md").write_text(a_text, encoding="utf-8")
    (files / "notes/b.txt").write_text(
        "A fully distinct second text about harbor logistics and tide tables.\n"
        + varied_sentences(20, "silver") + "\n", encoding="utf-8")
    make_text_pdf(files / "docs/c.pdf",
                  ["The C document text layer, line one.",
                   "Line two mentions the planted token QUINCE."])
    make_scanned_pdf(files / "docs/scan.pdf",
                     "SCANNED PAGE: words that exist only as pixels.")
    make_docx(files / "docs/d.docx",
              ["Docx paragraph one from the planted corpus.",
               "Docx paragraph two mentions the planted token MARIGOLD."])
    make_png(files / "img/e.png", "PNG NOTE: pixels-only caption text.")
    (files / "junk/skip.tmp").write_text("temp noise\n", encoding="utf-8")
    (files / "junk/blob.bin").write_bytes(bytes(range(256)) * 8)

    set_year(files / "notes/a.md", 2019)
    set_year(files / "notes/near_a.md", 2021)
    set_year(files / "notes/dup_of_a.md", 2019)
    set_year(files / "notes/b.txt", 2020)
    set_year(files / "docs/c.pdf", 2020)
    set_year(files / "docs/scan.pdf", 2021)
    set_year(files / "docs/d.docx", 2021)
    set_year(files / "img/e.png", 2021)
    set_year(files / "junk/blob.bin", 2020)

    (arch / "manifest.yaml").write_text(
        'archive: planted-s0\n'
        'roots:\n'
        '  - path: files\n'
        '    label: mixed\n'
        'exclude: ["**/*.tmp"]\n'
        'consent: "synthetic fixture corpus, generated by tests"\n',
        encoding="utf-8")

    return {
        "notes/a.md": "doc", "notes/near_a.md": "doc", "notes/dup_of_a.md": "dedup",
        "notes/b.txt": "doc", "docs/c.pdf": "doc", "docs/scan.pdf": "doc",
        "docs/d.docx": "doc", "img/e.png": "doc",
        "junk/skip.tmp": "excluded", "junk/blob.bin": "quarantined",
    }


# -- OCR stub ---------------------------------------------------------------

class _OcrStubHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        self._reply(200, b'{"status":"ok"}')

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        mode = getattr(self.server, "mode", "ok")
        if mode == "ok":
            content = json.dumps({
                "text": STUB_OCR_TEXT,
                "regions": [{"kind": "body", "text": STUB_OCR_TEXT}],
                "confidence_hint": 0.9})
        else:  # "raw": shape-breaking output, exercises typed degradation
            content = "plain words, no JSON shape at all"
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self._reply(200, body)

    def _reply(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        pass


@pytest.fixture()
def ocr_stub(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _OcrStubHandler)
    srv.mode = "ok"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setenv("SCRIPTORIUM_OCR_URL", url)
    yield srv
    srv.shutdown()


def wait_for(predicate, timeout: float, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# -- speech fixtures (Windows TTS + ffmpeg; used by the AV lane test + demo) --

def make_tts_wav(path: Path, text: str) -> bool:
    """Synthesize real speech with System.Speech; False when TTS is unavailable."""
    import subprocess
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{path}'); "
        f"$s.Speak('{text}'); $s.Dispose()")
    try:
        cp = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return cp.returncode == 0 and path.exists() and path.stat().st_size > 1000


def make_silent_wav(path: Path, seconds: float = 1.0) -> bool:
    import subprocess
    try:
        cp = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
             "-t", str(seconds), str(path)],
            capture_output=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return cp.returncode == 0 and path.exists()


def make_speech_video(mp4: Path, wav: Path, png: Path) -> bool:
    """One still frame + the speech track = the falsifier's 'one short video'."""
    import subprocess
    try:
        cp = subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-i", str(wav),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(mp4)],
            capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return cp.returncode == 0 and mp4.exists()
