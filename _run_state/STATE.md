# scriptorium — run state

**S0 GREEN · S1 GREEN · S2 code green, live on THREE catalogs · DUAL MODE
(api + harness) BUILT and QUALIFIED — the api lane is the production reader;
the harness lane's worker model failed the bar honestly. S2 ship-gate item 2
(a second real collection) DONE. 2026-07-31→09-01.** Trust this file + git
over any memory; RATIFIED.md holds the operator's standing delegation (items
7-9 added 2026-09-01; **item 9 changes an S1 falsifier and is flagged for
your review**). 151 pytest + ruff clean; all numbers from real runs.
Published public MIT at github.com/bochen2029-pixel/scriptorium.

**The one thing between here and the product: ~$25 more of DeepSeek balance.**
Everything else is built, tested, measured, and pushed. See BLOCKED.

## BLOCKED

- **Full-corpus P2 (api lane): operator top-up of about $25.** Realistic cost
  ~$37 (~$39 with retries), worst case $51 — measured, not guessed (the old
  ~$32 came from a 3x-low output estimate). Balance measured $15.15 on
  2026-09-01, so ~40% of the corpus is readable today if the operator
  prefers partial-now (the read is resumable, so a partial run is not
  wasted). This is the ONLY path to the full catalog
  now: the harness lane's worker model failed qualification (round-9 verdict
  — 0.26-0.37 vs the charter, 0.497 self-agreement, bar 0.55; zero cards
  shipped, $0 spent). The Modal 429 window from earlier resolved on its own
  and is NOT the blocker; the model's reproducibility is.
- Nothing else. Every other thread this session reached a recorded end.

## TL;DR for the next session

Corpus #1 exists as TWO tapes (spec section 5 version law — both valid, both
verifiable, negatives forever):
- **v1** `C:\_DAD\projects-mirror-archive` — raw envelopes, 1.753B tokens,
  charter frozen (root 209ed243), FERRYMAN slice read (2,683 cards).
- **v2** `C:\_DAD\projects-mirror-archive-v2` — session-extracted (voices only),
  **172M tokens (10.2x smaller)**, charter frozen (root a7d94b8e, scored
  0.710/0.718 — BETTER than v1), OUTREACH slice read (56 cards, fence 87.2%
  verified vs v1's 71.5%). **v2 is the production tape.**

**Two lanes exist. The qualification question is ANSWERED (2026-09-01):**
- **api lane — QUALIFIED, and the only production reader today.** Needs the
  operator top-up. **Corrected projection (2026-09-01, from measured card
  calls rather than the old guess): realistic ~$37, ~$39 with retries; worst
  case $51 if nothing caches.** The earlier ~$32 came from an estimator that
  assumed 900 output tokens/card when the real mean is 2,578 (v2) / 1,801
  (repo) — see "the cost model was wrong" below. Balance MEASURED $15.15, so
  a full read needs roughly **$25 more**; run it with a generous cap:
  `scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap 55`
  (PS-8 gates on the worst case, so a $40 cap would refuse a $37 run).
- **harness lane — the LANE is proven; the WORKER MODEL is not.** Four live
  calibration runs on corpus #1's frozen charter scored 0.262-0.370 (bar
  0.55); GLM-5.3-Flash's agreement with ITSELF on the same shards is 0.497 vs
  DeepSeek's 0.714, so even a GLM-authored charter would sit under the bar
  (claims F1 0.167 is the specific deficiency). Every run halted
  checkpoint-clean with zero cards written — the gate working, at $0 cash.
  Full evidence table: HARNESS_MODE_DESIGN.md "Round-9 VERDICT". The lane is
  one env var (`SCRIPTORIUM_HARNESS_MODEL`) from being useful the day a
  stronger worker model is wired to DSH.

## v2 pipeline results (2026-08-01) — the compression paid off twice

| metric | v1 (raw) | v2 (extracted) |
|---|---|---|
| tokens | 1,753,033,797 | 172,063,716 (**10.2x**) |
| reconciliation | 100.0% | 100.0% (13958/13958) |
| charter scoring | 0.671/0.681 | **0.710/0.718** |
| ontology | 45 proj/22 theme | 40 proj/14 theme (tighter; real PEOPLE surfaced) |
| read fence-verified | 71.5% | **87.2%** |
| fabrication (unlocated) | 28.5% | **12.8%** |
| full-read cost | ~$315 | **~$37 realistic / $51 worst case** (corrected 2026-09-01 from measured usage; was ~$32) |

