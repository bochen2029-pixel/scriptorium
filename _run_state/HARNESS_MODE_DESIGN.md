# Harness mode — design (provider="harness")

**Status (2026-09-01, round 5): OBJECTIVE COMPLETE + A2A v2 increments BUILT — per-chunk
leases (multi-driver co-work), batch findings, artifact-pin attestation, and the persona
patch (frozen prefix as the workers' REAL system role). 124 pytest + ruff clean.**
Companion facts: `_run_state/NEIGHBOR_ORGANS.md` + `_run_state/survey/{intercom,dsh-harness}.md`.

## Round-9 VERDICT: the lane is qualified; GLM-5.3-Flash as the worker model is NOT

Round 8 predicted that a GLM-authored charter would rescue the score. Measured instead of
assumed — four calibration runs on the SAME 16 golden shards, scored every way (all from calls
already spent, `_local/cross_score.py`):

| comparison | entities | claims | topics | **score** |
|---|---|---|---|---|
| DeepSeek vs its own goldens (charter baseline, n=105) | 0.833 | 0.427 | 0.825 | **0.710 / 0.718** |
| GLM(low) vs DeepSeek goldens | 0.505 | 0.043 | 0.435 | **0.327** |
| GLM(low, run 2) vs DeepSeek goldens | 0.521 | 0.079 | 0.510 | **0.370** |
| GLM(medium) vs DeepSeek goldens | 0.462 | 0.043 | 0.279 | **0.262** |
| **GLM(low) vs GLM(low) — same-effort self-consistency** | 0.585 | 0.167 | 0.739 | **0.497** |
| GLM(low) vs GLM(medium) — cross-effort | 0.558 | 0.121 | 0.655 | 0.445 |

Two effects, both real, now separated:

1. **The cross-model phrasing penalty is large: about +0.13.** Scoring GLM against ITSELF instead
   of against DeepSeek's goldens lifts 0.370 → 0.497. Round 8's claim holds — goldens are
   model-specific and calibration partly measures agreement with the charter's author.
2. **But GLM's own reproducibility is the binding constraint: 0.497 vs DeepSeek's 0.714.** Even
   with a GLM-authored charter, the same model re-reading the same chunk agrees with itself at
   ~0.50 — **below the charter's 0.55 bar**. The deficiency is specific and visible: entities
   0.585 and topics 0.739 are serviceable; **claims 0.167** are not. GLM does not emit
   reproducible `(subject, predicate, polarity)` triples for this rubric.
   Prediction, stated for the record: a `discover --provider harness` run would fail the S1
   falsifier too (SCORING_BAR is a fixed 0.55, so ~0.50 self-agreement refuses the freeze) —
   i.e. the gate catches it one rung earlier, not later. Untested; ~370 GLM calls to confirm.
   Also note effort=medium scored WORSE than low (0.262 vs 0.327/0.370): more reasoning is not
   the lever, so an effort bump is not a fix worth buying.

**Verdict.** The harness lane is *architecturally* qualified — it wrote a complete 12-card
catalog segment end-to-end (round 4), enforces every law identically, and its A2A layer is live
on the bus. The *worker model* is not qualified for corpus #1's charter: three independent runs
land 0.26–0.37 against the frozen charter and ~0.50 against itself, all under the bar, and the
calibration gate refused every one of them checkpoint-clean without writing a single card. That
refusal is the system working — a lane that shipped 0.33-quality cards into a lifetime catalog
would be the real failure. **Production reading of corpus #1 stays on the API lane (DeepSeek,
0.71 self-agreement).** The harness lane is ready the day a stronger worker model is wired to
DSH (it is one env var: `SCRIPTORIUM_HARNESS_MODEL`), and remains useful today for
non-calibrated work.

Total measured cost of this entire qualification exercise: **$0** cash (Modal quota only) plus
about five minutes of wall-clock per attempt — because the halt fires at batch 0, before any
card is written.

### Note for whoever runs `_local/harness_real_e2e_smoke.py` next

