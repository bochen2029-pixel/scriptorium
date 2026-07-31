"""Manifest loading: a small YAML-subset parser (stdlib) + the pydantic model.

The S0 dependency law (kickoff section 2) pins stdlib + pydantic + httpx + PyMuPDF;
PyYAML is not on the list, so manifest.yaml is parsed by this deliberately small
subset parser. Supported: nested mappings (2+ space indent), block lists
(`- scalar`, `- key: value` continued at deeper indent), flow lists of scalars
(`[a, b, "c"]`), comments, quoted and plain scalars with null/bool/int/float
inference. NOT supported (clear error, park the wish): anchors, aliases, multiline
block scalars, flow mappings, tabs. manifest.json is accepted as an alternative.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from models import Manifest


class ManifestError(ValueError):
    pass


# -- yamlite ---------------------------------------------------------------

_SCALAR_NULL = {"null", "~", ""}
_SCALAR_TRUE = {"true", "yes", "on"}
_SCALAR_FALSE = {"false", "no", "off"}
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d*[eE][+-]?\d+)$")


def _strip_comment(line: str) -> str:
    out = []
    in_s: str | None = None
    for ch in line:
        if in_s:
            out.append(ch)
            if ch == in_s:
                in_s = None
        elif ch in "'\"":
            in_s = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(tok: str, lineno: int) -> Any:
    tok = tok.strip()
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        body = tok[1:-1]
        return re.sub(r'\\(["\\/nrt])',
                      lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m.group(1), m.group(1)),
                      body)
    if tok.startswith("'") and tok.endswith("'") and len(tok) >= 2:
        return tok[1:-1].replace("''", "'")
    low = tok.lower()
    if low in _SCALAR_NULL:
        return None
    if low in _SCALAR_TRUE:
        return True
    if low in _SCALAR_FALSE:
        return False
    if _INT_RE.match(tok):
        return int(tok)
    if _FLOAT_RE.match(tok):
        return float(tok)
    for bad in ("&", "*", "|", ">"):
        if tok.startswith(bad):
            raise ManifestError(
                f"line {lineno}: YAML feature {bad!r}... not supported by the subset parser "
                "(use plain/quoted scalars, or manifest.json)")
    return tok


def _flow_list(tok: str, lineno: int) -> list[Any]:
    inner = tok.strip()[1:-1].strip()
    if not inner:
        return []
    items, cur, in_s = [], [], None
    for ch in inner:
        if in_s:
            cur.append(ch)
            if ch == in_s:
                in_s = None
        elif ch in "'\"":
            in_s = ch
            cur.append(ch)
        elif ch == ",":
            items.append("".join(cur))
            cur = []
        elif ch in "[{":
            raise ManifestError(f"line {lineno}: nested flow collections not supported")
        else:
            cur.append(ch)
    items.append("".join(cur))
    return [_scalar(i, lineno) for i in items]


def _value(tok: str, lineno: int) -> Any:
    tok = tok.strip()
    if tok.startswith("[") and tok.endswith("]"):
        return _flow_list(tok, lineno)
    if tok.startswith("{"):
        raise ManifestError(f"line {lineno}: flow mappings not supported")
    return _scalar(tok, lineno)


_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(\s*(.*))?$")


def parse_yamlite(text: str) -> Any:
    lines: list[tuple[int, int, str]] = []          # (lineno, indent, content)
    for n, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ManifestError(f"line {n}: tabs in indentation are not supported")
        line = _strip_comment(raw)
        if not line.strip():
            continue
        lines.append((n, len(line) - len(line.lstrip(" ")), line.strip()))
    if not lines:
        return {}
    val, nxt = _parse_block(lines, 0, lines[0][1])
    if nxt != len(lines):
        raise ManifestError(f"line {lines[nxt][0]}: unexpected content (bad indentation?)")
    return val


def _parse_block(lines: list[tuple[int, int, str]], pos: int, indent: int) -> tuple[Any, int]:
    if lines[pos][2].startswith("- ") or lines[pos][2] == "-":
        return _parse_list(lines, pos, indent)
    return _parse_map(lines, pos, indent)


def _parse_map(lines, pos, indent) -> tuple[dict[str, Any], int]:
    out: dict[str, Any] = {}
    while pos < len(lines):
        lineno, ind, content = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            raise ManifestError(f"line {lineno}: unexpected indent")
        m = _KEY_RE.match(content)
        if not m:
            raise ManifestError(f"line {lineno}: expected 'key: value', got {content!r}")
        key, val_tok = m.group(1), (m.group(3) or "").strip()
        if key in out:
            raise ManifestError(f"line {lineno}: duplicate key {key!r}")
        pos += 1
        if val_tok:
            out[key] = _value(val_tok, lineno)
        elif pos < len(lines) and lines[pos][1] > indent:
            out[key], pos = _parse_block(lines, pos, lines[pos][1])
        else:
            out[key] = None
    return out, pos


def _parse_list(lines, pos, indent) -> tuple[list[Any], int]:
    out: list[Any] = []
    while pos < len(lines):
        lineno, ind, content = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            raise ManifestError(f"line {lineno}: unexpected indent in list")
        if not (content.startswith("- ") or content == "-"):
            break
        item_tok = content[2:].strip() if content.startswith("- ") else ""
        pos += 1
        if not item_tok:
            raise ManifestError(f"line {lineno}: bare '-' items not supported")
        m = _KEY_RE.match(item_tok)
        if m:                                   # `- key: value` starts an inline map
            first_key, first_val = m.group(1), (m.group(3) or "").strip()
            item: dict[str, Any] = {}
            if first_val:
                item[first_key] = _value(first_val, lineno)
            elif pos < len(lines) and lines[pos][1] > ind + 2:
                item[first_key], pos = _parse_block(lines, pos, lines[pos][1])
            else:
                item[first_key] = None
            # continuation keys sit at the scalar's column (indent + 2)
            if pos < len(lines) and lines[pos][1] == ind + 2 and _KEY_RE.match(lines[pos][2]):
                rest, pos = _parse_map(lines, pos, ind + 2)
                for k, v in rest.items():
                    if k in item:
                        raise ManifestError(f"line {lineno}: duplicate key {k!r} in list item")
                    item[k] = v
            out.append(item)
        else:
            out.append(_value(item_tok, lineno))
    return out, pos


# -- loading ---------------------------------------------------------------

MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "manifest.json")


def find_manifest(target: str | Path) -> Path:
    p = Path(target)
    if p.is_dir():
        for name in MANIFEST_NAMES:
            if (p / name).exists():
                return p / name
        raise ManifestError(f"no {' / '.join(MANIFEST_NAMES)} found in {p}")
    if p.is_file():
        return p
    raise ManifestError(f"manifest not found: {p}")


def load_manifest(target: str | Path) -> tuple[Manifest, Path]:
    """Return (manifest, archive_root). The archive root is the manifest's folder."""
    mf_path = find_manifest(target)
    raw = mf_path.read_text("utf-8-sig")
    if mf_path.suffix == ".json":
        data = json.loads(raw)
    else:
        data = parse_yamlite(raw)
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a mapping at the top level")
    if isinstance(data.get("roots"), list):
        data["roots"] = [{"path": r} if isinstance(r, str) else r for r in data["roots"]]
    try:
        mf = Manifest.model_validate(data)
    except Exception as e:
        raise ManifestError(f"invalid manifest {mf_path}: {e}") from e
    return mf, mf_path.parent.resolve()


def resolve_root(spec_path: str, archive_root: Path) -> Path:
    p = Path(spec_path)
    return (p if p.is_absolute() else archive_root / p).resolve()
