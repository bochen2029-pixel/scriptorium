# scriptorium — the organ that reads a lifetime

> **One sentence:** `scriptorium.cmd run <manifest>` walks a life's files through
> P0–P6 — intake → schema discovery → first reading → cartography → second
> reading to a fixed point → syntheses → fence — and leaves on disk the four
> deliverables the protocol names: the **Tape** (negatives), the **Cards+Map**
> (catalog), the **Atlas+Ledgers+Concordance** (codex), and the **QC
> Certificate** — rebuildable forever from Tape + frozen charter + model
> fingerprint.

## Why this exists, and why now

A verbose lifetime is 10⁸–10⁹ tokens: years of session logs, letters, journals,
transcripts, documents. At ~15k tokens/hour of human reading, one billion
tokens is **~33 person-years to read once** — no notes, no index, no second
pass. So nobody reads it. Archives rot as bytes that no one can ask anything.

**DeepSeek V4 Flash (released 2026-07-31) changed the arithmetic.** An
Artificial Analysis Intelligence Index score of ~50 — frontier-adjacent
reading comprehension — priced at **$0.14 per million input tokens**
($0.0028/M on cache hits, $0.28/M out), with a 1M context window and 2,500
concurrent requests. At that price, *reading a billion tokens three times*
(first reading, then re-reading twice with global context) is a
few-hundred-dollar line item, and this repo's measured runs put a full first
reading of an extracted archive at **roughly $100 per billion raw tokens** and
a weekend of wall-clock. The scriptorium tradition — read, annotate, index,
concord, cross-reference, peer-review — becomes an algorithm you can afford to
run on your own life.

What makes this more than "summarize my files":

- **The Tape** — every source normalized to canonical text in an append-only,
  blake2b-hash-chained store. The negatives are forever; catalogs are prints;
  better models rescan.
- **A bespoke ontology per corpus** — the schema is *induced from your archive*
  and frozen under an explicit, operator-ratified editorial charter, not
  imposed from a taxonomy.
- **Stateless workers, measured consistency** — one frozen model + one frozen
  rubric = a million identical librarians, calibrated against golden shards
  with planted defects so the QC can actually fail.
- **The fence** — every quote and claim is span-checked against the Tape by
  deterministic code, never by a model. In this repo's first live run the
  fence caught **28.5% of model "quotes" as paraphrase-as-quote** — measured,
  quarantined, and structurally unable to ship as verbatim. That refusal *is*
  the product working.
- **Sovereignty split** — pixels and audio never leave the box (local
  Qwen3.5-9B OCR, local whisper.cpp ASR, local embeddings); only canonical
  *text* rents the reading.

**Ideally used for:** personal lifetime archives (the operator's own corpus #1
is 1.75B tokens of coding-session history), family papers and correspondence,
research-group memory, small-org institutional knowledge — anything where the
corpus outgrew every context window and every human reader, but still deserves
a catalog with receipts.

**Honest status (2026-07-31): rung S0 green; rung S1 in flight.** `plan`,
`intake`, `status`, `resume` (S0) and `discover`, `freeze` (S1) are real and
tested; `read`/`map`/`reread`/`synthesize`/`certify`/`run`/`ask` print their
rung and refuse. P0 uses no API; P1+ go through the one provider seam
([ds.py](ds.py), laws PS-1..PS-10, DeepSeek V4 Flash) with a hard `usd_cap`
per pass. `DEEPSEEK_API_KEY` lives in `.env` (gitignored).
Spec: [`SCRIPTORIUM_ORGAN_SPEC_proposed_by_fable5_2026-07-31.md`](SCRIPTORIUM_ORGAN_SPEC_proposed_by_fable5_2026-07-31.md).
Live build state: [`_run_state/STATE.md`](_run_state/STATE.md).

## Quick start

```
:: 1. write a manifest at your archive root (see below), then:
scriptorium.cmd plan     D:\my-archive     :: preflight + census, writes nothing
scriptorium.cmd intake   D:\my-archive     :: builds/extends the Tape under that root
scriptorium.cmd status   D:\my-archive --verify
scriptorium.cmd discover D:\my-archive     :: P1: propose charter + goldens (API, capped)
scriptorium.cmd freeze   D:\my-archive     :: verify the S1 falsifier, fingerprint charter
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

- **S0 · Tape** — green. Falsifiers: planted corpus with zero silent drops ·
  one-byte corruption caught · kill-resume with zero dupes/gaps · import-graph
  closed · CANON-JSON known-answer vectors.
- **S1 · Charter** — `discover` (stratified sample → ontology + rubric + prior
  + golden shards with planted defects + 3 golden syntheses, double-scored for
  stability) + `freeze` (refuses unless the falsifier passed; fingerprints
  everything). Ratification currently by operator delegation
  (_run_state/RATIFIED.md).
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

## License

MIT — see [LICENSE](LICENSE). The organ family this plugs into
(`everything` / `everywhere` / `chunker` / `earshot` / `imguard`) are separate
fixed-path tools on the author's machine; this repo is self-contained code +
frozen prompts and degrades honestly (typed quarantines, never silent drops)
when an organ is absent.