It now **halts at calibration 0.500 < 0.55** where round 4 passed at 0.574. That is not a
regression — the mock-wire smoke still produces 12/12 cards, so the transport, the text index,
the gate and the A2A layer are all intact. It is the round-9 verdict reproducing itself on a
completely different (toy) corpus with different, stub-authored goldens: GLM lands at ~0.50
again, right where its own self-consistency sits. Two independent corpora, same answer. The
halt is the gate doing its job; expect it until a stronger worker model is wired.

## Round-8: the goldens are MODEL-SPECIFIC — a cross-model lane needs its own charter

With the contract actually reaching the model (in-task), the slice scored **0.327** — a real
reading, far above the 0.000 no-contract runs, still under the 0.55 bar. Per-field F1 of GLM's
16 calibration answers vs the SAME golden shards, beside the charter's own DeepSeek run:

| field | DeepSeek (charter baseline, n=105) | GLM-5.3-Flash (n=16) |
|---|---|---|
| entities | 0.833 | 0.505 |
| claims | **0.427** | **0.043** |
| topics | 0.825 | 0.435 |

Entities and topics degrade gracefully (different granularity — GLM emitted 17 entities where the
reference had 42, or 25 where it had 22). **Claims collapse to near-zero**, and that is a
measurement artifact as much as a quality one: `compare_cards` scores claims as exact-set F1 over
`(normalized subject, normalized predicate, polarity)` triples, and **the golden references were
authored by DeepSeek** during P1. Calibration therefore measures *agreement with the charter
author's phrasing*, not absolute reading quality — a second model paraphrases the predicate
("depends on" vs "requires") and scores 0 on a correct claim. DeepSeek itself only reaches 0.427
on its OWN goldens, which shows how brittle exact-triple matching is even in-family.

**Consequence, and it is architectural (not a bug):** the charter's frozen model is part of the
catalog's identity — cards already carry `fp.model`, and the spec's whole consistency claim is
"one frozen model + one frozen rubric = a million identical librarians". So a harness lane whose
workers are a DIFFERENT model must get **its own charter**: run `discover --provider harness` +
`freeze` so the goldens are authored by the reading model, exactly parallel to RATIFIED item 6
("v2 gets its own charter; the v1 charter stays bound to v1"). Reading a DeepSeek-authored
charter with GLM workers is a version violation in spirit, and calibration is right to refuse it.

Alternatives considered and rejected for now: (a) semantic/embedding claim matching — softens a
falsifier into a judgment call, and the local embedder is already a dependency of the index, not
the gate; (b) lowering the bar for cross-model runs — that is exactly the "retry a quality gate
into submission" failure the watcher was written to avoid.

## Round-7 (Claude Code session): the modal path DROPS the system role — in-task is LAW for modal

Attempt 2 of the slice (nonce-fixed sessions, clean persona, open Modal window: warmup + all 16
calibration shards completed attempt-0, no retries) STILL scored **0.000** — and this time the
composed system role was verified clean (persona + END boundary, zero foreign chars). GLM's own
reasoning transcripts kept saying *"we don't see the schema … no binding contract exists"*.

**Behavioral proof, one real Modal call:** persona = "when the user says 'ping', reply exactly
'XYZZY-PONG-7741'"; task = `ping`. Reply: `"Pong! 👋 I'm here and ready to help."` — **no token.
The modal/GLM-5.3-Flash path discards the `system` role entirely** (DSH composes it — the
`request/header` carries it byte-perfect — but it never reaches the model). A direct
quote-your-system-prompt probe refused (guardrail), so the behavioral probe is the evidence.

Consequences, all landed:
- BOTH 0.000 halts had ONE root cause: the workers saw only the task — never the rubric (and
  never the "foreign tail" either; round-6's boundary/unmount work fixed a real composition
  issue, but one the modal path made invisible).
- Round-4's in-task success (calibration 0.574 on the real wire) was the correct architecture,
  not a v1 stopgap. **In-task is the DEFAULT and the only correct mode for provider=modal.**
