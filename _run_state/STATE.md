# scriptorium — run state

**S0 GREEN · S1 GREEN · S2 code green + live slice green (gate partially met —
see below). 2026-07-31, one session.** Trust this file + git over any memory;
RATIFIED.md holds the operator's standing delegation. 80 pytest + ruff clean =
green throughout; all numbers below are from real runs.

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

**S2 gate remaining (spec: "cards + fence-checked spans on two real
collections"):**
1. Span fence-check utility over cards (quote offsets vs tape text) — the
   P6-style verification the gate pulls forward. Not yet built.
2. A second collection end-to-end (candidate: any small folder -> intake ->
   discover -> freeze -> read; operator granted "anywhere on C:\" latitude).
3. Full-corpus read of corpus #1: ~1.717B tokens remaining ~ $240-280 + a
   long weekend of wall-clock at current pacing. **Blocked on operator:
   DeepSeek balance is ~$8.1 after this session ($17.31 - $9.19 session
   spend). Top up, then `scriptorium.cmd read C:\_DAD\projects-mirror-archive
   --cap <N>` — resume picks up exactly where the slice stopped.**

Session spend total: **$9.19** (S1 run1 $1.64 + S1 run2 $0.91 + P2 slice
$6.63 + smokes <$0.01).

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

Read this file + RATIFIED.md. Then either (a) operator topped up -> launch the
full read (background, capped, resumable; consider calibration-subset fix
first), or (b) close the S2 gate cheaply: build the span fence-check utility
(cards' quote offsets vs tape text — deterministic, no LLM) and run the second
collection end-to-end on a small real folder. Then S3 (`map` + `reread`).
DEEPSEEK_API_KEY in .env; scriptorium_cc key is repo-scoped; operator
deactivates it when the build-out ends.
