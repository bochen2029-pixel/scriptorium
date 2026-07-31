# scriptorium — run state

**Rung: S0 (the Tape) — GREEN, 2026-07-31.** Next session starts S1 (charter:
`discover` → operator `freeze`) unless RATIFIED.md says otherwise. Trust this
file + git over any memory. 54 pytest green + ruff clean = the definition of
green used throughout; every falsifier below was run for real, none simulated.

## Green (S0 definition of done, kickoff section 3)

1. **Scaffold** — `scriptorium.py` (dispatch: plan/intake/status/resume real,
   rest print their rung and refuse), `scriptorium.cmd` (NOTE: must stay CRLF —
   LF-only endings break cmd.exe parsing; caught live), `pyproject.toml` (uv,
   py>=3.12; deps pydantic v2 + httpx + PyMuPDF + optional tiktoken; dev
   pytest+ruff), `scriptorium.lock` (organ paths + script hashes, gguf
   blake2b-256 for Qwen3.5-9B/mmproj/embedder, Flash price sheet pinned
   2026-07-31, chunk budget 8000 [2000,32000], CANON-JSON known-answer vectors,
   OCR prompt hash), `.env.example`, `.gitignore`, `README.md` v0, git repo
   (commits at each green milestone).
2. **tape.py** — append-only JSONL segments (64 MiB roll), blake2b-128 chain
   over CANON-JSON (`canon.py`: UTF-8, NFC, sorted keys, CPython
   shortest-roundtrip float repr; NFC-collision + non-string-key + NaN
   refusals), kinds doc|text|journal|contact, fsync'd batched appends,
   `verify_tape()`, boot-time torn-tail repair (<=1 line, journaled as
   `tape_repair`), crash roll-forward (fsync'd-but-unacknowledged lines are
   adopted at open), corruption inside the acknowledged region refuses repair.
3. **intake (P0)** — manifest.yaml via an in-house YAML-subset parser
   (stdlib; PyYAML is off the S0 dependency list; manifest.json also accepted);
   discovery = os.walk ground truth, `everything` runs as reconciliation
   cross-check (fresh files can lag its index ~1s, so walk is primary — spec's
   "everything where indexed" honored as the verifier role); gitignore-flavored
   include/exclude globs; exact dedup (blake2b-256) + MinHash near-dup
   flag-and-keep (128 perms, threshold 0.6, signature stored on the doc
   record); routing text/pdf/docx/image/av + strict text-sniff for unknown
   extensions; PDF text-layer first, low-density+image pages rendered 150 dpi
   -> imguard -> local OCR, interleaved by page; span system {doc_id, seq,
   start, end} = char offsets into NFC canonical text records (blocks <=32k
   chars, deterministic split, property-tested lossless).
4. **local.py** — attach-or-launch llama-server :8091 (`-ngl 99`), health
   poll, frozen OCR contract prompt (prompts/ocr_contract_v0.txt, hash in
   lock), R-class fingerprint (gguf+mmproj+prompt hashes) stamped on every OCR
   block; JSON-shape failure degrades to raw text + typed note, never a guess;
   :8092 embedding seam present and gated (`RungGate: S2`).
5. **Reconciliation + contact sheet** — completeness measured by fresh
   re-walk and printed + taped; census rows tokens x year x source x modality
   as `contact` records; cross-check vs `estimate_tokens.py` on a sample.
