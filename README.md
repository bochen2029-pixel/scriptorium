# scriptorium — the organ that reads a lifetime

> **One sentence:** `scriptorium.cmd run <manifest>` walks a life's files through
> P0–P6 — intake → schema discovery → first reading → cartography → second
> reading to a fixed point → syntheses → fence — and leaves on disk the four
> deliverables the protocol names: the **Tape** (negatives), the **Cards+Map**
> (catalog), the **Atlas+Ledgers+Concordance** (codex), and the **QC
> Certificate** — rebuildable forever from Tape + frozen charter + model
> fingerprint.

**Honest status (2026-07-31): rung S0 — the Tape.** `plan`, `intake`, `status`
(and `resume`, the honest alias of `intake`) are real and falsifier-tested;
every other subcommand prints its rung and refuses. No API key is needed or
used at S0 — P0 is no-LLM by definition; OCR and ASR are local sidecars.
Spec: [`SCRIPTORIUM_ORGAN_SPEC_proposed_by_fable5_2026-07-31.md`](SCRIPTORIUM_ORGAN_SPEC_proposed_by_fable5_2026-07-31.md).
Live build state: [`_run_state/STATE.md`](_run_state/STATE.md).

## Quick start

```
:: 1. write a manifest at your archive root (see below), then:
scriptorium.cmd plan   D:\my-archive       :: preflight + census, writes nothing
scriptorium.cmd intake D:\my-archive       :: builds/extends the Tape under that root
scriptorium.cmd status D:\my-archive --verify
```

The archive root is the folder holding `manifest.yaml`. **The Tape lives with
the archive, never inside `C:\scriptorium`** — the negatives belong to the life
they came from. Killing an intake mid-run is safe: rerun (or `resume`) and it
continues with zero duplicate records and zero gaps (falsifier-tested).

A minimal `manifest.yaml` (operator-owned):

```yaml
archive: my-life
roots:
  - path: D:\exports\blog        # absolute, or relative to the archive root
    label: blog
  - path: notes
include: ["**"]                  # gitignore-flavored globs
exclude: ["**/*.tmp", "**/node_modules/**"]
sovereignty:
  pixels_leave_box: false        # constitutionally false; a true refuses to run
  audio_leaves_box: false
consent: "my own archive; self-consented"
```

## The family (organs are called at fixed paths as subprocesses, never imported)

| organ | finds / makes |
|---|---|
| `C:\everything` | files by **name/path/date/size** (discovery cross-check) |
| `C:\everywhere` | files by **raw content** (P6's verifier of last resort) |
| `C:\chunker` | **structure** — token-aware splits (census cross-check at S0) |
| `C:\earshot` | audio/video → **transcript** (the ASR slow lane) |
| `C:\imguard` | images → **vision-safe** (preflight before every OCR call) |
| **`C:\scriptorium`** | a corpus → **a catalog** (the organ that *reads*) |

Paths, script hashes, gguf fingerprints, the price sheet, the chunk budget, and
the CANON-JSON known-answer vectors are pinned in
[`scriptorium.lock`](scriptorium.lock). Sovereignty split, fixed: *pixels and
audio never leave the box; text rents the reading.* OCR is local
(llama-server `:8091`, Qwen3.5-9B + mmproj, frozen contract prompt in
[`prompts/ocr_contract_v0.txt`](prompts/ocr_contract_v0.txt)); ASR is local
(earshot/whisper.cpp); embeddings (`:8092`) are an S2 seam, stubbed.

## What intake leaves on disk (spec section 3)

```
<archive_root>\
  manifest.yaml                  # yours
  tape\segments\seg-000001.jsonl # append-only, blake2b-128 hash-chained records:
                                 #   doc | text | journal | contact
  tape\tape.lock                 # checkpoint (the segments are the truth)
  runs\<run_id>\journal.jsonl    # driver checkpoints
```

Every discovered file terminates as a `doc` record or a typed `journal` record
(`excluded` / `dedup` / `quarantined`) — nothing is silently dropped, and the
final reconciliation prints a measured completeness percentage. Near-duplicates
are *flagged and kept* (retellings are biography gold), never folded. The span
coordinate system every later pass cites: `{doc_id, seq, start, end}`,
character offsets into the NFC canonical `text` records.

## The ladder (spec section 7; one rung per session, falsifier-gated)

- **S0 · Tape** — *this build.* Falsifiers green: planted corpus with zero
  silent drops · one-byte corruption caught · kill-resume with zero dupes/gaps ·
  import-graph closed · CANON-JSON known-answer vectors.
- **S1 · Charter** — `discover` + operator-ratified `freeze`.
- **S2 · First reading** — `read` (cards, calibration, budget meter, cache law).
- **S3 · The circle** — `map` ⇄ `reread` to convergence.
- **S4 · Codex + certificate** — `synthesize` + `certify`; the certificate is
  the product.
- **S5 · LIVE annex** — journal-fed increments + the elicitation loop (gated).

## Development

```
uv sync --all-extras          :: pydantic v2 + httpx + PyMuPDF (+ tiktoken)
uv run pytest tests/ -q       :: green = the only definition of green
uv run ruff check .
```

Windows-native: Python ≥3.12 via uv, `.cmd` launcher, UTF-8 consoles, no WSL,
no Docker, no symlinks. Provider seam (`ds.py`, DeepSeek V4 Flash, laws
PS-1..PS-10) arrives at S1+ — S0 spends zero API dollars by construction.
