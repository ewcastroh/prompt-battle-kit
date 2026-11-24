# Claude Code prompts, per phase

Paste each prompt as is into a **new** Claude Code session started in the **parent folder** (`/clear` between phases).
The "Model / effort" column says how to configure the session before pasting. Calendar: `docs/WORKFLOW.md`.

**Branches (D-028).** Every phase prompt below runs on its own branch in the repo it changes (for example `a4/<topic>`, or `a1/game-core` for the first phase), never on `main`. Where a prompt says "commit", it means a commit on that branch; the pull request is opened only when you confirm, and you merge it. The same applies to every later fix.

| Phase | Track | Model / effort | Mode |
|---|---|---|---|
| 0. Plan and API contract | Parent | Opus 5.5 · `high` | Plan mode (`claude --permission-mode plan`) |
| A1. Game core | API | Opus 5.5 · `medium` | Normal |
| A2. Providers, failover, scoring | API | Opus 5.5 · `high` | Normal |
| A3. Commentary, moderation, extras | API | Opus 5.5 · `medium` | Normal |
| U1. UI foundation | UI | Opus 5.5 · `medium` | Normal |
| U2. Player screens | UI | Opus 5.5 · `medium` | Normal |
| U3. Stage and admin screens | UI | Opus 5.5 · `medium` | Normal |
| I1. Integration and deploy | Both | Opus 5.5 · `high` | Normal |
| I2. Hardening | Both | Opus 5.5 · `high` | Normal |

---

## Phase 0 — Plan and API contract (plan mode, no code)

```text
Read CLAUDE.md, DESIGN.md, docs/DECISIONS.md, docs/SPEC.md, docs/PROVIDERS.md and docs/DEPLOYMENT.md completely. Do not write any code yet.

1. List every decision the spec leaves open, every contradiction, and every assumption you would otherwise make. Then interview me with the AskUserQuestion tool about the ones that change what you build. Skip anything the spec or DECISIONS.md already answers.
2. Check the current documentation for: the latest stable Spring Boot 4.1.x patch and Spring AI 2.0.x patch (and that they are compatible), the latest stable Angular 22.x and Transloco versions, the fal.ai queue API for fal-ai/flux-2/klein/9b, the Black Forest Labs API for FLUX.2 [klein] 9B, the Runware API for FLUX.2 [klein] 9B, OpenAI gpt-image-2.5-flare, Gemini gemini-nano-banana-2.1 and gemini-embedding-2, Cohere embed-v4.0 image embeddings, and the Anthropic model claude-sonnet-5-5 through Spring AI. Note request/response shapes, seed support, safety parameters and concurrency limits. Record links.
3. Write docs/API.md: the full HTTP contract from SPEC §9 (paths, request and response JSON with examples, status codes, error codes from §9.5, ETag behavior, CORS). Both tracks build against it.
4. Write docs/PLAN.md with phases A1–A3, U1–U3, I1–I2 matching docs/PROMPTS.md. For each phase: files to create, the tests that prove it works, risks, and what is explicitly out of the phase. Decide the UI's API_BASE_URL mechanism (SPEC §7.1) and record it. Add a section "Provider API notes" with what you found in step 2. Keep PLAN.md under 350 lines.
5. Add any new decision to docs/DECISIONS.md.

Stop after writing the plan so I can review it.
```

## A1 — Game core (offline, fake providers)

```text
Work in prompt-battle-api/. If the folder does not exist, clone https://github.com/ewcastroh/prompt-battle-api.git into it.

Implement phase A1 from docs/PLAN.md: project skeleton (use the create-spring-boot-java-project skill, but no database and no Spring Security), the `game` domain and per-city state machine, city configuration, the fake image and embedding providers, the score calculator, per-city ranking, snapshot persistence, the player/stage/admin REST endpoints from docs/API.md needed to play a full event, admin token → city mapping, ProblemDetail error codes, CORS, the forbidden-models startup guard, the repo's CLAUDE.md, README.md and the GitHub Actions CI workflow. No real providers.

Follow SPEC sections 2, 3, 4.1, 7.2–7.4, 8, 9, 14.1 (items 1, 4, 5, 6).
Write the tests first for: state transitions and 409s, per-city isolation, attempt accounting, auto-entry at close, grace period, ranking with both tie-breaks, score normalization, nickname validation and per-city uniqueness, admin cross-city rejection, round definition lock, snapshot restore, CORS, and the 2-city × 50-player simulation on the `fake` profile.

Done means: `./mvnw verify` passes and you show me the output. Then commit "a1: game core" in prompt-battle-api (do not push until I confirm).
```

