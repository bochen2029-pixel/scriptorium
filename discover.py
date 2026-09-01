"""P1 SCHEMA DISCOVERY + FREEZE (spec section 4 P1; rung S1).

`discover`: stratified sample over the Tape -> induce the corpus's OWN ontology
(thinking, effort high) -> merge -> author rubric_P2 + compression prior ->
golden shards (reference cards, non-thinking t=0, incl. planted defects so QC
can fail) -> 3 golden syntheses -> score the goldens TWICE with the proposed
rubric (the S1 falsifier: below bar or unstable across re-runs = the rubric is
not frozen-stable; freeze refuses).

`freeze`: verifies the falsifier passed, stamps status frozen, fingerprints
every charter artifact into charter/charter.lock, and records the active
charter in scriptorium.lock. Ratification per RATIFIED.md item 1 (operator
delegation) — operator edits + re-freeze remain cheap by design.

P1's sampling unit is the tape text record (<=32k chars ~ <=8k tokens, which is
the chunk budget); the chunker organ enters at P2. Charter artifacts live under
<archive_root>/charter — they are a render of the Tape + this pass, and the
Tape itself is never written by discovery.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import a2a
from canon import blake2b128_hex
from cards import CardV0, OntologyMerged, RubricOut
from ds import DsClient, UnitQuarantined
from harness import make_client
from manifest import load_manifest, parse_yamlite
from organs import CODE_DIR
from tape import Tape

SEED_DEFAULT = 20260731
SCORING_BAR = 0.55           # proposed at S1; calibration refines at S2
STABILITY_EPS = 0.05         # absolute tolerance FLOOR (see stability_verdict)
STABILITY_SE = 2.0           # ... or this many standard errors, whichever is wider
BATCH_TOKENS = 45_000
INDUCTION_CONCURRENCY = 32


def _prompt(name: str) -> str:
    return (CODE_DIR / "prompts" / f"{name}.txt").read_text("utf-8")


# -- tape scanning ---------------------------------------------------------

@dataclass
class RecRow:
    doc_id: str
    seq: int
    tokens: int
    chars: int
    year: int = 0
    project: str = ""
    modality: str = ""


def scan_tape(root: Path) -> tuple[list[RecRow], int, dict[str, dict[str, Any]]]:
    """One streaming pass: text-record rows joined with their doc's metadata.
    Rows belonging to docs that never completed are dropped (partial docs)."""
    tape = Tape.open(root, readonly=True)
    rows: dict[str, list[RecRow]] = {}
    kept: list[RecRow] = []
    doc_meta: dict[str, dict[str, Any]] = {}
    try:
        for rec in tape.iter_records():
            b = rec["body"]
            if rec["kind"] == "text":
                rows.setdefault(b["doc_id"], []).append(RecRow(
                    doc_id=b["doc_id"], seq=b["seq"],
                    tokens=b.get("meta", {}).get("tokens_est", 0), chars=b["chars"]))
            elif rec["kind"] == "doc":
                doc_rows = rows.pop(b["doc_id"], [])
                project = b["path"].split("/", 1)[0]
                doc_meta[b["doc_id"]] = {"path": b["path"], "year": b["year"],
                                         "project": project, "modality": b["modality"],
                                         "source": b["source"]}
                for r in doc_rows:
                    r.year, r.project, r.modality = b["year"], project, b["modality"]
                kept.extend(doc_rows)
    finally:
        tape.close()
    return kept, sum(r.tokens for r in kept), doc_meta


def fetch_texts(root: Path, wanted: set[tuple[str, int]]) -> dict[tuple[str, int], str]:
    tape = Tape.open(root, readonly=True)
    out: dict[tuple[str, int], str] = {}
    try:
        for rec in tape.iter_records(kinds=("text",)):
            b = rec["body"]
            key = (b["doc_id"], b["seq"])
            if key in wanted:
                out[key] = b["text"]
                if len(out) == len(wanted):
                    break
    finally:
        tape.close()
    return out


def stratified_sample(rows: list[RecRow], budget_tokens: int, seed: int
                      ) -> list[RecRow]:
    """Proportional-by-tokens across (year, project) cells; seeded, deterministic."""
    usable = [r for r in rows if 50 <= r.tokens <= 8500]
    total = sum(r.tokens for r in usable)
    if not total:
        return []
    cells: dict[tuple[int, str], list[RecRow]] = {}
    for r in usable:
        cells.setdefault((r.year, r.project), []).append(r)
    rng = random.Random(seed)
    picked: list[RecRow] = []
    for key in sorted(cells):
        cell = cells[key]
        cell_tokens = sum(r.tokens for r in cell)
        cell_budget = max(budget_tokens * cell_tokens / total,
                          min(cell_tokens, 60))     # every cell gets a voice
        order = sorted(cell, key=lambda r: (r.doc_id, r.seq))
        rng.shuffle(order)
        got = 0
        for r in order:
            if got >= cell_budget:
                break
            picked.append(r)
            got += r.tokens
    return picked


def pack_batches(sampled: list[RecRow], max_tokens: int = BATCH_TOKENS
                 ) -> list[list[RecRow]]:
    batches: list[list[RecRow]] = []
    cur: list[RecRow] = []
    cur_tok = 0
    for r in sorted(sampled, key=lambda r: (r.year, r.project, r.doc_id, r.seq)):
        if cur and cur_tok + r.tokens > max_tokens:
            batches.append(cur)
            cur, cur_tok = [], 0
        cur.append(r)
        cur_tok += r.tokens
    if cur:
        batches.append(cur)
    return batches


# -- defect planting (so QC can fail; REEL section 10) ---------------------

_CAP_RE = re.compile(r"\b[A-Z][a-z]{3,}\b")
_YEAR_RE = re.compile(r"\b(19|20)\d\d\b")
_NUM_RE = re.compile(r"\b\d{2,6}\b")


def mutate(text: str, kind: str) -> tuple[str, str] | None:
    """Deterministic corpus mutations; returns (mutated, description) or None."""
    if kind == "entity_swap":
        counts: dict[str, int] = {}
        for m in _CAP_RE.finditer(text):
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
        common = [w for w, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n >= 3]
        if not common:
            return None
        w = common[0]
        first = text.find(w)
        head = text[: first + len(w)]
        return (head + text[first + len(w):].replace(w, "Zorbell"),
                f"entity '{w}' becomes 'Zorbell' after first occurrence")
    if kind == "negation_flip":
        if " is not " in text:
            return text.replace(" is not ", " is ", 1), "' is not ' -> ' is ' (first)"
        if " is " in text:
            return text.replace(" is ", " is not ", 1), "' is ' -> ' is not ' (first)"
        return None
    if kind == "year_shift":
        m = _YEAR_RE.search(text)
        if not m:
            return None
        y = int(m.group(0))
        return (text[: m.start()] + str(y + 7) + text[m.end():],
                f"year {y} -> {y + 7} (first occurrence)")
    if kind == "number_scale":
        for m in _NUM_RE.finditer(text):
            if _YEAR_RE.fullmatch(m.group(0)):
                continue
            n = int(m.group(0))
            return (text[: m.start()] + str(n * 10) + text[m.end():],
                    f"number {n} -> {n * 10}")
        return None
    return None


DEFECT_KINDS = ("entity_swap", "negation_flip", "year_shift", "number_scale")


# -- scoring (deterministic, no LLM — fence-flavored) ----------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _f1(a: set, b: set) -> float | None:
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    inter = len(a & b)
    p, r = inter / len(b), inter / len(a)
    return 2 * p * r / (p + r) if p + r else 0.0


def stability_verdict(rep1: dict[str, Any], rep2: dict[str, Any]) -> dict[str, Any]:
    """The S1 stability falsifier, noise-aware.

    Both runs score the SAME shards, so the honest question is whether their
    per-shard scores differ by more than measurement noise — a PAIRED
    comparison. The tolerance is `max(STABILITY_EPS, STABILITY_SE * SE)`:
    the absolute epsilon stays a floor (large-n runs are never held to an
    impossibly tight standard), and small samples get the wider tolerance
    their own variance earns.

    Why (measured 2026-09-01, all four charters ever scored on this box):
      corpus#1 v1   n=118  gap 0.0099  SE 0.0208  |t| 0.47  -> stable (unchanged)
      corpus#1 v2   n=120  gap 0.0083  SE 0.0186  |t| 0.45  -> stable (unchanged)
      collection#2  n=30   gap 0.0759  SE 0.0337  |t| 2.25  -> UNSTABLE (still refused)
      collection#2  n=42   gap 0.0516  SE 0.0407  |t| 1.27  -> stable (was a FALSE POSITIVE)
    A fixed absolute epsilon tests a gap that shrinks as 1/sqrt(n) against a
    constant, so it silently becomes a corpus-size test: small archives get
    refused for sampling noise. Both frozen charters keep their verdicts, the
    genuinely unstable run is still refused, and the quality bar (SCORING_BAR,
    absolute) is untouched — this rule only decides "same or different", never
    "good enough"."""
    s1 = {s["id"]: s["score"] for s in rep1.get("shards", [])}
    s2 = {s["id"]: s["score"] for s in rep2.get("shards", [])}
    ids = sorted(set(s1) & set(s2))
    gap = abs(rep1["mean"] - rep2["mean"])
    diffs = [s1[i] - s2[i] for i in ids]
    n = len(diffs)
    se = 0.0
    if n >= 2:
        md = sum(diffs) / n
        var = sum((d - md) ** 2 for d in diffs) / (n - 1)
        se = math.sqrt(var / n)
    tol = max(STABILITY_EPS, STABILITY_SE * se)
    return {"gap": round(gap, 4), "paired_n": n, "paired_se": round(se, 4),
            "t": round(gap / se, 2) if se else None,
            "tolerance": round(tol, 4), "same": gap <= tol}


def compare_cards(ref: CardV0, got: CardV0) -> dict[str, Any]:
    f1s = {
        "entities": _f1({_norm(e.name) for e in ref.entities},
                        {_norm(e.name) for e in got.entities}),
        "claims": _f1({(_norm(c.subject), _norm(c.predicate), c.polarity)
                       for c in ref.claims},
                      {(_norm(c.subject), _norm(c.predicate), c.polarity)
                       for c in got.claims}),
        "topics": _f1({_norm(t) for t in ref.topics},
                      {_norm(t) for t in got.topics}),
    }
    present = [v for v in f1s.values() if v is not None]
    return {**f1s, "score": sum(present) / len(present) if present else 1.0}


# -- tiny YAML dumper (emits exactly the yamlite subset) -------------------

_PLAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-/()]*$")


def _scalar_out(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if _PLAIN_RE.match(s) and s.lower() not in ("null", "true", "false", "yes",
                                                "no", "on", "off", "~"):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") \
        .replace("\r", "").replace("\t", "\\t") + '"'


def dump_yaml(obj: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(obj, dict):
        if not obj:
            return ""
        lines = []
        for k, v in obj.items():
            if isinstance(v, dict) and v:
                lines.append(f"{pad}{k}:")
                lines.append(dump_yaml(v, indent + 2))
            elif isinstance(v, list) and v:
                if all(not isinstance(i, (dict, list)) for i in v):
                    lines.append(f"{pad}{k}: [" + ", ".join(_scalar_out(i) for i in v) + "]")
                else:
                    lines.append(f"{pad}{k}:")
                    lines.append(dump_yaml(v, indent + 2))
            elif isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: " + ("{}" if isinstance(v, dict) else "[]"))
            else:
                lines.append(f"{pad}{k}: {_scalar_out(v)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for item in obj:
            if isinstance(item, dict) and item:
                keys = list(item)
                first = keys[0]
                lines.append(f"{pad}- {first}: {_scalar_out(item[first])}")
                for k in keys[1:]:
                    v = item[k]
                    if isinstance(v, (dict, list)):
                        raise ValueError("dump_yaml: nested collections inside "
                                         "list items unsupported (subset)")
                    lines.append(f"{pad}  {k}: {_scalar_out(v)}")
            else:
                lines.append(f"{pad}- {_scalar_out(item)}")
        return "\n".join(lines)
    return pad + _scalar_out(obj)


# -- the pass --------------------------------------------------------------

def _fmt_record(r: RecRow, text: str) -> str:
    return (f"[doc {r.doc_id[:10]} | year {r.year} | project {r.project} | seq {r.seq}]\n"
            f"{text}\n")


async def run_discover(target: str | Path, *, usd_cap: float = 5.0,
                       sample_tokens: int | None = None, goldens_n: int = 120,
                       defects_n: int = 12, seed: int = SEED_DEFAULT,
                       rescore_only: bool = False,
                       concurrency: int = INDUCTION_CONCURRENCY,
                       base_url: str | None = None,
                       provider: str = "api") -> dict[str, Any]:
    _mf, root = load_manifest(target)
    charter = root / "charter"
    if (charter / "charter.lock").exists() and not rescore_only:
        raise SystemExit("charter is FROZEN; a re-derive is a new catalog version "
                         "(spec section 5) — refuse. Use --rescore-only to re-run QC.")
    run_id = "p1-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    runs_dir = root / "runs" / run_id
    runs_dir.mkdir(parents=True, exist_ok=True)
    # The bus first: a lease refusal exits before anything is built.
    bridge = a2a.begin("P1-discover", root.name)
    client = make_client("P1-discover", usd_cap, provider=provider,
                         concurrency=concurrency,
                         journal_path=runs_dir / "ds_calls.jsonl",
                         base_url=base_url)
    keeper = a2a.LeaseKeeper(bridge)       # renews the pass lease for the
    keeper.start()                         # whole pass, inside every phase
    t0 = time.monotonic()

    def say(msg: str) -> None:
        print(msg, flush=True)

    try:
        if rescore_only:
            return await _rescore(client, root, charter, say)

        say(f"[{run_id}] scanning tape under {root} ...")
        rows, corpus_tokens, _doc_meta = scan_tape(root)
        say(f"  {len(rows)} text records, {corpus_tokens:,} tokens census")
        budget = sample_tokens or min(max(int(corpus_tokens * 0.02), 200_000), 6_000_000)
        sampled = stratified_sample(rows, budget, seed)
        s_tokens = sum(r.tokens for r in sampled)
        cells = len({(r.year, r.project) for r in sampled})
        say(f"  sampled {len(sampled)} records, {s_tokens:,} tokens across {cells} cells "
            f"(budget {budget:,})")
        a2a.note(bridge, f"run_start: {run_id} provider={provider} "
                         f"sampled={len(sampled)} tokens={s_tokens} "
                         f"cells={cells} cap=${usd_cap}")

        goldens_pool = [r for r in sampled if 400 <= r.tokens <= 6000]
        rng = random.Random(seed + 1)
        rng.shuffle(goldens_pool)
        shard_rows = goldens_pool[:goldens_n]
        est_in = s_tokens + 3 * sum(r.tokens for r in shard_rows) + 150_000
        est_out = len(pack_batches(sampled)) * 4000 + 3 * len(shard_rows) * 1200 + 40_000
        est = client.gate_estimate(est_in, est_out)
        say(f"  PS-8 gate: estimate ${est:.2f} under cap ${usd_cap:.2f} — proceeding")

        say("  fetching sampled texts (tape pass 2) ...")
        texts = fetch_texts(root, {(r.doc_id, r.seq) for r in sampled})

        # -- induction ------------------------------------------------------
        batches = pack_batches(sampled)
        say(f"  induction: {len(batches)} batches, thinking effort=high ...")
        induce_sys = _prompt("p1_induce_v0")
        await client.warmup(induce_sys)

        async def induce(i: int, batch: list[RecRow]):
            user = "".join(_fmt_record(r, texts.get((r.doc_id, r.seq), "")) + "\n"
                           for r in batch)
            try:
                out, _ = await client.chat(
                    system=induce_sys, user=user,
                    tail=f"\n[batch {i + 1} of {len(batches)}]",
                    mode="think", effort="high", max_tokens=24_000,
                    unit_id=f"induce-{i:03d}", out_model=None)
                from cards import OntologyDraft
                return OntologyDraft.model_validate(
                    json.loads(out[out.find("{"): out.rfind("}") + 1]))
            except (UnitQuarantined, json.JSONDecodeError, ValueError) as e:
                say(f"    batch {i} quarantined: {str(e)[:120]}")
                return None

        drafts = [d for d in await asyncio.gather(
            *(induce(i, b) for i, b in enumerate(batches))) if d is not None]
        say(f"  induction done: {len(drafts)}/{len(batches)} batches usable; "
            f"meter ${client.meter.usd():.3f}")
        if not drafts:
            raise SystemExit("all induction batches failed — no charter")

        # -- merge + rubric (fatal if quarantined: no charter without them) --
        try:
            merged_raw, _ = await client.chat(
                system=_prompt("p1_merge_v0"),
                user=json.dumps([d.model_dump() for d in drafts], ensure_ascii=False)
                + f"\n\nCorpus stats: {corpus_tokens:,} tokens, {len(rows)} records, "
                  f"years {min(r.year for r in rows)}-{max(r.year for r in rows)}.",
                mode="think", effort="high", max_tokens=49_152,
                unit_id="merge", out_model=OntologyMerged)
        except UnitQuarantined as e:
            raise SystemExit(f"merge pass quarantined after the full ladder — no "
                             f"charter this run; meter ${client.meter.usd():.3f}. "
                             f"({e.detail[:160]})") from e
        merged: OntologyMerged = merged_raw
        say(f"  merged ontology: {len(merged.projects)} projects, "
            f"{len(merged.themes)} themes, {len(merged.genres)} genres")

        excerpts = "\n\n".join(
            _fmt_record(r, texts[(r.doc_id, r.seq)][:1200])
            for r in sampled[:: max(1, len(sampled) // 8)][:8])
        try:
            rubric_out, _ = await client.chat(
                system=_prompt("p1_rubric_v0"),
                user="ONTOLOGY:\n" + json.dumps(merged.model_dump(), ensure_ascii=False)
                + "\n\nEXCERPTS:\n" + excerpts,
                mode="think", effort="high", max_tokens=49_152,
                unit_id="rubric", out_model=RubricOut)
        except UnitQuarantined as e:
            raise SystemExit(f"rubric pass quarantined after the full ladder — no "
                             f"charter this run; meter ${client.meter.usd():.3f}. "
                             f"({e.detail[:160]})") from e

        charter.mkdir(exist_ok=True)
        (charter / "ontology.yaml").write_text(
            dump_yaml(merged.model_dump()) + "\n", "utf-8")
        (charter / "rubric_P2.md").write_text(rubric_out.rubric_md, "utf-8")
        (charter / "prior.md").write_text(rubric_out.prior_md, "utf-8")
        say("  charter drafts written (ontology.yaml, rubric_P2.md, prior.md)")

        # -- golden shards ---------------------------------------------------
        say(f"  authoring {len(shard_rows)} golden shards "
            f"({min(defects_n, len(shard_rows))} with planted defects) ...")
        refcard_sys = rubric_out.rubric_md + "\n\n" + _prompt("p1_refcard_v0")
        await client.warmup(refcard_sys)
        shards_dir = charter / "goldens" / "shards"
        shards_dir.mkdir(parents=True, exist_ok=True)

        shard_specs: list[dict[str, Any]] = []
        for k, r in enumerate(shard_rows):
            text = texts[(r.doc_id, r.seq)]
            defect = None
            if k >= len(shard_rows) - defects_n:
                for kind in (DEFECT_KINDS[k % len(DEFECT_KINDS)], *DEFECT_KINDS):
                    got = mutate(text, kind)
                    if got:
                        text, desc = got
                        defect = {"kind": kind, "description": desc}
                        break
            shard_specs.append({"id": f"shard-{k:04d}", "doc_id": r.doc_id,
                                "seq": r.seq, "year": r.year, "project": r.project,
                                "defect": defect, "text": text})

        async def author(spec: dict[str, Any]):
            try:
                card, _ = await client.chat(
                    system=refcard_sys, user="CHUNK:\n" + spec["text"],
                    tail=f"\n\n[{spec['id']}]", mode="extract",
                    max_tokens=6000, unit_id="ref-" + spec["id"], out_model=CardV0)
                return spec, card
            except UnitQuarantined as e:
                say(f"    {spec['id']} reference quarantined: {str(e)[:100]}")
                return spec, None

        authored = await asyncio.gather(*(author(s) for s in shard_specs))
        shards = []
        for spec, card in authored:
            if card is None:
                continue
            spec["reference"] = card.model_dump()
            (shards_dir / f"{spec['id']}.json").write_text(
                json.dumps(spec, ensure_ascii=False, indent=1), "utf-8")
            shards.append(spec)
        n_defects = sum(1 for s in shards if s["defect"])
        say(f"  goldens: {len(shards)} shards written, {n_defects} defective; "
            f"meter ${client.meter.usd():.3f}, hit-rate {client.meter.hit_rate():.0%}")

        # -- golden syntheses ------------------------------------------------
        syn_dir = charter / "goldens" / "syntheses"
        syn_dir.mkdir(parents=True, exist_ok=True)
        top_theme = merged.themes[0].name if merged.themes else "the archive's center"
        top_project = merged.projects[0].name if merged.projects else "the main project"
        assignments = [
            ("ledger", f"evolution ledger for the theme '{top_theme}'", top_theme),
            ("portrait", f"portrait of the project '{top_project}'", top_project),
            ("dossier", f"retelling/connection dossier around '{top_theme}' "
                        f"and '{top_project}'", top_project),
        ]

        async def synth(name: str, task: str, needle: str):
            support = [r for r in sampled
                       if needle.lower() in texts.get((r.doc_id, r.seq), "").lower()]
            support = sorted(support, key=lambda r: -r.tokens)[:6] or sampled[:4]
            user = (f"ASSIGNMENT: {task}\n\nONTOLOGY SUMMARY: {merged.summary}\n\n"
                    + "EXCERPTS:\n\n"
                    + "\n\n".join(_fmt_record(r, texts[(r.doc_id, r.seq)][:6000])
                                  for r in support))
            try:
                text_out, _ = await client.chat(
                    system=_prompt("p1_synthesis_v0"), user=user, mode="think",
                    effort="high", max_tokens=12_000, unit_id=f"synth-{name}")
                (syn_dir / f"{name}.md").write_text(text_out, "utf-8")
                return True
            except UnitQuarantined as e:
                say(f"    synthesis {name} quarantined: {str(e)[:100]}")
                return False

        syn_ok = sum(await asyncio.gather(*(synth(*a) for a in assignments)))
        say(f"  golden syntheses: {syn_ok}/3 written")

        # -- scoring x2 (the S1 falsifier) ----------------------------------
        means = []
        reps = []
        for n in (1, 2):
            rep = await _score_once(client, shards, refcard_sys, say, n)
            means.append(rep["mean"])
            reps.append(rep)
            (charter / "scoring").mkdir(exist_ok=True)
            (charter / "scoring" / f"run-{n}-{run_id}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
        sv = stability_verdict(reps[0], reps[1])
        stable = sv["same"] and all(m >= SCORING_BAR for m in means)
        say(f"  scoring: run1 {means[0]:.3f}  run2 {means[1]:.3f}  bar {SCORING_BAR} "
            f"| gap {sv['gap']:.4f} vs tolerance {sv['tolerance']:.4f} "
            f"(paired n={sv['paired_n']} SE={sv['paired_se']:.4f} |t|={sv['t']}) "
            f"-> {'STABLE (falsifier passed)' if stable else 'UNSTABLE/BELOW BAR (freeze will refuse)'}")

        # -- charter.yaml ----------------------------------------------------
        meta = {
            "schema": 1, "status": "proposed", "run_id": run_id,
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "model_fp": client.model_fp or "",
            "rubric_v": "r1", "ontology_v": "o1",
            "sample": {"corpus_tokens": corpus_tokens, "records": len(rows),
                       "sampled_records": len(sampled), "sampled_tokens": s_tokens,
                       "cells": cells, "batches": len(batches),
                       "batches_quarantined": len(batches) - len(drafts),
                       "seed": seed},
            "goldens": {"shards": len(shards), "defects": n_defects,
                        "syntheses": syn_ok},
            "scoring": {"bar": SCORING_BAR, "stability_eps": STABILITY_EPS,
                        "stability_se_k": STABILITY_SE,
                        "stability": sv,
                        "runs": [round(m, 4) for m in means],
                        "stable": stable},
            "meter": client.meter.snapshot(),
            "prompts": {n: blake2b128_hex((CODE_DIR / "prompts" / f"{n}.txt").read_bytes())
                        for n in ("p1_induce_v0", "p1_merge_v0", "p1_rubric_v0",
                                  "p1_refcard_v0", "p1_synthesis_v0")},
        }
        (charter / "charter.yaml").write_text(dump_yaml(meta) + "\n", "utf-8")
        say(f"\n== P1 discover done in {int(time.monotonic() - t0)}s — "
            f"${client.meter.usd():.3f} spent, hit-rate {client.meter.hit_rate():.0%}, "
            f"charter PROPOSED at {charter}")
        return meta
    finally:
        await keeper.stop()
        await client.close()
        a2a.end(bridge, f"${client.meter.usd():.3f} spent")


async def _score_once(client: DsClient, shards: list[dict[str, Any]],
                      refcard_sys: str, say, run_n: int) -> dict[str, Any]:
    say(f"  scoring run {run_n}: re-extracting {len(shards)} shards (t=0, cached prefix)...")

    async def one(spec):
        try:
            card, _ = await client.chat(
                system=refcard_sys, user="CHUNK:\n" + spec["text"],
                tail=f"\n\n[score-{run_n}-{spec['id']}]", mode="extract",
                max_tokens=6000, unit_id=f"score{run_n}-{spec['id']}",
                out_model=CardV0)
            cmp_ = compare_cards(CardV0.model_validate(spec["reference"]), card)
            return {"id": spec["id"], "defect": bool(spec["defect"]), **cmp_}
        except UnitQuarantined:
            return {"id": spec["id"], "defect": bool(spec["defect"]),
                    "entities": 0.0, "claims": 0.0, "topics": 0.0, "score": 0.0,
                    "quarantined": True}

    results = await asyncio.gather(*(one(s) for s in shards))
    mean = sum(r["score"] for r in results) / len(results) if results else 0.0
    return {"run": run_n, "mean": round(mean, 4), "n": len(results),
            "quarantined": sum(1 for r in results if r.get("quarantined")),
            "shards": results}


async def _rescore(client: DsClient, root: Path, charter: Path, say) -> dict[str, Any]:
    shards = [json.loads(p.read_text("utf-8"))
              for p in sorted((charter / "goldens" / "shards").glob("shard-*.json"))]
    refcard_sys = (charter / "rubric_P2.md").read_text("utf-8") + "\n\n" + _prompt("p1_refcard_v0")
    await client.warmup(refcard_sys)
    rep = await _score_once(client, shards, refcard_sys, say, run_n=99)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (charter / "scoring" / f"rescore-{ts}.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    say(f"  rescore mean {rep['mean']:.3f} (bar {SCORING_BAR}) — ${client.meter.usd():.3f}")
    return rep


# -- freeze ----------------------------------------------------------------

CHARTER_CORE = ("ontology.yaml", "rubric_P2.md", "prior.md", "charter.yaml")


def _roster_key(slock: dict[str, Any], root: Path) -> str:
    """The roster row name for an archive: its folder name, unless another
    archive already holds that name — then name@<8 hex of the full path>, so
    two archives whose folders happen to share a basename can never
    overwrite each other's frozen record."""
    rows = slock.get("charters") or {}
    key = root.name
    held = rows.get(key)
    if held and held.get("archive") not in (None, str(root)):
        key = f"{root.name}@{blake2b128_hex(str(root).encode('utf-8'))[:8]}"
    return key


