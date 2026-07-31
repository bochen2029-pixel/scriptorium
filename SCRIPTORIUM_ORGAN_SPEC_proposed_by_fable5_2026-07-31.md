# scriptorium — the organ that reads a lifetime
### Build spec for `C:\scriptorium`: the sixth fixed-path organ — manifest in → Tape + Catalog + Codex + Certificate out

**Status:** proposed build spec, authored by Claude Fable 5, 2026-07-31, operator-directed. Implements `C:\cortex\SCRIPTORIUM_PROTOCOL_proposed_by_fable5_2026-07-31.md` (the protocol) on the truth discipline of `C:\cortex\CORTEX_V2_ARCHITECTURE_proposed_by_fable5_2026-07-31.md` (Tape + fence), as a member of the organ family (`C:\everything` · `C:\everywhere` · `C:\chunker` · `C:\earshot` · `C:\imguard`). Nothing here re-litigates the protocol; where this doc is silent, the protocol governs. Operator ratifies before any full-corpus pass runs (the P1 freeze is the gate).
**Platform:** Windows 11 native. Python ≥3.12 + `uv`. No WSL, no Docker, no Linux/mac assumptions anywhere. Launchers are `.cmd`; scheduling is Task Scheduler; consoles are forced UTF-8 (`sys.stdout.reconfigure`, the chunker pattern).
**Provider:** DeepSeek **V4 Flash only** (`deepseek-v4-flash`, released 2026-07-31) — operator's decision: Flash is smart enough that Pro buys nothing, and Flash's 2500 concurrency (vs Pro's 500) is worth more than Pro's benchmarks. Encoded as law PS-1, with a config escape hatch, not a hardcode.
**Sovereignty split (fixed):** *pixels and audio never leave the box; text rents the reading.* OCR/vision = local Qwen3.5-9B (native early-fusion vision; llama.cpp `--mmproj` tower). ASR = local `earshot` (whisper.cpp). Embeddings = local (llama.cpp embedding server). Only canonical *text* goes to the API.

> **One sentence:** `scriptorium.cmd run <manifest>` walks a life's files through P0–P6 — intake → schema discovery → first reading → cartography → second reading to a fixed point → syntheses → fence — and leaves on disk the four deliverables the protocol names: the **Tape** (negatives), the **Cards+Map** (catalog), the **Atlas+Ledgers+Concordance** (codex), and the **QC Certificate** — rebuildable forever from Tape + frozen charter + model fingerprint, at roughly $600–800 and a weekend per billion tokens.

---

## §0 · What it is, in the family

| organ | finds / makes |
|---|---|
| `C:\everything` | files by **name/path/date/size** |
| `C:\everywhere` | files by **raw content** (exact bytes; the fence's verifier of last resort) |
| `C:\chunker` | **structure** — token-aware splits with breadcrumbs |
| `C:\earshot` | audio/video → **transcript** |
| `C:\imguard` | images → **vision-safe** |
| **`C:\scriptorium`** | a corpus → **a catalog** (the organ that *reads*) |

Organ discipline, kept: one folder; point-and-run; README-as-contract (the README is written at S0 and kept truthful); self-contained driver; **organs are called at their fixed paths as subprocesses, never imported** — paths + versions pinned in `scriptorium.lock`. No imports from `C:\KEEL`, `C:\hypercell*`, `C:\cortex` code, or any framework. What it shares with CORTEX v2 is a *format* (the Tape) and a *doctrine* (the fence), not a dependency.

What it is **not**: not a chatbot, not a RAG service, not a UI, not multi-tenant, not an agent. Serving the finished catalog is CORTEX's job; a thin read-only `ask` subcommand (R1/R2-grade: FTS + embedding + span fetch) ships for demo purposes only and never asserts uncited.

## §1 · The provider seam (`ds.py`) — laws PS-1..PS-10

All API traffic goes through one module with one metering wrapper (the BRAIN L4/L13 pattern: one path to the model, the meter cannot be bypassed).

- **PS-1 · One model.** `model: "deepseek-v4-flash"`; base `https://api.deepseek.com` (OpenAI-format `/chat/completions` primary; the Responses API is Flash-only today and MAY be adapted later, never required). `provider.base_url` / `provider.model` are config so the seam can point at any OpenAI-compatible endpoint (including local llama-server) — but the shipped default is Flash everywhere, **including the apex passes P1/P5** (operator override of the protocol's frontier-apex suggestion; revisit only if P1 golden syntheses fail their bar).
- **PS-2 · Two modes, split by epistemic kind.** Thinking is ON by default at the API; this pipeline splits deliberately:
  - **Extraction (P2, P4 workers; P3 adjudications):** `thinking: {"type":"disabled"}` + `temperature: 0` + JSON mode. Determinism knobs only work in non-thinking mode (thinking mode silently ignores `temperature`/`top_p`), and cards need format discipline more than chain-of-thought.
  - **Synthesis & judgment (P1 discovery, P5 codex, P6 NLI-grade checks that need judgment):** thinking **enabled**, `reasoning_effort` mapped per task (`low` for headers, `high` for ledgers/atlas, `max` reserved). `reasoning_content` is logged to the run journal (it is working paper, never a citable artifact).
- **PS-3 · JSON mode, verified client-side.** `response_format: {"type":"json_object"}`; the frozen prompts contain the literal word "json" and an example object (documented requirement); `max_tokens` set explicitly per output type. There is no server-side json_schema — **pydantic v2 frozen models validate every worker output**; invalid or empty content (a documented failure mode) triggers the retry ladder: same call → retry ×2 → thinking-enabled rescue ×1 → **quarantine** the chunk with a typed reason (never silently dropped; quarantines appear in the certificate).
- **PS-4 · Cache-shaping law.** DeepSeek context caching is automatic, exact-prefix, unit-boundaried (units close at end-of-user-input, end-of-model-output, and fixed intervals inside long inputs), persisting hours-to-days. Therefore, per pass: `[system message] = the frozen charter (rubric_v + ontology_v + card schema + register rules) — byte-identical across every call of the pass`; `[user message] = (P4 only: the map-slice) + the chunk + the tiny volatile tail (ids)`. **Nothing volatile ever precedes stable bytes**; timestamps/ids ride at the end of the user message; the charter never interpolates. The meter logs `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` per call and prints the pass's realized hit rate; a hit rate < 60% on P2/P4 is a build bug (K-CACHE vital, certificate line).
- **PS-5 · Warm-up rule.** Each pass sends **one serial warm-up call** per frozen prefix and waits for completion before fanning out, so the prefix is cached before 2000 concurrent misses pay full price. (Map-slices in P4 are grouped by thread/era so sibling workers share slice prefixes too.)
- **PS-6 · Concurrency + backoff.** asyncio + `httpx` bounded semaphore, default 1024 in-flight, config max 2400 (headroom under the 2500 account limit); AIMD backoff on 429/5xx (halve, then +64/min recovery); per-request timeout with jittered retry; idempotent by unit-id (the journal makes re-sends safe).
- **PS-7 · Peak/off-peak awareness.** DeepSeek has announced peak/off-peak pricing (peak = 9:00–12:00, 14:00–18:00 Beijing, prices ×2; date TBD). The driver knows those windows (`provider.peak_windows_beijing`) and full-corpus passes default to `--offpeak-bias` scheduling via Task Scheduler; a pass started inside a peak window prints the surcharge estimate first.
- **PS-8 · Budget is a hard stop.** Every pass declares `usd_cap` in config; the meter (computed from usage fields at the pinned price sheet in `scriptorium.lock`) refuses to *start* a pass whose estimate exceeds cap and **halts** a pass that crosses cap mid-flight (checkpoint-clean). Estimates come from the P0 contact sheet's token census — measured, not guessed.
- **PS-9 · Fingerprint everything.** Every stored output row carries `{model_fp}` = the model version string returned by the API (not the alias), plus `{rubric_v, ontology_v, prompt_hash, mode, effort}`. A mid-pass change in the API's reported model version = **halt + operator decision** (the §5 consistency law: an upgrade is a new catalog version, never a mid-pass mutation).
- **PS-10 · No tool-loops in workers.** Workers are single-shot (one request → one typed object). Tool calls (and the thinking-mode rule that `reasoning_content` must be passed back inside tool loops) are out of scope for P0–P6; the LIVE-annex elicitation module may use them later, behind this same seam.

## §2 · Local sidecars (`local.py`) — the sovereign floor

Attach-or-launch against `C:\llama.cpp` binaries + `C:\models` weights; ports are scriptorium's own (never squat KEEL's 8081–8083):

- **VISION/OCR — `:8091`.** `llama-server -m C:\models\Qwen3.5-9B-Q5_K_M.gguf --mmproj C:\models\mmproj-F16.gguf` (Qwen3.5-9B is a native early-fusion vision LLM; llama.cpp mounts the vision tower via mmproj — works, and pixels stay on the box). OpenAI-compatible image input on localhost. **OCR contract (frozen prompt):** transcribe verbatim; preserve reading order; mark layout (`[table]`, `[column-break]`, `[handwritten]`); mark uncertainty inline as `⟨?…⟩` never silently guessed; emit `{text, regions[], confidence_hint}` JSON. Every OCR output is R-class provenance with extractor fingerprint (gguf + mmproj hashes from `scriptorium.lock`).
- **Preflight:** every image (and every rasterized PDF page) passes `C:\imguard` first (downscale >2000px, transcode) before the vision call.
- **PDF routing:** text-layer first (chunker's PyMuPDF path); pages whose extracted text density falls below floor are rendered to PNG (PyMuPDF) → imguard → `:8091` OCR. Mixed documents interleave by page, in order, spans preserved.
- **EMBEDDINGS — `:8092`.** llama.cpp embedding server on the local embedding model (default: the qwen3-embedding gguf in `C:\models`; exact file pinned in `scriptorium.lock`). All P2 embeddings and P3/P4 neighbor-mining are local and free; embedder fingerprint stamps every vector (a swap = re-embed, never a silent mix).
- **ASR:** `C:\earshot` at its fixed path (`--diarize`; `--translate` off by default — the catalog reads the language the life was lived in). GPU-heavy; runs as its own P0 queue, resumable, before any API pass needs the text.

## §3 · The Tape (`tape/`) — the truth layer

CORTEX v2's discipline, instantiated for a static-then-appending corpus:

```
<archive_root>\                      # operator-chosen, NOT inside C:\scriptorium
  manifest.yaml                      # operator-owned: roots, include/exclude globs,
                                     #   sovereignty flags, consent/scope note, era hints
  tape\
    segments\seg-000001.jsonl ...    # append-only, hash-chained (blake2b-128,
                                     #   prev_h ‖ CANON-JSON(record)), fsync'd
    tape.lock                        # chain head, counts, segment index
  catalog\  codex\  certificate\     # renders (all rebuildable from tape + charter)
  runs\<run_id>\journal.jsonl        # driver checkpoints (resume = skip completed)
```

**Record kinds:** `doc` (one source file: path, content-hash, mtime, modality, extractor fp, canonical text stored as one or more `text` records), `text` (a canonical-text block with `{doc_id, seq, chars}` — **the span coordinate system**: every citation everywhere is `{doc_id, seq, start, end}` against these exact bytes), `journal` (intake events: admitted / dedup-folded / quarantined / excluded-by-manifest — nothing silently dropped), `contact` (the census rows). Dedup is content-hash exact + near-dup flagging (MinHash) — near-dups are *flagged, kept, and cross-referenced*, because retellings are biography gold, not noise (protocol P4).
**Reconciliation (I-ING-7 kept):** intake ends by diffing manifest-discovered files (via `C:\everything` where indexed, direct walk otherwise) against Tape `doc` records; the completeness number is printed and stored — measured, never assumed from exit codes.
**Deliverable rule:** the Tape lives with the *customer's* archive root (Jin's disk, your disk), never inside the organ folder. `C:\scriptorium` holds code and frozen prompts only. The negatives belong to the life they came from.

## §4 · The passes — modules, contracts, modes

One entry point: `scriptorium.cmd <subcommand>` = `python scriptorium.py <subcommand>` — `plan · intake · discover · freeze · read · map · reread · synthesize · certify · run · status · resume · ask`.

| Pass | Subcommand | Engine | Mode | Output (typed, span-cited) |
|---|---|---|---|---|
| **P0 intake** | `intake` | organs + stdlib, **no API** | — | Tape + journal + **contact sheet** (tokens × year × source × modality; the pass-cost estimator) |
| **P1 discovery** | `discover` → `freeze` | Flash | thinking `high` | `charter\ontology.yaml` + `charter\rubric_P2.md` + compression prior + **golden shards** (N=100–300 ref-annotated chunks incl. ≥10 planted defects) + 3 golden syntheses; **`freeze` = operator ratifies → fingerprints locked** |
| **P2 first reading** | `read` | Flash | **non-thinking, t=0, JSON** | `catalog\cards.jsonl` (one Card per chunk: entities+aliases, claims as (subject, predicate, polarity, confidence, time) tuples, verbatim quotes worth keeping, topics, style fp, retelling candidates — every field cites spans) + local embeddings + SQLite index (FTS5 + vectors) |
| **P3 cartography** | `map` | deterministic + Flash adjudication | non-thinking JSON | `catalog\map\` — entity registry (embedding-cluster + adjudicated merges; **never surface-string identity**), thread/theme communities (leidenalg via python-igraph, pip wheels on Windows; networkx fallback), era change-points (CUSUM over theme/style distributions), **contradiction candidates by arithmetic** (same entity+predicate, opposite polarity, different times), pyramid gists |
| **P4 second reading** | `reread` | Flash | non-thinking, t=0, JSON | cards annotated with global context: first-occurrence flags, development links, retelling drift, contradiction confirmations, surprising-connection candidates → Map v(n+1). **Iterate P3⇄P4 until converged** |
| **P5 syntheses** | `synthesize` | Flash | thinking `high` | `codex\` — evolution ledgers per major entity/theme · contradiction dossiers (both sides + timeline, never resolved) · era portraits · connection dossiers · the Concordance · the Atlas. **Two registers, mechanically separated:** the subject's words are *extracted spans by reference* (rendered verbatim from the Tape at read time, never model-retyped); the catalog's gloss is the only model prose |
| **P6 fence** | `certify` | **no LLM** (+ `everywhere`) | — | `certificate\` — span verification of every citation (exact substring vs Tape; `C:\everywhere --patterns --jsonl` as raw-byte verifier of last resort vs original files) · coverage audit (% of Tape tokens reachable by citation-walk) · **dark-matter report** (unreferenced regions listed) · calibration report · quarantine log · **audit kit** (`audit.html`: stratified random cards/claims, each with its span rendered inline — any assertion checkable in seconds) · `certificate.json` + human `certificate.md` |

**Chunking:** fixed-path call to `C:\chunker` (`--budget 8000` content tokens default, config `[2000, 32000]`) — breadcrumbs become card context headers. **Convergence (`convergence.contract`):** converged when, across two consecutive P3⇄P4 iterations, thread-membership churn < 2% ∧ new cross-links < 5 per 100k chunks ∧ registry edit distance < 1%; **hard stop at iteration 4** = P1 falsifier tripped (schema too fluid) → halt, re-derive, re-freeze. **P1 ontology-thrash falsifier:** if P2 routes > 10% of content to `OTHER/doesn't-fit`, stop the pass, re-derive, re-freeze — caught early by design, not at the end.

## §5 · Consistency, measured (the immortal-librarian QC)

- **Calibration shards ride every pass:** the P1 golden shards (planted defects included, so QC *can* fail) are interleaved every Nth batch (default N=50 batches) during P2/P4; score drift beyond the ratified threshold → **halt the pass, diagnose** (model updated? prompt truncated? genre shifted past the schema?) — never silently continue. Anti-checkpoint-theater, per REEL §10.
- **Dual-extraction floor:** a 2% random sample of P2 chunks is re-extracted with a paraphrased-but-equivalent rubric variant; field-level disagreement rate = the extraction error floor, printed in the certificate. (Same-model second-seed is the Windows-affordable stand-in for a second family; honest about what it does and doesn't catch.)
- **Version law:** rubric/ontology/model change = a **new catalog version** re-derived from the Tape (`catalog v(N) = protocol v(P) × model M × Tape`), never a mid-pass mutation. `scriptorium.lock` pins: organ paths+versions, gguf hashes (LLM, mmproj, embedder), price sheet, prompt hashes, charter fingerprints, chunk budget. The negatives are forever; the prints are versioned; better scanners rescan.

## §6 · Cost & wall-clock model (pinned prices, 2026-07-31)

Flash: $0.14/M in (miss) · **$0.0028/M in (hit)** · $0.28/M out · 1M ctx · 384K max out · 2500 concurrency.

| Corpus | P2+P4×2 (3 readings) | P1+P5 apex | Total est. | Wall-clock (1024 in-flight) |
|---|---|---|---|---|
| 100M tok (Jin-scale, post-earshot) | ~$45–65 | ~$10–30 | **~$60–100** | hours |
| 1B tok (verbose lifetime) | ~$450–650 | ~$50–150 | **~$500–800** | a weekend |
| 10B tok (organization) | ~$4.5–6.5K | ~$0.5–1.5K | **~$5–8K** | 1–2 weeks |

(Output assumed ~12% of input; cache-hit share ~30–40% of input tokens via charter + map-slice prefixes; peak-hour surcharge avoided per PS-7. The alternative remains ~33 person-years per 1B tokens, read once, no cards, no certificate.)

## §7 · Build ladder (each rung independently useful; falsifier-gated)

- **S0 · Tape.** `intake` end-to-end on one small mixed collection (text+PDF+images+one video): Tape hash-chain verifies, reconciliation printed, contact sheet correct vs `estimate_tokens.py`. *Falsifier: any silently dropped file = red.*
- **S1 · Charter.** `discover` on a stratified sample of corpus #1 (**the operator's own archive** — no consent questions, instant dogfood); operator edits + ratifies; `freeze` locks fingerprints. *Falsifier: golden shards score below bar on re-run = the rubric isn't frozen-stable.*
- **S2 · First reading.** `read` with calibration interleave, resume, budget meter, cache-hit accounting. **Gate (= DRDJ G1):** cards + fence-checked spans on two real collections — for corpus #2 this is literally the DRDJ condensation gate: 精华 cut source material and 金句 quote cards fall out of Cards here. *Falsifiers: kill the driver mid-pass → resume with zero dupes/gaps; hit-rate < 60% = prompt-shape bug; shard drift → halt fires (drill it once deliberately).*
- **S3 · The circle.** `map` + `reread`, converge on corpus #1. *Falsifier: non-convergence by iter 4 handled as specified (halt, not thrash).*
- **S4 · Codex + certificate.** `synthesize` + `certify`. **Ship gate: citation-verification ≥ 99.5%, planted defects all caught, dark matter listed, audit.html spot-checks pass by hand.** The certificate is the product.
- **S5 · LIVE annex (later, gated):** journal-fed increments (new files → P2 cards → local map update; era-boundary partial P4) + the **elicitation loop** (the corpus generates the interview it demands; answers append to the Tape) — the standing-service mode, and the seam where a future BRAIN cell becomes the archive's custodian. Not before S4 ships.

## §8 · Refusals (binding)

No Pro model in the default path (PS-1). No cloud OCR/ASR/embeddings — pixels and audio never leave the box. No UI/SaaS/multi-tenant. No VRAM-resident CORTEX M2 skeleton as a build dependency (SQLite+FTS+local vectors serve S0–S4; the resident skeleton is CORTEX's own stage, later, over the same artifacts). No hypercell/KEEL/BRAIN imports (the fabric may *call* scriptorium someday; never the reverse). No fifth API call-site outside `ds.py`. No un-span-cited assertion in any deliverable — the certificate refuses to ship below the citation bar, and that refusal *is* the product working.

## Appendix A · DeepSeek compatibility cheat sheet (verified 2026-07-31)

- Endpoints: OpenAI-format `https://api.deepseek.com` (primary); Anthropic-format `https://api.deepseek.com/anthropic`; Responses API currently Flash-only (optional adapter).
- Model string `deepseek-v4-flash`; thinking **default ON** — disable per-call via `thinking: {"type":"disabled"}` (OpenAI SDK: `extra_body`); efforts `low/high/max`; CoT arrives in `reasoning_content` (journaled, never cited).
- Thinking mode **ignores** `temperature/top_p` silently → determinism claims are legal only in non-thinking calls (hence PS-2). `frequency_penalty`/`presence_penalty` deprecated — never send.
- JSON mode: `response_format={"type":"json_object"}` + the word "json" + an example in the prompt + explicit `max_tokens`; empty-content is a known failure → PS-3 retry ladder. No server-side schema → pydantic validates, client-side.
- Caching: automatic, exact-prefix, unit-boundaried, hours-to-days persistence; usage returns `prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` (+ `reasoning_tokens` under `completion_tokens_details`) → the meter reads them per call (PS-4/PS-8).
- Concurrency 2500 (Flash); announced peak/off-peak (×2 in 9:00–12:00, 14:00–18:00 Beijing; date TBD) → PS-7.
- Tool calls: ≤128 functions; inside tool loops with thinking, `reasoning_content` must be passed back or 400 — workers are single-shot (PS-10).
- Bonus, not a dependency: the Anthropic-format endpoint means the *coding harness that builds this* can itself run on Flash (`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`) — the organ that reads a lifetime can be built on the same nearly-free cognition it spends.

---
*Lineage: organ family (2026-06) → CORTEX v0.4 (07-01) → CORTEX v2 + SCRIPTORIUM protocol (07-31) → this build spec (07-31, same day Flash 0731 made the economics almost embarrassing). Ratification hooks: operator approves §1 PS-laws + §3 Tape placement + §7 ladder; S1's `freeze` is the per-corpus gate. The scribes are stateless; the notes remember; the fence certifies; the negatives are forever.*