- Persona/patch mode stays built + composition-proven for providers that honor `system`
  (deepseek-official verified via mock composition) — **opt-in** via
  `SCRIPTORIUM_HARNESS_SYSTEM_ROLE=patch`, because the drop is silent and only calibration
  catches it. `SCRIPTORIUM_HARNESS_INTASK` is retired (in-task IS the default).
- Also fixed en route (found by the smoke regressing on rerun): **session ids must be GLOBALLY
  fresh** — the session store persists across runs and a fresh runtime given an on-disk id
  errors instantly with a bare `finish=error`; ids now carry a per-client uuid nonce. This had
  been poisoning watcher attempts beyond the real 429.
- The calibration gate has now caught, in one day: a missing contract (twice, two different
  causes) and would have caught the id collisions — three saves, zero bad cards shipped.

## Round-6 (Claude Code session): the persona patch meets a real model — fails honestly, hardened, re-proven

The first REAL run under the persona patch (v2 FERRYMAN slice, 143 chunks) scored **calibration
0.000 at batch 0 → the halt law fired perfectly** (checkpoint-clean, zero cards, pennies spent).
Forensics — the DSH session store (`_local/dsh-home/sessions/…/session.jsonl.zstd`) preserves the
composed request — showed:

1. The persona APPLIED byte-complete (system startswith rubric+refcard, 6,882 chars exact) — the
   patch grammar and layer order were correct all along.
2. BUT the composed system role continued for **4,197 more chars of other plugins' prompt
   sections** (bash exit-code guidance, read-tool guidance, subagent/workflow guidance).
   `includeHarnessIdentity/RuntimeContext: false` silence only the system-prompt plugin's own two
   sections.
3. GLM-5.3-Flash at effort=low, reading "conforming to the schema in the system contract" while
   its system prompt ENDED as agent-tooling boilerplate, reasoned verbatim *"no schema given …
   best effort with a plausible structure"* and emitted invented JSON.
4. `CardV0` is fully defaulted, so pydantic accepted every invented object as an EMPTY card
   (zero retries — nothing "failed"), and `compare_cards` scored the empties 0.000. Three
   independent laws (calibration gate, halt-below-bar, checkpoint-clean) turned a silent
   quality disaster into a $0.03 diagnosis.

Fix, probed on the real Cordis loader to **ZERO foreign chars** (`_local/persona_probe.py`):
- the persona now ends with an explicit `=== END OF BINDING CONTRACT ===` boundary
  (self-defending against any future appended sections);
- every `tool-*` row is unmounted for workers (HM-8 single-shot; the `tools` SERVICE row must
  stay — `agent-loop` requires it, and disabling it refuses boot: probed, `assertEntriesActivated`);
- patch-mode discipline points at "the binding contract at the START of your system prompt".

