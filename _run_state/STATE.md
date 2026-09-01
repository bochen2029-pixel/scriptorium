# scriptorium — run state

**S0 GREEN · S1 GREEN · S2 code green + validated on TWO tapes · DUAL MODE
(api + harness) BUILT, HARDENED, live-blocked only on the Modal window.
2026-07-31→09-01.** Trust this file + git over any memory; RATIFIED.md holds
the operator's standing delegation (items 7+8 added 2026-09-01). 125 pytest +
ruff clean; all numbers from real runs. Published public MIT at
github.com/bochen2029-pixel/scriptorium.

## TL;DR for the next session

Corpus #1 exists as TWO tapes (spec section 5 version law — both valid, both
verifiable, negatives forever):
- **v1** `C:\_DAD\projects-mirror-archive` — raw envelopes, 1.753B tokens,
  charter frozen (root 209ed243), FERRYMAN slice read (2,683 cards).
- **v2** `C:\_DAD\projects-mirror-archive-v2` — session-extracted (voices only),
  **172M tokens (10.2x smaller)**, charter frozen (root a7d94b8e, scored
  0.710/0.718 — BETTER than v1), OUTREACH slice read (56 cards, fence 87.2%
  verified vs v1's 71.5%). **v2 is the production tape.**

**Two lanes to the full v2 read now exist; each needs one thing:**
- **api lane**: operator top-up (~$32 at $0.184/M; balance ~$6.8), then
  `scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --cap 35`.
- **harness lane** (the operator's own GLM-5.3-Flash via Modal, ~$0 cash):
  waits on the Modal plan window (429 mid-session 2026-09-01, see BLOCKED),
  then `SCRIPTORIUM_A2A=1 SCRIPTORIUM_DSH_BIN=C:/scriptorium/_local/dsh-dev.cmd
  scriptorium.cmd read C:\_DAD\projects-mirror-archive-v2 --provider harness
  --cap 35` — but the FERRYMAN qualification slice (auto-retrying via
  `_local/ferryman_watcher.sh`) and its fence comparison come FIRST; the full
  harness read stays the operator's call.

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
boundary: SDK installed editable from the DSH checkout (PyPI name is an empty
stub — never `pip install deepseek-harness-sdk` from PyPI), `_local\dsh-dev.cmd`
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

- **Harness lane (v2 FERRYMAN slice + any harness read): the Modal plan
  window.** Mid-session 2026-09-01 every worker call started returning
  `429 "Plan credits cannot be applied to shared endpoint usage. Add a payment
  method or increase your spend limit"`. `_local/ferryman_watcher.sh` retries
  the slice every 20 min for ~5.3h and needs nothing if the window refreshes
  on its own. IF the 429 persists past that: it is a Modal plan/billing state
  only the operator can change (add payment method / raise spend limit), or
  the operator may bless routing workers via the ZAI credentials instead
  (`SCRIPTORIUM_HARNESS_PROVIDER`/`MODEL` env — different pocket, so it stays
  the operator's call).
- **API lane full-corpus P2: operator top-up** (~$32; balance ~$6.8).
- Nothing else.

## Next session's first move

Read this file + RATIFIED.md. Then check
`_local/ferryman_v2_harness_watch.log` (tail):
- **SUCCESS** → run `spancheck.py` on the new harness cards (the run id is in
  the log), record fence beside api numbers here, and compare cards/fence vs
  v1-FERRYMAN-api 71.5% and v2-OUTREACH-api 87.2%. A clean slice qualifies
  the harness lane; the FULL harness read stays the operator's call.
- **still retrying** → leave it; do other work.
- **STOP-DRIFT** → GLM couldn't hit the v2 calibration bar with the clean
  system role: diagnose with the run journal (`finish_failure`, response
  shapes) + session store; consider effort=medium for calibration, or accept
  api-lane-only production.
- **GAVE UP / STOP-*** → see BLOCKED.

If the operator topped up the DeepSeek balance: launch the full v2 api read
(command in TL;DR; CALIB_SHARDS now defaults 16). When a full read finishes:
`spancheck.py` for the whole-catalog fence rate, then S3 (`map` + `reread` to
convergence), then S4 (`synthesize` + `certify` — the certificate is the
product).

Span fence-check (spancheck.py) is BUILT and is the S2 gate's fence item;
whole-corpus rate prints after the full read. Exact-offset is 0% on both tapes
(model char-offsets are useless) — S4's certify must DERIVE spans by locating
quotes, never trust model offsets; the P5 renderer only ships fence-located
spans, so the 12-28% unlocated can't surface as verbatim.

DEEPSEEK_API_KEY in .env; scriptorium_cc key is repo-scoped; operator
deactivates it when the build-out ends. Keep the GitHub repo current
(`git push`) at green milestones.
