from textnorm import canonical, decode_bytes, estimate_tokens, sniff_text, split_blocks


def test_decode_ladder():
    assert decode_bytes("héllo".encode())[1] == "utf-8"
    assert decode_bytes(b"\xef\xbb\xbfbom")[0] == "bom"
    assert decode_bytes("smart “quote”".encode("cp1252"))[1] == "cp1252"


def test_canonical_newlines_and_nfc():
    assert canonical("a\r\nb\rc") == "a\nb\nc"
    assert canonical("café") == "café"


def test_split_blocks_lossless_property():
    text = "\n".join(f"line {i} " + "x" * (i % 97) for i in range(4000))
    for max_chars in (100, 1000, 32000):
        blocks = split_blocks(text, max_chars)
        assert "".join(blocks) == text
        assert all(len(b) <= max_chars for b in blocks)


def test_split_blocks_hard_split_huge_line():
    text = "y" * 75_000
    blocks = split_blocks(text, 32_000)
    assert "".join(blocks) == text
    assert len(blocks) == 3


def test_split_blocks_empty():
    assert split_blocks("") == []


def test_sniff_text():
    assert sniff_text("plain utf-8 中文\n".encode())
    assert not sniff_text(b"\x00\x01\x02binary")
    assert not sniff_text(b"\xff\xfe garbage \x81\x8d")


def test_estimate_tokens_sane():
    n = estimate_tokens("the quick brown fox jumps over the lazy dog " * 100)
    assert 500 <= n <= 1500
    assert estimate_tokens("") == 0