6. **Falsifiers, all green:**
   (a) planted corpus (text/md, exact dup, near dup, text-PDF, scanned-image
       PDF, hand-built docx, PNG, .tmp excluded, binary blob, real TTS speech
       + silence wavs, real TTS video in the demo) — zero silently dropped;
       every path ends doc/dedup/excluded/quarantined; 100.0% measured.
   (b) one flipped byte in a copied tape -> `verify_tape` catches (and full
       verify catches older-segment corruption boot-scan skips).
   (c) kill-resume — real subprocess, hard kill mid-run, rerun: zero duplicate
       records, zero gaps (doc unique, seqs contiguous), plus a deterministic
       partial-doc continuation unit (texts fsync'd, doc record lost).
   (d) import-graph — allowlist-closed (stdlib + pydantic/httpx/fitz/tiktoken/
       pytest + own modules); organ names forbidden as imports; no sys.path
       hacks.
   (e) CANON-JSON known-answer vectors pinned in scriptorium.lock.

## The S0 live demo (run 20260731T172934Z-47f809, pasted verbatim)

No operator-named real collection existed when this session started, so per
kickoff the demo ran on the planted corpus + a real Windows-TTS speech video
(`_testdata\demo-s0`, 11 files, 7 modalities), through `scriptorium.cmd`, with
the REAL sidecars: llama-server+Qwen3.5-9B OCR on :8091 (launched by the seam,
18 s to healthy) and earshot/whisper.cpp ASR. $0 API, as required.

```
== intake 20260731T172934Z-47f809 ==
admitted 8 docs (8 text records) | skipped(done) 0 | dedup 1 | excluded 1 | quarantined 1 | near-dup flags 1 | 108.2s
quarantined (typed, retried next run):
  unsupported_modality   junk/blob.bin

reconciliation: 11/11 classified = 100.0% complete (doc 8 / dedup 1 / excluded 1 / quarantined 1)
  everything x-check [mixed]: index 11 vs walk 11 — agrees

contact sheet (tokens x year x source x modality):
  year  source        modality    files       chars    tokens
  2019  mixed         text            1       3,675       844
  2020  mixed         pdf             1          80        19
  2020  mixed         text            1       2,539       572
  2021  mixed         docx            1          99        21
  2021  mixed         image           1          35         8
  2021  mixed         pdf             1          46        12
  2021  mixed         text            1       4,265       984
  2026  mixed         av              1         110        24
  *     *             *               8      10,849     2,484
  census x-check vs estimate_tokens.py on 3 sample(s): mean ratio 1.0 (1.0 = perfect agreement)
```

`status --verify`: `tape OK: 33 records, 1 segments, head a546a4a8f431182f639950cdb4bbf4b4`.
Sovereign-floor spot checks (from the tape, real model output):

```
[ocr] 'SCANNED PAGE: words that exist only as pixels.'        conf 0.99, fp Qwen3.5-9B-Q5_K_M.gguf 7553c9770716
[ocr] 'PNG NOTE: pixels-only caption text.'                   conf 0.99, fp Qwen3.5-9B-Q5_K_M.gguf 7553c9770716
[transcript] 'Hello from the scriptorium demo. The tape keeps every word, and the fence will certify what the readers claim.'
```

Both OCR transcriptions are verbatim-exact against the planted pixels; the
transcript is word-perfect.

**NEEDS-OPERATOR: name a small real mixed folder for an S0 live run** (the
demo above used the planted corpus per kickoff; point me at a real folder and
`scriptorium.cmd intake <root>` is the whole ceremony — S1's `discover` also
wants your archive as corpus #1).

## Deviations from spec/kickoff (recorded, operator to bless or reverse)

- **docx via stdlib zip+xml**, not "through chunker's extractors": the chunker
  has no clean full-text CLI mode — its chunk output carries section/recap
  headers that would pollute canonical text. Same text-first philosophy, zero
  new deps. (intake.py module docstring documents it too.)
- **Discovery is walk-primary; `everything` is the cross-check** (kickoff
  phrased it the other way around). Reason: Everything's index lags fresh
  files ~1s, which would make discovery of just-written archives racy; the
  walk is the ground truth of now, the index confirms it (it printed
  "agrees" in the demo). Big-archive fast-path via everything is parked below.
- **whisper hallucination on digital silence** ("You", exit 0) is taped
  faithfully as the organ's output; the exit-4 no-speech path is covered by a
  deterministic unit instead. Honesty note, not a bug.

## Parked (wishes, not blockers)

- PyYAML (full YAML manifests) — subset parser refuses anchors/multiline with
  clear errors; park until an operator manifest actually needs them.
- Walk `on_error` journaling: unreadable *directories* are currently a silent
  blind spot on both discovery and reconciliation sides (consistent, but
  blind). Wants a typed `walk_error` journal record.
- Aggregated exclusion journaling for huge exclude sets (per-file records
  would bloat the tape at millions of files).
- `everything` as discovery fast path for 2 TB archives (with walk verify).
- OCR latency: ~97 s first call, ~45-50 s warm per image on this box —
  llama-server tuning (batch, kv, mmproj offload) is S1+ work; contract and
  provenance are correct today.
- Near-dup flagging is O(n^2) over signatures (fine at S0 scale); LSH banding
  when a real corpus makes it hurt.
- Resumed (crash-interrupted) docs get no MinHash signature (prefix isn't
  re-read); flagged in doc.notes as "resumed".

## BLOCKED

(nothing)

## Next session's first move

Read this file, then spec section 4 P1 + section 7 S1. Build `discover`:
stratified sample over the Tape (the demo tape or the operator's corpus #1),
Flash-thinking `high` through a new `ds.py` (laws PS-1..PS-10; meter + usd_cap
BEFORE the first paid call, PS-8), emit charter/ontology.yaml + rubric_P2.md +
compression prior + golden shards (>=10 planted defects) + 3 golden syntheses;
`freeze` = operator ratifies -> fingerprints into scriptorium.lock. Falsifier:
golden shards score below bar on re-run = the rubric isn't frozen-stable.
DEEPSEEK_API_KEY goes in .env (never committed). The OCR sidecar may still be
up on :8091 from this session (attach case will find it); a stray python from
2026-07-27 (PID 104380) predates this project and was left alone.
