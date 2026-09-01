"""Falsifier (d): the import-graph law. Organs are subprocesses at fixed paths,
never imported; zero imports from KEEL/hypercell/cortex/cognee/BRAIN code; and
the S0 dependency set is closed (stdlib + pydantic + httpx + PyMuPDF + optional
tiktoken + pytest). Written as an allowlist so a new dependency cannot sneak in
silently."""

import ast
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent

FORBIDDEN = {
    "keel", "hypercell", "cortex", "cognee", "brain", "drdj",
    "everything", "everywhere", "chunker", "earshot", "imguard",  # organs: subprocess only
    "llama_cpp", "yaml", "requests", "numpy", "pandas",
}
# deepseek_harness: OPTIONAL harness-mode SDK (provider="harness" only), lazy
# import inside harness._default_factory; the default api path never imports it.
ALLOWED_THIRD_PARTY = {"pydantic", "httpx", "fitz", "pymupdf", "tiktoken",
                       "pytest", "deepseek_harness"}
OWN = {"canon", "tape", "models", "manifest", "organs", "local", "intake",
       "textnorm", "minhash", "scriptorium", "conftest", "ds", "discover",
       "cards", "read", "spancheck", "harness", "a2a", "query"}
OWN |= {p.stem for p in (REPO / "tests").glob("test_*.py")}


def repo_sources() -> list[Path]:
    out = []
    # amanuensis/ + amanuensis-native/ are untracked sibling subprojects with
    # their own conventions (dropped inside the repo dir); they are not
    # scriptorium code and are outside this law until properly committed.
    skip = {".venv", "_testdata", "__pycache__", "_local",
            "amanuensis", "amanuensis-native"}
    for p in REPO.rglob("*.py"):
        parts = {q.lower() for q in p.parts}
        if parts & skip:
            continue
        out.append(p)
    return out


def test_import_graph_closed():
    stdlib = set(sys.stdlib_module_names)
    bad: list[str] = []
    for src in repo_sources():
        tree = ast.parse(src.read_text("utf-8"), filename=str(src))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        for r in roots:
            low = r.lower()
            if low in FORBIDDEN:
                bad.append(f"{src.name}: FORBIDDEN import {r}")
            elif r not in stdlib and low not in ALLOWED_THIRD_PARTY and r not in OWN:
                bad.append(f"{src.name}: import {r} outside the pinned S0 dependency set")
    assert not bad, "\n".join(bad)


def test_no_sys_path_manipulation():
    """Organ code must never be reached by path hacking either."""
    needles = ("sys.path" + ".insert", "sys.path" + ".append")  # split: don't match self
    offenders = [
        src.name for src in repo_sources()
        if any(n in src.read_text("utf-8") for n in needles)
    ]
    assert not offenders, offenders
