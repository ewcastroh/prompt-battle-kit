# Implementation plan

Version 1.0 · 2026-11-20 (phase 0). Inputs: `docs/SPEC.md`, `docs/DECISIONS.md` (D-011…D-020 are new today), `docs/API.md`, `DESIGN.md`. Prompts per phase: `docs/PROMPTS.md`. Calendar: `docs/WORKFLOW.md`.

## 1. Summary

| Track | Phases | Repo |
|---|---|---|
| API | A1 game core → A2 providers and scoring → A3 commentary, moderation, extras | `prompt-battle-api/` |
| UI | U1 foundation → U2 player → U3 stage and admin | `prompt-battle-ui/` |
| Both | I1 integration and deploy → I2 hardening | both + parent |

**Versions (D-014):**
- API: Java 25, Spring Boot **4.2.0**, Spring AI **2.1.0**, Maven wrapper.
- UI: Angular **22.3.0**, Transloco **8.4.0**, Node 24 LTS, TypeScript 6.0, Vitest (Angular default), Playwright.
- Pin exact versions and never upgrade implicitly.
- Retreat (owner decision only): Boot 4.1.3 + Spring AI 2.0.3.

**Provider setup (D-011, D-012, D-013):**
- Images: chain `fal,bfl`; `IMAGE_LOAD_SPLIT=fal,bfl` in overflow mode; `FAL_MAX_CONCURRENCY=10`.
- Embeddings: `gemini-embedding-2` on the free tier, `EMBEDDING_MODE=entries`.
- Commentary: `claude-sonnet-5-5` through Spring AI.
- Not built: Runware, OpenAI, Gemini image, Pollinations.

**Base package (API):** `io.github.ewcastroh.promptbattle`. Packages per SPEC §7.3; `game` has no Spring imports.

## 2. UI `API_BASE_URL` mechanism (D-017)

Runtime `config.json`, one build for every target:
- `public/config.json` (dev default): `{ "apiBaseUrl": "http://localhost:8080" }`.
- `provideAppInitializer(() => inject(AppConfig).load())` fetches `config.json` relative to `document.baseURI` (works under `/prompt-battle-ui/` on GitHub Pages) before routing. If it fails, the app shows a static error page; there is no hard-coded fallback.
- **CI:** both deploy jobs overwrite `dist/…/browser/config.json` from the GitHub Actions variable `API_BASE_URL` after `ng build`.
- **Docker:** the nginx image's entrypoint writes `config.json` from env `API_BASE_URL` (`envsubst`) before starting nginx.
- **Caching:** Cloudflare `_headers` sets `/config.json` to `Cache-Control: no-cache`; nginx does the same.
- **Fake backend:** an Angular build configuration `fake` (`ng serve -c fake`) swaps in a fake-backend interceptor through `fileReplacements`. Production bundles never contain it.

## 3. Cross-cutting rules for every phase

- Contract: `docs/API.md` is the source of truth. Any change goes there first (and into its change log).
- Tests first for game rules. The API never calls real providers in tests (`fake` profile, WireMock).
- One serialized mutation path: `GameEngine` runs commands on a single-thread executor. Controllers, timers, generation callbacks and scoring completions submit commands and never touch state directly.
- Per-city isolation is tested by asserting the other city's state is byte-identical (snapshot JSON) after each command.
- No new dependency beyond this plan without asking. Planned dependencies:
  - API: `spring-boot-starter-web`, `-actuator`, `-validation`; `spring-ai-starter-model-anthropic`; `com.google.zxing:core` + `javase`; tests: `wiremock-spring-boot` (fallback `wiremock-standalone`), AssertJ, Awaitility.
  - UI: `@jsverse/transloco`, `@playwright/test`. Icons, fonts and the confetti choice are confirmed in U1 (DESIGN.md §11).

---

## A1 — Game core (offline, `fake` profile)

**Goal:** a full two-city event playable through the REST API with fake providers; snapshot and restore; CI green.

