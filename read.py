"""P2 THE FIRST READING (spec section 4 P2; rung S2).

Every selected chunk -> one typed Card (non-thinking, t=0, JSON) under the
FROZEN charter: the system prefix is byte-identical for every call —
rubric_P2.md + the frozen p1_refcard_v0 contract, the exact pair the golden
references were authored and scored with, verified against charter.lock
fingerprints before the first call. Cards land append-only in
catalog/cards/cards.jsonl (fsync'd per batch); quarantines are typed rows in
quarantine.jsonl; resume = skip keys already present in either.

Calibration (spec section 5): a rotating subset of the golden shards is
re-extracted every N batches and compared to the frozen references; a mean
below the charter bar halts the pass checkpoint-clean — never silently
continue. SCRIPTORIUM_TEST_FORCE_DRIFT=1 forces one failing calibration (the
falsifier drill).

Embeddings + index: chunk texts are embedded on the local :8092 sidecar
(qwen3-embedding, pinned) into catalog/index.sqlite — chunks table + FTS5 +
float32 vectors; the CORTEX skeleton gets built here, in passing.

Cache accounting: DeepSeek reports hit/miss in TOKENS, so on unique 8-13k-token
chunks the *total* hit share is arithmetically capped near
prefix/(prefix+chunk) (~20-30%) — the spec's ">=60% or build bug" vital is
therefore measured here as PREFIX-HIT EFFICIENCY: the share of calls whose
cache-hit tokens cover >=75% of the frozen prefix. Both numbers are reported;
the discrepancy is recorded in STATE.md, not silently reinterpreted.

P2's chunk unit is the tape text record (<=32k chars, inside the configured
budget range [2000, 32000]); the chunker organ remains the census cross-check.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import re
import sqlite3
import struct
import time
from pathlib import Path
from typing import Any

import a2a
from canon import blake2b128_hex
from cards import CardV0
from discover import SCORING_BAR, RecRow, compare_cards, scan_tape
from ds import CapExceeded, UnitQuarantined
from harness import make_client
from local import EmbedSidecar
from manifest import load_manifest
from organs import CODE_DIR
from textindex import TextReader
from textnorm import estimate_tokens

BATCH_SIZE = 48
CALIB_EVERY = 50          # batches (spec section 5 default N=50)
CALIB_SHARDS = 16         # rotating golden subset per calibration round; 8
                          # swung 0.57-0.72 on the FERRYMAN v1 slice (SE ~
                          # sigma/sqrt(n)) — 16 halves nothing but trims the
                          # swing ~30%; a variance-aware band was considered
                          # and rejected: the bar is the charter's own scored
                          # floor and halt-below-bar stays a hard law
DRIFT_FLOOR = SCORING_BAR  # calibration mean below the charter bar = halt
HARNESS_CONCURRENCY = 6   # HM-7: each slot is a full runtime subprocess
OUT_TOKENS = 6000         # per-card output budget; dense chunks that exhaust
                          # it quarantine as json-hostile — --max-out-tokens
                          # raises it for a --retry-quarantined rerun
# Estimation inputs, MEASURED from real card calls (2026-09-01) rather than
# guessed: mean completion was 2,578 tok/card on the v2 tape and 1,801 on the
# repo corpus (the old 900 under-counted output ~3x, which quietly cancelled
# the input side's no-cache-credit pessimism). The prefix cache rate is what
# the same runs realized: 46% (v2) / 53% (repo).
EST_OUT_TOKENS = 2600
EST_CACHE_HIT_RATE = 0.46


def _refcard_prompt() -> str:
    return (CODE_DIR / "prompts" / "p1_refcard_v0.txt").read_text("utf-8")


def _charter_baseline(charter: Path) -> float | None:
    """scoring.runs[-1] from charter.yaml — the charter's own scored quality,
    printed beside each calibration mean. Targeted stdlib parse (no YAML dep);
    scoring lives in charter.yaml, not charter.lock."""
    try:
        m = re.search(r"^\s*runs:\s*\[([^\]]*)\]",
                      (charter / "charter.yaml").read_text("utf-8"), re.M)
        if m:
            vals = [float(x) for x in m.group(1).split(",") if x.strip()]
            return vals[-1] if vals else None
    except (OSError, ValueError):
        pass
    return None


def verify_frozen_charter(charter: Path) -> dict[str, Any]:
    """The freeze discipline: refuse to read under a tampered or absent charter."""
    lock_path = charter / "charter.lock"
    if not lock_path.exists():
        raise SystemExit("no frozen charter (charter.lock missing) — run "
                         "`discover` then `freeze` first; P2 refuses.")
    lock = json.loads(lock_path.read_text("utf-8"))
    for rel in ("rubric_P2.md", "ontology.yaml", "prior.md"):
        want = lock["fingerprints"].get(rel)
        got = blake2b128_hex((charter / rel).read_bytes())
        if got != want:
            raise SystemExit(f"charter artifact {rel} does not match its frozen "
                             f"fingerprint — refuse (spec section 5 version law)")
    return lock


# -- catalog stores --------------------------------------------------------

class CardStore:
    """Append-only cards + quarantine JSONL with fsync'd batch writes."""

    def __init__(self, cards_dir: Path):
        cards_dir.mkdir(parents=True, exist_ok=True)
        self.cards_path = cards_dir / "cards.jsonl"
        self.quar_path = cards_dir / "quarantine.jsonl"

    def done_keys(self, *, include_quarantined: bool = True) -> set[tuple[str, int]]:
        """Resume law: skip keys already present. include_quarantined=False is
        the --retry-quarantined mode — quarantined keys become todo again; a
        key later appearing in BOTH files means resolved-on-retry (cards.jsonl
        wins; quarantine.jsonl is append-only history)."""
        paths = ((self.cards_path, self.quar_path) if include_quarantined
                 else (self.cards_path,))
        done: set[tuple[str, int]] = set()
        for p in paths:
            if not p.exists():
                continue
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        done.add((row["doc_id"], row["seq"]))
                    except (json.JSONDecodeError, KeyError):
                        continue          # torn tail from a kill; overwritten next append
        return done

    def append_batch(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        blob = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        with open(path, "a", encoding="utf-8") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())


