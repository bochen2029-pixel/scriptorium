# RATIFIED — operator decisions of record

2026-07-31, operator, via chat (screenshots: DeepSeek key console, C:\_DAD\projects-mirror,
usage panel $17.31 balance / $2.68 lifetime, pricing docs page):

1. **Standing delegation.** "directly proceed agentically and autonomous on full
   autopilot and go for it, decide everything on my behalf" — recorded here per
   kickoff section 0 as the amendment channel. Scope: all build decisions,
   including S1 charter ratification-by-delegation. Every delegated decision is
   written down (here or STATE.md); operator review is invited at any time; a
   re-freeze after operator edits is cheap by design.
2. **S0 deviations BLESSED** (STATE.md "Deviations", decided on the operator's
   behalf under #1): stdlib docx extraction stands; walk-primary discovery with
   `everything` as reconciliation cross-check stands.
3. **Corpus #1 named:** `C:\_DAD\projects-mirror` — the operator's own working
   archive (mirrors of Claude Code project folders, mostly .jsonl session
   transcripts). Archive root (tape + manifest): `C:\_DAD\projects-mirror-archive`
   — a sibling, not the mirror itself, so a mirror re-sync can never clobber the
   Tape. Consent: operator's own material, operator-directed; sampled *text*
   going to the API at S1+ is the protocol's sovereignty split working as
   designed (pixels/audio still never leave the box).
4. **Budget posture.** Operator: Flash is "too cheap to meter" — but PS-8 stays
   law; caps set generously rather than removed: `discover` usd_cap $5.00,
   goldens scoring $2.00 per run. Session API key is repo-scoped
   (`scriptorium_cc`), lives in `.env` only (gitignored), operator deactivates
   it when the build-out ends.
5. **Price sheet verified** 2026-07-31 against api-docs.deepseek.com: matches
   scriptorium.lock exactly (DeepSeek-V4-Flash-0731; $0.14 / $0.0028 / $0.28
   per Mtok; 1M ctx; 384K max out; 2500 concurrency). Note for later rungs:
   Responses API is Flash-only today, Pro support "early August 2026" — the
   OpenAI-format /chat/completions path stays primary per PS-1.
6. **Tape generation v2 approved** (operator, 2026-07-31, "proceed according
   to your recommendation plan"): session-jsonl content extraction (voices
   kept: user/assistant text + summaries; envelope/thinking/tool traffic
   dropped; true content years from timestamps) as manifest opt-in
   `options.sessions: extract`. New archive root
   C:\_DAD\projects-mirror-archive-v2; v1 stays intact and verifiable
   (negatives forever, spec section 5 version law). Purpose: full P2 read at
   ~$70-110 instead of ~$315, with cleaner cards. v2 gets its own charter
   (discover + freeze re-run); the v1 charter stays bound to the v1 tape.
   RESULT (v2 intake done 2026-08-01): 1.753B -> 172.06M tokens = **10.2x
   compression** (better than 3-5x projected); full-read projection now **~$32**
   at the measured $0.184/M. Reconciliation 13958/13958 = 100.0%; 4 typed
   quarantines (2 .bin + 2 ocr_failed PDFs, OCR non-determinism vs v1's 2).
   Editorial consequence, ACCEPTED: extraction keeps the voice/decision layer
   (Bo's instructions + assistant text) and drops thinking + tool_use +
   tool_result, so this coding archive's actual code/command-outputs live only
   in v1 (raw negatives). A future v3 could keep tool_use code blocks if the
   work-product layer is ever wanted.

2026-09-01, operator, via chat (Claude Code session, dual-mode handoff):

7. **Survey docs stay local.** `_run_state/NEIGHBOR_ORGANS.md` + `_run_state/survey/*`
   (the 20-target machine survey) are deliberately NOT committed/pushed: they
   summarize the designs of the operator's other, unpublished repos (Intercom,
   KEEL, hypercell, everywhen, the DSH harness). They remain on-disk required
   reading for sessions on this box; the public scriptorium repo carries only
   scriptorium's own work. (Asked and answered explicitly; option "survey stays
   local" chosen over "push everything".)
8. **Two harnesses only.** The only agent harnesses in use or planned on this
   machine are DSH (C:\deepseek-harness-master) and Claude Code. Integration
   work (worker seams, wake adapters, A2A identity) targets exactly these two.
