"""P0 INTAKE (spec section 4): organs + stdlib, no API, no LLM.

manifest -> discovery (os.walk ground truth; `everything` as reconciliation
cross-check) -> exact content-hash dedup + MinHash near-dup *flagging* ->
modality routing -> canonical `text` records with the span coordinate system
{doc_id, seq, start, end} -> reconciliation (completeness measured, never
assumed) -> contact sheet (tokens x year x source x modality).

Nothing is silently dropped: every discovered path terminates as a `doc` record
or a `journal` record (excluded / dedup / quarantined), the falsifier-(a) gate.

Resume: a file is committed by its trailing `doc` record (texts first, doc
last, one fsync'd batch). A killed run leaves at most one partially-taped doc;
rerun continues its units (page / block / transcript-slice index in
`meta.unit`) from where the tape ends — zero duplicate records, zero gaps,
the falsifier-(c) gate. Determinism of the unit split is pinned by
scriptorium.lock (text_block_max_chars); prior units are trusted from the
hash-chained tape, never re-extracted.

Scanned-page detection is deliberately boring: a PDF page OCRs only when its
text layer is under PDF_TEXT_FLOOR chars AND it embeds an image. A vector-only
scan (rare) therefore stays text-layer-empty — honest dark matter for P6.

Deviation from the kickoff, recorded: docx is extracted with stdlib
zipfile+ElementTree rather than "through chunker's extractors" — the chunker
has no clean full-text CLI mode (its chunk output carries section/recap
headers that would pollute canonical text). Same text-first philosophy, zero
new dependencies. Parked in STATE.md for operator review.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import time
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import fitz  # PyMuPDF — a pinned S0 dependency (the chunker's own PDF engine)

import minhash
import organs
import textnorm
from canon import blake2b128_hex, canon_bytes
from local import OcrFailed, OcrSidecar
from manifest import load_manifest, resolve_root
from models import ContactBody, DocBody, JournalBody, TextBody
from tape import Tape

PDF_TEXT_FLOOR = 25          # chars; below this + an embedded image = scanned page
PDF_OCR_DPI = 150
NEAR_DUP_THRESHOLD = 0.6
NEAR_DUP_FLAG_CAP = 5        # flag only the top-K most similar priors per doc
HASH_CHUNK = 1 << 23

TEXT_EXTS = {
    ".md", ".txt", ".rst", ".org", ".csv", ".tsv", ".log", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".rs", ".go", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php",
    ".sh", ".ps1", ".cmd", ".bat", ".html", ".htm", ".xml", ".css", ".sql",
    ".tex", ".srt", ".vtt", ".eml",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
AV_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma",
           ".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".m4v"}
ARCHIVE_INTERNAL = ("tape", "runs", "catalog", "codex", "certificate")


class QuarantineError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# -- glob matching ---------------------------------------------------------

def glob_to_re(pat: str) -> re.Pattern[str]:
    """gitignore-flavored: `**` spans segments; a bare-name pattern matches at
    any depth. Matched case-insensitively against root-relative posix paths."""
    if "/" not in pat:
        pat = "**/" + pat
    parts = pat.split("/")
    out: list[str] = []
    for i, part in enumerate(parts):
        if part == "**":
            out.append("(?:[^/]+/)*" if i < len(parts) - 1 else ".*")
            continue
        seg = ""
        for ch in part:
            if ch == "*":
                seg += "[^/]*"
            elif ch == "?":
                seg += "[^/]"
            else:
                seg += re.escape(ch)
        out.append(seg + ("/" if i < len(parts) - 1 else ""))
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


class GlobSet:
    def __init__(self, patterns: list[str]):
        self.res = [glob_to_re(p) for p in patterns]

    def match(self, rel_posix: str) -> bool:
        return any(r.match(rel_posix) for r in self.res)


# -- discovery -------------------------------------------------------------

@dataclass(frozen=True)
class FileEntry:
    root: str          # absolute root, posix separators
    label: str         # manifest source label
    rel: str           # root-relative posix path
    abspath: Path
    size: int
    mtime: float

    @property
    def key(self) -> tuple[str, str]:
        return (self.root, self.rel)


def discover(mf, archive_root: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    seen: set[tuple[str, str]] = set()
    for spec in mf.roots:
        rootp = resolve_root(spec.path, archive_root)
        if not rootp.is_dir():
            raise FileNotFoundError(f"manifest root does not exist: {rootp}")
        label = spec.label or rootp.name
        root_posix = rootp.as_posix()
        for dirpath, dirnames, filenames in rootp.walk(on_error=None):
            dirnames.sort()
            for name in sorted(filenames):
                p = dirpath / name
                try:
                    st = p.stat()
                except OSError:
                    st = None
                rel = p.relative_to(rootp).as_posix()
                key = (root_posix, rel)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(FileEntry(
                    root=root_posix, label=label, rel=rel, abspath=p,
                    size=st.st_size if st else -1,
                    mtime=st.st_mtime if st else 0.0))
    return entries


def is_archive_internal(entry: FileEntry, archive_root: Path) -> bool:
    try:
        rel = entry.abspath.resolve().relative_to(archive_root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0].lower() in ARCHIVE_INTERNAL


# -- modality routing ------------------------------------------------------

def route(entry: FileEntry) -> str:
    ext = entry.abspath.suffix.lower()
    if ext in TEXT_EXTS:
        return "text"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AV_EXTS:
        return "av"
    try:
        with entry.abspath.open("rb") as f:
            head = f.read(65536)
    except OSError as e:
        raise QuarantineError("read_error", str(e)) from e
    if textnorm.sniff_text(head):
        return "text"
    raise QuarantineError("unsupported_modality", f"unknown extension {ext or '(none)'}")


# -- extractors: yield (unit, text, meta) for units >= start_unit ----------

Block = tuple[int, str, dict[str, Any]]


def extract_text_file(path: Path, start_unit: int) -> tuple[list[Block], dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError as e:
        raise QuarantineError("read_error", str(e)) from e
    text, encoding = textnorm.decode_bytes(data)
    blocks = textnorm.split_blocks(textnorm.canonical(text))
    fp = {"kind": "text", "encoding": encoding}
    return ([(u, b, {"unit": u, "source": "file"})
             for u, b in enumerate(blocks) if u >= start_unit and b], fp)


def extract_docx(path: Path, start_unit: int) -> tuple[list[Block], dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as e:
        raise QuarantineError("docx_unreadable", str(e)) from e
    try:
        tree = ElementTree.parse(io.BytesIO(xml))
    except ElementTree.ParseError as e:
        raise QuarantineError("docx_unreadable", str(e)) from e

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    paras: list[str] = []
    for el in tree.iter():
        if local(el.tag) != "p":
            continue
        run: list[str] = []
        for sub in el.iter():
            t = local(sub.tag)
            if t == "t" and sub.text:
                run.append(sub.text)
            elif t == "tab":
                run.append("\t")
            elif t == "br":
                run.append("\n")
        paras.append("".join(run))
    blocks = textnorm.split_blocks(textnorm.canonical("\n".join(paras)))
    fp = {"kind": "docx", "extractor": "stdlib-zip-xml"}
    return ([(u, b, {"unit": u, "source": "file"})
             for u, b in enumerate(blocks) if u >= start_unit and b], fp)


class Extractor:
    """Holds the lazy OCR sidecar + per-run scratch for renders."""

    def __init__(self, scratch: Path, launch_ocr: bool = True):
        self.scratch = scratch
        self.launch_ocr = launch_ocr
        self._ocr: OcrSidecar | None = None
        self._ocr_state: str = "unprobed"        # unprobed | up | down

    def ocr(self) -> OcrSidecar | None:
        if self._ocr_state == "unprobed":
            side = OcrSidecar()
            up = side.ensure(launch=self.launch_ocr)
            self._ocr_state = "up" if up else "down"
            self._ocr = side if up else None
        return self._ocr

    def _ocr_png(self, png: Path, unit: int, page: int | None) -> Block:
        ocr = self.ocr()
        if ocr is None:
            raise QuarantineError(
                "ocr_unavailable",
                "no OCR sidecar (llama-server/model missing or failed to launch)")
        try:
            ready = organs.imguard_ready(png)
        except organs.OrganUnavailable as e:
            raise QuarantineError("extract_error", f"imguard: {e}") from e
        try:
            res = ocr.ocr_image(Path(ready["view_path"]))
        except OcrFailed as e:
            raise QuarantineError("ocr_failed", str(e)) from e
        meta: dict[str, Any] = {
            "unit": unit, "source": "ocr",
            "ocr": {"confidence_hint": res.get("confidence_hint"),
                    "regions": len(res.get("regions") or []),
                    "fp": res["fp"]},
        }
        if page is not None:
            meta["page"] = page
        if res.get("note"):
            meta["ocr"]["note"] = res["note"]
        return (unit, textnorm.canonical(res["text"]), meta)

    def extract_pdf(self, path: Path, start_unit: int) -> tuple[list[Block], dict[str, Any]]:
        try:
            doc = fitz.open(path)
        except Exception as e:  # noqa: BLE001 - fitz raises plain RuntimeError
            raise QuarantineError("pdf_unreadable", str(e)) from e
        blocks: list[Block] = []
        ocr_pages = 0
        with doc:
            for pno in range(doc.page_count):
                if pno < start_unit:
                    continue
                page = doc.load_page(pno)
                text = textnorm.canonical(page.get_text("text")).strip("\n")
                if len(text) >= PDF_TEXT_FLOOR or not page.get_images(full=True):
                    if text:
                        blocks.append((pno, text,
                                       {"unit": pno, "page": pno + 1, "source": "text-layer"}))
                    continue
                ocr_pages += 1
                pix = page.get_pixmap(dpi=PDF_OCR_DPI)
                png = self.scratch / f"pdfpage-{path.stem[:40]}-{pno + 1}.png"
                pix.save(png)
                try:
                    blocks.append(self._ocr_png(png, unit=pno, page=pno + 1))
                finally:
                    png.unlink(missing_ok=True)
        fp: dict[str, Any] = {"kind": "pdf", "extractor": "pymupdf",
                              "pymupdf": fitz.pymupdf_version}
        if ocr_pages:
            fp["ocr_pages"] = ocr_pages
        return [b for b in blocks if b[1]], fp

    def extract_image(self, path: Path, start_unit: int) -> tuple[list[Block], dict[str, Any]]:
        blocks: list[Block] = []
        if start_unit <= 0:
            blk = self._ocr_png(path, unit=0, page=None)
            if blk[1]:
                blocks.append(blk)
        return blocks, {"kind": "image", "extractor": "imguard+qwen3.5-9b-ocr"}

    def extract_av(self, path: Path, start_unit: int) -> tuple[list[Block], dict[str, Any]]:
        res = organs.earshot_transcribe(path)
        if res.kind == "ok":
            text = textnorm.canonical(res.text).strip("\n")
            blocks = textnorm.split_blocks(text)
            fp = {"kind": "av", "extractor": "earshot", "engine": "whisper.cpp"}
            return ([(u, b, {"unit": u, "source": "transcript"})
                     for u, b in enumerate(blocks) if u >= start_unit and b], fp)
        if res.kind == "no_speech":
            return [], {"kind": "av", "extractor": "earshot", "engine": "whisper.cpp",
                        "note": "no_speech"}
        raise QuarantineError(f"asr_{res.kind}"
                              if res.kind in ("unavailable", "timeout", "error")
                              else "asr_error", res.detail)

    def extract(self, modality: str, path: Path, start_unit: int
                ) -> tuple[list[Block], dict[str, Any]]:
        if modality == "text":
            return extract_text_file(path, start_unit)
        if modality == "docx":
            return extract_docx(path, start_unit)
        if modality == "pdf":
            return self.extract_pdf(path, start_unit)
        if modality == "image":
            return self.extract_image(path, start_unit)
        if modality == "av":
            return self.extract_av(path, start_unit)
        raise QuarantineError("unsupported_modality", modality)


# -- tape-derived state (the resume ledger) --------------------------------

@dataclass
class TapeState:
    docs_done: set[str] = field(default_factory=set)              # doc_ids with doc record
    by_content: dict[str, str] = field(default_factory=dict)      # content_b2 -> doc_id
    partial: dict[str, dict[str, Any]] = field(default_factory=dict)
    path_state: dict[tuple[str, str], str] = field(default_factory=dict)
    journal_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    sigs: dict[str, list[int]] = field(default_factory=dict)
    doc_meta: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_state(tape: Tape) -> TapeState:
    st = TapeState()
    for rec in tape.iter_records():
        kind, body = rec["kind"], rec["body"]
        if kind == "text":
            p = st.partial.setdefault(body["doc_id"],
                                      {"n": 0, "max_unit": -1, "chars": 0, "tokens": 0})
            p["n"] += 1
            p["max_unit"] = max(p["max_unit"], body.get("meta", {}).get("unit", -1))
            p["chars"] += body["chars"]
            p["tokens"] += body.get("meta", {}).get("tokens_est", 0)
        elif kind == "doc":
            st.docs_done.add(body["doc_id"])
            st.by_content.setdefault(body["content_b2"], body["doc_id"])
            st.path_state[(body["root"], body["path"])] = "doc"
            st.partial.pop(body["doc_id"], None)
            if body.get("minhash"):
                st.sigs[body["doc_id"]] = body["minhash"]
            st.doc_meta[body["doc_id"]] = {"path": body["path"], "source": body["source"]}
        elif kind == "journal":
            ev = body.get("event")
            if ev in ("excluded", "dedup", "quarantined"):
                key = (body.get("root", ""), body.get("path", ""))
                if st.path_state.get(key) != "doc":
                    st.path_state[key] = ev
                st.journal_keys.add((ev, body.get("path", ""),
                                    body.get("content_b2", "") or "",
                                    body.get("reason", "") or ""))
    return st


def doc_id_for(root_posix: str, rel: str, content_b2: str) -> str:
    return blake2b128_hex(canon_bytes(
        {"_": "doc-id-v1", "root": root_posix, "path": rel, "content": content_b2}))


def hash_file(path: Path) -> str:
    h = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


# -- the run ---------------------------------------------------------------

@dataclass
class IntakeReport:
    run_id: str
    counts: dict[str, int] = field(default_factory=dict)
    completeness_pct: float = 0.0
    reconciliation: dict[str, Any] = field(default_factory=dict)
    contact_rows: list[dict[str, Any]] = field(default_factory=list)
    crosscheck: dict[str, Any] = field(default_factory=dict)
    quarantined: list[tuple[str, str]] = field(default_factory=list)


class IntakeRun:
    def __init__(self, target: str | Path, launch_ocr: bool = True, quiet: bool = False):
        self.mf, self.archive_root = load_manifest(target)
        self.launch_ocr = launch_ocr
        self.quiet = quiet
        self.run_id = (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                       + "-" + secrets.token_hex(3))
        self.run_dir = self.archive_root / "runs" / self.run_id
        self.counts: dict[str, int] = {
            "done": 0, "skipped": 0, "dedup": 0, "excluded": 0, "quarantined": 0,
            "near_dup_flags": 0, "texts": 0}
        self.quarantined: list[tuple[str, str]] = []

    def say(self, msg: str) -> None:
        if not self.quiet:
            print(msg, flush=True)

    def jline(self, **kw: Any) -> None:
        kw.setdefault("ts", datetime.now(UTC).isoformat(timespec="seconds"))
        with open(self.run_dir / "journal.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    # -- helpers ----------------------------------------------------------
    def _tape_journal(self, tape: Tape, body: dict[str, Any],
                      dedupe_key: tuple[str, str, str, str] | None = None) -> None:
        if dedupe_key is not None:
            if dedupe_key in self.state.journal_keys:
                return
            self.state.journal_keys.add(dedupe_key)
        tape.append("journal", JournalBody(**body).model_dump())

    # -- main -------------------------------------------------------------
    def run(self) -> IntakeReport:
        t0 = time.monotonic()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        scratch = self.run_dir / "tmp"
        scratch.mkdir(exist_ok=True)
        tape = Tape.open(self.archive_root)
        try:
            report = self._run_inner(tape, scratch)
        finally:
            tape.close()
        report.counts["seconds"] = round(time.monotonic() - t0, 1)
        return report

    def _run_inner(self, tape: Tape, scratch: Path) -> IntakeReport:
        for note in tape.repairs:
            tape.append("journal", JournalBody(
                event="tape_repair", run_id=self.run_id, detail=note).model_dump())
            self.say(f"tape repair journaled: {note}")
        self.state = load_state(tape)
        ex = Extractor(scratch, launch_ocr=self.launch_ocr)
        mf_hash = blake2b128_hex(canon_bytes(self.mf.model_dump()))
        self._tape_journal(tape, {"event": "run_start", "run_id": self.run_id,
                                  "manifest_blake2b128": mf_hash,
                                  "archive": self.mf.archive})
        self.jline(event="run_start", run_id=self.run_id, manifest=mf_hash)

        entries = discover(self.mf, self.archive_root)
        self.say(f"discovered {len(entries)} files under {len(self.mf.roots)} root(s)")
        self.jline(event="discovered", n=len(entries))

        include = GlobSet(self.mf.include)
        exclude = GlobSet(self.mf.exclude)
        work: list[FileEntry] = []
        for e in entries:
            if is_archive_internal(e, self.archive_root):
                self._journal_excluded(tape, e, "archive-internal")
            elif not include.match(e.rel):
                self._journal_excluded(tape, e, "not-included")
            elif exclude.match(e.rel):
                self._journal_excluded(tape, e, "excluded-by-manifest")
            else:
                work.append(e)

        # cost lanes: cheap text first, then pdf (possible OCR), images, AV last —
        # a slow scanned PDF must never stall thousands of text files behind it
        def lane(e: FileEntry) -> int:
            ext = e.abspath.suffix.lower()
            if ext == ".pdf":
                return 1
            if ext in IMAGE_EXTS:
                return 2
            if ext in AV_EXTS:
                return 3
            return 0
        work.sort(key=lambda e: (lane(e), e.root, e.rel))
        n_slow = sum(1 for e in work if lane(e))
        if n_slow:
            self.say(f"{n_slow} file(s) queued to slow lanes (pdf/image/av, after text)")

        for e in work:
            self._process(tape, ex, e)

        recon = self._reconcile(tape, entries_before=entries)
        contact_rows, crosscheck = self._contact_sheet(tape)
        self._tape_journal(tape, {"event": "run_end", "run_id": self.run_id,
                                  "counts": dict(self.counts)})
        self.jline(event="run_end", counts=dict(self.counts))
        return IntakeReport(
            run_id=self.run_id, counts=dict(self.counts),
            completeness_pct=recon["completeness_pct"], reconciliation=recon,
            contact_rows=contact_rows, crosscheck=crosscheck,
            quarantined=list(self.quarantined))

    def _journal_excluded(self, tape: Tape, e: FileEntry, reason: str) -> None:
        self.counts["excluded"] += 1
        self.state.path_state.setdefault((e.root, e.rel), "excluded")
        self._tape_journal(
            tape,
            {"event": "excluded", "run_id": self.run_id, "root": e.root,
             "path": e.rel, "reason": reason},
            dedupe_key=("excluded", e.rel, "", reason))

    def _process(self, tape: Tape, ex: Extractor, e: FileEntry) -> None:
        slow = os.environ.get("SCRIPTORIUM_TEST_SLEEP_PER_FILE")
        if slow:                       # test seam: makes kill-resume timing deterministic
            time.sleep(float(slow))
        try:
            content_b2 = hash_file(e.abspath)
        except OSError as err:
            self._quarantine(tape, e, "read_error", str(err), content_b2="")
            return
        doc_id = doc_id_for(e.root, e.rel, content_b2)
        if doc_id in self.state.docs_done:
            self.counts["skipped"] += 1
            self.jline(event="skip", path=e.rel, doc_id=doc_id)
            return
        prior = self.state.by_content.get(content_b2)
        if prior is not None:
            self.counts["dedup"] += 1
            self.state.path_state[(e.root, e.rel)] = "dedup"
            self._tape_journal(
                tape,
                {"event": "dedup", "run_id": self.run_id, "root": e.root, "path": e.rel,
                 "content_b2": content_b2, "ref_doc_id": prior},
                dedupe_key=("dedup", e.rel, content_b2, ""))
            self.jline(event="dedup", path=e.rel, ref=prior)
            return

        try:
            modality = route(e)
        except QuarantineError as q:
            self._quarantine(tape, e, q.reason, q.detail, content_b2)
            return

        part = self.state.partial.get(
            doc_id, {"n": 0, "max_unit": -1, "chars": 0, "tokens": 0})
        start_seq, start_unit = part["n"], part["max_unit"] + 1
        if start_seq:
            self.say(f"resuming {e.rel} at seq {start_seq} (unit {start_unit})")
            self.jline(event="resume_partial", path=e.rel, start_seq=start_seq)

        try:
            blocks, extractor_fp = ex.extract(modality, e.abspath, start_unit)
        except QuarantineError as q:
            self._quarantine(tape, e, q.reason, q.detail, content_b2)
            return
        except Exception as err:  # noqa: BLE001 - typed into the journal, never dropped
            self._quarantine(tape, e, "extract_error", repr(err), content_b2)
            return

        full_text = "".join(b[1] for b in blocks)
        chars = part["chars"] + sum(len(b[1]) for b in blocks)
        block_tokens = [textnorm.estimate_tokens(b[1]) for b in blocks]
        tokens = part["tokens"] + sum(block_tokens)
        # a resumed (crash-interrupted) doc gets no signature: honest gap, noted on the doc
        sig = minhash.signature(full_text) if start_seq == 0 else None
        mtime_dt = datetime.fromtimestamp(e.mtime, UTC)

        items: list[tuple[str, dict[str, Any]]] = []
        for k, (_unit, text, meta) in enumerate(blocks):
            items.append(("text", TextBody(
                doc_id=doc_id, seq=start_seq + k, text=text, chars=len(text),
                meta={**meta, "tokens_est": block_tokens[k]}).model_dump()))
        doc_body = DocBody(
            doc_id=doc_id, root=e.root, path=e.rel, source=e.label,
            content_b2=content_b2, size=e.size,
            mtime=mtime_dt.isoformat(timespec="seconds"), year=mtime_dt.year,
            modality=modality, extractor=extractor_fp,
            n_texts=start_seq + len(blocks), chars=chars, tokens_est=tokens,
            notes=(["resumed"] if start_seq else [])
                  + (["no_speech"] if extractor_fp.get("note") == "no_speech" else []),
        ).model_dump()
        doc_body["minhash"] = sig
        items.append(("doc", doc_body))
        tape.append_many(items)

        self.state.docs_done.add(doc_id)
        self.state.by_content[content_b2] = doc_id
        self.state.path_state[(e.root, e.rel)] = "doc"
        self.state.doc_meta[doc_id] = {"path": e.rel, "source": e.label}
        self.counts["done"] += 1
        self.counts["texts"] += len(blocks)
        self.jline(event="file_done", path=e.rel, doc_id=doc_id,
                   n_texts=len(blocks), modality=modality)

        if sig is not None:
            self._flag_near_dups(tape, doc_id, sig)
            self.state.sigs[doc_id] = sig

    def _flag_near_dups(self, tape: Tape, doc_id: str, sig: list[int]) -> None:
        hits = sorted(
            ((minhash.jaccard_est(sig, other_sig), other_id)
             for other_id, other_sig in self.state.sigs.items()),
            reverse=True)
        items: list[tuple[str, dict[str, Any]]] = []
        for j, other_id in hits[:NEAR_DUP_FLAG_CAP]:
            if j < NEAR_DUP_THRESHOLD:
                break
            self.counts["near_dup_flags"] += 1
            other = self.state.doc_meta.get(other_id, {})
            items.append(("journal", JournalBody(
                event="near_dup_flag", run_id=self.run_id,
                doc_id=doc_id, other_doc_id=other_id,
                other_path=other.get("path"),
                jaccard_est=round(j, 3)).model_dump()))
            self.say(f"  near-dup flagged (j~{j:.2f}) vs {other.get('path')}"
                     " — kept, cross-referenced")
        if items:                       # one fsync'd batch per doc, capped at K
            tape.append_many(items)

    def _quarantine(self, tape: Tape, e: FileEntry, reason: str, detail: str,
                    content_b2: str) -> None:
        self.counts["quarantined"] += 1
        self.quarantined.append((e.rel, reason))
        if self.state.path_state.get((e.root, e.rel)) != "doc":
            self.state.path_state[(e.root, e.rel)] = "quarantined"
        self._tape_journal(
            tape,
            {"event": "quarantined", "run_id": self.run_id, "root": e.root,
             "path": e.rel, "reason": reason, "detail": detail[:500],
             "content_b2": content_b2},
            dedupe_key=("quarantined", e.rel, content_b2, reason))
        self.jline(event="quarantined", path=e.rel, reason=reason)
        self.say(f"  quarantined ({reason}): {e.rel}")

    # -- reconciliation (I-ING-7: measured, never assumed) -----------------
    def _reconcile(self, tape: Tape, entries_before: list[FileEntry]) -> dict[str, Any]:
        after = discover(self.mf, self.archive_root)
        before_keys = {e.key for e in entries_before}
        unaccounted: list[str] = []
        states: dict[str, int] = {"doc": 0, "dedup": 0, "excluded": 0, "quarantined": 0}
        new_since = [e.rel for e in after if e.key not in before_keys]
        for e in after:
            s = self.state.path_state.get(e.key)
            if s in states:
                states[s] += 1
            elif e.key in before_keys:
                unaccounted.append(e.rel)
        vanished = [k[1] for k in before_keys - {e.key for e in after}]
        total = len(after)
        classified = sum(states.values())
        pct = 100.0 * classified / total if total else 100.0

        xcheck: dict[str, Any] = {}
        for spec in self.mf.roots:
            rootp = resolve_root(spec.path, self.archive_root)
            ev = organs.everything_list(rootp)
            xcheck[spec.label or rootp.name] = (
                {"everything": len(ev),
                 "walk": sum(1 for e in after if e.root == rootp.as_posix())}
                if ev is not None else "unavailable")

        recon = {"total": total, "classified": classified, "completeness_pct": round(pct, 2),
                 "states": states, "unaccounted": unaccounted[:50],
                 "new_since_discovery": new_since[:50], "vanished_during_run": vanished[:50],
                 "everything_crosscheck": xcheck}
        self._tape_journal(tape, {"event": "reconciliation", "run_id": self.run_id, **recon})
        self.jline(event="reconciliation", **recon)
        return recon

    # -- contact sheet (the census; the pass-cost estimator's ground) ------
    def _contact_sheet(self, tape: Tape) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        agg: dict[tuple[int, str, str], dict[str, int]] = {}
        doc_files: dict[str, tuple[Path, int]] = {}
        for rec in tape.iter_records(kinds=("doc",)):
            b = rec["body"]
            key = (b["year"], b["source"], b["modality"])
            row = agg.setdefault(key, {"files": 0, "chars": 0, "tokens_est": 0})
            row["files"] += 1
            row["chars"] += b["chars"]
            row["tokens_est"] += b["tokens_est"]
            if b["modality"] == "text":
                doc_files[b["doc_id"]] = (Path(b["root"]) / b["path"], b["tokens_est"])

        rows: list[dict[str, Any]] = []
        items: list[tuple[str, dict[str, Any]]] = []
        tot = {"files": 0, "chars": 0, "tokens_est": 0}
        for (year, source, modality), row in sorted(agg.items()):
            body = ContactBody(run_id=self.run_id, year=year, source=source,
                               modality=modality, **row).model_dump()
            rows.append(body)
            items.append(("contact", body))
            for k in tot:
                tot[k] += row[k]
        summary = ContactBody(run_id=self.run_id, year=None, source="*",
                              modality="*", **tot).model_dump()
        rows.append(summary)
        items.append(("contact", summary))
        if items:
            tape.append_many(items)

        crosscheck = self._census_crosscheck(tape, doc_files)
        return rows, crosscheck

    def _census_crosscheck(self, tape: Tape, doc_files: dict[str, tuple[Path, int]]
                           ) -> dict[str, Any]:
        """Spec S0 gate: contact sheet cross-checked against estimate_tokens.py
        on a sample (text-layer files, where the original bytes ARE the text)."""
        sample = sorted(doc_files.items())[:10]
        results, ratios = [], []
        for doc_id, (path, ours) in sample:
            try:
                organ = organs.estimate_tokens_organ(path)
            except organs.OrganUnavailable as err:
                results.append({"doc_id": doc_id, "file": path.name, "error": str(err)[:120]})
                continue
            ratio = round(ours / organ, 4) if organ else None
            ratios.append(ratio)
            results.append({"doc_id": doc_id, "file": path.name,
                            "ours": ours, "organ": organ, "ratio": ratio})
        mean_ratio = round(sum(r for r in ratios if r) / len(ratios), 4) if ratios else None
        out = {"samples": results, "mean_ratio": mean_ratio,
               "note": "ratio = tape tokens_est / chunker estimate_tokens"}
        self._tape_journal(tape, {"event": "census_crosscheck", "run_id": self.run_id, **out})
        return out


def run_intake(target: str | Path, launch_ocr: bool = True, quiet: bool = False
               ) -> IntakeReport:
    return IntakeRun(target, launch_ocr=launch_ocr, quiet=quiet).run()
