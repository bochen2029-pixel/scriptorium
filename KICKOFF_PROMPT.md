# SCRIPTORIUM · implementation kickoff (reusable — every session starts here)

You are the implementing session for `C:\scriptorium` — the sixth organ of the fixed-path family. **The design is finished; your job is code, not re-design.** The spec was authored 2026-07-31 and stands ratified by the operator launching this prompt (any amendments appear in `_run_state\RATIFIED.md`; absent that file, the spec as written is law).

## 0 · Find your rung

Read `_run_state\STATE.md` if it exists — it names the current rung, what is green, and what is parked; trust it + git over any memory. If it does not exist, this is **session 1 → rung S0 (the Tape)**. Work exactly one rung per session unless STATE.md says the current rung is green.

## 1 · Orientation (read in this order, nothing else — ~20K tokens total)

1. `C:\scriptorium\SCRIPTORIUM_ORGAN_SPEC_proposed_by_fable5_2026-07-31.md` — **the authoritative spec** (~6K tok). §1 PS-laws, §3 Tape, §4 passes, §7 ladder, §8 refusals.
2. `C:\cortex\SCRIPTORIUM_PROTOCOL_proposed_by_fable5_2026-07-31.md` — the protocol it implements (~4.2K tok).
3. `C:\cortex\CORTEX_V2_ARCHITECTURE_proposed_by_fable5_2026-07-31.md` — read §2 (hierarchy/Tape invariants) and the fence law; skim the rest (~4.7K tok).
4. READMEs only (not source): `C:\chunker\README.md` · `C:\everything\README.md` · `C:\everywhere\README.md` · `C:\earshot\README.md` · `C:\imguard\README.md` (skip any that don't exist).

**Do NOT load:** `C:\hypercell*`, `C:\KEEL`, the BRAIN blueprint, `C:\cortex\cognee-main`, anything DRDJ. They are out of the critical path by spec §0/§8; reading them is context spent on refusals.
**If any file exceeds a clean read:** size it with `python C:\chunker\estimate_tokens.py "FILE"`, chunk with `python C:\chunker\chunker.py`, read chunks in order.

## 2 · Standing rules (constitutional — violating any one is a failed session)

- **The spec is law.** PS-1..PS-10, the Tape format, the sovereignty split (pixels/audio never leave the box), and §8 refusals are not yours to amend. If implementation reveals a *genuine* contradiction, STOP, write it to `_run_state\STATE.md` under `## BLOCKED`, choose nothing, and end with the question surfaced.
- **Organs are subprocesses at fixed paths** (pinned in `scriptorium.lock`) — never imported. Zero imports from KEEL/hypercell/cortex code; write the import-graph test that enforces this before writing anything it could catch.
- **Windows-native:** Python ≥3.12 via `uv`; `.cmd` launchers; Task Scheduler not cron; every console stream `reconfigure(encoding="utf-8", errors="replace")`; paths with drive letters; no symlinks, no WSL, no Docker.
- **Dependencies for S0:** stdlib + `pydantic` v2 + `httpx` + `PyMuPDF` + optional `tiktoken`. Anything else: park the wish in STATE.md; do not install.
- **Test-first, falsifier-gated:** every falsifier named in spec §7 for your rung is a `pytest` *before* it is a feature. `pytest` + `ruff` green = the only definition of green. Commit to git at every green milestone with a one-line receipt (`git init` on first session; commits end with the standard co-author line).
- **Tape placement:** the Tape lives under the *archive root* being ingested, never inside `C:\scriptorium`. Test archive roots live in `C:\scriptorium\_testdata\` (gitignored).
- **$0 API this session if your rung is S0** — P0 is no-LLM by definition; the sidecars are local. If you find yourself wanting a DeepSeek call at S0, you have left the rung. (S1+ sessions: `.env` holds `DEEPSEEK_API_KEY`; the meter and `usd_cap` come up *before* the first paid call, per PS-8.)

## 3 · Rung S0 — definition of done (expand later rungs from spec §7)

Deliverables, all demonstrated live, none simulated:

1. **Repo scaffold:** `scriptorium.py` (single entry, subcommand dispatch: `plan · intake · status` real; the rest stubs that print their rung), `scriptorium.cmd`, `pyproject.toml` (uv), `scriptorium.lock` (organ paths + versions, gguf hashes, price sheet, chunk budget), `.env.example`, `.gitignore` (`_testdata/`, `.env`, `__pycache__`), `README.md` v0 (README-as-contract: quick start, the one-sentence, the family table, honest status line), `_run_state\STATE.md`.
2. **`tape.py`:** append-only JSONL segments; blake2b-128 hash chain over CANON-JSON (UTF-8, NFC, sorted keys, fixed float repr — pin known-answer vectors in `scriptorium.lock`); record kinds `doc | text | journal | contact`; fsync'd appends; `verify_tape()`; boot-time torn-tail repair (truncate ≤1 line, journal the repair).
3. **`intake` (P0):** manifest.yaml parsing (roots, include/exclude globs, sovereignty flags, consent note) → discovery (via `C:\everything\search.py --in ROOT` when the root is indexed; `os.walk` fallback) → content-hash dedup (exact) + MinHash near-dup *flagging* (stdlib implementation, flag-and-keep, never fold) → modality routing: text/md/docx/pdf-with-text-layer through chunker's extractors; low-text-density PDF pages rendered to PNG (PyMuPDF) → `C:\imguard` → local OCR; images → imguard → OCR; AV → `C:\earshot` (queue + resume; it's the slow lane) → canonical `text` records with the span coordinate system `{doc_id, seq, start, end}`.
4. **`local.py` sidecar seam:** attach-or-launch `llama-server` on **:8091** with `-m C:\models\Qwen3.5-9B-Q5_K_M.gguf --mmproj C:\models\mmproj-F16.gguf`; health check; the frozen OCR contract prompt (verbatim, layout-marked, `⟨?…⟩` uncertainty, JSON out); R-class provenance + extractor fingerprint on every OCR block. (Embedding server :8092 is S2 — stub the seam, don't wire it.)
5. **Reconciliation + contact sheet:** end of intake diffs manifest-discovered files vs Tape `doc` records → completeness % printed and taped (measured, never assumed); contact sheet = tokens × year × source × modality, cross-checked against `python C:\chunker\estimate_tokens.py` on a sample.
6. **Falsifier tests green:** (a) planted corpus — build a deterministic fixture tree (text + a PDF with text layer + a scanned-image PDF page + a PNG + one short video if earshot is available; generate what you can, note what you can't) and assert *zero silently dropped files* — every discovered path ends as `doc`, `journal:dedup`, `journal:excluded`, or `journal:quarantined`; (b) chain integrity — corrupt one byte in a copy, `verify_tape()` catches; (c) **kill-resume** — kill the intake mid-run (subprocess test), rerun, assert zero duplicate records and zero gaps; (d) import-graph test; (e) CANON-JSON known-answer vectors.
7. **The live demo, run and reported honestly:** intake the operator's real test collection — `_run_state\STATE.md` names it if the operator has; otherwise use the planted corpus and write `NEEDS-OPERATOR: name a small real mixed folder for the S0 live run` in STATE.md — and paste the reconciliation + contact-sheet output into STATE.md verbatim.

## 4 · Working style

- Keep `_run_state\STATE.md` current as you go: rung, green list, parked list, BLOCKED list, next session's first move. It is the next session's boot sector — write it for a stranger.
- Prefer boring code in the house voice: small modules, typed pydantic models, no cleverness the spec didn't ask for. Match the chunker's register, not a framework's.
- Report outcomes faithfully: failing test output goes in STATE.md as-is; nothing is "done" that wasn't run.
- End-of-session: all tests green for the rung (or BLOCKED honestly), git committed, STATE.md updated, and a closing summary of exactly what a reviewer should spot-check.

**Begin now:** print your S0 checklist (or your rung's, per STATE.md), then build.
