# Workflow with Claude Code: 2026-11-20 to 2026-12-02

Replaces `FLUJO.md` (Spanish). Phase prompts: `docs/PROMPTS.md`.

## The rule above all others

Code freezes on **Thursday 2026-11-26**. Friday 27 is the dry run with real phones. From the 28th to the 1st, only bug fixes. If a phase slips, cut scope (see "What to cut"), never move the freeze.

## Two tracks in parallel

The API and UI are separate repos, so they are built in **two Claude Code sessions at the same time**, both started from the parent folder. Phase 0 writes the shared API contract (`docs/API.md`) first; until the real API is ready, the UI works against a fake backend that follows the contract.

| Day | API track (`prompt-battle-api/`) | UI track (`prompt-battle-ui/`) |
|---|---|---|
| Fri 20 | **Phase 0 — plan** (parent folder, one session): `docs/PLAN.md`, `docs/API.md` | Accounts and keys (`docs/PROVIDERS.md`), Railway and Cloudflare accounts |
| Sat 21 | **A1 — game core**, cities, fake providers, REST, snapshot, CI | **U1 — foundation**: scaffold, design tokens, i18n, themes, shell, CI/CD to Cloudflare + GitHub Pages |
| Sun 22 | **A2 — providers**, failover, scoring, probe | **U2 — player screens** |
| Mon 23 | **A3 — commentary, moderation, extras**; first Railway deploy | **U3 — stage and admin screens** |
| Tue 24 | **I1 — integration** (one session): Docker Compose, end to end on `fake`, both deploys, CORS, real probe | |
| Wed 25 | **I2 — hardening**: load test for 100 players, spec review, code review, runbook | |
| Thu 26 | **Freeze**: tag `v1.0-freeze` in both repos | |

## Model and effort in Claude Code

Claude Code 2.1.280 or later is required for Opus 5.5. Run `claude update` before starting.

| Work | Model | Effort | Why |
|---|---|---|---|
| Plan (phase 0) | Opus 5.5 | `high` | Architecture and API reading; a mistake here costs every phase |
| A1, A3, U1, U2, U3 | Opus 5.5 | `medium` | Clearly scoped work; Opus 5.5's default and the recommended level for defined features |
| A2, I1, I2 | Opus 5.5 | `high` | Concurrency, partial failures and edge cases: verification matters most here |
| One hard decision | Same | Write `ultrathink` in that prompt | Thinks harder for that turn without changing the session effort |

How to set it:
- At launch: `claude --model opus --effort high`
- Inside a session: `/model opus` and `/effort medium` (or `/effort high`)

**Don't use `max`.** The docs warn it has diminishing returns and tends to overthink.

**You don't need Fable.** Fable does best on long, ambiguous tasks worked autonomously. Here the spec removes the ambiguity and the work is split into short phases. Depending on your plan, Fable may also bill extra usage credits.

**If you approach your plan's limit:** use `/model opusplan` (plans with Opus, executes with Sonnet 5.5), or move U2 and U3 to `sonnet`.

## Step by step

### Friday 20 — Preparation and phase 0
1. Create the accounts and keys in `docs/PROVIDERS.md`, with spending limits. Buy fal.ai credits and note the concurrency limit in the dashboard.
2. Create the Railway (Hobby) and Cloudflare accounts (`docs/DEPLOYMENT.md`).
3. Copy `.env.example` to `.env` in the parent folder and fill in the keys.
4. Phase 0: `claude --model opus --effort high --permission-mode plan` in the parent folder, paste the phase 0 prompt.
5. Answer the interview. If a question is already answered in the spec or `docs/DECISIONS.md`, say so and let it continue.
6. Review `docs/PLAN.md` and `docs/API.md` (`Ctrl+G` opens the plan in your editor). Fix what you don't like before approving.
7. Commit in the parent repo: `docs: implementation plan and API contract`.

### Saturday 21 — A1 and U1 (two sessions)
- Session 1: `/clear`, `/effort medium`, phase A1 prompt. Clones and scaffolds `prompt-battle-api/`.
- Session 2: `/clear`, `/effort medium`, phase U1 prompt. Clones and scaffolds `prompt-battle-ui/`.
- At the end of each: `spec-reviewer` subagent review (loose prompt in `docs/PROMPTS.md`) and commit in that repo.
- **Quality gates:**
  - A1: the 2-city × 50-player simulation on `fake` passes and each city's podium comes out in the expected order.
  - U1: the empty shell deploys to Cloudflare Pages and GitHub Pages from `main`; language and theme toggles work and persist.

### Sunday 22 — A2 and U2
- A2 (`/effort high`). **Gate:** the probe against real providers works from your machine; the embedding determinism check gives a difference below 1e-4; WireMock tests cover fal and BFL queue polling.
- U2 (`/effort medium`). **Gate:** a full player flow against the fake backend at 360×800, in both languages and both themes. Check it on a real phone yourself, not only in the emulator.