class CatalogIndex:
    """SQLite: chunks + FTS5 + float32 vectors (the resident-skeleton feedstock)."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS chunks("
            " doc_id TEXT, seq INT, project TEXT, year INT, path TEXT,"
            " tokens INT, chars INT, PRIMARY KEY(doc_id, seq));"
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text);"
            "CREATE TABLE IF NOT EXISTS fts_map("
            " fts_rowid INTEGER PRIMARY KEY, doc_id TEXT, seq INT,"
            " UNIQUE(doc_id, seq));"
            "CREATE TABLE IF NOT EXISTS vectors("
            " doc_id TEXT, seq INT, dim INT, vec BLOB, model TEXT,"
            " PRIMARY KEY(doc_id, seq));")

    def has_vector(self, key: tuple[str, int]) -> bool:
        cur = self.db.execute("SELECT 1 FROM vectors WHERE doc_id=? AND seq=?", key)
        return cur.fetchone() is not None

    def add_chunk(self, row: RecRow, meta: dict[str, Any], text: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO chunks VALUES(?,?,?,?,?,?,?)",
            (row.doc_id, row.seq, row.project, row.year,
             meta.get("path", ""), row.tokens, row.chars))
        cur = self.db.execute(
            "SELECT fts_rowid FROM fts_map WHERE doc_id=? AND seq=?",
            (row.doc_id, row.seq))
        if cur.fetchone() is None:
            fts_cur = self.db.execute("INSERT INTO chunks_fts(text) VALUES(?)", (text,))
            self.db.execute("INSERT INTO fts_map VALUES(?,?,?)",
                            (fts_cur.lastrowid, row.doc_id, row.seq))

    def add_vector(self, key: tuple[str, int], vec: list[float], model: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO vectors VALUES(?,?,?,?,?)",
            (key[0], key[1], len(vec), struct.pack(f"{len(vec)}f", *vec), model))

    def counts(self) -> dict[str, int]:
        n = lambda q: self.db.execute(q).fetchone()[0]  # noqa: E731
        return {"chunks": n("SELECT COUNT(*) FROM chunks"),
                "fts": n("SELECT COUNT(*) FROM chunks_fts"),
                "vectors": n("SELECT COUNT(*) FROM vectors")}

    def commit_close(self) -> None:
        self.db.commit()
        self.db.close()


# -- the pass --------------------------------------------------------------

def backfill_vectors(target: str | Path, batch: int = 16) -> dict[str, Any]:
    """Embed carded chunks that have no vector yet — local sidecar only, no
    API, no charter. This exists because "deferred to a rerun" was NOT true:
    a rerun skips already-carded chunks by the resume law, so a read that ran
    while :8092 was down could never gain its vectors. Idempotent and
    resumable; safe to run any time."""
    _mf, root = load_manifest(target)
    cards_path = root / "catalog" / "cards" / "cards.jsonl"
    if not cards_path.exists():
        raise SystemExit(f"no cards at {cards_path} — run `read` first")
    keys: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    with open(cards_path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                key = (row["doc_id"], row["seq"])
            except (json.JSONDecodeError, KeyError):
                continue
            if key not in seen:
                seen.add(key)
                keys.append(key)

    index = CatalogIndex(root / "catalog" / "index.sqlite")
    missing = [k for k in keys if not index.has_vector(k)]
    print(f"cards {len(keys)} | already vectored {len(keys) - len(missing)} | "
          f"missing {len(missing)}")
    if not missing:
        index.commit_close()
        return {"cards": len(keys), "missing": 0, "added": 0}

    sidecar = EmbedSidecar()
    if not sidecar.ensure(launch=True):
        index.commit_close()
        raise SystemExit("embedding sidecar (:8092) unavailable — cannot "
                         "backfill; start it and rerun")
    reader = TextReader(root)
    added, unreadable = 0, 0
    try:
        for i in range(0, len(missing), batch):
            grp = missing[i:i + batch]
            texts = reader.get_many(grp)
            have = [k for k in grp if k in texts]
            unreadable += len(grp) - len(have)
            if not have:
                continue
            try:
                vecs = sidecar.embed([texts[k][:8000] for k in have])
            except Exception as e:  # noqa: BLE001 — report, never half-claim
                print(f"  embed failed at {i}: {str(e)[:150]} — stopping; "
                      f"{added} added so far are committed")
                break
            for k, v in zip(have, vecs, strict=True):
                index.add_vector(k, v, sidecar.fingerprint()["embedder"])
                added += 1
            index.db.commit()
            print(f"  {min(i + batch, len(missing))}/{len(missing)} ...",
                  flush=True)
    finally:
        reader.close()
        counts = index.counts()
        index.commit_close()
    print(f"backfill done: +{added} vectors"
          + (f" | {unreadable} chunks unreadable from the tape" if unreadable else "")
          + f" | index now {counts}")
    return {"cards": len(keys), "missing": len(missing), "added": added,
            "unreadable": unreadable, "index": counts}


def select_rows(rows: list[RecRow], projects: list[str] | None,
                max_tokens: int | None) -> list[RecRow]:
    picked = rows
    if projects:
        picked = [r for r in picked
                  if any(fnmatch.fnmatch(r.project.lower(), p.lower())
                         for p in projects)]
    picked.sort(key=lambda r: (r.project, r.doc_id, r.seq))
    if max_tokens:
        out, tot = [], 0
        for r in picked:
            if tot + r.tokens > max_tokens:
                break
            out.append(r)
            tot += r.tokens
        picked = out
    return picked


async def run_read(target: str | Path, *, usd_cap: float,
                   projects: list[str] | None = None,
                   max_tokens: int | None = None,
                   batch_size: int = BATCH_SIZE, calib_every: int = CALIB_EVERY,
                   concurrency: int | None = None, base_url: str | None = None,
                   provider: str = "api", embed: bool = True,
                   retry_quarantined: bool = False,
                   out_tokens: int = OUT_TOKENS,
                   dry_run: bool = False) -> dict[str, Any]:
    if concurrency is None:
        concurrency = BATCH_SIZE if provider == "api" else HARNESS_CONCURRENCY
    _mf, root = load_manifest(target)
    charter = root / "charter"
    charter_lock = verify_frozen_charter(charter)
    rubric = (charter / "rubric_P2.md").read_text("utf-8")
    system = rubric + "\n\n" + _refcard_prompt()
    prefix_tokens = estimate_tokens(system)

    run_id = "p2-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    runs_dir = root / "runs" / run_id
    runs_dir.mkdir(parents=True, exist_ok=True)
    client = make_client("P2-read", usd_cap, provider=provider,
                         concurrency=concurrency,
                         journal_path=runs_dir / "ds_calls.jsonl",
                         base_url=base_url, system_persona=system)
    bridge = a2a.begin("P2-read", root.name)
    stats = {"cards": 0, "quarantined": 0, "vectors": 0, "skipped_leased": 0,
             "prefix_hits": 0, "calls": 0, "calibrations": []}

    def say(msg: str) -> None:
        print(msg, flush=True)

    def jline(**kw: Any) -> None:
        with open(runs_dir / "journal.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    store = CardStore(root / "catalog" / "cards")
    index = CatalogIndex(root / "catalog" / "index.sqlite")
    reader: TextReader | None = None
    t0 = time.monotonic()
    try:
        say(f"[{run_id}] scanning tape ...")
        rows, corpus_tokens, doc_meta = scan_tape(root)
        selected = select_rows(rows, projects, max_tokens)
        sel_tokens = sum(r.tokens for r in selected)
        done = store.done_keys(include_quarantined=not retry_quarantined)
        todo = [r for r in selected if (r.doc_id, r.seq) not in done]
        say(f"  corpus {corpus_tokens:,} tok | selected {len(selected)} chunks "
            f"{sel_tokens:,} tok | done {len(selected) - len(todo)} | todo {len(todo)}")
        jline(event="run_start", run_id=run_id, selected=len(selected),
              todo=len(todo), sel_tokens=sel_tokens,
              projects=projects, max_tokens=max_tokens)
        a2a.note(bridge, f"run_start: {run_id} provider={provider} "
                         f"todo={len(todo)} sel_tokens={sel_tokens} "
                         f"cap=${usd_cap}")
        if not todo:
            say("  nothing to do — slice fully read")
            return {"run_id": run_id, "cards": 0, "already": len(selected)}

        est_in = sum(r.tokens for r in todo) + prefix_tokens * len(todo)
        est_out = EST_OUT_TOKENS * len(todo)
        # PS-8 gates on the WORST case (every input token billed as a cache
        # miss); the realistic line is printed beside it so a cap can be set
        # from evidence instead of from the worst case alone.
        est = client.gate_estimate(est_in, est_out)
        prices = client.meter.prices
        hit = est_in * EST_CACHE_HIT_RATE
        realistic = ((est_in - hit) * prices["input_cache_miss"]
                     + hit * prices["input_cache_hit"]
                     + est_out * prices["output"]) / 1e6
        say(f"  PS-8 gate: worst case ${est:.2f} (no cache credit) under cap "
            f"${usd_cap:.2f} — proceeding")
        say(f"    realistic ~${realistic:.2f} at the measured "
            f"{EST_CACHE_HIT_RATE:.0%} prefix-cache rate "
            f"({len(todo)} chunks, prefix ~{prefix_tokens} tok/call, "
            f"~{EST_OUT_TOKENS} out/card)")

        # Bounded memory: index the tape's text records once, then read each
        # batch's chunks on demand. Loading every selected text upfront costs
        # ~1GB of strings held for hours on a full-corpus read.
        say("  indexing tape text records (offsets sidecar) ...")
        reader = TextReader(root)
        say(f"  text index: {reader.stats['indexed']} records "
            f"({reader.stats['added']} newly indexed)")

        if dry_run:
            # Preflight for an expensive run: everything except the spend.
            # The charter has been fingerprint-verified, the slice selected,
            # the budget gated and the tape proven readable by this point.
            sample = todo[:min(len(todo), 200)]
            served = reader.get_many([(r.doc_id, r.seq) for r in sample])
            unreadable = len(sample) - len(served)
            emb = "skipped (--no-embed)"
            if embed:
                probe = EmbedSidecar()
                emb = ("up" if probe.ensure(launch=False)
                       else "DOWN — vectors would be deferred to a rerun")
            report = {
                "run_id": run_id, "dry_run": True, "provider": provider,
                "selected": len(selected), "already_done": len(selected) - len(todo),
                "todo": len(todo), "todo_tokens": sum(r.tokens for r in todo),
                "batches": (len(todo) + batch_size - 1) // batch_size,
                "est_worst_case_usd": round(est, 2),
                "est_realistic_usd": round(realistic, 2),
                "usd_cap": usd_cap,
                "charter_root": charter_lock.get("root_fingerprint"),
                "text_index": reader.stats,
                "sampled_chunks_readable": f"{len(served)}/{len(sample)}",
                "embed_sidecar": emb,
            }
            say(f"\n== DRY RUN {run_id}: {len(todo)} chunks over "
                f"{report['batches']} batches | worst case ${est:.2f}, "
                f"realistic ~${realistic:.2f}, cap ${usd_cap:.2f}")
            say(f"   charter {report['charter_root']} verified | "
                f"tape readable {report['sampled_chunks_readable']} sampled | "
                f"embed sidecar {emb}")
            if unreadable:
                say(f"   WARNING {unreadable} sampled chunks are NOT readable "
                    f"from the tape — they would become typed quarantines")
            say("   nothing was spent; rerun without --dry-run to read")
            jline(event="dry_run", **report)
            return report

        shards = [json.loads(p.read_text("utf-8")) for p in
                  sorted((charter / "goldens" / "shards").glob("shard-*.json"))]
        baseline = ((charter_lock.get("scoring") or {}).get("runs", [None])[-1]
                    or _charter_baseline(charter))

        sidecar: EmbedSidecar | None = None
        if embed:
            sidecar = EmbedSidecar()
            if not sidecar.ensure(launch=True):
                say("  WARNING: embedding sidecar unavailable — cards proceed, "
                    "vectors deferred; backfill later with "
                    "`scriptorium.cmd vectors <archive>` (a plain rerun will "
                    "NOT do it: these chunks are already carded, so the resume "
                    "law skips them)")
                sidecar = None

        await client.warmup(system)

        async def extract(r: RecRow, texts: dict[tuple[str, int], str]
                          ) -> tuple[RecRow, CardV0 | None, dict | str]:
            meta = doc_meta.get(r.doc_id, {})
            header = (f"[doc {r.doc_id[:10]} | {meta.get('path', '?')} | "
                      f"year {r.year} | project {r.project} | seq {r.seq}]\n")
            try:
                card, m = await client.chat(
                    system=system, user=header + "CHUNK:\n" + texts[(r.doc_id, r.seq)],
                    tail=f"\n\n[{r.doc_id[:10]}:{r.seq}]", mode="extract",
                    max_tokens=out_tokens, unit_id=f"card-{r.doc_id[:10]}-{r.seq}",
                    out_model=CardV0)
                return r, card, m
            except UnitQuarantined as e:
                return r, None, e.reason + ": " + e.detail[:200]

        async def calibrate(round_n: int) -> float:
            if os.environ.get("SCRIPTORIUM_TEST_FORCE_DRIFT"):
                return 0.0
            subset = [shards[(round_n * CALIB_SHARDS + k) % len(shards)]
                      for k in range(min(CALIB_SHARDS, len(shards)))]

            async def one(spec):
                try:
                    card, _ = await client.chat(
                        system=system, user="CHUNK:\n" + spec["text"],
                        tail=f"\n\n[calib-{round_n}-{spec['id']}]", mode="extract",
                        max_tokens=out_tokens, unit_id=f"calib{round_n}-{spec['id']}",
                        out_model=CardV0)
                    return compare_cards(CardV0.model_validate(spec["reference"]),
                                         card)["score"]
                except UnitQuarantined:
                    return 0.0

            scores = await asyncio.gather(*(one(s) for s in subset))
            return sum(scores) / len(scores) if scores else 0.0

        batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
        for bi, batch in enumerate(batches):
            a2a.heartbeat(bridge)      # a multi-hour read must keep its lease
            if bi % calib_every == 0:
                mean = await calibrate(bi // calib_every)
                stats["calibrations"].append(round(mean, 4))
                jline(event="calibration", batch=bi, mean=round(mean, 4),
                      baseline=baseline, bar=DRIFT_FLOOR)
                say(f"  calibration @batch {bi}: mean {mean:.3f} "
                    f"(bar {DRIFT_FLOOR}, charter baseline {baseline})")
                a2a.note(bridge, f"calibration @batch {bi}: mean {mean:.3f} "
                                 f"bar {DRIFT_FLOOR}")
                if mean < DRIFT_FLOOR:
                    jline(event="halt", reason="calibration_drift", batch=bi,
                          mean=round(mean, 4))
                    a2a.note(bridge, f"OPERATOR ATTENTION calibration_halt: "
                                     f"mean {mean:.3f} < bar {DRIFT_FLOOR} at "
                                     f"batch {bi} — run {run_id} halted "
                                     f"checkpoint-clean")
                    raise SystemExit(
                        f"CALIBRATION DRIFT: mean {mean:.3f} < bar {DRIFT_FLOOR} "
                        f"at batch {bi} — pass halted checkpoint-clean "
                        f"(cards so far are fsync'd; diagnose before rerun)")

            # Multi-driver co-work (A2A item 2): claim each chunk before
            # spending on it; a refusal means a live co-driver owns it — skip
            # without writing anything (their card lands in the shared
            # catalog; the resume law keeps every key single-writer forever).
            work = batch
            if bridge is not None:
                wins = await asyncio.gather(*(
                    asyncio.to_thread(
                        a2a.try_claim, bridge,
                        f"scriptorium:{root.name}:p2:{r.doc_id}:{r.seq}")
                    for r in batch))
                work = [r for r, w in zip(batch, wins, strict=True) if w]
                if len(work) < len(batch):
                    skipped = len(batch) - len(work)
                    stats["skipped_leased"] += skipped
                    jline(event="leased_elsewhere", batch=bi, skipped=skipped)
                if not work:
                    continue

            # this batch's texts only; dropped when the batch ends. Read on
            # this thread: it happens between batches with nothing in flight,
            # and it keeps sqlite's thread-affinity guard meaningful.
            texts = reader.get_many([(r.doc_id, r.seq) for r in work])
            missing = [r for r in work if (r.doc_id, r.seq) not in texts]
            if missing:
                # the tape cannot serve these chunks: a typed quarantine, never
                # a crash and never a silent skip (no-silent-drops law)
                store.append_batch(store.quar_path, [
                    {"doc_id": r.doc_id, "seq": r.seq, "run_id": run_id,
                     "reason": "text_unavailable: chunk not readable from the "
                               "tape text index"} for r in missing])
                stats["quarantined"] += len(missing)
                jline(event="text_unavailable", batch=bi, n=len(missing))
                a2a.note(bridge, f"text_unavailable: {len(missing)} chunks in "
                                 f"batch {bi} could not be read from the tape")
                work = [r for r in work if (r.doc_id, r.seq) in texts]
                if not work:
                    continue

            results = await asyncio.gather(*(extract(r, texts) for r in work))
            card_rows, quar_rows = [], []
            for r, card, m in results:
                stats["calls"] += 1
                if card is None:
                    quar_rows.append({"doc_id": r.doc_id, "seq": r.seq,
                                      "reason": str(m), "run_id": run_id})
                    stats["quarantined"] += 1
                    a2a.note(bridge, f"quarantined {r.doc_id[:10]}:{r.seq} "
                                     f"{str(m)[:150]}")
                    continue
                usage = m["usage"]
                hit = usage.get("prompt_cache_hit_tokens", 0) or 0
                if hit >= 0.75 * prefix_tokens:
                    stats["prefix_hits"] += 1
                card_rows.append({
                    "doc_id": r.doc_id, "seq": r.seq, "run_id": run_id,
                    "card": card.model_dump(),
                    "fp": {"model": m["model"],
                           "rubric_v": charter_lock.get("rubric_v"),
                           "ontology_v": charter_lock.get("ontology_v"),
                           "charter_root": charter_lock.get("root_fingerprint")},
                    "usage": {"hit": hit,
                              "miss": usage.get("prompt_cache_miss_tokens", 0),
                              "out": usage.get("completion_tokens", 0)}})
                stats["cards"] += 1
            store.append_batch(store.cards_path, card_rows)
            store.append_batch(store.quar_path, quar_rows)

            for r, card, _m in results:
                if card is not None:
                    index.add_chunk(r, doc_meta.get(r.doc_id, {}),
                                    texts[(r.doc_id, r.seq)])
            if sidecar is not None:
                need = [r for r, c, _ in results
                        if c is not None and not index.has_vector((r.doc_id, r.seq))]
                for k in range(0, len(need), 16):
                    grp = need[k:k + 16]
                    try:
                        vecs = sidecar.embed([texts[(r.doc_id, r.seq)][:8000]
                                              for r in grp])
                        for r, v in zip(grp, vecs, strict=True):
                            index.add_vector((r.doc_id, r.seq), v,
                                             sidecar.fingerprint()["embedder"])
                            stats["vectors"] += 1
                    except Exception as e:  # noqa: BLE001 - vectors are backfillable
                        jline(event="embed_error", detail=str(e)[:200])
                        break
            index.db.commit()
            jline(event="batch_done", batch=bi, cards=stats["cards"],
                  quarantined=stats["quarantined"], usd=round(client.meter.usd(), 4))
            a2a.note(bridge, f"batch_done: {bi + 1}/{len(batches)} "
                             f"cards {stats['cards']} "
                             f"quar {stats['quarantined']} "
                             f"${client.meter.usd():.3f}")
            if (bi + 1) % 10 == 0 or bi == len(batches) - 1:
                say(f"  batch {bi + 1}/{len(batches)}: cards {stats['cards']} "
                    f"quar {stats['quarantined']} vec {stats['vectors']} "
                    f"${client.meter.usd():.2f} hit {client.meter.hit_rate():.0%}")

        prefix_eff = stats["prefix_hits"] / stats["calls"] if stats["calls"] else 0.0
        report = {
            "run_id": run_id, **{k: v for k, v in stats.items() if k != "prefix_hits"},
            "coverage_pct": round(100 * (len(selected) - len(todo) + stats["cards"]
                                         + stats["quarantined"]) / len(selected), 2)
            if selected else 100.0,
            "prefix_hit_efficiency": round(prefix_eff, 4),
            "total_hit_share": round(client.meter.hit_rate(), 4),
            "meter": client.meter.snapshot(),
            "index": index.counts(),
            "seconds": int(time.monotonic() - t0),
        }
        jline(event="run_end", **report)
        leased = (f", {stats['skipped_leased']} leased to a co-driver"
                  if stats["skipped_leased"] else "")
        say(f"\n== P2 read {run_id}: {stats['cards']} cards, "
            f"{stats['quarantined']} quarantined, {stats['vectors']} vectors"
            f"{leased} | "
            f"prefix-hit efficiency {prefix_eff:.0%} (vital >=60%) | "
            f"total hit share {client.meter.hit_rate():.0%} | "
            f"${client.meter.usd():.3f} in {report['seconds']}s")
        if provider == "api" and stats["calls"] > 20 and prefix_eff < 0.6:
            # the PS-4 cache-shaping vital is an API-lane law; harness usage is
            # ESTIMATED with hit=0 by construction (HM-5), so it cannot apply
            say("  WARNING (K-CACHE vital): prefix-hit efficiency < 60% — "
                "message shaping bug per PS-4; investigate before scaling up")
        if stats["cards"] and store.cards_path.exists():
            a2a.pin(bridge, store.cards_path,
                    f"cards.jsonl after {run_id}: +{stats['cards']} cards "
                    f"(attestation receipt)")
        return report
    except CapExceeded as e:
        jline(event="halt", reason="usd_cap", detail=str(e))
        a2a.note(bridge, f"halt usd_cap: {str(e)[:150]}")
        raise SystemExit(f"PS-8 halt: {e} — cards so far are fsync'd; "
                         f"rerun resumes where this stopped") from e
    finally:
        index.commit_close()
        if reader is not None:
            reader.close()
        await client.close()
        skipped = stats["skipped_leased"]
        a2a.end(bridge, f"cards {stats['cards']} quar {stats['quarantined']} "
                        f"${client.meter.usd():.3f}"
                        + (f" skipped_leased {skipped}" if skipped else ""))