**Files (`prompt-battle-api/`):**
- Build and repo: `pom.xml`, `mvnw`, `.mvn/`, `.gitignore`, `.env.example`, `CLAUDE.md`, `README.md`, `.github/workflows/ci.yml` (Temurin 25, `./mvnw -B verify`, actions pinned by SHA).
- `config/`:
  - `AppProperties` (`@ConfigurationProperties`, every SPEC §11.1 variable plus D-013 `EMBEDDING_MODE`, `GEMINI_EMBEDDING_RPM`/`_TPM`/`_RPD`, `GEMINI_EMBEDDING_DIMENSIONS`).
  - `ForbiddenModelsGuard` (reads `forbidden-models.txt`; fails startup on a match).
  - `ClockConfig`.
- `city/`: `CityCatalog` (parses `CITIES`, validates codes `[a-z]{2,8}`), `AdminTokens` (`ADMIN_TOKEN_<CODE>` ≥ 24 chars, constant-time `MessageDigest.isEqual`).
- `game/` (no Spring):
  - `EventState`, `RoundDefinition`, `Calibration`, `CityRun`, `RoundRun`, `Player`, `Attempt`, `Entry`, `Phase`, `RunStatus`.
  - `GameEngine` (command executor), `commands/*`, `GameException(ErrorCode, params)`.
  - `Ranking`, `ScoreCalculator` (cosine, floor, normalization), `NicknameRules`, `PromptRules`, `ClaimCodes`, `RoundTimers` (round end, grace).
- `generation/` (A1 part):
  - `ImageGenerator` port, `GenerationRequest`, `GenerationResult` (sealed: `Success | Failure(kind)`).
  - `FakeImageGenerator`: a deterministic JPEG from `hash(prompt, seed)`; writes the prompt in a JPEG COM segment.
  - A simple `GenerationQueue` (FIFO + one executor; A2 replaces its dispatcher).
- `scoring/` (A1 part): `EmbeddingProvider` port, `FakeEmbeddingProvider`, `RunScorer` (floor + scores for a city run).
  - Targets embed to a fixed unit vector.
  - A prompt containing `[sim=0.83]` embeds to a vector with exactly that cosine to the target; other prompts get a hash-based vector.
  - This gives simulations a known podium order.
- `commentary/` (A1 part): `CommentaryPort` + `FallbackCommentary` (canned es/en by score band); the files `commentary/fallback-es.txt` and `-en.txt`.
- `persistence/`:
  - `SnapshotStore`: JSON of `EventState`, atomic write (temp file + `ATOMIC_MOVE`); every 10 s and on every phase transition; restore on startup.
  - `ImageStore`: `DATA_DIR/images/{uuid}.jpg` + `_thumb.jpg`, via ImageIO; resize and center-crop.
- `web/`:
  - Controllers: `CityController`, `PlayerController`, `StageController`, `ImageController`, `QrController` (ZXing).
  - Errors: `ApiExceptionHandler` (ProblemDetail + `code` + `params`), `ErrorCode` enum (all of API.md §2).
  - Infrastructure: `CorsConfig`, `EtagSupport` (weak ETag over the serialized body, 304), `PlayerAuthResolver`, `RateLimiter` (per token 30 writes/min; per IP 120 joins/min).
- `admin/`: `AdminAuthInterceptor`, `AdminStateController`, `AdminRoundController` (generate-target, CRUD, multipart, calibrate), `AdminRunController` (start/close/extend/rescore, mini-podium, podium, practice gallery), `AdminPlayerController`, `AdminEntryController`, `AlertsController`, `EventResetController`.
- `src/main/resources/`: `application.yml`, `application-fake.yml`, `forbidden-models.txt`, `moderation/blocklist.txt` (placeholder; filled in A3).

