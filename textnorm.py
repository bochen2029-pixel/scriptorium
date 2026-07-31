"""Canonical text: decoding, normalization, deterministic block splitting, token estimate.

Canonical form (what `text` records store and spans cite): NFC-normalized,
newlines \\n only, content otherwise verbatim. Splitting is deterministic so a
killed intake resumed later reproduces identical blocks ("".join(blocks) == text,
property-tested).
"""

from __future__ import annotations

import unicodedata

TEXT_BLOCK_MAX_CHARS = 32_000

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("o200k_base")
except Exception:                                    # optional dep; heuristic fallback
    _ENC = None


def decode_bytes(data: bytes) -> tuple[str, str]:
    """Decode with a boring fallback ladder; report which encoding won."""
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def canonical(s: str) -> str:
    return unicodedata.normalize("NFC", s.replace("\r\n", "\n").replace("\r", "\n"))


def split_blocks(s: str, max_chars: int = TEXT_BLOCK_MAX_CHARS) -> list[str]:
    """Split at the last newline before max_chars; hard-split a single huge line."""
    if len(s) <= max_chars:
        return [s] if s else []
    blocks: list[str] = []
    pos = 0
    while pos < len(s):
        end = pos + max_chars
        if end >= len(s):
            blocks.append(s[pos:])
            break
        cut = s.rfind("\n", pos, end)
        cut = cut + 1 if cut > pos else end          # keep the newline with its block
        blocks.append(s[pos:cut])
        pos = cut
    return blocks


def sniff_text(data: bytes) -> bool:
    """Strict sniff for unknown extensions: NUL-free and clean UTF-8 in the head.

    Deliberately conservative — a miss quarantines typed (`unsupported_modality`),
    never silently admits garbage as text.
    """
    head = data[:65536]
    if b"\x00" in head:
        return False
    try:
        # guard against a multi-byte char torn at the boundary
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        if e.start < len(head) - 4:
            return False
        try:
            head[: e.start].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return True


def estimate_tokens(s: str) -> int:
    """tiktoken o200k_base when installed (the chunker's exact proxy), else a
    density-aware heuristic: CJK ~1 token/char, everything else ~1 token/4 chars."""
    if not s:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(s, disallowed_special=()))
    cjk = sum(1 for ch in s if "　" <= ch <= "鿿" or "豈" <= ch <= "﫿")
    return int(cjk + (len(s) - cjk) / 4)
