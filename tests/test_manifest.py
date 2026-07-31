import pytest

from manifest import ManifestError, load_manifest, parse_yamlite

FULL = """\
# operator-owned manifest
archive: test-life
roots:
  - path: files
    label: blog
  - path: C:\\somewhere\\else
include: ["**/*.md", "**/*.pdf"]
exclude:
  - "**/*.tmp"
  - "**/node_modules/**"
sovereignty:
  pixels_leave_box: false
  audio_leaves_box: false
consent: "operator's own archive; self-consented"
era_hints: []
"""


def test_parse_full_manifest(tmp_path):
    (tmp_path / "manifest.yaml").write_text(FULL, encoding="utf-8")
    mf, root = load_manifest(tmp_path)
    assert root == tmp_path.resolve()
    assert mf.archive == "test-life"
    assert [r.label for r in mf.roots] == ["blog", None]
    assert mf.include == ["**/*.md", "**/*.pdf"]
    assert mf.exclude[1] == "**/node_modules/**"
    assert mf.consent.startswith("operator")


def test_yamlite_scalars_and_nesting():
    d = parse_yamlite(
        "a: 1\nb: -2.5\nc: true\nd: null\ne: 'quo # ted'\nf: \"x\\ny\"\n"
        "g:\n  h: plain text here\n  i: [1, 2, three]\n")
    assert d == {"a": 1, "b": -2.5, "c": True, "d": None, "e": "quo # ted",
                 "f": "x\ny", "g": {"h": "plain text here", "i": [1, 2, "three"]}}


def test_yamlite_list_of_scalars_and_string_roots(tmp_path):
    (tmp_path / "manifest.yaml").write_text(
        "roots:\n  - files\n  - more\n", encoding="utf-8")
    mf, _ = load_manifest(tmp_path)
    assert [r.path for r in mf.roots] == ["files", "more"]


def test_yamlite_refuses_unsupported():
    with pytest.raises(ManifestError, match="not supported"):
        parse_yamlite("a: &anchor 1\n")
    with pytest.raises(ManifestError, match="tabs"):
        parse_yamlite("a:\n\tb: 1\n")
    with pytest.raises(ManifestError, match="duplicate"):
        parse_yamlite("a: 1\na: 2\n")


def test_sovereignty_refusal(tmp_path):
    (tmp_path / "manifest.yaml").write_text(
        "roots:\n  - files\nsovereignty:\n  pixels_leave_box: true\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="sovereignty"):
        load_manifest(tmp_path)


def test_missing_manifest(tmp_path):
    with pytest.raises(ManifestError, match="no manifest"):
        load_manifest(tmp_path)


def test_json_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"roots": [{"path": "files"}]}', encoding="utf-8")
    mf, _ = load_manifest(tmp_path)
    assert mf.roots[0].path == "files"