**Tests (JUnit 5 + AssertJ; `./mvnw verify`):**
- `GameEngineTransitionsTest`: every row of API.md §4, plus a 409 `INVALID_TRANSITION` for each invalid pair; timer auto-close; extend; practice → `LOBBY`.
- `CityIsolationTest`: every command on `mde` leaves the `bog` snapshot unchanged.
- `AttemptAccountingTest`: a success consumes; failure and block don't; 3 blocks → flagged; one in flight; `NO_ATTEMPTS_LEFT`.
- `CloseAndGraceTest`: auto-entry = last `DONE`; a result after grace is discarded; scoring starts when the run is idle (D-018).
- `RankingTest`: totals, tie-breaks 1 and 2, hidden and kicked excluded, podium sizes < 5, best-entry selection (D-015), frozen ranking + hide recompute.
- `ScoreCalculatorTest`: clamp, rounding to one decimal, anchor exclusion at cos > 0.9.
- `NicknameRulesTest`: length, charset, per-city uniqueness, case and accents; the same nickname in two cities is allowed.
- `ClaimCodeTest`: alphabet, uniqueness.
- `AdminAuthTest`: token → city; cross-city → 403; bad token → 401; short token → startup failure.
- `RoundLockTest`: edit, delete and calibrate → `ROUND_LOCKED` after any start.
- `ForbiddenModelsGuardTest`.
- `SnapshotRestoreTest`: run a partial two-city event, restart the context on the same `DATA_DIR`, get identical state.
- `CorsTest`: allowed origin, exposed headers, refused origin, preflight.
- `EtagTest`: 304 on match; a new ETag after a change.
- `ApiContractTest`: JSON field names and shapes match API.md examples (MockMvc + JSON assertions) for `/api/me`, stage state, admin state, round.
- `TwoCitySimulationTest` (`fake`, SPEC §14.1-4): 2 × 50 players; practice + 2 scored rounds; cities start at different times; known podium order per city; `next` reveals exactly one entry; stage never exposes unrevealed entries or the other city.

**Risks:**
- Boot 4.2 is two days old: a fast smoke build on day 1; retreat only with the owner's approval.
- Jackson 3 (`tools.jackson.*`) in snapshot (de)serialization: test round-trips.
- Timer races with the engine: timers only submit commands that check `endsAt` and the phase.

**Out of A1:** real providers, the circuit breaker, load split, rate-limited embeddings, Anthropic, the blocklist content, LLM moderation, translation, CSV, Dockerfile.

## A2 — Real providers, failover and scoring

**Goal:** real image generation on fal and BFL with overflow split and failover, Gemini embeddings within free-tier limits, probe.

**Files:**
- `generation/`:
  - `FalImageGenerator`: queue API; uses the `status_url` and `response_url` returned at submit; `X-Fal-Request-Start-Timeout`.
  - `BflImageGenerator`: polls `polling_url`; downloads `result.sample` at once.
  - `ProviderSlots` (a semaphore per provider).
  - `GenerationDispatcher`: shared FIFO across both cities; the queue position is exposed. Dispatches to the active provider; if `IMAGE_LOAD_SPLIT` is set, to the first listed healthy provider with a free slot.
  - `CircuitBreaker`: own small class; 3 failures in 30 s → open 60 s → half-open probe. `SAFETY_BLOCKED` never counts.
  - `ProviderRegistry`: active provider, chain, forced switch, alerts.
  - `RetryPolicy`: 1 retry, jitter, honors `Retry-After` / `X-Fal-Needs-Retry`.
  - `LatencyStats` (p50 and p95 over the last 200 calls).
- `scoring/`:
  - `GeminiEmbeddingProvider`: `:embedContent`, one image per content, 768 dims.
  - `EmbeddingRateLimiter`: sliding minute window for RPM 90 and TPM 27K (tokens from `usageMetadata`); a daily counter (RPD 1000, midnight Pacific) with alert `EMBEDDING_QUOTA_LOW` at 80 %.
  - `EmbeddingService`: modes `entries` | `eager`; cache by `(imageId, provider)`; entries first at close.
  - `DeterminismCheck`: averaging mode when diff > 1e-4.
  - `RunScorer` failover: re-embed target, anchors and every entry with the next provider; records the provider.
  - `CohereEmbeddingProvider`: **last; first cut**.
- `admin/`: `ProviderController` (get, force active), `ProbeService` (1 image per configured provider, embedding ×2, 1 commentary call).
- `application.yml`: model IDs only here and in env vars (`FAL_MODEL`, `BFL_MODEL=flux-2-klein-9b`, `GEMINI_EMBEDDING_MODEL`).

