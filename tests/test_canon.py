"""CANON-JSON falsifier (e): known-answer vectors pinned in scriptorium.lock."""

import json
from pathlib import Path

import pytest

from canon import GENESIS, CanonError, blake2b128_hex, canon_bytes, chain_hash

LOCK = json.loads((Path(__file__).parent.parent / "scriptorium.lock").read_text("utf-8"))


def test_known_answer_vectors():
    vectors = LOCK["canon_vectors"]["serialization"]
    assert len(vectors) >= 5, "the lock must pin a real vector set"
    for v in vectors:
        got = canon_bytes(v["input"])
        assert got.decode("utf-8") == v["canon"], f"canon drift on {v['name']}"
        assert blake2b128_hex(got) == v["blake2b128"], f"hash drift on {v['name']}"


def test_chain_vectors():
    v = LOCK["canon_vectors"]["chain"]
    h1 = chain_hash(GENESIS, v["records"][0])
    assert h1 == v["h1"]
    h2 = chain_hash(h1, v["records"][1])
    assert h2 == v["h2"]


def test_nfc_normalization():
    composed = canon_bytes({"s": "café"})
    decomposed = canon_bytes({"s": "café"})
    assert composed == decomposed


def test_nfc_key_collision_refused():
    with pytest.raises(CanonError, match="collide"):
        canon_bytes({"café": 1, "café": 2})


def test_sorted_keys_and_types():
    assert canon_bytes({"b": 1, "a": [True, None, "x"]}) == b'{"a":[true,null,"x"],"b":1}'
    assert canon_bytes((1, 2)) == b"[1,2]"  # tuple -> list


def test_float_repr_fixed():
    assert canon_bytes([0.1, 1e300, -0.0, 2.5]) == b"[0.1,1e+300,-0.0,2.5]"


def test_refusals():
    with pytest.raises(CanonError):
        canon_bytes({1: "non-string key"})
    with pytest.raises(CanonError):
        canon_bytes(float("nan"))
    with pytest.raises(CanonError):
        canon_bytes({"x": {1, 2}})
