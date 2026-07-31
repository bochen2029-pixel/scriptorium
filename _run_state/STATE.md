# scriptorium — run state

**Rungs S0 (Tape) and S1 (Charter) — GREEN, 2026-07-31, one session.** Next
session starts **S2 (first reading: `read`)**. Trust this file + git over any
memory; RATIFIED.md holds the operator's standing delegation and decisions of
record. 75 pytest green + ruff clean = the definition of green throughout;
every number below is from a real run, none simulated.

## S0 — the Tape (green; see git history for the falsifier detail)

Delivered: `canon.py` (CANON-JSON-v1 + blake2b-128 chain, KAVs pinned in
scriptorium.lock) · `tape.py` (append-only segments, fsync'd batches, torn-tail
repair <=1 line journaled, crash roll-forward, full verify; Windows
lock-replace race found BY the kill-resume falsifier and fixed with bounded
retry) · `intake.py` (P0: walk discovery + `everything` cross-check, exact
dedup + strided-MinHash near-dup flag-and-keep (top-5/doc, batched), modality
routing text/pdf/docx/image/av, cost-lane ordering, span system {doc_id, seq,
start, end}) · `local.py` (:8091 attach-or-launch Qwen3.5-9B+mmproj OCR,
frozen contract prompt, R-class fingerprints; :8092 gated until S2) ·
`scriptorium.py` CLI + `scriptorium.cmd` (CRLF!) · falsifiers (a)-(e) green
incl. real TTS speech/video through real earshot.

**S0 at real scale — corpus #1 = C:\_DAD\projects-mirror (RATIFIED item 3),
intake run 20260731T175629Z-48884d, verbatim:**

```
admitted 9743 docs (166742 text records) | skipped(done) 0 | dedup 4213 | excluded 0 | quarantined 2 | near-dup flags 7777 | 6004.3s
reconciliation: 13958/13958 classified = 100.0% complete (doc 9743 / dedup 4213 / excluded 0 / quarantined 2)
  everything x-check [claude-projects]: index 14026 vs walk 13958 — DIFFERS (index lag?)
census: 9,743 files, 4,356,509,907 chars, 1,753,033,797 tokens (text 1.750B + pdf 2.6M)
census x-check vs estimate_tokens.py on 10 samples: mean ratio 0.9999
status --verify: tape OK: 188484 records, 65 segments, head fec1ef561b8ebdaa8606d537133c2d78
```

1.75B tokens — past the spec's "verbose lifetime" scale point. Quarantines: 2
webfetch .bin files, typed. The everything x-check delta (+68) is informational
(index-side extras); walk is ground truth. **Known census caveat:** the mirror
copy reset all mtimes to 2026 -> the year axis is degenerate; stratification
falls back to per-project (107 cells), which is the meaningful axis for this
corpus. Content-time chronology is a P3-era concern (or re-intake from the
original dirs someday — new docs, append-only, dedup folds the rest).

## S1 — the Charter (green)

Delivered: `ds.py` — the ONE provider seam, PS-1..PS-10 all implemented and
stub-tested (retry ladder -> thinking rescue -> typed quarantine; AIMD gate
halve/+64-per-min; hard usd_cap at start AND mid-flight; model-fp change halt;
cache-aware meter; .env loader; **adaptive max_tokens escalation** when
reasoning exhausts the output budget — found by live-run 1, see below) ·
`discover.py` + `cards.py` + 5 frozen P1 prompts (hashes pinned in
scriptorium.lock) · `freeze` gated on the S1 falsifier.

**Live run 1 (p1-20260731T193852Z): failed honestly, $1.64.** 104/152
induction batches returned empty content — thinking-high consumed the whole
max_tokens=8000 as reasoning, and the same-call retry ladder repeated the
doomed call. Fix: think-call headroom (24K-49K) + the adaptive ladder (empty
content + completion_tokens ~ max_tokens -> triple the budget before retrying;
tested). Merge/rubric quarantines now exit clean instead of tracebacking.

**Live run 2 (p1-20260731T193852Z fix, run id in charter.yaml): GREEN,
verbatim:**

```
166742 text records, 1,753,033,797 tokens census
sampled 1120 records, 6,351,194 tokens across 107 cells (budget 6,000,000)
PS-8 gate: estimate $1.39 under cap $5.00 — proceeding
induction: 152 batches, thinking effort=high ... 144/152 usable
merged ontology: 45 projects, 22 themes, 14 genres
goldens: 118 shards written, 12 defective; hit-rate 90%
golden syntheses: 3/3 written
scoring: run1 0.671  run2 0.681  bar 0.55 -> STABLE (falsifier passed)
== P1 discover done in 1621s — $0.913 spent, hit-rate 91%
charter FROZEN: 125 artifacts fingerprinted, root 209ed2439de94905ebe99f7da60b2ffd
```