**Tests:**
- WireMock per adapter (SPEC §14.1-2):
  - fal: submit → `IN_QUEUE` → `IN_PROGRESS` → `COMPLETED`; `has_nsfw_concepts: [true]` → `SAFETY_BLOCKED`; 422 `content_policy_violation` → `SAFETY_BLOCKED`; 429 then success; `COMPLETED` with `error`; timeout; malformed JSON.
  - BFL: `Pending` → `Ready` + sample download; `Request Moderated` and `Content Moderated` → `SAFETY_BLOCKED`; 429 then success; 402 no retry; expired sample (404) → `PROVIDER_ERROR`; timeout; malformed.
  - Gemini: success (asserts `inline_data` and the dimensions field), 429 `rate_limit_exceeded` then success, `quota_exceeded`, malformed.
  - Cohere: success, 429, malformed (if built).
- `FailoverTest`: 3 failures switch the active provider for all open runs with an alert; `SAFETY_BLOCKED` ×10 never switches; a forced switch raises `PROVIDER_FORCED`.
- `LoadSplitTest`: overflow goes to BFL only when fal's slots are full; providers outside the list are never used; each attempt records its provider.
- `QueueFairnessTest`: one FIFO across cities; per-provider limit never exceeded (concurrent counter); queue positions decrease.
- `EmbeddingConsistencyTest`: a forced Gemini failure at scoring re-embeds the whole run (with a fake second provider); runs are never mixed; `SCORING_FAILED` + `rescore` path.
- `EmbeddingModeTest`: in `entries` mode, non-entry attempts are never embedded. `EmbeddingRateLimiterTest`: RPM, TPM and RPD limits, 80 % alert.
- `DeterminismCheckTest`, `ProbeServiceTest` (WireMock).

**Risks:**
- fal's status and result URLs use only the app id: always use the URLs returned at submit.
- The Gemini dimensions field placement conflicts between pages: WireMock asserts one form; the probe confirms it against the live API on day 1.
- Free-tier quota (100 RPM / 30K TPM / 1K RPD): `EmbeddingRateLimiterTest` covers all three, including the 80 % alert.
- The two image paths (fal vs BFL) give different pixels for the same seed (accepted, D-012).

**Out of A2:** Runware, OpenAI, Gemini image, Pollinations (D-011), Spring AI commentary, moderation.

## A3 — Commentary, moderation, extras

**Files:**
- `commentary/SpringAiCommentary`:
  - `ChatClient` with the target and entry images (`Media` JPEG), score and rank.
  - Native structured output `{es,en}` (`additionalProperties:false`), per-call timeout 8 s, `max-retries: 0`.
  - `ContentFilteredException`, timeouts and anything else → `FallbackCommentary`. Precomputed at scoring (mini) and at `podium/start` (final).
- `moderation/`:
  - `TextNormalizer`: lowercase, strip accents, leetspeak `4→a 3→e 1→i 0→o 5→s @→a`, collapse repeated letters.
  - `Blocklist` + `moderation/blocklist.txt` (es + en).
  - `LlmModerator` (`PROMPT_LLM_MODERATION`, `{allowed}`), `PromptTranslator` (`PROMPT_TRANSLATE_TO_EN`, stores `promptEn`).
- `admin/ResultsCsvController`, `EventResetService` (delete snapshot + images, clear state).
- `Dockerfile`: multi-stage Temurin 25 build → JRE 25 runtime, non-root, `VOLUME /data`; a comment says ONE instance only.

**Tests:**
- `CommentaryFallbackTest`: the model throws, times out, or is filtered → canned es and en by band.
- `RevealNeverWaitsTest`: the commentary stub sleeps 30 s, and `podium/next` and `mini-podium/next` still return in < 200 ms.
- `CommentaryWireMockTest`: Anthropic stubbed; asserts the `Authorization: Bearer` header and the JSON schema in the request.
- `BlocklistNormalizationTest`: accents, leetspeak, repeats, nickname and prompt.
- `LlmModerationFlagTest`, `TranslationFlagTest`, `ResultsCsvTest`, `EventResetTest` (401 for old tokens, empty `DATA_DIR`).

**Then:** the first Railway deploy following `docs/DEPLOYMENT.md` (owner at the keyboard; Claude guides).

**Out of A3:** load testing, the runbook, UI.

---

## U1 — UI foundation