### Monday 23 — A3 and U3
- A3 (`/effort medium`). First Railway deploy of the API. **Gate:** with the Anthropic key removed on purpose, the podium still works with canned comments in both languages.
- U3 (`/effort medium`). **Gate:** stage readable at 1920×1080 and 1280×720 on a real projector or TV; admin works on a laptop and a phone.

### Tuesday 24 — I1 integration (`/effort high`)
- Docker Compose in the parent folder; a full two-city event on `fake` with two stages, two admins and a few phones.
- Deploy both repos; run the probe in production.
- **Gate:** the deployed UI talks to the deployed API from both UI origins (Cloudflare and GitHub Pages).

### Wednesday 25 — I2 hardening (`/effort high`)
- Load test: 2 cities × 50 players on `fake` with the fake provider's concurrency set to your real fal.ai limit, then a `--real` run (40 images maximum).
- **Gate:** p95 generation ≤ 15 s and close → results ≤ 15 s in production.
- Write `docs/RUNBOOK.md`.

### Thursday 26 — Freeze
- Tag `v1.0-freeze` in both child repos. From here on, only bug fixes, each with its test.
- Generate and save the target images (see "How to choose the targets").

### Friday 27 — Dry run with 8 to 10 colleagues
Split them across two "cities" (two stages, two admins). Measure and write down:
1. Real time from "Generar" to visible image, on mobile data.
2. Whether Spanish prompts produce worse images than English ones. If so, set `PROMPT_TRANSLATE_TO_EN=true` and repeat a round.
3. Whether the score range is reasonable: not everyone near 0, not everyone near 100. If not, adjust the calibration prompts or change the targets.
4. Whether anyone misreads a screen, in either language. Fix the copy, not the flow.
5. A forced failover from one admin mid-round; check that both admins see the alert.
6. Language and theme toggles on the stage and admin screens.

### Saturday 28 to Monday 30 — Fixes only
- Each bug: a short Claude Code prompt with the symptom, the likely cause and a test that reproduces it first.
- Print each city's QR code large and prepare Plan B (Padlet + Slido from the earlier conversation), once per city.

### Tuesday 1 December — Pre-flight check
- Run the probe in production. It is the day OpenAI retires `gpt-image-1.5` and `gpt-image-1-mini`: confirm nothing uses them.
- Top up credits if needed and check spending limits.
- Reset the event and load the final rounds (practice + 2 scored rounds).
- Each city admin logs in with their own token and checks their stage.

### Wednesday 2 — Event (both cities)
Follow `docs/RUNBOOK.md` (written in I2). Summary per city:
- 60 minutes before: open admin and stage, run the probe, check alerts.
- 45 minutes of activity: entry by QR (0–5), practice (5–9), round 1 (9–18), mini-podium (18–21), round 2 (21–30), scoring and podium 5 → 1 (30–40), prizes and photo (40–45).
- If a provider fails, failover is automatic; otherwise either admin forces the backup. If everything fails, Plan B.
- **No deploys today.**
- After: export each city's CSV, reset the event, rotate the keys.

## Claude Code practices for the whole project

- **Start every session in the parent folder** so the shared `CLAUDE.md`, skills and agents load; the session then works inside the child folder for its track.
- **One session per phase.** Use `/clear` between phases and name each session with `/rename a2-providers` to resume it with `claude --resume`.
- **Independent review.** At the end of each phase, the `spec-reviewer` subagent reviews the diff in a clean context. Ask it to report only what affects behavior or requirements, to avoid over-engineering.
- **Verification with evidence.** Require Claude to show the output of `./mvnw verify`, the UI tests and build, the load test or screenshots. Don't accept "done" without evidence.
- **Correct early.** If it drifts, `Esc` stops it without losing context. `Esc` twice (or `/rewind`) goes back to an earlier point. If you correct the same thing twice, `/clear` and write a more precise prompt.
- **Commits per phase, in the right repo.** Claude Code checkpoints don't replace git. The parent repo never receives child code.
- **Secrets out of context.** `.claude/settings.json` denies Claude reading any `.env` file.

## What to cut if you're behind (in this order)
1. Automatic prompt translation and LLM moderation (leave them off).
2. Mini-podium after round 1.
3. The Cohere embedding adapter (no key; D-011).
4. (Done in phase 0: the Runware, OpenAI, Gemini image and Pollinations adapters are not built, D-011.)
5. LLM commentary (the canned ones remain).
6. The GitHub Pages backup deploy.

Never cut: the fixed seed per round, the fal.ai → BFL failover, per-city isolation, snapshot persistence, the claim code, Spanish and English copy, the probe.

## How to choose the targets
- Practice: a single simple object on a light background.
- Round 1: a scene with 2 or 3 elements and a strong style (for example, watercolor or pixel art).
- Round 2: a scene with local identity that works for both cities, such as a small-town Antioquia café at dawn or a *chiva* bus in the rain.
- Generate each target from the admin with the same provider and the round's seed, and keep the original prompt to reveal at the end.
- No logos, brands, well-known fictional characters or real people.