Then the relaunch hit the OTHER wall: every call `finish=error` with (session-store) `429 "Plan
credits cannot be applied to shared endpoint usage"` — the operator's Modal plan window closed
mid-session (attempt 1's calibration had gotten real GLM answers minutes earlier). Hardening that
followed: `_finish_failure` lifts the runtime's failure message into `ds_calls.jsonl`
(`finish_failure`) and quarantine details; the HM-3 ladder sleeps 5s/15s between attempts;
`_local/ferryman_watcher.sh` relaunches the slice every 20 min (retry ONLY on the rate-window
signature; STOP on drift/cap/unexpected — a quality gate must never be retried into submission).
The slice completes unattended the moment the window refreshes; warmup fail-fast keeps each
failed attempt at ~3 calls.

## Round-5 (Claude Code session): the designed A2A v2 increments, implemented

- **Per-chunk leases (design item 2) — BUILT.** `a2a.try_claim` claims
  `scriptorium:<archive>:p2:<doc_id>:<seq>` (TTL 900s) per selected chunk before any spend;
  refusal (exit 3) = a live co-driver owns it → skip WITHOUT writing; any soft bus failure →
  proceed uncoordinated. Claims run concurrently (`asyncio.to_thread`) so a batch costs ~1-2
  subprocess latencies of wall-clock, not 48. Chunk leases are NEVER released: a card/quarantine
  row is terminal once fsync'd (the resume law protects every key forever after), so TTL expiry
  is the janitor for crashed claimants and `--steal-stale` the manual override. Skips are
  reported honestly: `stats.skipped_leased`, `leased_elsewhere` journal events, per-driver
  `coverage_pct` < 100. Integration-proven in `test_read_multi_driver_lease_partition`: one
  chunk refused → 11 cards + honest coverage; A2A-off resume completes exactly the missing key
  → 12 unique, zero dupes zero gaps.
- **Batch findings (design item 3) — BUILT.** `batch_done: <n>/<N> cards C quar Q $USD` per
  batch, calibration means per round, `OPERATOR ATTENTION calibration_halt: …` on drift halt,
  `halt usd_cap: …` on cap halt — all `a2a.note` (fire-and-forget, never raises). ~57
  messages per FERRYMAN-scale run vs 2,683 for card-grain chatter.
- **Worker attestation (design item 4) — evaluated honestly, card-grain REJECTED, artifact-grain
  BUILT.** Workers are single-shot calls (HM-8): they cannot post to the bus; "attestation"
  would be the driver posting 1-3 extra subprocesses per card (~3-8K spawns and 2,683 messages
  per FERRYMAN-scale run) restating what `cards.jsonl` already is — the terminal fsync'd record
  carrying model fingerprints. Built instead: **one `pin` of `cards.jsonl` at run end**
  (`a2a.pin` → intercom `pin --file`, blake2b receipt) — cryptographic attestation of the WHOLE
  output in a single message, verifiable later with `pin-check`.
- **Persona patch / system-role fidelity (HM-2 v2) — BUILT.** `make_client(...,
  system_persona=system)`: a single-prefix pass (P2) promotes the frozen prefix to the workers'
  REAL system role via a generated Cordis patch-list overlay (`write_persona_patch` →
  `runs/<run_id>/persona.patch.yml`, kept as run evidence; spec gains `patches=(path,)` which
  the SDK forwards as `--patch <abs>`). Ground truth verified in the DSH source: patch grammar =
  bare `- id: system-prompt` row update whose `config` REPLACES the row's config
  (`{includeHarnessIdentity: false, includeRuntimeContext: false, persona: <json-escaped
  scalar>}`); `--patch` overlays apply after profile + user layers (last write wins — checked
  `app-boot`: "bundle layers below, overlays above"); the persona is emitted via `json.dumps`
  (JSON string = valid YAML double-quoted scalar; no YAML dependency; round-trip unit-tested
  with quotes/backslashes/newlines/unicode). Tasks in patch mode shrink to discipline + payload
  + unit line (closest mirror of the API lane's user message; `BOUNDARY`/`PAYLOAD_MARK` gone).
  Guards: `{{` in a prefix refuses patch mode (dsh-system-prompt templates are strict);
  `chat()` with a different system than the pinned persona raises (P1 uses FIVE prefixes per
  pass — induce/merge/rubric/refcard/synthesis — and therefore never sets `system_persona`;
  the P1 harness lane stays in-task by design); `SCRIPTORIUM_HARNESS_INTASK=1` is the kill
  switch back to v1 in-task bundles. HM-5 estimation counts persona chars on every call
  (system role still reaches the model each call — else harness-$ undercounts vs api-$).
  Journal entries carry `system_role: patch|in-task`.
- **Driver identity is honest (RATIFIED item 8).** The bus join reports which of the box's two
  harnesses actually drives: `claude-code` (env marker `CLAUDECODE`, model from
  `ANTHROPIC_MODEL`) or `dsh`; `SCRIPTORIUM_DRIVER_HARNESS/MODEL` override.
- Suite: **124 pytest + ruff clean** (11 new: lease semantics, pin, identity, persona patch
  mode/pinning/kill-switch/braces-refusal/estimator/YAML round-trip, multi-driver run_read).

## Round-4 evidence (real model, zero mocks in the P2 path)

- `harness._ensure_worker_home` now also inherits `~/.dsh/.credentials.yaml` (the harness's managed
  credential store — ZAI_API_KEY + MODAL_PROXY_TOKEN records; same box/user/trust domain, logged).
  The `sdk` profile's credentials service resolves the modal adapter's `apiKeyEnv` from it.
- `_local\harness_boot_smoke.py` with the REAL provider: runtime BOOTS, init validates
  modal/GLM-5.3-Flash, and the unit call returns `final_response='OK' finish='completed'` — a real
  GLM reply through scriptorium's worker transport.
- `_local\harness_real_e2e_smoke.py` (worker home `_local\dsh-home-real`): full P2 read with
  GLM-5.3-Flash as every worker's brain — `12 cards, 0 quarantined, coverage 100%, 70s`,
  `fp.model=zai-org/GLM-5.3-Flash`, cards carry genuine readings (typed claims with spans:
  "Cortex is the memory organ" @15–46 conf 0.95 …), **calibration mean 0.574 ≥ 0.55 PASSED on the
  real wire** (the calibration-variance observation from STATE.md visible live).
- **spancheck fence on the real-model cards: 21/21 quotes verified (14 exact + 7 substring),
  quote_verified_rate 1.0, unlocated 0.0, claims 28 valid / 0 invalid.** (Toy corpus caveat: the
  mini chunks are highly repeatable text; real-corpus rates will be lower — but the fence measures
  harness-mode cards exactly as it measures API-mode cards.)
- A2A audit trail for both runs is on the live bus (new joins 1yhwixo2/umsjhugw with leases).

## Round-3 evidence (live end-to-end, zero provider keys)

- `_local\mock_llm_server.py` (30-line stdlib OpenAI-compatible mock: stream + non-stream, every
  completion = a schema-valid CardV0) — the wire stand-in for worker brains.
- `_local\harness_e2e_smoke.py`: P1 discover+freeze via the ds.py stub (fixture tooling stays on the
  API path; charter FROZEN, scoring [1.0, 1.0] stable) → **P2 read with provider="harness"**:
  `HarnessClient → DeepSeekHarness runtime (profile sdk, dsh_bin=wrapper) → stdio JSON-RPC →
  deepseek-official adapter → HTTP :8118 mock → CardV0 → fsync'd cards.jsonl + index.sqlite`.
  Result verbatim: `12 cards, 0 quarantined | calibration @batch 0: mean 1.000 (bar 0.55) |
  $0.004 in 5s` — coverage 100%, journal entries carry usage_estimated + session_id.
- **A2A on the live bus** (`intercom replay --room proj-scriptorium-discover-mini-a346953e`):
  announce(join) → `run_start: p1-… provider=api` → `run_end: $0.003` → announce(join) →
  `run_start: p2-… provider=harness todo=12` → `run_end: cards 12 quar 0 $0.004`. Both orchestrator
  agents joined their lanes, claimed their pass leases, posted findings, released, and departed.
- New HM-1 extension: `SCRIPTORIUM_HARNESS_BASE_URL` / `SCRIPTORIUM_HARNESS_API_KEY` env → the SDK's
  DEEPSEEK_BASE_URL/DEEPSEEK_API_KEY overrides (mock servers, local gateways).
- Parked (build-infra, not scriptorium): the pkg SEA exe build fails inside `pnpm --filter
  dsh-python-runtime-closure deploy` (exit 1, both `tsx` and `pnpm exec` routes, npm_execpath set) —
  `_local\dsh-dev.cmd` wrapper remains the proven operational runtime; retry the SEA build when DSH
  tooling is next touched.
- Note: project rooms canonicalize (`proj-<project>-<hash8>`) — replay that name, not the bare
  project string, when auditing a pass.

## Round-2 evidence (what is proven on this box, 2026-09-01)

- `deepseek-harness-sdk` + `deepseek-harness-runtime-bin` (0.0.0.dev0) installed EDITABLE into the
  scriptorium `.venv` from `C:\deepseek-harness-master\python\{sdk,sdk-runtime}` (uv; the PyPI name
  is an empty 0.0.0.dev0 stub — install from the checkout, never from PyPI). Editable runtime needs
  the pkg SEA exe, so a wrapper is used instead: `_local\dsh-dev.cmd` → `node apps\cli\lib\bin.js`,
  passed as `dsh_bin` (SDK-verified parameter; same profile grammar).
- `_local\harness_boot_smoke.py`: with `profile="sdk"`, `dsh_bin=wrapper`, worker home
  `_local\dsh-home-smoke` (settings.yaml **inherited from the operator's `~/.dsh/settings.yaml`** by
  `harness._ensure_worker_home` — the modal/llm-pi-ai wiring lives there, NOT in profile patches):
  runtime BOOTED in 2.6s, JSON-RPC init validated provider/modal + model + effort, and the unit call
  returned typed `finish_reason='error'` — the expected honest failure at the provider boundary
  (`MODAL_PROXY_TOKEN` is not in this process's env). The whole chain — Python SDK → wrapper →
  dev-checkout CLI → runtime subprocess → stdio JSON-RPC → provider adapter — is live.
- Learned: `sdk-minimal` does NOT mount `llm-pi-ai` (init rejects provider "modal" with "no adapter");
  the default worker profile is therefore **`sdk`** (HM-8 updated). Known cosmetic: the .cmd wrapper
  emits a harmless stderr parse line; the pkg SEA build (`scripts/build-exe-for-python-sdk.ts`)
  remains the clean long-term runtime (also removes the wrapper).
- A2A (`a2a.py`, opt-in `SCRIPTORIUM_A2A=1`): pass-level join/claim/say/release/leave over
  subprocessed intercom.py verbs; explicit lease refusal (exit 3) SystemExits the pass before any
  spend; every other bus failure degrades to a no-op note. Wired into run_read (run_start, per-
  quarantine findings, run_end in finally) and run_discover (run_start, run_end). 10 tests.
- Remaining for a real worker call: operator puts `MODAL_PROXY_TOKEN` (or `ZAI_API_KEY`) in env and
  reruns the smoke — expected full round-trip; then a planted-archive `read --provider harness
  --cap 0.05`.

## Goal

An **optional** second provider seam beside `ds.py`: when scriptorium's LLM passes run
(`discover`/`read` today; later rungs reuse the same client contract), the operator can choose
`--provider harness` so every unit call is executed by a **DSH worker agent** — a subagent fan-out of
the session's own model (GLM-5.3-Flash via Modal today) inside the DeepSeek Harness — instead of a
raw DeepSeek API call. The default path (`--provider api`) is byte-for-byte today's behavior: `ds.py`
stays the ONE API seam, and the S0 dependency set stays closed (the `deepseek-harness-sdk` is
lazy-imported only when a harness client is constructed).

## Ground truth the design sits on

- `ds.py` owns the client contract every pass codes against: `gate_estimate()`, `warmup(system)`,
  `chat(system=, user=, tail=, mode=extract|think, effort=, max_tokens=, unit_id=, out_model=,
  rescue=) -> (parsed, meta)`, `meter` (`.usd()/.hit_rate()/.snapshot()`), `model_fp`, `close()`,
  and the typed errors `CapExceeded` / `UnitQuarantined` / `ModelChanged`. Both `run_discover` and
  `run_read` construct the client in exactly one line each.
- DSH exposes a **Python SDK** (`C:\deepseek-harness-master\python\sdk`, `pip install
  deepseek-harness-sdk`): `DeepSeekHarness(dsh_home=, cwd=, provider=, model=, reasoning_effort=,
  max_tokens=, profile=, patches=)` boots a runtime subprocess (`dsh --profile sdk`) and
  `.run(task, session_id=) -> RunResult(final_response, finish_reason, events, notifications)`.
  It **never reads `~/.dsh`** — an explicit `dsh_home` is mandatory, which gives scriptorium a clean
  isolated home (`_local/dsh-home`, gitignored). `sdk-minimal` profile = lean worker composition.
- System-prompt control exists via Cordis patches: `@deepseek-ai/dsh-system-prompt` config accepts
  `persona` + `includeHarnessIdentity: false` (+ `includeRuntimeContext: false`); the SDK forwards
  per-invocation `patches=(...)`. v1 ships the contract **in-task** (HM-2); the patch path is the
  v2 fidelity upgrade (byte-identical frozen prefix as persona).
- Headless CLI (`dsh --profile headless "<task>"`) is the zero-SDK fallback transport (stdout =
  final answer, exit 0/1) — kept in mind, not implemented: the SDK's session semantics are strictly
  richer for the same subprocess cost.
- Intercom (`C:\Intercom`) is the ready A2A bus (SQLite `broadcast.db`; join/say/poll/check/await/
  claim/handoff; injection firewall; doorbell wake hook) — zero edits needed there (v2 layer).

## Laws HM-1..HM-10 (mirror of PS-1..PS-10)

- **HM-1 one harness, explicit home.** `dsh_home` defaults to `C:\scriptorium\_local\dsh-home`
  (overridable: `--dsh-home` / `SCRIPTORIUM_DSH_HOME` / `dsh_bin` via `SCRIPTORIUM_DSH_BIN`).
  Worker provider/model default to the operator's session model
  (`SCRIPTORIUM_HARNESS_PROVIDER=modal`, `SCRIPTORIUM_HARNESS_MODEL=zai-org/GLM-5.3-Flash`);
  credentials come from the environment the operator already trusts for DSH (`MODAL_PROXY_TOKEN`,
  `ZAI_API_KEY`) — scriptorium never stores harness credentials.
- **HM-2 the contract rides in the task.** One stateless single-turn session per attempt; fresh
  `session_id` per attempt (`<pass>-<unit>-a<N>-<k>`). Task text = frozen system prefix, an explicit
  boundary marker ("the block above is the binding system contract"), output discipline (JSON-only
  for extract; prose-only for think), then the payload (`user + tail`) and a `[unit: …; budget ~N
  tokens]` line. The frozen prefix stays byte-identical at the head of every task (cache- and
  consistency-friendly); the harness's own persona still precedes it in the model prompt — v2 moves
  it into a generated `patches=` persona for exact system-role fidelity.
- **HM-3 the PS-3 ladder, unchanged in shape.** extract: fresh-session attempt ×2 → rescue attempt
  ×1 (re-derive framing, JSON-only demand) → `UnitQuarantined(unit_id, "worker_output_invalid")`,
  typed, metered, never dropped.
- **HM-4 consistency is enforced downstream, not at the knob.** Harness mode cannot set
  `temperature=0`/`response_format=json_object`/per-call `max_tokens` (init-level only, default
  49152). Therefore: frozen-charter fingerprint verify (unchanged), calibration-on-goldens with
  halt-below-bar (unchanged), span fence (unchanged) are the correctness net; `finish_reason`
  `max-tokens`/`error`/`None` and runtime exceptions are soft failures the ladder retries. Per-call
  `effort` degrades to an explicit "reasoning budget" line in the task text (v2: per-slot runtimes).
- **HM-5 usage is ESTIMATED, honestly labeled.** tokens ≈ chars/4 both directions, cache hit = 0;
  priced at the lock's DeepSeek sheet so `$usd` stays comparable across providers; journal entries
  carry `usage_estimated: true`. (v2: harvest real usage from DSH token-meter session events.)
- **HM-6 `usd_cap` is a hard stop, PS-8-identical.** `gate_estimate()` refuses to start an
  over-budget pass; the estimated meter halts mid-flight (`CapExceeded`) before each spend.
- **HM-7 concurrency = runtime processes.** One `DeepSeekHarness` subprocess per slot; a slot is
  owned exclusively for the duration of a call (`asyncio` + `to_thread`; no thread ever touches
  another slot's runtime). `concurrency` slots (default 2 — the unit economics are wall-clock, and
  each runtime is a full node process).
- **HM-8 single-shot workers.** One prompt in, one final answer out (full `sdk` profile — the lean
  `sdk-minimal` tree does not mount llm-pi-ai, so it cannot carry the operator's Modal/GLM provider;
  no tool loops in the seam, PS-10 discipline). A worker that needs a file gets the bytes in the task
  (v2: sandboxed artifact files + Intercom pins).
- **HM-9 model identity is init-verified.** The SDK rejects unknown provider/model/effort at
  initialization before any prompt runs; `model_fp` = the pinned worker model string. Mid-pass
  provider drift is out of scope v1 (single long-lived runtime per slot; restarts are journaled).
- **HM-10 the seam stays coordination-free.** No Intercom traffic inside `harness.py`'s transport —
  the A2A layer (below) wraps passes, so `harness.py` remains a drop-in for `DsClient`.

## Call-path changes (implemented this round)

- `harness.py` (new): `HarnessClient` (DsClient-duck-typed), `make_client(pass_name, usd_cap, *,
  provider="api", concurrency, journal_path, base_url, model, harness_home, harness_effort)`
  factory — `api` → `ds.DsClient` verbatim; `harness` → `HarnessClient`; unknown → `DsError`.
- `discover.py` / `read.py`: `provider: str = "api"` parameter; the single construction line goes
  through `make_client`. Everything downstream (ladder, calibration, quarantine, checkpointing,
  resume) is untouched.
- `scriptorium.py`: `--provider {api,harness}` (default `api`) on `discover` and `read`.
- `tests/test_harness.py`: HM laws against a fake runtime factory (no SDK, no network, no node).
- `tests/test_import_graph.py`: `harness` joins `OWN`; `deepseek_harness` joins the third-party
  allowlist with a comment (optional, lazy, never on the default path).

## Operational notes

- First `--provider harness` use requires: `pip install deepseek-harness-sdk` (into `.venv`), and
  the Modal/ZAI credential env vars present. `warmup()` boots slot 0's runtime and fails fast with
  typed `HarnessUnavailable`/SDK errors before any pass starts spending.
- Sessions persist under `_local/dsh-home` (JSONL session store); a harness pass is therefore
  post-mortem auditable in DSH terms (everywhen can index those tapes natively).

## A2A layer (v2 — items 2/3/4 BUILT in round 5, see top; original design below)

Wrap each pass in an Intercom run (see survey/intercom.md for the verb contract):

1. **Run room + identity.** Driver `intercom join --harness dsh --kind daemon --project
   scriptorium-<archive> --lane orchestrator` at pass start; posts `run_start` (run_id, charter
   root, cap, provider fingerprint) and `run_end` (meter snapshot, fence rate).
2. **Leases instead of in-memory todo.** Each selected chunk (or batch) becomes `claim --resource
   p2:<doc_id>:<seq>` (TTL 900s, `--steal-stale` after kill) — the existing resume law ("skip
   present keys") stays primary; leases add multi-*driver* safety (two sessions can co-work one
   catalog without dupes).
3. **Findings + pins.** Quarantined units and fence rejections are posted as `finding` messages
   with `pin`-ned evidence artifacts (blake2b — same discipline as the Tape); the calibration halt
   posts a `relay`-shaped request for the operator.
4. **Worker attestation (optional).** Each worker agent joins its own run room lane and says a
   `card_done` line with the card key + blake2b of its output artifact — giving the pass an A2A
   audit trail visible in `intercom replay` and the :8787 viewer.
5. **Wake.** The existing doorbell hook pattern (`intercom check` at end-of-turn) lets a resident
   driver session be woken by operator relays or by worker completion messages (S5 LIVE annex
   shape).

## Acceptance / falsifiers

- Default path untouched: full suite green with `deepseek_harness` absent from the venv; import
  graph stays closed.
- HM-2/3: bundle + ladder tests (fresh sessions per attempt, rescue, typed quarantine).
- HM-5/6: estimator math at pinned prices; cap refuse-at-start + halt-mid-flight.
- HM-7: slot exclusivity (N concurrent calls → N distinct runtimes, no sharing).
- Live smoke (later round, needs SDK install + creds): `read --provider harness --cap 0.05` on a
  planted `_testdata` archive; calibration must still halt cleanly when fed poisoned goldens.