**Files (`prompt-battle-ui/`):**
- Scaffold with `angular-new-app` (no SSR, Vitest, `--ai-config=claude`).
- `src/app/app.config.ts`: zoneless (default), `provideHttpClient(withFetch(), withInterceptors([apiBaseUrl, problemDetail]))`, `provideAppInitializer(config)`, Transloco.
- `src/app/app.routes.ts`: `/`, `/play/:city`, `/stage/:city`, `/admin/:city`, unknown → not-found.
- `core/config/app-config.ts`: D-017.
- `core/api/`: `api-base-url.interceptor.ts`, `problem.interceptor.ts` (ProblemDetail → `ApiError{code,params,status}`), `error-messages.ts` (code → `errors.<CODE>`), typed models from API.md (`api.models.ts`).
- `core/i18n/`: `transloco-loader.ts` (`public/i18n/{lang}.json`), `language.service.ts` (localStorage `lang`, `<html lang>` = `es-CO` | `en`).
- `core/theme/theme.service.ts`: DESIGN.md §2 two-state rules, `storage` and `matchMedia` change listeners.
- `core/city/city.guard.ts`: `GET /api/cities`, cached.
- `shared/`: `app-header`, `settings-menu` (popover), `icon` component.
- `src/index.html`: color-scheme meta + inline script, text-scale meta.
- `src/styles/`: `@layer` order, `reset.css`, `tokens.css` (DESIGN.md §3–5), `base.css`.
- `public/`: `fonts/*.woff2` (self-hosted), `i18n/es.json` + `en.json`, `config.json`, `_headers`.
- `src/app/fake-backend/`: an in-memory implementation of API.md (dev only, build config `fake`).
- `scripts/check-i18n-keys.mjs`.
- `.github/workflows/ci-cd.yml` (verify → deploy-cloudflare + deploy-github-pages with `--base-href /prompt-battle-ui/`, `404.html`, `config.json` written from `vars.API_BASE_URL`).
- `CLAUDE.md`, `README.md`.

**Tests (Vitest):** `language.service` (switch, persist, `<html lang>`), `theme.service` (every DESIGN.md §2 rule incl. "never remove on later match"), `problem.interceptor` + `error-messages` (every API.md §2 code has es and en keys), `city.guard`, `app-config` (base-href-relative fetch), key parity script.

**Risks:** Transloco 8.4 declares only `>=16` as its Angular peer, so verify with the build on day 1. GitHub Pages base href with `config.json` and the fonts.

**Out of U1:** feature screens.

## U2 — Player screens

**Files:**
- `features/player/`:
  - `player-state.service.ts`: polls `/api/me` ≤ 1.5 s with `If-None-Match`, 304 → keep the signal; pauses when hidden; backoff; token in localStorage key `pb.token.<city>`; 401 → clear the token and rejoin.
  - Screens: `join`, `lobby`, `round-open` (target + zoom `<dialog>`, countdown with server offset, `prompt-editor`, `generate-button`, `generation-status` live region, `attempt-card` gallery with submit and selected badge), `round-closed`, `final` (rank, total, claim-code message).
- Playwright: `e2e/player.spec.ts` + `playwright.config.ts` (360×800, es/en × light/dark).

**Tests:**
- Vitest: polling/ETag, the countdown math, the state → screen mapping per phase, attempt-card states, the prompt counter.
- Playwright smoke: join → generate → submit → round closed against the fake backend; no horizontal scroll; no third-party requests (`page.on('request')`); tap targets ≥ 44 px.

**Risks:** iOS Safari (`light-dark()` fallback, the 100vh bug, input zoom); slow mobile data (thumbnails, `loading="lazy"`).

**Out of U2:** stage and admin.

## U3 — Stage and admin screens

