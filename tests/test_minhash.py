from minhash import jaccard_est, signature

BASE = " ".join(
    f"On day {i} the brown fox jumped over the lazy dog number {i} and recounted "
    f"the story of jump {i} with slightly different details each evening."
    for i in range(30))


def test_identical_texts_score_one():
    s1, s2 = signature(BASE), signature(BASE)
    assert s1 is not None
    assert jaccard_est(s1, s2) == 1.0


def test_disjoint_texts_score_low():
    other = " ".join(
        f"Quarter {i} financial projections show amortization schedule {i} and "
        f"depreciation of asset class {i} trending against forecast {i}."
        for i in range(30))
    s1, s2 = signature(BASE), signature(other)
    assert jaccard_est(s1, s2) < 0.2


def test_retelling_scores_high():
    retold = BASE.replace("recounted the story", "retold the story")
    s1, s2 = signature(BASE), signature(retold)
    assert jaccard_est(s1, s2) > 0.5


def test_tiny_text_gets_no_signature():
    assert signature("too small to matter") is None


def test_cjk_falls_back_to_char_shingles():
    cjk = "".join(f"第{i}天，狐狸跳过第{i}只懒狗，讲述了第{i}次跳跃的故事，细节各有不同。"
                  for i in range(20))
    s = signature(cjk)
    assert s is not None
    assert jaccard_est(s, signature(cjk)) == 1.0


def test_signature_stable_across_runs():
    """Seeds are fixed: a resumed run must reproduce identical signatures."""
    s = signature(BASE)
    assert s[:3] == signature(BASE)[:3]
    assert all(isinstance(x, int) for x in s)
