# scriptorium — run state

**S0 GREEN · S1 GREEN · S2 code green + validated on TWO tapes. 2026-07-31→08-01.**
Trust this file + git over any memory; RATIFIED.md holds the operator's standing
delegation. 84 pytest + ruff clean; all numbers from real runs. Published public
MIT at github.com/bochen2029-pixel/scriptorium.

## TL;DR for the next session

Corpus #1 exists as TWO tapes (spec section 5 version law — both valid, both
verifiable, negatives forever):
- **v1** `C:\_DAD\projects-mirror-archive` — raw envelopes, 1.753B tokens,
  charter frozen (root 209ed243), FERRYMAN slice read (2,683 cards).
- **v2** `C:\_DAD\projects-mirror-archive-v2` — session-extracted (voices only),
  **172M tokens (10.2x smaller)**, charter frozen (root a7d94b8e, scored
  0.710/0.718 — BETTER than v1), OUTREACH slice read (56 cards, fence 87.2%
  verified vs v1's 71.5%). **v2 is the production tape.**

**The one open action = operator top-up.** Full v2 read projects to ~$32 at
$0.184/M; DeepSeek balance is ~$6.8. Then, one command:
`scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap 35`
(resumable, calibration-gated, kill-safe). That produces the full Cards + index
for corpus #1 and completes the S2 ship-gate's "two real collections" on the
clean tape.

## v2 pipeline results (2026-08-01) — the compression paid off twice

| metric | v1 (raw) | v2 (extracted) |
|---|---|---|
| tokens | 1,753,033,797 | 172,063,716 (**10.2x**) |
| reconciliation | 100.0% | 100.0% (13958/13958) |
| charter scoring | 0.671/0.681 | **0.710/0.718** |
| ontology | 45 proj/22 theme | 40 proj/14 theme (tighter; real PEOPLE surfaced) |
| read fence-verified | 71.5% | **87.2%** |
| fabrication (unlocated) | 28.5% | **12.8%** |
| full-read cost | ~$315 | **~$32** |

Extraction keeps Bo's instructions + assistant text; drops thinking/tool_use/
tool_result (so v2 lacks the raw code/command-outputs — those live in v1 only;
RATIFIED item 6). It didn't just cut cost — cleaner input measurably improved
catalog fidelity (fence, scoring, ontology all better). v2 intake 4 quarantines
(2 .bin + 2 ocr_failed PDFs), 3h13m (OCR slow lane on ~130 PDFs dominated).

Session spend to date: ~$10.5 (S1 $1.64+$0.91, FERRYMAN $6.63, v2 discover
$1.22, OUTREACH $0.09, smokes). Balance ~$6.8.

## Rung scoreboard

- **S0 · Tape — GREEN at 1.75B-token scale.** Real intake of corpus #1
  (C:\_DAD\projects-mirror -> archive root C:\_DAD\projects-mirror-archive):
  13,958/13,958 classified = 100.0%; 9,743 docs / 166,742 text records /
  4,213 dedup folds / 7,777 near-dup flags / 2 typed quarantines; census
  1,753,033,797 tokens, x-check ratio 0.9999; `status --verify`: tape OK,
  188,484 records, 65 segments, head fec1ef561b8ebdaa8606d537133c2d78.
  All five S0 falsifiers green (incl. real TTS video through real earshot;
  kill-resume found + fixed a real Windows lock-replace race).
- **S1 · Charter — GREEN, FROZEN.** discover run 2 on the real tape: 1,120
  records / 6.35M tokens sampled across 107 project cells; 144/152 induction
  batches; ontology 45 projects / 22 themes / 14 genres; 118 golden shards
  (12 planted defects); 3 golden syntheses; scoring 0.671 / 0.681 -> STABLE;
  charter FROZEN, 125 artifacts, root 209ed2439de94905ebe99f7da60b2ffd.
  $0.913, 27 min. (Run 1 failed honestly for $1.64 — reasoning exhausted
  max_tokens -> empty content; fixed with the adaptive ladder in ds.py.)
- **S2 · First reading — code green; live slice green; RUNG GATE PARTIAL.**

## S2 detail (the live section)

`read.py` (P2): frozen-charter fingerprint verify before the first call
(tamper -> refuse); system prefix = rubric_P2.md + p1_refcard_v0 byte-identical
(the exact golden-authoring pair); non-thinking t=0 JSON -> CardV0; cards
append-only fsync'd in catalog/cards/cards.jsonl, typed quarantines beside it;
resume = skip present keys (unit-tested: zero dupes zero gaps, incl. truncated
file); calibration every 50 batches on rotating 8-shard golden subsets with
halt-below-bar (drilled TWICE: unit test + live on the real archive — mean
0.000 -> checkpoint-clean halt, zero cards, halt journaled); EmbedSidecar
:8092 wired (attach-or-launch, qwen3-embedding pinned); catalog/index.sqlite =
chunks + FTS5 + float32 vectors.

**Live slice run p2-20260731T221032Z (project C--FERRYMAN, 36.1M tokens,
2,705 chunks, cap $8), verbatim:**

```
calibration @batch 0: mean 0.702 (bar 0.55)
calibration @batch 50: mean 0.571 (bar 0.55)
batch 57/57: cards 2683 quar 22 vec 2683 $6.63 hit 16%
== P2 read p2-20260731T221032Z: 2683 cards, 22 quarantined, 2683 vectors |
   prefix-hit efficiency 99% (vital >=60%) | total hit share 16% | $6.634 in 5315s
```

2,683 + 22 = 2,705 — every selected chunk terminal. Spot-check: cards carry
{model, rubric_v r1, charter_root 209ed243} fingerprints; claims are typed
(subject/predicate/object/polarity/confidence); topics use the charter's own
theme vocabulary; FTS queries answer; vectors 1:1 with cards.

**K-CACHE vital, interpreted and recorded (not gamed):** DeepSeek reports
cache hit/miss in tokens, so total hit share on unique ~13K-token chunks is
arithmetically capped near prefix/(prefix+chunk) ~ 11-16%. The spec's ">=60%
or build bug" is measured as PREFIX-HIT EFFICIENCY (calls whose hits cover
>=75% of the frozen ~1,555-token prefix): **99%** — the shaping law works.
Both numbers are always reported. Operator may want to reconcile spec section
1 PS-4's wording with section 6's "~30-40% hit share" economics note.