**Files:**
- `features/stage/`: `stage-state.service.ts`; `lobby` (QR, URL, counter, nicknames), `round-open` (target, huge countdown, submissions), `scoring`, `reveal` (mini/podium step with score count-up, `prompt`, commentary in the stage language, confetti for #1 inside `prefers-reduced-motion: no-preference`), `finished` (hidden prompts), `practice-gallery`.
- `features/admin/`: `admin-auth` (token in localStorage `pb.admin.<city>`, `/api/admin/me` city check, log out), `dashboard` (state, start/close/extend/rescore, big Next for mini and podium, podium preview), `round-builder` (generate preview / upload multipart, calibration status, edit/delete), `players` table, `entries` table (thumb, provider, model, cos, floor, score, hide), `providers` panel + probe, `alerts`, CSV download via `fetch` → blob, `reset` dialog (type `RESET`).

**Tests:**
- Vitest: the reveal renders only `entries`, the count-up end state with reduced motion, the admin city mismatch, the CSV download call, the reset confirmation gating.
- Playwright: stage at 1920×1080 and 1280×720 (screenshots); admin at a laptop size and 360×800.

**Out of U3:** real API wiring (I1).

---

## I1 — Integration and deploy

**Files:**
- Parent `docker-compose.yml`:
  - `api`: build `./prompt-battle-api`, `SPRING_PROFILES_ACTIVE=fake`, `./data:/data`, `.env`, port 8080.
  - `ui`: build `./prompt-battle-ui`, port 4200:80, `API_BASE_URL=http://localhost:8080`.
- UI `Dockerfile` (node build → nginx), `nginx.conf` (SPA fallback, `config.json` no-cache), `docker-entrypoint.d/40-config.sh`.

**Steps:**
1. Compose up.
2. Run the Playwright smoke against the real API (`fake` profile).
3. Fix contract mismatches; if API.md itself was wrong, update it and report.
4. A full two-city event with screenshots.
5. Deploy the API to Railway and the UI to Cloudflare + GitHub Pages.
6. `curl -H "Origin: …"` from both UI origins (CORS); probe in production.

**Tests:** the Compose e2e run; the production CORS check; the probe output saved to the I1 report.

**Risks:** Railway volume permissions for a non-root user; Cloudflare `_headers`; GitHub Pages deep links.

## I2 — Hardening

**Files:**
- `prompt-battle-api/scripts/loadtest.sh` wraps `scripts/LoadTest.java` (single-file `java` launch, JDK `HttpClient`, no deps): 2 cities × 50 virtual players × 3 attempts in 120 s; prints p50/p95/max and errors per city. `--real` caps total generations at 40.
- Parent `docs/RUNBOOK.md`.

**Steps:**
1. Load test on `fake` with `FAKE_MAX_CONCURRENCY=10` (fal), plus a second fake provider with 24 (BFL) and the split on; then a `--real` run (≤ 40 images ≈ US$0.25–0.60).
2. `spec-reviewer` review of both repos, then `/code-review` of each repo.
3. Write the runbook, then tag `v1.0-freeze`.

**Gates:** p95 generation ≤ 15 s; close → results ≤ 15 s; no errors on `fake`.

---

## 4. Assumptions written into the contract (D-020)

1. Players see only their final rank and total, never per-round scores.
2. Podium size = min(5, eligible); mini = min(3, eligible). Eligible = not kicked and ≥ 1 non-hidden scored entry.
3. Each round definition runs once per city; one open round per city; start from `LOBBY`, `ROUND_SCORED` or `MINI_PODIUM`; final podium after ≥ 1 scored round.
4. Podium step 0 = intro; `next` ×5 reveals #5…#1; `next` → `FINISHED` (hidden prompts). The ranking is frozen at start; hiding recomputes unrevealed steps only.
5. Calibration is asynchronous after create/edit; scored rounds can't start until `READY`; practice needs none.
6. The practice gallery is 6 random non-hidden entries, shown when the admin toggles it.
7. Kick invalidates the token; rejoining under a new nickname is possible.
8. Target upload: JPEG/PNG/WebP ≤ 10 MB, center-crop → 1024² JPEG.
9. The admin token is kept in localStorage per city, with a log-out control.
10. Countdown = `endsAt` + server `Date` offset.
11. `/api/me` carries attempt status and queue position (one poll URL).
12. The 30 writes/min limit counts POSTs only.

## 5. Provider API notes (verified 2026-11-20)

**fal.ai: `fal-ai/flux-2/klein/9b`** ([queue](https://fal.ai/docs/model-apis/model-endpoints/queue), [API](https://fal.ai/models/fal-ai/flux-2/klein/9b/api), [llms.txt](https://fal.ai/models/fal-ai/flux-2/klein/9b/llms.txt), [errors](https://fal.ai/docs/model-apis/errors), [concurrency](https://fal.ai/docs/documentation/model-apis/concurrency-limits))
- Submit: `POST https://queue.fal.run/fal-ai/flux-2/klein/9b`, `Authorization: Key $FAL_KEY` → `{request_id, status_url, response_url, cancel_url, queue_position}`.
- Status and result URLs use **only the app id** (`…/fal-ai/flux-2/requests/{id}/status`); the full path gives 405. Use the returned URLs.
- Status `IN_QUEUE` (`queue_position`) → `IN_PROGRESS` → `COMPLETED`. A failure can still be `COMPLETED` with `error`, `error_type`.
- Body: `{prompt, seed, image_size:"square_hd" | {width:1024,height:1024}, num_inference_steps:4, num_images:1, output_format:"jpeg", enable_safety_checker:true}`. There is no guidance parameter.
- Result: `{images:[{url,width,height,content_type}], seed, has_nsfw_concepts:[bool], timings}`. A flagged image is black → `SAFETY_BLOCKED`. 422 `content_policy_violation` → `SAFETY_BLOCKED`.
- 429 `concurrent_requests_limit` with `X-Fal-Needs-Retry: 1`. Only `IN_PROGRESS` counts toward the limit.
- Account limit: US$10 bought in the last 4 weeks → 10 concurrent (dashboard: $100→20, $500→30, $1000+→40).
- `X-Fal-Request-Start-Timeout` header. Price ≈ US$0.006/MP.

**Black Forest Labs: FLUX.2 [klein] 9B** ([model](https://docs.bfl.ml/api-reference/models/generate-or-edit-an-image-with-flux2-[klein]-9b.md), [get_result](https://docs.bfl.ml/api-reference/utility/get-result.md), [guidelines](https://docs.bfl.ml/api_integration/integration_guidelines.md), [pricing](https://bfl.ai/pricing))
- Submit: `POST https://api.bfl.ai/v1/flux-2-klein-9b`, header `x-key`, body `{prompt, seed, width:1024, height:1024, output_format:"jpeg", safety_tolerance:2}` (0–7; no steps field) → `{id, polling_url, cost}`.
- Poll `polling_url` with `x-key`. Statuses `Pending`, `Ready` (`result.sample`), `Request Moderated` / `Content Moderated` → `SAFETY_BLOCKED`, `Error` / `Failed` / `Task not found` → `PROVIDER_ERROR`.
- The sample URL expires after 10 min and has no CORS: download immediately.
- 24 concurrent. 429 → exponential backoff; 402 → no retry. US$0.015 per 1024².

**Gemini embeddings: `gemini-embedding-2`** ([model](https://aistudio.google.com/docs/models/gemini-embedding-2), [guide](https://aistudio.google.com/docs/embeddings), [reference](https://aistudio.google.com/api-reference/embeddings), [errors](https://aistudio.google.com/docs/api-errors), [rate limits](https://aistudio.google.com/docs/rate-limits), [terms](https://aistudio.google.com/docs/terms))
- `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent`, `x-goog-api-key`, body `{content:{parts:[{inline_data:{mime_type:"image/jpeg",data:<b64>}}]}, output_dimensionality:768}` (the reference nests it as `embedContentConfig.outputDimensionality`; confirm in the probe).
- Response `{embedding:{values:[…]}, usageMetadata}`. Several parts merge into **one** vector: one image per call.
- 128–3072 dims, auto-normalized. No taskType. ≈ 267 tokens per image (estimate).
- Free tier (dashboard, 2026-11-20): 100 RPM, 30K TPM, 1K RPD; no Batch API; data may be used to improve Google products. Colombia is allowed.
- 429 `rate_limit_exceeded` / `quota_exceeded`. Paid tier: US$0.00012 per image.

**Cohere: `embed-v4.0`** (optional) ([embed](https://docs.cohere.com/reference/embed), [rate limits](https://docs.cohere.com/docs/rate-limits))
- `POST https://api.cohere.com/v2/embed`, Bearer, `{model, input_type:"image", images:["data:image/jpeg;base64,…"], embedding_types:["float"], output_dimension:1024}` → `embeddings.float[][]`.
- Trial key: 5 images/min (unusable). Production: 400/min.

**Anthropic via Spring AI 2.1.0** ([reference](https://docs.spring.io/spring-ai/reference/api/chat/anthropic-chat.html), [upgrade notes](https://docs.spring.io/spring-ai/reference/upgrade-notes.html), [2.1 GA](https://spring.io/blog/2026/11/20/spring-ai-2-1-0-GA-available-now/))
- Starter `spring-ai-starter-model-anthropic` (anthropic-java 3.8.0).
- Properties: `spring.ai.anthropic.api-key`, `.chat.model=${COMMENTARY_MODEL}`, `.chat.max-tokens`, `.timeout`, `.max-retries`. `chat.temperature` is ignored in 2.1.
- Per-call `AnthropicChatOptions.timeout()`. `Media` image input. Structured output via `outputSchema` (every object `additionalProperties:false`).
- `.entity()` throws `ContentFilteredException` / `GuardrailRefusalException`. The key is sent as `Authorization: Bearer`.

**Spring Boot 4.2.0** ([release notes](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.2-Release-Notes), [RestClient](https://docs.spring.io/spring-boot/reference/io/rest-client.html))
- Framework 7.1, Jackson 3 (`tools.jackson.*`).
- `RestTemplate` / `TestRestTemplate` are deprecated → `RestClient`, `RestTestClient` + `@AutoConfigureRestTestClient`.
- Timeouts: `HttpClientSettings`, `spring.http.clients.*`.
- `server.forward-headers-strategy` → `server.request.header.forwarded.strategy` (needed behind Railway's proxy for per-IP join limits).
- Health stays at `/actuator/health`.
- WireMock: `org.wiremock.integrations:wiremock-spring-boot` 4.4.3, unverified on Boot 4.2 (Jetty 12.1.6 vs 12.1.15).

**Angular 22.3.0 / Transloco 8.4.0** ([versions](https://angular.dev/reference/versions), [provideAppInitializer](https://angular.dev/api/core/provideAppInitializer), [Signal Forms](https://angular.dev/guide/forms/signals/overview), [Transloco](https://jsverse.gitbook.io/transloco/getting-started/installation))
- Node `^22.22.3 || ^24.15.0 || ^26.0.0`, TS `>=6.0 <6.1`. Vitest and zoneless are the defaults; Signal Forms are stable since v22.0.
- Transloco loader path `public/i18n/{lang}.json`; `setActiveLang()`.

**Not built (D-011), for later:**
- Runware `runware:400@2` ([model](https://runware.ai/docs/models/bfl-flux-2-klein-9b)): array of tasks, `safety.checkContent`, `NSFWContent`, `serviceOverloaded` + `retryAfter`.
- OpenAI `gpt-image-2.5-flare` ([model](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)): no seed, base64, `moderation_blocked`.
- Gemini `gemini-nano-banana-2.1` ([model](https://aistudio.google.com/docs/models/gemini-nano-banana-2.1)): `generationConfig.seed` without a determinism guarantee, ≈ US$0.034/img, paid only.

## 6. Risks and cut list

| Risk | Mitigation |
|---|---|
| fal at 10 slots can't absorb a 100-player burst | Overflow to BFL (34 slots); queue position shown; load test with the real limits |
| Gemini free-tier quota (1K/day) exhausted | `entries` mode (~250 calls), limiter + 80 % alert, `rescore`; enable billing if the dry run needs averaging |
| Boot 4.2 / Spring AI 2.1 too new | Day-1 smoke; documented retreat (owner decides) |
| fal vs BFL pixels differ for the same seed | Accepted (D-012); the provider is shown per entry in admin |
| Budget: fal US$10 | Dev and CI on `fake`; `--real` ≤ 40 images; probe sparingly |

Cut order if late (WORKFLOW.md, adjusted): translation and LLM moderation → Cohere adapter → mini-podium after round 1 → LLM commentary (canned remain) → GitHub Pages backup. Never cut: fixed seed, fal → BFL failover, per-city isolation, snapshot, claim code, es/en copy, probe.