Extraction keeps Bo's instructions + assistant text; drops thinking/tool_use/
tool_result (so v2 lacks the raw code/command-outputs — those live in v1 only;
RATIFIED item 6). It didn't just cut cost — cleaner input measurably improved
catalog fidelity (fence, scoring, ontology all better). v2 intake 4 quarantines
(2 .bin + 2 ocr_failed PDFs), 3h13m (OCR slow lane on ~130 PDFs dominated).

Spend to date: ~$10.7 through 2026-08-01 (S1 $1.64+$0.91, FERRYMAN $6.63, v2
discover $1.22, OUTREACH $0.09, smokes) + **$0.19 on 2026-09-01** (collection
#2 end-to-end $0.17, a one-card re-read $0.014). Balance MEASURED $15.15 at
2026-09-01T09:40Z — the operator topped up since the previous session's
"~$6.8". Harness-lane work cost $0 cash (Modal quota only).

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
- **S2 · First reading — code green; live on three catalogs; GATE ITEM 2
  (two real collections) DONE.** Fence-checked spans: DONE (and now derived,
  not just measured). Remaining for the full S2 claim: the whole-corpus read
  of corpus #1 (blocked on the top-up).

## S2 detail (the live section)

`read.py` (P2): frozen-charter fingerprint verify before the first call
(tamper -> refuse); system prefix = rubric_P2.md + p1_refcard_v0 byte-identical
(the exact golden-authoring pair); non-thinking t=0 JSON -> CardV0; cards
append-only fsync'd in catalog/cards/cards.jsonl, typed quarantines beside it;
resume = skip present keys (unit-tested: zero dupes zero gaps, incl. truncated
file); calibration every 50 batches on rotating 16-shard golden subsets with
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

## Collection #2 — DONE end-to-end (S2 ship-gate item 2), 2026-09-01

`C:\_DAD\scriptorium-repo-archive` — **the published scriptorium repo reading
itself** (local-only material excluded: survey docs, `_local`, `_testdata`,
secrets, the amanuensis subprojects). Every rung on the api lane, one sitting,
**$0.17 total**:

| stage | result |
|---|---|
| intake | 56 docs / 57 text records / 110,869 tokens; 59,470 excluded; 0 quarantined; reconciliation 99.99% (5 files appeared mid-run: 4 git objects + a script I wrote) |
| discover | 42 golden shards (11 defective), scoring **0.704 / 0.705**, gap 0.0009 vs tolerance 0.05, paired n=41 SE=0.0208 \|t\|=0.04 → STABLE; $0.103 |
| freeze | 49 artifacts fingerprinted, charter root **cddeb55f09ab8380376e1e7bf1aeced5** |
| read | **56 cards, 1 quarantined**, 56 vectors, calibration 0.676 (bar 0.55, baseline 0.705), prefix-hit efficiency 98%, total hit share 63%, $0.068 in 271s |
| fence | 191 quotes, **verified 87.43%**, unlocated 12.57%, exact-from-model 0.52%; derived spans located **167/191 = 87.43%** (96 find + 71 whitespace) |

Two independent corpora now agree closely on the fence (87.19% on v2-OUTREACH,
87.43% here) — that ~87% verified / ~13% paraphrase-as-quote looks like a
property of the model + rubric, not of one archive. The first two discover
attempts here were REFUSED by the S1 falsifier (see RATIFIED 9); the third
passed on its own merits under the corrected rule.

Worth noting: the induced ontology of this repo's own source came back as
"span-verified truth / verbatim fidelity", "determinism / frozen
reproducibility", "falsifier-gated rungs", "measured, never assumed", "the
negatives are forever" — the organ read its own constitution off its own code.
It also shows exactly why S3 exists: `Tape` (9) and `the Tape` (8) are
separate entities, `scriptorium` (15) and `SCRIPTORIUM` (5) likewise — alias
fragmentation is P3's registry problem, visible here in miniature.

Inspect it with: `scriptorium.cmd query C:\_DAD\scriptorium-repo-archive`
(summary) or `... query <root> "fence AND spans"` (hits with verbatim).

## Session log 2026-09-01 (Claude Code) — what changed, in one place

Suite went 113 → **133 pytest + ruff clean**; every item below is committed and
pushed (survey docs stay local per RATIFIED 7).

**Dual mode finished and then honestly qualified** (rounds 5-9, full evidence
in HARNESS_MODE_DESIGN.md): all four designed A2A increments built (per-chunk
leases, batch findings, artifact-pin attestation, persona patch); three real
defects found by running it (silently-dropped `system` role on the modal path,
process-fresh session ids colliding with the persistent session store,
composed-prompt pollution); then the verdict — the LANE works, GLM-5.3-Flash
as the worker model does not meet the charter's bar.

**Fence became a producer, not just a meter.** `spancheck.locate` /
`derive_spans` write `catalog/cards/spans.jsonl` — code-derived spans for
every LOCATED quote, so the model's 0%-usable offsets are fully replaced and
an unlocated quote structurally cannot render as verbatim. Measured on the v2
catalog: **245/281 = 87.19% located**, exactly matching the fence's verified
rate. New `scriptorium.cmd fence <root> [--derive]` subcommand. Also fixed two
real fence defects: a card whose chunk isn't in this Tape was scoring as
fabrication (now `cards_unfetchable`, excluded from rates), and correct
offsets with a padded quote were downgraded from exact.

**S1 stability falsifier fixed** (RATIFIED 9, flagged for review): it compared
an absolute gap to 0.05 while sampling error shrinks as 1/sqrt(n), so it was
silently a corpus-SIZE test that refused small archives for noise. Now
`max(0.05, 2 x paired SE)`; both frozen charters keep their verdicts, a
genuinely unstable run (|t|=2.25) is still refused.

**The catalog became inspectable.** New `query` module + subcommand (no LLM,
no API): `query <root>` prints a catalog summary (counts, quotes/claims per
card, project/year/topic/entity distributions, quarantine reasons, and loud
warnings if one catalog mixes reader models or charter roots); `query <root>
"<fts5>"` searches the indexed chunks and shows hits in TWO REGISTERS —
VERBATIM (only quotes whose spans code could derive from the Tape) and
READING (the model's claims/topics/entities, labelled as such). An unlocated
quote is withheld and counted, never rendered as verbatim, so the window
cannot launder a fabrication. Terminal control bytes from archived console
captures are neutered before display.

**The full-corpus read is now memory-safe** (`textindex.py`, the parked "tape
kind-index sidecar"). `read.py` used to load EVERY selected chunk's text into
RAM before the first card — fine for a slice, ~1GB of Python strings held for
hours on the 172M-token corpus, plus a full tape pass before any card is
written. Now: one pass records each text record's byte offset into a derived
sqlite beside the tape, and each batch seeks for exactly the chunks it needs.
Derived + regenerable (segments stay the truth), append-aware (an extended
tape indexes only new records), and honest (an unservable key returns None; a
stale offset pointing at the wrong record is REFUSED, never guessed; chunks
the tape cannot serve become typed quarantines, never a crash or a silent
skip). Measured on the real 583MB v2 tape: **index builds in 3.2s** (27,448
records, 3.1MB file), and fetching a catalog's texts goes **2.1s → under 1ms,
byte-identical** to the old path. Validated end-to-end on collection #2:
resume finds zero work; a forced re-read produced a same-shape card under the
same charter root with zero dupes/gaps and the fence unchanged at 87.43%.

**The cost model was wrong, and it is the number the top-up decision rests
on.** `read.py` estimated 900 output tokens per card; measured across every
real card call it is **2,578 (v2 tape) / 1,801 (repo corpus)** — roughly 3x
under. That optimism had been quietly cancelling the input side's pessimism
(the gate bills every input token as a cache miss), so the headline came out
plausible for the wrong reasons. Now both sides are honest and BOTH are
printed: PS-8 still gates on the worst case, and the realistic figure at the
measured 46% prefix-cache rate is shown beside it so a cap can be set from
evidence. Full v2 read: **worst case $51, realistic ~$37 (~$39 with
retries)** — up from the recorded ~$32. Measured per-card reality also
confirms the parked observation that some cards exhaust the 6,000-token
budget (p90 = 6,000 on both corpora), which is what `--max-out-tokens` +
`--retry-quarantined` are for.

**Two latent defects in the api seam (`ds.py`), both fail-proven against the
old code:** a transport-error retry slept INSIDE the AIMD gate (a network
wobble would park every concurrency slot on sleeping calls), and a first
response missing `model` pinned the PS-9 fingerprint to `""` so the next
honest answer raised ModelChanged and halted a paid pass. Both matter for the
long full-corpus read.

**`scriptorium.lock` charters roster:** the single `charter` block was
last-writer-wins across archives; collection #2's freeze would have
overwritten corpus #1's record. Now one row per archive (v1/v2 migrated from
their own charter.locks, which remain the truth).

**A false claim in the code, fixed.** `read.py` told the operator that a
sidecar-down run's vectors were "deferred to a rerun" — but a rerun skips
already-carded keys by the resume law, so those chunks could never gain
vectors by any existing path. The message now says what actually happens and
`scriptorium.cmd vectors <archive>` is the real path (local :8092 only, no
API, idempotent, reports tape-unreadable chunks instead of skipping them).
The test proves the gap was real: after clearing vectors a full rerun leaves
zero, and only the backfill restores them.

**`read --dry-run`** preflights an expensive run — charter verified, slice
selected, budget gated (worst case AND realistic), tape proven readable by
sampling real chunks, embed sidecar probed — with zero model calls and zero
cards written.

**Smaller things:** `--retry-quarantined` + `--max-out-tokens` (the parked
observations), `--concurrency`, charter baseline printed from charter.yaml,
CALIB_SHARDS 8→16, provider failure messages surfaced into the journal
(`finish_failure`) with ladder backoff, honest driver identity on the bus,
README brought to 2026-09-01 with a dual-mode section, `_local/README.md`
documenting the working directory (incl. the DSH session store as a forensic
asset — two of this session's findings came from reading it).

## Dual mode round 5-6 (2026-09-01, Claude Code session) — A2A v2 built; persona hardened by live failure

All prior harness work committed + pushed (71ea18f); this session's increments
(full detail + evidence: HARNESS_MODE_DESIGN.md "Round-5"):

- **Per-chunk leases** (`a2a.try_claim`, `scriptorium:<archive>:p2:<doc>:<seq>`):
  two drivers co-work one catalog, refusal skips without writing, never
  released (cards are terminal; TTL 900s is the janitor). Multi-driver
  partition + A2A-off resume proven in tests (11 cards + 1 leased-away → 12
  unique, zero dupes/gaps).
- **Batch findings + halts on the bus**; **artifact-pin attestation** (ONE pin
  of cards.jsonl at run end, blake2b receipt — card-grain attestation
  evaluated and REJECTED as driver-posted chatter; verdict in design doc).
- **Persona patch (HM-2 v2)**: the frozen prefix is now the workers' REAL
  system role via a generated Cordis patch. FIRST live run scored calibration
  **0.000 → halt law fired perfectly** (checkpoint-clean, zero cards, pennies).
  Session-store forensics: persona applied byte-complete BUT other plugins
  appended ~4.2K chars of tool/subagent guidance after it; a low-effort worker
  declared "no schema given" and pydantic's fully-defaulted CardV0 accepted
  its invented JSON as empty cards. Fix (probed to ZERO foreign chars on the
  real Cordis loader): persona ends with an explicit END-OF-BINDING-CONTRACT
  boundary + every `tool-*` row unmounted (the `tools` SERVICE stays —
  agent-loop requires it; disabling it refuses boot, probed). Kill switch:
  `SCRIPTORIUM_HARNESS_INTASK=1`.
- **Resilience**: runtime failure messages (e.g. the Modal 429) now surface in
  ds_calls.jsonl as `finish_failure` and in quarantine details; HM-3 ladder
  backs off 5s/15s between attempts. `--concurrency` CLI flag (harness default
  6 — each slot is a full runtime subprocess). CALIB_SHARDS 8→16 (the
  variance observation; band idea rejected — the bar stays a hard law).
  Charter baseline now prints from charter.yaml (was "None" cosmetic).
- **Driver identity honest** (RATIFIED 8): bus joins say claude-code or dsh.
- Live during the failed slice: run_start/calibration/OPERATOR-ATTENTION-halt
  findings + lease + release all verified on the real bus.
- **FERRYMAN v2 slice (143 chunks, 649,442 tok — 55x smaller than v1's
  36.1M)**: LAUNCH BLOCKED by the Modal plan window mid-session
  (`429 Plan credits cannot be applied to shared endpoint usage`) after
  attempt 1's calibration got real GLM answers. `_local/ferryman_watcher.sh`
  auto-retries every 20 min (16 attempts ≈ 5.3h), retrying ONLY on the
  rate-window signature; stops on drift/cap/unexpected. Its log:
  `_local/ferryman_v2_harness_watch.log`; est. cost per attempt ~3 warmup
  calls; slice estimate $0.16 under cap $2.

## Harness mode (2026-09-01) — provider="harness" LANDED (transport + tests)

Optional second provider seam beside ds.py: `discover/read --provider harness`
routes every unit call through DSH worker agents (the operator's session model,
GLM-5.3-Flash via Modal) instead of raw DeepSeek API calls; the DeepSeek Harness
Python SDK drives one runtime subprocess per concurrency slot (isolated
`_local/dsh-home`, never ~/.dsh). Default path byte-identical and SDK-free
(deepseek_harness lazy-imports only inside harness._default_factory; pyproject
extra `harness`). Design + laws HM-1..HM-10:
`_run_state/HARNESS_MODE_DESIGN.md`. 102 pytest + ruff clean (15 new
tests/test_harness.py against a fake runtime factory: bundle shape, ladder +
fresh-session-per-attempt, typed quarantine, estimated-meter cap gates, slot
exclusivity, fatal-vs-soft boot errors; api path re-verified end-to-end through
the new `make_client` factory). Import-graph + ruff now skip the untracked
`amanuensis/` + `amanuensis-native/` subprojects (their 4 stray test files +
wakeword.py were tripping the repo-wide laws — pre-existing red, not harness
work). ROUND 2 (2026-09-01): the Intercom A2A layer landed (`a2a.py`, opt-in
`SCRIPTORIUM_A2A=1` — pass lease refuses double-drivers before any spend,
run_start/run_end + per-quarantine findings, soft-degrades when the bus is
down; 10 tests, 113 total green). The REAL runtime smoke PASSED to the provider
boundary: SDK installed editable from the DSH checkout (PyPI note, re-measured
2026-09-01: `deepseek-harness-sdk 0.1.1rc1` now EXISTS on PyPI with real wheels,
but `deepseek-harness-runtime-bin` ships mac/linux wheels ONLY — no Windows —
so on this box the editable-from-checkout install remains the law), `_local\dsh-dev.cmd`
wrapper as `dsh_bin`, worker home inherits the operator's `~/.dsh/settings.yaml`
(`harness._ensure_worker_home`), profile **`sdk`** (sdk-minimal lacks llm-pi-ai
— init rejected provider "modal"), boot 2.6s, init validated modal/GLM-5.3-Flash,
unit call returned typed `finish='error'` exactly where expected (no
MODAL_PROXY_TOKEN in env). ROUND 3: **FULL E2E PROOF** — a real DSH runtime
executed an entire P2 read (`_local\harness_e2e_smoke.py` +
`_local\mock_llm_server.py`, zero provider keys): 12/12 cards, calibration
1.000 THROUGH the wire, A2A audit trail live on the real bus. ROUND 4: **THE
OPERATOR'S OWN MODEL WROTE A CATALOG SEGMENT** — `_ensure_worker_home` now also
inherits `~/.dsh/.credentials.yaml` (managed ZAI/MODAL creds; the sdk profile's
credentials service resolves the adapter's apiKeyEnv from it), and
`_local\harness_real_e2e_smoke.py` ran the full P2 read with GLM-5.3-Flash as
every worker's brain: 12/12 cards 0 quarantines, fp.model=zai-org/GLM-5.3-Flash,
real typed claims with spans, calibration 0.574 ≥ 0.55 PASSED on the real wire,
70s; spancheck fence on those cards: **quote_verified_rate 1.0 (21/21),
unlocated 0.0, claims 28 valid / 0 invalid** (toy-corpus caveat recorded). 113
pytest + ruff clean. Harness mode is DONE and proven; using it on the
production tape is one command: `scriptorium.cmd read
C:\_DAD\projects-mirror-archive-v2 --provider harness --cap <N>` (estimated
meter uses the DeepSeek price sheet — HM-5 — so caps stay comparable). Parked:
SEA exe build fails in pnpm workspace deploy (DSH build-infra; the
`_local\dsh-dev.cmd` wrapper is the proven runtime path). Per-chunk Intercom
leases + worker attestation are designed, not needed for the ship gate. Laws +
all evidence: `_run_state/HARNESS_MODE_DESIGN.md`.

## Observations for the next session

- ~~Calibration variance~~ ADDRESSED 2026-09-01: CALIB_SHARDS default 8→16
  (swing ~0.7x); variance-aware band considered and rejected (the bar is the
  charter's scored floor; halt-below-bar stays a hard law).
- Batches 30-40 ran ~5 min each (retry-heavy chunks; 22 quarantines total are
  json-hostile transcript chunks — the run journal ds_calls.jsonl has full
  reasoning_content for diagnosis). Consider: per-call max_tokens bump for
  P2 (some chunks likely exhausted 6000 with dense cards), and a
  --retry-quarantined flag.
- ~~charter baseline "None"~~ FIXED 2026-09-01: `_charter_baseline` parses
  scoring.runs[-1] from charter.yaml (stdlib, targeted).
- CardV0 is fully defaulted — ANY JSON object validates as an empty card
  (measured live: schema-less GLM answers parsed then scored 0.000). Fine
  under calibration's protection; if a future rubric wants hard schema
  enforcement, make required fields required in a CardV1.
- Defect-shard mechanics, verified by reading + measurement (2026-09-01):
  defects mutate the TEXT and the reference is authored FROM the mutated
  text, so honest re-reads score HIGH on defect shards (measured 0.70-0.89
  across all four scorings — that is the design: they catch a
  prior-following model, e.g. one that writes the real entity name where
  the text says "Zorbell"). Two soft observations: (a) nothing yet
  self-tests the scorer's discrimination (score a card from the ORIGINAL
  unmutated text against the mutated reference — should drop; ~12 extra
  calls at discover time); (b) `defects_n` is absolute (12), so small
  golden pools get a high defect share (collection #2: 11/42 = 26% vs
  corpus #1's 10%) — consider proportional (10%) when touching discover.
- Scoring means POOL clean + defect shards. Since defect shards score high
  when the model is honest, this slightly raises means and (on collection
  #2 attempt 2) hid a bit of clean-shard instability (clean-only gap 0.0623
  vs pooled 0.0516). Not changed — cross-charter comparability of the
  recorded means wins for now; revisit if a charter ever passes/fails
  within noise of the bar.
- Embedding truncation: vectors embed chunk[:8000] chars (sidecar ctx
  safety) — document/decide before the resident-skeleton stage cares.
- Parked from earlier (still live): Baidu Unlimited-OCR S2+ eval plan ·
  read-only Tape.open · ~~session-jsonl content extractor~~ (DONE — v2 tape) ·
  walk on_error journaling · LSH banding · ~~tape kind-index sidecar~~ (DONE
  2026-09-01 — `textindex.py`; `scan_tape` still does its own pass, so a full
  read now costs 2 passes + a 3s index build rather than 2 passes + a full
  in-RAM text load) · OCR latency tuning · PyYAML.
- OCR sidecar (:8091) and embed sidecar (:8092) may still be resident;
  attach case finds them, or kill to free ~8GB VRAM.

## Next session's first move

Read this file + RATIFIED.md (items 7-9 are new). The harness qualification
question is CLOSED (round-9 verdict above; the watcher fork in older notes is
obsolete — every calibration attempt was refused checkpoint-clean and the
evidence is in HARNESS_MODE_DESIGN.md). Then:

1. ~~Collection #2~~ DONE (section above; numbers recorded).
2. **If the balance is topped up, launch the full v2 api read** — it is
   background, capped, resumable, kill-safe, memory-bounded, and its lease
   now renews. Preflight it first (spends nothing, ~1 min):
   ```
   scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap 55 --dry-run
   ```
   which on 2026-09-01 reported: **27,392 chunks over 571 batches, worst case
   $50.60 / realistic $36.78 under the $55 cap, charter a7d94b8e verified,
   200/200 sampled chunks readable, embed sidecar up.** Then:
   ```
   scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap 55
   ```
   Expect ~$37 realistic and several hours. When it finishes:
   ```
   scriptorium.cmd fence C:\_DAD\projects-mirror-archive-v2 --derive
   scriptorium.cmd query C:\_DAD\projects-mirror-archive-v2
   ```
   for the whole-catalog fence rate + derived spans and a look at what it
   found — then S3 (`map` + `reread`), then S4 (`synthesize` + `certify` —
   the certificate is the product).
   If a run halts on the cap, rerun the same command: it resumes.
3. If a stronger DSH worker model appears: re-run the FERRYMAN qualification
   slice with `SCRIPTORIUM_HARNESS_MODEL=<model>` — one command, ~5 min, $0;
   the calibration gate gives the verdict.

The fence is no longer only a meter: `spancheck.locate`/`derive_spans` write
`catalog/cards/spans.jsonl` with spans DERIVED from the Tape (model offsets
measured 0% usable on both tapes and are never trusted). 87.2%/87.4% of
quotes locate on the two measured catalogs; the rest have no coordinates and
therefore cannot render as verbatim — which is what S4's certify and the P5
two-register renderer are built on.

DEEPSEEK_API_KEY in .env; scriptorium_cc key is repo-scoped; operator
deactivates it when the build-out ends. Keep the GitHub repo current
(`git push`) at green milestones.
