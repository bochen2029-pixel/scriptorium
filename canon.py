"""CANON-JSON-v1 + the chain hash: the one serialization every tape hash is computed over.

Rules (constitutional; known-answer vectors pinned in scriptorium.lock, enforced by
tests/test_canon.py):

- UTF-8 bytes, no BOM.
- Every string — keys and values — is NFC-normalized before serialization.
- Object keys sorted by Unicode code point (after NFC normalization).
- Separators "," and ":", no whitespace.
- Floats: CPython shortest-roundtrip repr (json.dumps default). NaN/Inf refused.
- Only JSON types: dict (str keys only), list/tuple, str, int, float, bool, None.
- Two distinct keys that NFC-collide are refused (they would serialize as duplicates).

Chain hash (spec section 3): h_i = blake2b-128( ascii(h_{i-1}) || CANON-JSON(record_i) )
with the genesis prev "0"*32. Hex lowercase, 32 chars.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from typing import Any

GENESIS = "0" * 32
_HASH_HEX_LEN = 32  # blake2b digest_size=16 -> 32 hex chars


class CanonError(TypeError):
    """A value cannot be represented in CANON-JSON."""


def _norm(obj: Any) -> Any:
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, bool) or obj is None or isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise CanonError(f"non-finite float not representable: {obj!r}")
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonError(f"non-string key not representable: {k!r}")
            nk = unicodedata.normalize("NFC", k)
            if nk in out:
                raise CanonError(f"keys collide after NFC normalization: {k!r}")
            out[nk] = _norm(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_norm(v) for v in obj]
    raise CanonError(f"type not representable in CANON-JSON: {type(obj).__name__}")


def canon_bytes(obj: Any) -> bytes:
    """Serialize obj to canonical UTF-8 bytes."""
    return json.dumps(
        _norm(obj), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def blake2b128_hex(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def chain_hash(prev_h: str, record: dict[str, Any]) -> str:
    """h = blake2b-128( ascii(prev_h) || canon(record) ). record must not contain 'h'."""
    if len(prev_h) != _HASH_HEX_LEN:
        raise CanonError(f"prev hash must be {_HASH_HEX_LEN} hex chars, got {len(prev_h)}")
    return blake2b128_hex(prev_h.encode("ascii") + canon_bytes(record))