def run_freeze(target: str | Path) -> dict[str, Any]:
    _mf, root = load_manifest(target)
    charter = root / "charter"
    lock_path = charter / "charter.lock"
    if lock_path.exists():
        raise SystemExit("charter.lock already exists — a re-derive is a new "
                         "catalog version (spec section 5); refuse.")
    meta = parse_yamlite((charter / "charter.yaml").read_text("utf-8"))
    if meta.get("status") != "proposed":
        raise SystemExit(f"charter status is {meta.get('status')!r}, not 'proposed'")
    scoring = meta.get("scoring") or {}
    if not scoring.get("stable"):
        raise SystemExit(
            "S1 falsifier NOT passed (scoring unstable or below bar) — "
            "the rubric is not frozen-stable; freeze refuses. Re-run discover.")
    meta["status"] = "frozen"
    meta["frozen_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (charter / "charter.yaml").write_text(dump_yaml(meta) + "\n", "utf-8")

    files = [charter / n for n in CHARTER_CORE]
    files += sorted((charter / "goldens" / "shards").glob("shard-*.json"))
    files += sorted((charter / "goldens" / "syntheses").glob("*.md"))
    fps = {str(p.relative_to(charter)).replace("\\", "/"):
           blake2b128_hex(p.read_bytes()) for p in files}
    root_fp = blake2b128_hex(json.dumps(fps, sort_keys=True).encode())
    lock = {"schema": 1, "frozen_at": meta["frozen_at"],
            "rubric_v": meta.get("rubric_v"), "ontology_v": meta.get("ontology_v"),
            "model_fp": meta.get("model_fp"), "root_fingerprint": root_fp,
            "ratification": "RATIFIED.md item 1 (operator delegation, 2026-07-31)",
            "fingerprints": fps}
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=1), "utf-8")

    slock_path = CODE_DIR / "scriptorium.lock"
    slock = json.loads(slock_path.read_text("utf-8"))
    # one row per archive: freezes must never overwrite each other's record
    # (the truth stays each archive's own charter.lock; this is the roster)
    slock.setdefault("charters", {})[_roster_key(slock, root)] = {
        "status": "frozen", "archive": str(root),
        "model_fp": meta.get("model_fp"),
        "rubric_v": meta.get("rubric_v"),
        "ontology_v": meta.get("ontology_v"),
        "root_fingerprint": root_fp, "frozen_at": meta["frozen_at"]}
    slock.pop("charter", None)          # legacy single-archive block
    slock_path.write_text(json.dumps(slock, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"charter FROZEN: {len(fps)} artifacts fingerprinted, root {root_fp}")
    print(f"  charter.lock at {lock_path}; scriptorium.lock charter block updated")
    return lock
