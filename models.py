"""Typed record bodies and the manifest model (pydantic v2, frozen).

The span coordinate system (spec section 3): every citation anywhere is
{doc_id, seq, start, end} where start/end are **character (code point) offsets
into the NFC-normalized canonical `text` field** of the text record (doc_id, seq).
The tape stores that exact string; renderers slice it, never retype it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Modality = Literal["text", "pdf", "docx", "image", "av"]

QUARANTINE_REASONS = (
    "read_error",            # unreadable bytes / permissions
    "unsupported_modality",  # unknown extension, fails the strict text sniff
    "pdf_unreadable",        # PyMuPDF cannot open
    "docx_unreadable",       # not a parsable docx zip
    "ocr_unavailable",       # image/scanned page present, no OCR sidecar
    "ocr_failed",            # sidecar up, call failed after retry
    "asr_unavailable",       # earshot missing a dependency (its exit 2)
    "asr_timeout",           # earshot exit 3
    "asr_error",             # earshot other nonzero exit
    "extract_error",         # extractor raised
)


class DocBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    doc_id: str
    root: str                 # absolute root path, posix separators, NFC
    path: str                 # root-relative path, posix separators, NFC
    source: str               # manifest root label
    content_b2: str           # blake2b-256 of raw bytes, hex
    size: int
    mtime: str                # ISO-8601 UTC
    year: int                 # from mtime (P0's best chronology; era hints refine later)
    modality: Modality
    extractor: dict[str, Any] # extractor fingerprint (R-class provenance for OCR/ASR)
    n_texts: int
    chars: int
    tokens_est: int
    notes: list[str] = Field(default_factory=list)


class TextBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    doc_id: str
    seq: int
    text: str                 # canonical text: NFC, \n newlines — the cited bytes
    chars: int
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chars")
    @classmethod
    def _chars_match(cls, v: int, info):  # noqa: ANN001 - pydantic signature
        if "text" in info.data and v != len(info.data["text"]):
            raise ValueError("chars must equal len(text)")
        return v


class JournalBody(BaseModel):
    """Intake events: nothing is ever silently dropped (spec section 3)."""
    model_config = ConfigDict(frozen=True, extra="allow")
    event: str                # run_start | run_end | excluded | dedup | quarantined
    #                         | near_dup_flag | reconciliation | tape_repair | resume_seam


class ContactBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str
    year: int | None          # None = the summary row
    source: str
    modality: str
    files: int
    chars: int
    tokens_est: int


class RootSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str
    label: str | None = None


class Sovereignty(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pixels_leave_box: bool = False
    audio_leaves_box: bool = False


class Manifest(BaseModel):
    """Operator-owned. Lives at the archive root; roots may point anywhere."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    archive: str | None = None
    roots: list[RootSpec]
    include: list[str] = Field(default_factory=lambda: ["**"])
    exclude: list[str] = Field(default_factory=list)
    sovereignty: Sovereignty = Field(default_factory=Sovereignty)
    consent: str | None = None
    era_hints: list[Any] = Field(default_factory=list)

    @field_validator("roots")
    @classmethod
    def _nonempty(cls, v):  # noqa: ANN001
        if not v:
            raise ValueError("manifest needs at least one root")
        return v

    @field_validator("sovereignty")
    @classmethod
    def _sovereign(cls, v: Sovereignty) -> Sovereignty:
        if v.pixels_leave_box or v.audio_leaves_box:
            raise ValueError(
                "sovereignty violation: pixels and audio never leave the box "
                "(spec section 0, fixed split) — this build refuses such a manifest")
        return v