**Span fence-check (S2 gate item 1) — BUILT AND RUN LIVE (spancheck.py):**
FERRYMAN's 2,683 cards, 12,167 quotes: verified 71.5% (substring 2,070 +
no-offset-hit 6,577 + whitespace-normalized 54), **unlocated 28.5%** (3,466
paraphrase-as-quote — fluent fiction MEASURED and caught), **exact-offset 0%**
(model-emitted character offsets are 100% unusable; claim spans 15,201/21,234
out of bounds). Constitutional consequences, recorded: (a) span coordinates
must be DERIVED (locate quote in chunk deterministically), never trusted from
the model — P6/S4 implements; the P5 two-register renderer only ever renders
fence-LOCATED spans, so unlocated quotes cannot ship as verbatim (the design
already contains the mitigation); (b) the next rubric version should harden
the copy-exact demand on quotes.

**TAPE GENERATION v2 (RATIFIED item 6) — approved and IN FLIGHT:** session-
jsonl extractor built + tested (voices kept: USER/ASSISTANT text + summaries;
thinking/tool_use/tool_result dropped; true content years from timestamps fix
the mtime-degenerate census; manifest opt-in `options.sessions: extract`;
default raw = v1 behavior byte-identical). New archive root
C:\_DAD\projects-mirror-archive-v2; v1 stays intact forever. Rationale: full
read ~$70-110 instead of ~$315 (measured slice intensity $0.184/M x remaining
1.717B raw = ~$316 — the earlier $240-280 estimate underweighted output and
was corrected to the operator).

**Remaining sequence (exact commands, resume-safe at every step):**
1. v2 intake completing in background (log: scratchpad intake_v2.log).
2. `scriptorium.cmd discover C:\_DAD\projects-mirror-archive-v2 --cap 5`
   then `freeze` (v2 charter; the v1 charter stays bound to v1). ~$1.
3. Optional validation slice within remaining balance:
   `scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --projects
   C--FERRYMAN --cap 5`.
4. **Operator top-up**, then the full read:
   `scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap <N>`
   (estimate ~$70-110 on the compressed tape; PS-8 refuses/halts on cap;
   kill-safe; consider the calibration-subset fix in Observations first).
5. Second collection end-to-end (S2 gate item 2) — any small folder.

Session spend so far: **$9.19** (S1 $1.64 + $0.91, P2 slice $6.63, smokes).
DeepSeek balance ~ $8.1.

## Observations for the next session

- Calibration variance: 8-shard rotating subsets swing hard (0.702 vs 0.571,
  full-set mean 0.676). For the full read: larger or fixed calibration subset
  (16-24 shards), and consider a variance-aware band rather than a hard floor.
- Batches 30-40 ran ~5 min each (retry-heavy chunks; 22 quarantines total are
  json-hostile transcript chunks — the run journal ds_calls.jsonl has full
  reasoning_content for diagnosis). Consider: per-call max_tokens bump for
  P2 (some chunks likely exhausted 6000 with dense cards), and a
  --retry-quarantined flag.
- charter baseline shows "None" in calibration lines (scoring lives in
  charter.yaml, not charter.lock) — cosmetic, fix when touching read.py.
- Embedding truncation: vectors embed chunk[:8000] chars (sidecar ctx
  safety) — document/decide before the resident-skeleton stage cares.
- Parked from earlier (still live): Baidu Unlimited-OCR S2+ eval plan ·
  read-only Tape.open · session-jsonl content extractor (would cut this
  corpus ~3-5x for a v2 catalog) · walk on_error journaling · LSH banding ·
  tape kind-index sidecar (scan_tape does 2 full 4.3GB passes per pass-run) ·
  OCR latency tuning · PyYAML.
- OCR sidecar (:8091) and embed sidecar (:8092) may still be resident;
  attach case finds them, or kill to free ~8GB VRAM.

## BLOCKED

- Full-corpus P2: operator top-up (see above). Nothing else.

## Next session's first move

Read this file + RATIFIED.md. If the operator topped up: launch the full v2
read (command in TL;DR above; consider the calibration-subset fix first — 8
rotating shards swing 0.57-0.72, want 16-24 or fixed). It's background,
capped, resumable, kill-safe. When it finishes: run spancheck.py for the
whole-catalog fence rate, then S3 (`map` + `reread` to convergence), then S4
(`synthesize` + `certify` — the certificate is the product).

Span fence-check (spancheck.py) is BUILT and is the S2 gate's fence item;
whole-corpus rate prints after the full read. Exact-offset is 0% on both tapes
(model char-offsets are useless) — S4's certify must DERIVE spans by locating
quotes, never trust model offsets; the P5 renderer only ships fence-located
spans, so the 12-28% unlocated can't surface as verbatim.

DEEPSEEK_API_KEY in .env; scriptorium_cc key is repo-scoped; operator
deactivates it when the build-out ends. Keep the GitHub repo current
(`git push`) at green milestones.
