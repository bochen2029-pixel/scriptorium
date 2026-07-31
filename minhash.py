"""MinHash near-duplicate *flagging* (spec section 3: flag-and-keep, never fold —
retellings are biography gold, not noise).

Stdlib only. 128 permutations of a 64-bit base hash under universal hashing
((a*h + b) mod p, p = 2^61-1), seeds fixed so signatures are stable across runs
(resume-safe). Word 5-gram shingles; character 8-grams when the text has too few
word tokens (CJK has no spaces). Texts below the floor get no signature — tiny
files all look alike and would flood the flags.
"""

from __future__ import annotations

import hashlib
import random
import re

N_PERM = 128
_P = (1 << 61) - 1
_SEED = 20260731
_rng = random.Random(_SEED)
_AB = [(_rng.randrange(1, _P), _rng.randrange(0, _P)) for _ in range(N_PERM)]

_WORD_RE = re.compile(r"\w+", re.UNICODE)
MIN_SHINGLES = 30


def _shingles(text: str) -> set[bytes]:
    words = _WORD_RE.findall(text.lower())
    if len(words) >= MIN_SHINGLES + 4:
        return {" ".join(words[i:i + 5]).encode("utf-8") for i in range(len(words) - 4)}
    compact = re.sub(r"\s+", " ", text.lower())
    if len(compact) >= 200:
        return {compact[i:i + 8].encode("utf-8") for i in range(len(compact) - 7)}
    return set()


def signature(text: str) -> list[int] | None:
    sh = _shingles(text)
    if len(sh) < MIN_SHINGLES:
        return None
    bases = [int.from_bytes(hashlib.blake2b(s, digest_size=8).digest(), "big") for s in sh]
    return [min((a * h + b) % _P for h in bases) for a, b in _AB]


def jaccard_est(sig1: list[int], sig2: list[int]) -> float:
    return sum(1 for x, y in zip(sig1, sig2, strict=True) if x == y) / len(sig1)