## A2 — Real providers, failover and scoring

```text
Work in prompt-battle-api/. Implement phase A2 from docs/PLAN.md: the fal (queue API) and bfl image adapters (Runware, OpenAI and Gemini image are not built, D-011), the gemini and cohere embedding adapters, the per-provider executors with their own concurrency limits and the shared FIFO queue, the optional load split, the circuit breaker and event-wide failover with alerts, eager embeddings, re-embedding a whole city run on embedding failover, the determinism check, the admin provider endpoints and the probe endpoint.

Follow SPEC sections 4.2, 4.3, 5, 7.6, 11 and 14.1 (items 2 and 3).
Before each adapter, re-read that provider's current docs (start from docs/PROVIDERS.md); put model IDs only in configuration. Test every adapter with WireMock (success, 429 then success, timeout, safety block including fal's black-image flag, malformed response, queue polling where it applies). Test that SAFETY_BLOCKED never triggers failover, that embeddings are never mixed within a city run, and that the load split only uses listed providers.

ultrathink about the concurrency between the shared generation queue, the per-provider limits, the two cities' round timers and the grace period before you code it.

Done means: `./mvnw verify` passes and you show me the output. Then commit "a2: providers and scoring".
```

## A3 — Commentary, moderation and extras

```text
Work in prompt-battle-api/. Implement phase A3 from docs/PLAN.md: the commentary service with Spring AI ChatClient (Anthropic) returning Spanish and English in one call, with the fallback comments in both languages; the moderation blocklist with normalization; optional LLM moderation and optional prompt translation behind their flags; the per-city results CSV export; the global event reset with typed confirmation; the Dockerfile (single instance, DATA_DIR volume).

Follow SPEC sections 4.4, 5.6, 6 and 9.3. Comments must be precomputed before the reveal; test that the reveal never waits on an AI call and that a commentary failure falls back to a canned comment in both languages.

Done means: `./mvnw verify` passes and you show me the output. Then commit "a3: commentary and moderation". Then walk me through the Railway setup in docs/DEPLOYMENT.md for the first deploy.
```

## U1 — UI foundation

```text
Work in prompt-battle-ui/. If the folder does not exist, clone https://github.com/ewcastroh/prompt-battle-ui.git into it.

Implement phase U1 from docs/PLAN.md: scaffold the app with the angular-new-app skill (latest stable Angular, no SSR, Vitest, --ai-config=claude), then: routes from SPEC §10.1 with a city guard, the API_BASE_URL mechanism from PLAN.md, an HTTP layer that maps ProblemDetail `code` to translation keys, Transloco with es (default) and en and a key-parity check, the design tokens, theme mechanics and settings menu from DESIGN.md (§2–§6), self-hosted fonts, an app shell for player/stage/admin, a fake backend that follows docs/API.md for local development, the repo's CLAUDE.md and README.md, and the GitHub Actions CI/CD workflow from docs/DEPLOYMENT.md (Cloudflare Pages + GitHub Pages backup).

Before writing any CSS or HTML, run the modern-web-guidance skill for each pattern (dark mode toggle, design tokens, popover menu, typography). Use the angular-developer skill for Angular code.
Write tests for: language switch and persistence, the two-state theme toggle rules in DESIGN.md §2, error-code mapping, the city guard, translation key parity.

Done means: lint, tests and `ng build` pass and you show me the output, plus screenshots of the shell in both languages and both themes at 360×800. Then commit "u1: foundation" (do not push until I confirm).
```

## U2 — Player screens