The charter (C:\_DAD\projects-mirror-archive\charter\) is genuinely grounded:
ontology names the operator, Access Intellect LLC, the organ family, the
doctrine lines; the compression prior names whose voices count and lets tool
chatter fall. Ratification = RATIFIED.md item 1 (operator delegation);
**operator edits + re-freeze remain invited** — discover refuses to overwrite a
frozen charter (version law), `--rescore-only` re-runs QC anytime.

Session spend total: **$2.55** (run1 $1.64 + run2 $0.91 + smoke $0.0001)
against the operator's "too cheap to meter" posture and a $5/pass cap.

## Deviations (all blessed via RATIFIED.md item 2, or recorded here)

- docx via stdlib zip+xml (chunker has no clean full-text CLI mode).
- Discovery walk-primary; `everything` as reconciliation cross-check.
- whisper silence hallucination ("You") taped faithfully as organ output;
  exit-4 no-speech covered by deterministic unit.
- P1 sampling unit = tape text record (<=32k chars ~ chunk budget); the chunker
  organ enters at P2/S2 as spec'd.
- Model fingerprint from the API is the alias "deepseek-v4-flash" (not a dated
  version string); PS-9 still functions as change detection.

## Parked (wishes, not blockers)

- **Baidu Unlimited-OCR (hf.co/baidu/Unlimited-OCR) as the S2+ OCR engine
  candidate** (operator surfaced 2026-07-31): DeepEncoder + 3B-MoE-A570M +
  R-SWA, dedicated long-horizon document OCR; likely 10-50x our current
  45-100s/image llama.cpp path. No llama.cpp support -> own venv + torch +
  ~50-line OpenAI-compatible shim behind the existing local.py seam (it is
  engine-agnostic by design; a swap = new extractor fingerprint = rescan the
  negatives, spec section 5). Verify before adopting: license,
  trust_remote_code surface, Windows-torch cleanliness, VRAM, output contract
  (their fixed format -> our {text, regions, confidence_hint} envelope in the
  shim). Adoption falsifier: both engines over the same golden scanned pages,
  verbatim fidelity + wall-clock, winner takes the fingerprint.
- Read-only Tape.open mode (no boot repair/lock write) so `status`/`discover`
  can safely run DURING an intake; today: don't open a tape a writer holds.
- Session-jsonl content extractor (messages' text out of the envelope) as a
  future intake modality refinement — would shrink this corpus ~3-5x and clean
  the register; a re-derive under version law, not a mid-corpus mutation.
- Walk on_error journaling (unreadable dirs are a consistent blind spot);
  aggregated exclusion journaling; LSH banding for near-dup at larger scale;
  tape kind-index sidecar to avoid full scans in scan_tape/fetch_texts (two
  ~4.3GB passes per discover today, ~2-4 min each); OCR latency tuning;
  PyYAML full-syntax manifests.
- 8/152 induction batches + 2/120 shards quarantined typed in live run 2 —
  acceptable; worth a glance at ds_calls.jsonl before S2 to see if they share
  a shape (they carry full reasoning_content in the run journal).

## BLOCKED

(nothing)

## Next session's first move

Read this file, RATIFIED.md, spec section 4 P2 + section 7 S2. Build `read`
(P2 first reading): chunker-organ chunking at budget 8000 (breadcrumbs ->
card context headers), the frozen charter as the byte-identical system prefix
(PS-4; expect >=60% hit rate — run 2 measured 91% on the goldens fan-out),
non-thinking t=0 JSON cards via ds.py, calibration shards interleaved every
N=50 batches with halt-on-drift, resume via run journal, budget estimate from
the census (1.75B tokens -> roughly $250-300 in at miss rates; the cache +
the 4213-dedup fold and near-dup structure will pull it down; operator cap
decision per pass), local embeddings via the :8092 sidecar (un-gate
EmbedSidecar; qwen3-embedding-0.6b pinned in the lock), SQLite FTS5+vector
index under catalog\. Falsifiers (spec S2): kill mid-pass -> resume zero
dupes/gaps; hit-rate < 60% = prompt-shape bug; deliberately drill one
calibration-drift halt. The OCR sidecar may still be running on :8091;
harmless. DEEPSEEK_API_KEY is in .env; the scriptorium_cc key is repo-scoped
and the operator deactivates it when the build-out ends.
