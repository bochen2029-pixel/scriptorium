"""scriptorium — the organ that reads a lifetime.

`scriptorium.cmd <subcommand> <archive-root-or-manifest>`; the archive root is
the folder holding manifest.yaml, and the Tape is written under it (never under
C:\\scriptorium — the negatives belong to the life they came from).

Real at S0: plan, intake, status (+ resume as the honest alias of intake, which
skips completed work by construction). Everything else prints its rung and
refuses — one rung per session, falsifier-gated (spec section 7).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


RUNG_STUBS = {
    "map": ("S3", "P3 cartography (registry, threads, eras, contradictions)"),
    "reread": ("S3", "P4 second reading (the hermeneutic fixed point)"),
    "synthesize": ("S4", "P5 codex (ledgers, dossiers, concordance, atlas)"),
    "certify": ("S4", "P6 fence + certificate (the product)"),
    "run": ("S4", "the full P0-P6 drive"),
    "ask": ("S4", "demo-grade cited retrieval over the finished catalog"),
}


def cmd_plan(target: str) -> int:
    import intake as ik
    import organs
    from local import OcrSidecar
    from manifest import load_manifest

    mf, root = load_manifest(target)
    print(f"archive root : {root}")
    print(f"archive      : {mf.archive or '(unnamed)'}")
    print(f"consent note : {mf.consent or '(none — manifest is operator-owned; add one)'}")

    print("\npreflight (organs at pinned paths):")
    lock = organs.load_lock()
    for name in ("everything", "chunker", "imguard", "earshot"):
        p = Path(lock["organs"][name]["path"])
        state = "ok" if p.exists() else "MISSING"
        if name == "earshot" and p.exists():
            state = "ok" if organs.earshot_available() else "present, deps MISSING"
        print(f"  {name:<11}: {state}  ({p})")
    side = OcrSidecar()
    if side.healthy():
        ocr_state = f"up at {side.url}"
    else:
        cfg = side.cfg
        launchable = all(Path(cfg[k]).exists() for k in ("exe", "model", "mmproj"))
        ocr_state = f"launchable on demand (:{cfg['port']})" if launchable \
            else "MISSING (llama-server or gguf not at pinned paths)"
    print(f"  ocr sidecar: {ocr_state}")
    print(f"  embeddings : stubbed until S2 (:{lock['sidecars']['embedding']['port']})")

    entries = ik.discover(mf, root)
    include, exclude = ik.GlobSet(mf.include), ik.GlobSet(mf.exclude)
    by_mod: dict[str, list[ik.FileEntry]] = {}
    n_excluded = 0
    for e in entries:
        if ik.is_archive_internal(e, root) or not include.match(e.rel) \
                or exclude.match(e.rel):
            n_excluded += 1
            continue
        ext = e.abspath.suffix.lower()
        mod = ("text" if ext in ik.TEXT_EXTS else
               "pdf" if ext == ".pdf" else
               "docx" if ext == ".docx" else
               "image" if ext in ik.IMAGE_EXTS else
               "av" if ext in ik.AV_EXTS else "unknown")
        by_mod.setdefault(mod, []).append(e)

    print(f"\ndiscovery: {len(entries)} files; {n_excluded} excluded by manifest/internal")
    total_mb = 0.0
    for mod in sorted(by_mod):
        files = by_mod[mod]
        mb = sum(max(f.size, 0) for f in files) / 1e6
        total_mb += mb
        extra = ""
        if mod == "text":
            extra = f"  (~{int(sum(max(f.size, 0) for f in files) / 4):,} tokens, rough pre-read)"
        if mod == "unknown":
            extra = "  (will sniff; failures quarantine typed)"
        print(f"  {mod:<7}: {len(files):>5} files  {mb:>9.2f} MB{extra}")
    print(f"  total  : {sum(len(v) for v in by_mod.values()):>5} files  {total_mb:>9.2f} MB")
    print("\nP0 is no-LLM by definition: $0 API. OCR/ASR are local sidecars only.")
    return 0


def cmd_intake(target: str, launch_ocr: bool, quiet: bool) -> int:
    from intake import run_intake
    report = run_intake(target, launch_ocr=launch_ocr, quiet=quiet)
    print(render_report(report))
    return 0 if report.completeness_pct >= 100.0 else 1


def render_report(report) -> str:
    out = [f"\n== intake {report.run_id} =="]
    c = report.counts
    out.append(f"admitted {c['done']} docs ({c['texts']} text records) | "
               f"skipped(done) {c['skipped']} | dedup {c['dedup']} | "
               f"excluded {c['excluded']} | quarantined {c['quarantined']} | "
               f"near-dup flags {c['near_dup_flags']} | {c.get('seconds', '?')}s")
    if report.quarantined:
        out.append("quarantined (typed, retried next run):")
        for path, reason in report.quarantined[:20]:
            out.append(f"  {reason:<22} {path}")
    r = report.reconciliation
    out.append(f"\nreconciliation: {r['classified']}/{r['total']} classified = "
               f"{report.completeness_pct}% complete "
               f"(doc {r['states']['doc']} / dedup {r['states']['dedup']} / "
               f"excluded {r['states']['excluded']} / quarantined {r['states']['quarantined']})")
    if r["unaccounted"]:
        out.append(f"  UNACCOUNTED ({len(r['unaccounted'])}): {r['unaccounted'][:10]}")
    if r["new_since_discovery"]:
        out.append(f"  new since discovery: {r['new_since_discovery'][:5]}")
    if r["vanished_during_run"]:
        out.append(f"  vanished during run: {r['vanished_during_run'][:5]}")
    for label, x in r["everything_crosscheck"].items():
        if isinstance(x, dict):
            mark = "agrees" if x["everything"] == x["walk"] else "DIFFERS (index lag?)"
            out.append(f"  everything x-check [{label}]: index {x['everything']} vs walk {x['walk']} — {mark}")
        else:
            out.append(f"  everything x-check [{label}]: {x}")

    out.append("\ncontact sheet (tokens x year x source x modality):")
    w_src = max(14, max((len(r["source"]) for r in report.contact_rows), default=0) + 2)
    out.append(f"  {'year':<6}{'source':<{w_src}}{'modality':<10}"
               f"{'files':>8}{'chars':>18}{'tokens':>16}")
    for row in report.contact_rows:
        y = row["year"] if row["year"] is not None else "*"
        out.append(f"  {y!s:<6}{row['source']:<{w_src}}{row['modality']:<10}"
                   f"{row['files']:>8}{row['chars']:>18,}{row['tokens_est']:>16,}")
    x = report.crosscheck
    if x.get("mean_ratio") is not None:
        out.append(f"  census x-check vs estimate_tokens.py on {len(x['samples'])} sample(s): "
                   f"mean ratio {x['mean_ratio']} (1.0 = perfect agreement)")
    elif x.get("samples"):
        out.append(f"  census x-check: no ratios ({x['samples'][0].get('error', 'n/a')})")
    return "\n".join(out)


def cmd_status(target: str, do_verify: bool) -> int:
    from manifest import find_manifest
    from tape import Tape

    root = find_manifest(target).parent
    t = Tape.open(root)
    try:
        by_kind: dict[str, int] = {}
        by_mod: dict[str, int] = {}
        last_recon = last_census_run = None
        census: list[dict] = []
        quarantines: dict[str, int] = {}
        for rec in t.iter_records():
            by_kind[rec["kind"]] = by_kind.get(rec["kind"], 0) + 1
            b = rec["body"]
            if rec["kind"] == "doc":
                by_mod[b["modality"]] = by_mod.get(b["modality"], 0) + 1
            elif rec["kind"] == "journal" and b.get("event") == "reconciliation":
                last_recon = b
            elif rec["kind"] == "journal" and b.get("event") == "quarantined":
                quarantines[b.get("reason", "?")] = quarantines.get(b.get("reason", "?"), 0) + 1
            elif rec["kind"] == "contact":
                if b["run_id"] != last_census_run:
                    last_census_run, census = b["run_id"], []
                census.append(b)
        print(f"archive root: {root}")
        print(f"tape: {t.count} records in {len(t.segments)} segment(s), head {t.head}")
        if t.repairs:
            print(f"boot repairs this open: {t.repairs}")
        print(f"records by kind: {by_kind or '(empty tape)'}")
        if by_mod:
            print(f"docs by modality: {by_mod}")
        if quarantines:
            print(f"quarantine history by reason: {quarantines}")
        if last_recon:
            print(f"last reconciliation ({last_recon.get('run_id')}): "
                  f"{last_recon['classified']}/{last_recon['total']} = "
                  f"{last_recon['completeness_pct']}% complete")
        if census:
            tot = census[-1]
            print(f"last census ({last_census_run}): {tot['files']} files, "
                  f"{tot['tokens_est']:,} tokens est.")
        if do_verify:
            rep = t.verify()
            print(rep.summary())
            return 0 if rep.ok else 1
        return 0
    finally:
        t.close()


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(
        prog="scriptorium",
        description="manifest in -> Tape + Catalog + Codex + Certificate out (S0: Tape)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, help_ in (("plan", "preflight + discovery census, no writes"),
                        ("intake", "P0: build/extend the Tape under the archive root"),
                        ("resume", "alias of intake (it skips completed work)"),
                        ("status", "tape state, last reconciliation + census"),
                        ("discover", "P1: sample the Tape, propose the charter + goldens"),
                        ("freeze", "verify the S1 falsifier, fingerprint the charter"),
                        ("read", "P2: the first reading — cards under the frozen charter"),
                        ("fence", "span fence over the catalog (deterministic, "
                                  "no LLM); --derive writes code-located spans")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("target", help="archive root dir or manifest path")
        if name == "intake" or name == "resume":
            p.add_argument("--no-launch-ocr", action="store_true",
                           help="attach-only: never launch llama-server")
            p.add_argument("--quiet", action="store_true")
        if name == "status":
            p.add_argument("--verify", action="store_true",
                           help="recompute the full hash chain")
        if name in ("discover", "read"):
            p.add_argument("--provider", choices=("api", "harness"),
                           default="api",
                           help="unit-call transport: DeepSeek API (default) or "
                                "DSH worker agents (optional harness mode)")
        if name == "discover":
            p.add_argument("--cap", type=float, default=5.0,
                           help="usd_cap for the pass (PS-8; default 5.00)")
            p.add_argument("--goldens", type=int, default=120)
            p.add_argument("--defects", type=int, default=12)
            p.add_argument("--sample-tokens", type=int, default=None)
            p.add_argument("--seed", type=int, default=20260731)
            p.add_argument("--rescore-only", action="store_true",
                           help="re-run goldens QC against the existing charter")
        if name == "read":
            p.add_argument("--cap", type=float, default=10.0,
                           help="usd_cap for the pass (PS-8; default 10.00)")
            p.add_argument("--projects", type=str, default=None,
                           help="comma-separated project globs (slice selector)")
            p.add_argument("--max-tokens", type=int, default=None,
                           help="hard token ceiling for the slice")
            p.add_argument("--no-embed", action="store_true",
                           help="skip the :8092 embedding sidecar (backfill later)")
            p.add_argument("--concurrency", type=int, default=None,
                           help="parallel unit calls (default: 48 for api; 6 "
                                "for harness — each harness slot is a full "
                                "runtime subprocess, HM-7)")
            p.add_argument("--retry-quarantined", action="store_true",
                           help="quarantined keys become todo again (cards "
                                "win over quarantine history on retry)")
            p.add_argument("--max-out-tokens", type=int, default=None,
                           help="per-card output budget (default 6000; raise "
                                "for dense chunks that quarantined)")
        if name == "fence":
            p.add_argument("--derive", action="store_true",
                           help="also write catalog/cards/spans.jsonl — "
                                "code-derived spans for every LOCATED quote "
                                "(model offsets are never trusted)")

    for name in RUNG_STUBS:
        sub.add_parser(name, help=f"[{RUNG_STUBS[name][0]}] {RUNG_STUBS[name][1]}")

    args = ap.parse_args(argv)
    if args.cmd == "plan":
        return cmd_plan(args.target)
    if args.cmd in ("intake", "resume"):
        if args.cmd == "resume":
            print("resume = intake at S0: completed files are skipped by construction")
        return cmd_intake(args.target, launch_ocr=not args.no_launch_ocr, quiet=args.quiet)
    if args.cmd == "status":
        return cmd_status(args.target, do_verify=args.verify)
    if args.cmd == "discover":
        import asyncio

        from discover import run_discover
        asyncio.run(run_discover(
            args.target, usd_cap=args.cap, sample_tokens=args.sample_tokens,
            goldens_n=args.goldens, defects_n=args.defects, seed=args.seed,
            rescore_only=args.rescore_only, provider=args.provider))
        return 0
    if args.cmd == "freeze":
        from discover import run_freeze
        run_freeze(args.target)
        return 0
    if args.cmd == "read":
        import asyncio

        from read import OUT_TOKENS, run_read
        asyncio.run(run_read(
            args.target, usd_cap=args.cap,
            projects=args.projects.split(",") if args.projects else None,
            max_tokens=args.max_tokens, provider=args.provider,
            embed=not args.no_embed, concurrency=args.concurrency,
            retry_quarantined=args.retry_quarantined,
            out_tokens=args.max_out_tokens or OUT_TOKENS))
        return 0
    if args.cmd == "fence":
        import json as _json

        from manifest import load_manifest
        from spancheck import derive_spans, fence_check
        _mf, root = load_manifest(args.target)
        rep = fence_check(root)
        if args.derive:
            rep["derived"] = derive_spans(root)
        print(_json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    rung, what = RUNG_STUBS[args.cmd]
    print(f"`{args.cmd}` is rung {rung} ({what}).\n"
          f"This build is rung S0 (the Tape). One rung per session, "
          f"falsifier-gated — see README and spec section 7.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