```text
Work in prompt-battle-ui/. Implement phase U2 from docs/PLAN.md: the player screens from SPEC §10.4 (join, lobby, round open with prompt editor, generation status, attempts gallery and entry selection, round closed, final result), polling with ETag at most every 1.5 s, and token storage per city.

Follow DESIGN.md §7 for every component and run modern-web-guidance for each UI pattern (forms, textarea counter, dialog for image zoom, live regions). Use the mobile-native skill for phone behavior and break-ui to test worst-case data (long nicknames, emoji, long prompts, errors).

Check yourself: usable at 360×800 with no horizontal scroll, tap targets ≥ 44 px, both languages, both themes, reduced motion, no requests to third-party origins. Take screenshots of each player screen in es/light and en/dark.

Done means: lint, tests and build pass, Playwright smoke test passes against the fake backend, screenshots reviewed, and you show me all of it. Then commit "u2: player screens".
```

## U3 — Stage and admin screens

```text
Work in prompt-battle-ui/. Implement phase U3 from docs/PLAN.md: the stage screens from SPEC §10.5 (lobby with QR, round open, scoring, mini-podium, podium reveal with score count-up, commentary in the stage's language, confetti for #1, hidden prompts) and the admin console from SPEC §10.6 (token login bound to the route's city, shared round builder, own-city controls, players, entries, provider panel, alerts, CSV, reset with typed confirmation).

Follow DESIGN.md and run modern-web-guidance for each UI pattern (tables, dialogs, buttons, motion). Check: stage readable at 1920×1080 and 1280×720; podium reveals exactly one entry per admin "Next"; the stage never shows images during an open round; admin usable on a laptop and a phone; both languages and themes.

Done means: lint, tests and build pass, screenshots of every stage phase and the admin page reviewed, and you show me both. Then commit "u3: stage and admin".
```

## I1 — Integration and deploy

```text
Work in the parent folder and both child folders. Implement phase I1 from docs/PLAN.md:
1. docker-compose.yml in the parent (api on `fake` by default, ui on nginx with single-page app fallback) and the UI Dockerfile.
2. Replace the UI's fake backend with the real API; fix every contract mismatch against docs/API.md (update API.md if the contract itself was wrong, and tell me).
3. Play a full two-city event with Compose: two stages, two admins, a few simulated players per city. Take screenshots.
4. Deploy: API to Railway, UI to Cloudflare Pages and GitHub Pages, following docs/DEPLOYMENT.md. Verify CORS from both UI origins and run the probe in production.

Done means: the full event works locally and in production, with evidence. Commit in each repo that changed.
```

## I2 — Hardening

```text
Implement phase I2 from docs/PLAN.md:
1. scripts/loadtest.sh in prompt-battle-api (SPEC §14.3): run it against the `fake` profile with the fake provider's concurrency set to <my fal.ai limit>, and show p50/p95/max and errors per city. Then a `--real` run against production (40 images maximum).
2. Use the spec-reviewer subagent to review both repos against docs/SPEC.md §14 and the Definition of Done. Fix only gaps that affect correctness or stated requirements.
3. Run /code-review on each repo's full diff since its first commit.
4. Write docs/RUNBOOK.md in the parent: start, probe, what to do when a provider fails mid-round, podium operation per city, switching to the GitHub Pages backup, reset, and Plan B (no platform), for both cities.

Done means: both repos green, the load test within SPEC §13 limits on `fake`, review findings resolved or listed with a reason. Then commit and tag v1.0-freeze in both child repos.
```

---

## Useful loose prompts

After each phase (independent review):
```text
Use the spec-reviewer subagent to review the diff of the last commit in <prompt-battle-api|prompt-battle-ui> against docs/SPEC.md, docs/API.md and docs/PLAN.md (and DESIGN.md for the UI). Report only gaps that affect correctness or the stated requirements.
```

Real-provider check (already deployed, with keys):
```text
Call POST /api/admin/providers/probe on the deployed API with the Medellín admin token from my environment and summarize latency, errors and the embedding determinism result per provider. Do not change code.
```

If you correct Claude twice on the same thing: `/clear` and ask again with what you learned, in a more specific prompt.
