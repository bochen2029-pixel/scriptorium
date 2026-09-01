# Harness mode — design (provider="harness")

**Status (2026-09-01, goal round 4): OBJECTIVE COMPLETE — the operator's own session model
(GLM-5.3-Flash via Modal) wrote an entire catalog segment as DSH worker agents: 12/12 cards,
calibration 1.000→0.574 (bar 0.55) through the real wire, deterministic fence 100% verified.
113 pytest + ruff clean.** Companion facts: `_run_state/NEIGHBOR_ORGANS.md` +
`_run_state/survey/{intercom,dsh-harness}.md`.

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

## A2A layer (v2, designed — Intercom)

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
