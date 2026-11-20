# Prompt Battle — Product & Technical Spec

Version 2.1 · 2026-11-20 · Owner: Eimer Castro (Java Americas community)
Replaces v1.0 (2026-11-19). Every change from v1 is recorded in `docs/DECISIONS.md`. v2.1 applies phase 0 decisions D-011…D-020; where details differ, `docs/API.md` is the contract.
UI copy is Spanish (default) and English. Code, comments, logs, commits and docs are English.

---

## 0. Context and hard constraints

- **Event:** EPAM Community Palooza 2026, Java Americas slot, **Wednesday 2026-12-02**, 45 minutes, in person, played **at the same time in two cities: Medellín and Bogotá** (Colombia).
- **Players:** about 50 per city, **100 concurrent in total**, on their own phones. Mixed technical and non-technical, Spanish-speaking. Venue Wi-Fi is unreliable; many will use mobile data. Each city has 1 admin and 1 projector stage.
- **Game in one sentence:** everyone sees a target image, writes a prompt, the platform generates the image with the **same model and seed for everyone**, an AI scores how close it is to the target, and each city's top 5 are revealed one by one from #5 to #1.
- **Schedule:** code freeze **2026-11-26**; dry run with real phones **2026-11-27**; after freeze only bug fixes.
- **Why players submit prompts, not images:** uploads would let a player photograph the projected target and win, and would let players use different generators. The platform generating every image is the anti-cheat and fairness mechanism. Do not add image upload for players.
- **Two deployables:** the API (`prompt-battle-api`) and the UI (`prompt-battle-ui`) are built, tested and deployed separately. See §7.

## 1. Scope

**In scope**
- Player web app (mobile), stage view (projector), admin console (laptop or phone). One set per city.
- Nickname-only join, claim code for prize verification.
- Shared round definitions: one practice round (unscored) + N scored rounds (default 2), played by every city.
- Server-side image generation with provider failover.
- Similarity scoring with image embeddings, calibrated to 0–100.
- AI commentary for podium entries in Spanish and English (entertainment only, never affects score).
- Per-city podium reveal 5 → 1, plus optional per-city mini-podium (top 3) after a scored round.
- UI in Spanish (default) and English; light and dark themes.
- Fake providers for tests, local development and load tests.
- Snapshot persistence to survive a restart.
- Docker Compose for local runs; CI/CD to the cloud on merge to `main`.

**Out of scope (do not build)**
- Player accounts, passwords, emails, OAuth, or any personal data collection.
- Player image upload.
- Multi-instance scaling, databases, message brokers, caches such as Redis.
- Languages other than Spanish and English.
- A combined ranking or "city vs city" score.
- Native apps, payments, analytics dashboards, server-side rendering.

## 2. Cities and event model

- Cities come from configuration: `CITIES=mde:Medellín,bog:Bogotá` (`code:display name`, comma-separated). Codes are 2–8 lowercase letters and appear in URLs.
- **Event** = the shared part: the list of round definitions, provider state, alerts, configuration.
- **City run** = the per-city part: players, attempts, entries, phase, timers, ranking, podium.
- Each round definition is played **once per city**, independently. A city's admin decides when their city starts, closes, extends and reveals.
- A round definition can be edited until any city starts it; then it is locked.
- Players, nicknames, claim codes, entries, rankings and podiums never cross cities.

## 3. Game rules

### 3.1 Join
- The player opens their city's link (from the city's QR code). The city is part of the URL; the player never picks it.
- Nickname 3–16 characters, letters/digits/space/`_`/`-`, trimmed, unique **within the city**, case- and accent-insensitive.
- Nickname passes the moderation blocklist (§6.3).
- On join the player receives an opaque `token` (stored in `localStorage`, keyed by city) and a 4-character **claim code** from an unambiguous alphabet (no `0 O 1 I L`).
- One active player per token. Rejoining with the same token returns the same player. A token belongs to exactly one city.

### 3.2 Round definitions (shared)
Each round definition has: `name`, target image, hidden reference prompt (shown at the very end), `durationSec` (default 480; practice 180), `attemptsPerPlayer` (default 3), `seed` (random int per round unless set), `scored` (bool), calibration anchors and floor (§4.1).

### 3.3 Round runs (per city)
Each city's run of a round records: status, `startedAt`, `endsAt`, the image provider and embedding provider it runs on, extensions, and its results.

During `OPEN`:
- A player writes a prompt (trimmed, whitespace collapsed, 1–300 chars) and presses **Generar** / **Generate**.
- A player can have at most **one generation in flight**.
- A successful generation consumes one attempt. A provider failure (timeout, 5xx, rate limit) does **not** consume an attempt. A moderation block does **not** consume an attempt but is counted; after 3 blocks in a round the player is flagged in admin.
- The player marks one successful attempt as their **entry** ("Enviar esta" / "Submit this one") and may change it until the round closes.
- If a player has at least one successful attempt but no entry at close, their **last successful attempt** becomes the entry automatically.
- Players never see scores while a round is open.

On close:
- New generations are rejected immediately.
- Generations already queued or running when the round closed may finish within `ROUND_GRACE_SECONDS` (default 20); later results are discarded.

### 3.4 Scoring and ranking (per city)
- Each scored-round entry gets a score 0.0–100.0 (one decimal), §4.
- Event total = sum of the player's scored-round scores (missing entry = 0).
- Ranking: total desc → tie-break 1: highest single-round score → tie-break 2: earliest `selectedAt` timestamp of the player's last entry.
- Entries hidden by an admin are excluded from ranking (score 0 for that round).
- Kicked players are excluded from ranking.

### 3.5 Podium (per city)
- Final podium = the city's top 5 by event total, revealed one step at a time from #5 to #1 by that city's admin.
- Optional mini-podium after a scored round: the city's top 3 of that round (`MINI_PODIUM_ENABLED`, default true).
- After #1 is revealed, the stage shows each scored round's hidden reference prompt ("El prompt original era…" / "The original prompt was…").
- Each player's phone shows their own final rank (in their city) and total after the final reveal. Podium players see "¡Estás en el podio! Muestra tu código {claimCode}" / "You're on the podium! Show your code {claimCode}".

## 4. Scoring

### 4.1 Similarity
- Embed the target image and each entry image with the city run's embedding model (default `gemini-embedding-2`, image input).
- `cos = cosine(targetVec, entryVec)`; L2-normalize vectors before computing.
- **Calibration floor** per round definition: at round creation, generate `CALIBRATION_ANCHORS` (default 6) images from a fixed list of neutral prompts (config, e.g. "a bowl of soup on a table", "a red bicycle", "a mountain landscape", "a city street at night", "a cat sleeping", "abstract colorful shapes") using the active image provider and the round's seed. Discard any anchor whose cosine to the target is > 0.9. `floor = mean(cos(target, anchor_i))`, computed with the city run's embedding provider.
- `score = round1(100 × clamp((cos − floor) / (1 − floor), 0, 1))`.
- Admin can see `cos`, `floor`, anchors and the final score per entry.

### 4.2 Determinism check
- The probe (§7.6) embeds the same image twice and reports the max absolute difference. If it exceeds 1e-4, scoring averages two embedding calls per image. The switch is automatic and visible in admin.

### 4.3 Embedding failover and consistency
- Compute embeddings asynchronously; cache by `(imageId, embeddingProvider)`. `EMBEDDING_MODE=entries` (default, D-013) embeds an attempt when it becomes an entry plus missing entries at close; `eager` embeds every successful generation.
- **Never mix embedding providers within a city run.** If the run's embedding provider fails at scoring time, re-embed the target, anchors and every entry of that city run with the next provider in `EMBEDDING_PROVIDER_CHAIN`, recompute the floor, and record which provider scored the run.
- Close → results ready must take ≤ 15 s with the primary provider.

### 4.4 Commentary
- For each podium and mini-podium entry, call the commentary model with the target image, the entry image, the score and the rank.
- **One call returns both languages:** JSON `{"es": string, "en": string}`. Spanish (es-CO) and English, ≤ 20 words each, playful and kind, about the image only. Never mention people's bodies, politics, religion or anything insulting. No emojis required.
- Timeout 8 s per call. On failure, use a canned comment chosen by score band (≥ 85, 70–85, 50–70, < 50) from `commentary/fallback-es.txt` and `commentary/fallback-en.txt`.
- Generate all comments right after scoring, before the admin starts the reveal. The reveal must never wait on an AI call.
- The stage shows the comment in the stage's current UI language.

## 5. Image generation

### 5.1 Port
```java
interface ImageGenerator {
  String providerId();
  GenerationResult generate(GenerationRequest request); // prompt, seed, width=1024, height=1024
}
// GenerationResult = Success(bytes, mimeType, modelId, latencyMs) | Failure(kind, message)
// kind ∈ SAFETY_BLOCKED, RATE_LIMITED, TIMEOUT, PROVIDER_ERROR, INVALID_RESPONSE
```

### 5.2 Adapters (all model IDs come from configuration, never hard-coded)
| providerId | Role | Default model (env var) | Seed | Notes |
|---|---|---|---|---|
| `fal` | Primary | `fal-ai/flux-2/klein/9b` (`FAL_MODEL`) | yes | **Queue API** (submit, then poll status, then fetch result), never sync `fal.run`. Send square 1024×1024, `output_format: jpeg`, `enable_safety_checker: true`. A flagged image comes back **black** with `has_nsfw_concepts`: map it to `SAFETY_BLOCKED`. |
| `bfl` | Backup 1 and overflow (D-012), same model | FLUX.2 [klein] 9B (`BFL_MODEL`) | yes | Submit, then poll the returned `polling_url`. Up to 24 concurrent requests. Results expire after 10 minutes: download immediately. |
| `runware` | **Not built (D-011)** | FLUX.2 [klein] 9B (`RUNWARE_MODEL`) | yes | Concurrency limit not published; `429` with `Retry-After`, `serviceOverloaded` with `retryAfter`. |
| `openai` | **Not built (D-011)** | `gpt-image-2.5-flare` (`OPENAI_IMAGE_MODEL`), quality `low` (`OPENAI_IMAGE_QUALITY`) | no | Slow (10–20 s); returns base64. |
| `gemini` | **Not built (D-011)** | `gemini-nano-banana-2.1` (`GEMINI_IMAGE_MODEL`) | check docs | Paid tier only. |
| `fake` | Tests, dev, load | n/a | yes | Deterministic image from `hash(prompt, seed)`; configurable latency, failure rate and concurrency limit. |
| `pollinations` | **Not built (D-011)** | (`POLLINATIONS_MODEL`) | yes | Keyless, no SLA. Enabled only when `ALLOW_KEYLESS_EMERGENCY=true`. |

Implementation notes:
- Use Spring `RestClient` for image and embedding adapters (thin, explicit, easy to test with WireMock). Spring AI does not cover every provider here and its option classes can lag new model parameters.
- Before writing each adapter, read the provider's **current** API documentation. Do not rely on remembered request formats. `docs/PROVIDERS.md` lists what was verified on 2026-11-20.

### 5.3 Forbidden model IDs (startup guard)
The API must refuse to start if any configured model ID matches `forbidden-models.txt`:
- Retired or retiring before the event: `gpt-image-1` (retired 2026-10-23), `gpt-image-1.5`, `gpt-image-1-mini`, `chatgpt-image-latest` (retire 2026-12-01), Nano Banana 2 `gemini-3.1-flash-image-preview` (shut down 2026-10-29), any `imagen-4*` on the Gemini API (discontinued 2026-08-17).
- Older generations we do not want even if still online: `dall-e-2`, `dall-e-3`, `gemini-2.5-flash-image`.

### 5.4 Provider selection and failover
- `IMAGE_PROVIDER_CHAIN` (default `fal,bfl`, D-011). Providers without a key are skipped.
- Provider health and the active provider are **event-wide** (shared by both cities).
- When a city starts a round, the run's provider = the current active provider. Record it on the run.
- Circuit breaker per provider: 3 failures of kind `TIMEOUT|PROVIDER_ERROR|RATE_LIMITED|INVALID_RESPONSE` within 30 s → open for 60 s → the active provider switches to the next healthy provider for **all open runs**, and every admin sees an alert. `SAFETY_BLOCKED` never counts as a failure.
- One automatic retry with jittered backoff for 429/5xx before reporting a failure (on top of honoring `Retry-After`).
- Either admin can force the active provider at any time; every admin sees an alert naming who forced it (city code).
- Every attempt stores the provider and model that generated it; admin shows it per entry so the jury can see whether a run was mixed.

### 5.5 Concurrency and queue
- One bounded executor per provider with its own limit: `FAL_MAX_CONCURRENCY` (set to the limit shown in the fal.ai dashboard), `BFL_MAX_CONCURRENCY` (default 24), `RUNWARE_MAX_CONCURRENCY` (default 4 until load-tested), `OPENAI_MAX_CONCURRENCY`, `GEMINI_MAX_CONCURRENCY`. One FIFO queue shared by both cities. The player sees their queue position.
- **Load split (on by default, D-012):** `IMAGE_LOAD_SPLIT=fal,bfl` sends each new job to the first listed healthy provider with a free slot (overflow); otherwise it waits in the FIFO. Use only providers that run the same model. Every attempt still records its provider.
- Timeouts per provider: connect 5 s, total `IMAGE_TIMEOUT_SECONDS` (default 45), including queue polling.
- Store output as JPEG quality 85 at 1024×1024 plus a 384 px thumbnail. Image IDs are random UUIDs.

### 5.6 Optional prompt translation
`PROMPT_TRANSLATE_TO_EN` (default false). When true, translate the prompt to English with the commentary model before generation and store both versions. The decision to enable it is made after the dry run.

## 6. Safety, moderation and privacy

### 6.1 Privacy
- Collect only nickname and prompts. No names, emails, phone numbers.
- Join screen notice, verbatim:
  - es: "Usa un alias. No escribas datos personales. Tus prompts se envían a servicios de IA de terceros para generar y evaluar imágenes."
  - en: "Use an alias. Don't write personal data. Your prompts are sent to third-party AI services to generate and evaluate images."
- Log prompt text only at DEBUG. Never log tokens or API keys.
- The event reset (§9.3) deletes the snapshot and all images.
- All three repos are public: no secrets, keys, real tokens or personal data in any commit. Secrets live in GitHub Actions secrets and the hosting dashboards only.

### 6.2 Content on the stage
- The stage shows player images only during results and podium, never live during an open round.
- Admin can hide any entry of their city; hidden entries never reach the stage.

### 6.3 Moderation
1. Deterministic blocklist for nicknames and prompts (Spanish + English) in `moderation/blocklist.txt`. Normalize before matching: lowercase, strip accents, basic leetspeak (`4→a, 3→e, 1→i, 0→o, 5→s, @→a`), collapse repeated letters.
2. Provider safety checkers enabled where the API allows.
3. Optional LLM prompt moderation (`PROMPT_LLM_MODERATION`, default false) with the commentary provider, structured output `{"allowed": bool}`.
- Blocked prompt → error code `PROMPT_BLOCKED`. UI message:
  - es: "Ese prompt no está permitido en este evento. Intenta con otra idea."
  - en: "That prompt isn't allowed at this event. Try another idea."

### 6.4 Abuse controls
- Per token: one generation in flight; at most 30 write requests per minute.
- Per IP: rate-limit **joins only** (120 per minute). Do not rate-limit other writes per IP: all 50 players in a venue can share one public IP behind the venue's NAT.
- Admin endpoints require header `X-Admin-Token`. Tokens come from `ADMIN_TOKEN_<CITY CODE IN UPPERCASE>` (e.g. `ADMIN_TOKEN_MDE`), each ≥ 24 chars, compared in constant time. The token determines the admin's city.

## 7. Architecture

### 7.1 System overview
```
 Phones (player)      Projector (stage)     Laptop (admin)
        \                    |                   /
         \__________ Angular SPA (static) ______/      Cloudflare Pages (GitHub Pages backup)
                             |
                     HTTPS JSON + images (CORS)
                             |
              Spring Boot API, ONE instance            Railway, volume at DATA_DIR
              in-memory state + snapshot
                 |            |            |
        image providers   embeddings   commentary (Spring AI → Anthropic)
```
- The UI and API live on different origins. The API enables CORS for `CORS_ALLOWED_ORIGINS` (the Cloudflare Pages URL, the GitHub Pages URL, and local dev origins) with methods `GET, POST, PUT, DELETE`, request headers `Authorization, X-Admin-Token, Content-Type, If-None-Match`, and **exposed** headers `ETag, Date, Retry-After, Content-Disposition` (D-019).
- The UI's API base URL is configuration, never hard-coded: a runtime `config.json` (D-017), so the same build runs on Cloudflare Pages, GitHub Pages and Docker Compose.

### 7.2 API stack
- Java 25, Maven wrapper, Spring Boot 4.2.0, Spring AI 2.1.0 (D-014). Pin exact versions.
- Spring AI `ChatClient` with the Anthropic model for commentary (and optional translation/moderation). This keeps a visible "Java + Spring AI" story for the community.
- ZXing for QR generation. `ImageIO` (or a small library) for thumbnails.
- Errors as RFC 9457 `ProblemDetail` with a machine-readable `code` property and optional `params` (see §9.5).

### 7.3 API packages
`game` (pure domain + state machine, no Spring), `city` (city config and per-city runs), `generation` (port, adapters, queue, circuit breakers), `scoring` (embedding port, adapters, calculator), `commentary`, `moderation`, `web` (REST, CORS, error handling), `admin`, `persistence` (snapshot), `config`.

### 7.4 State and persistence
- Single in-memory `EventState` holding the shared event and every city run. All mutations go through one serialized path (single lock or single-thread executor) to avoid races between generation callbacks, admin actions of both cities and timers.
- Snapshot state as JSON plus images under `DATA_DIR` every 10 s and on every phase transition of any city; restore on startup.
- **Exactly one instance.** Document this in the runbook, the Dockerfile comments and the Railway settings (replicas = 1, serverless off).

### 7.5 UI stack
- Angular 22.3.0 (D-014), standalone components, signals, zoneless change detection, Signal Forms, plain single-page app (no SSR).
- Transloco for i18n (§10.2). Plain modern CSS with design tokens (§10.3, `DESIGN.md`). No Tailwind, no component library.
- Vitest for unit tests; Playwright for end-to-end smoke tests and screenshots.
- **No runtime CDN calls:** fonts, icons and any JS library (confetti) are bundled or self-hosted. Images and the QR come from the API.

### 7.6 Provider probe
`POST /api/admin/providers/probe` runs, for each configured provider: one real image generation, one embedding (twice, for the determinism check), one commentary call. Returns latency, success and error per provider. It is the first thing each admin runs on event day.

## 8. Phases (state machine, per city)

`LOBBY → ROUND_OPEN(r) → ROUND_CLOSING(r) → ROUND_SCORED(r) → [MINI_PODIUM(r)] → ROUND_OPEN(r+1) … → FINAL_SCORING → PODIUM_REVEAL(step 1..5) → FINISHED`

- Each city has its own phase. One city's transitions never change the other city's phase.
- Practice round: `ROUND_OPEN → ROUND_CLOSING → LOBBY` (no scoring; admin may show a gallery of 6 random entries of their city on their stage).
- Invalid transitions return HTTP 409 with code `INVALID_TRANSITION`.
- Round timers are server-side, per city run; at 0 the run closes automatically. The admin can close early or extend by 60 s.

## 9. API (JSON over HTTP)

### 9.1 Public and player
Player endpoints use `Authorization: Bearer {token}`, except join. The token's city is the player's city.
- `GET /api/cities` → `[{code, name}]`
- `POST /api/cities/{city}/players` `{nickname}` → `{playerId, token, claimCode, city}`
- `GET /api/me` → player view: city, phase, current round (name, target image URL, ends-at, attempts left), attempts (status, thumb URL), entry id, final rank/total when revealed
- `POST /api/rounds/current/attempts` `{prompt}` → `202 {attemptId, queuePosition}`
- `GET /api/attempts/{id}` → `{status: QUEUED|GENERATING|DONE|BLOCKED|FAILED, queuePosition?, imageUrl?, thumbUrl?, code?}`
- `POST /api/rounds/current/entry` `{attemptId}` → `204`

### 9.2 Stage
No auth, read-only, only exposes what is already revealed for that city.
- `GET /api/cities/{city}/stage/state` → phase, join URL, players count, nickname list (lobby), round info + countdown, submissions count, reveal payload for revealed steps only (with commentary in `es` and `en`). Supports `ETag` / `If-None-Match`.
- `GET /api/cities/{city}/qr.png` encodes `{PUBLIC_UI_URL}/play/{city}`.

### 9.3 Admin
Header `X-Admin-Token`. "Own city" = the city of the token.
- `GET /api/admin/me` → `{city, cityName}`
- Shared round definitions (either admin):
  - `POST /api/admin/rounds/generate-target` `{prompt, seed?}` → preview image generated with the active provider
  - `POST /api/admin/rounds` (target from preview id or multipart upload, hidden prompt, name, durationSec, attemptsPerPlayer, scored, seed?)
  - `PUT /api/admin/rounds/{id}` (only while no city has started it; otherwise 409 `ROUND_LOCKED`)
  - `GET /api/admin/rounds` (includes each city's run status)
- Own city run:
  - `POST /api/admin/rounds/{id}/start|close|extend`
  - `POST /api/admin/mini-podium/next`, `POST /api/admin/podium/next`, `POST /api/admin/podium/reset`
  - `GET /api/admin/players`, `POST /api/admin/players/{id}/rename`, `POST /api/admin/players/{id}/kick`
  - `GET /api/admin/entries?roundId=`, `POST /api/admin/entries/{id}/hide`
  - `GET /api/admin/results.csv` (own city; includes a `city` column)
- Shared controls (either admin, alert to all):
  - `GET /api/admin/providers`, `POST /api/admin/providers/active` `{providerId}`, `POST /api/admin/providers/probe`
  - `GET /api/admin/alerts`
  - `POST /api/admin/event/reset` `{confirm: "RESET"}` → deletes snapshot and images for the whole event

### 9.4 Images
`GET /img/{uuid}.jpg`, `GET /img/{uuid}_thumb.jpg`, served by the API with long-lived cache headers.

### 9.5 Error codes
Every error response is a `ProblemDetail` with `code` (UPPER_SNAKE_CASE) and optional `params` for interpolation. The UI maps `code` to the translation key `errors.<CODE>`. Initial set: `NICKNAME_INVALID`, `NICKNAME_TAKEN`, `NICKNAME_BLOCKED`, `CITY_NOT_FOUND`, `UNAUTHORIZED`, `PLAYER_KICKED`, `ROUND_NOT_OPEN`, `GENERATION_IN_FLIGHT`, `NO_ATTEMPTS_LEFT`, `PROMPT_INVALID`, `PROMPT_BLOCKED`, `ATTEMPT_NOT_FOUND`, `ATTEMPT_NOT_SELECTABLE`, `GENERATION_FAILED`, `INVALID_TRANSITION`, `ROUND_LOCKED`, `RATE_LIMITED`, `ADMIN_FORBIDDEN`, `RESET_NOT_CONFIRMED`, `INTERNAL_ERROR`. Phase 0 may add codes; it must not remove them. Phase 0 added the codes and endpoints listed in `docs/API.md` (D-019).

## 10. UI

### 10.1 Routes
- `/` → short landing page listing the cities (for testing; players arrive by QR).
- `/play/:city` → player. `/stage/:city` → stage. `/admin/:city` → admin (asks for the admin token, then checks it belongs to `:city`).
- Unknown city → friendly page with code `CITY_NOT_FOUND`.
- GitHub Pages backup: built with base href `/prompt-battle-ui/` and a `404.html` copy of `index.html` so deep links work.

### 10.2 Languages
- Spanish is the default. Every screen has a language control (ES / EN); the choice is stored per device in `localStorage` and applied on next visit.
- Switching language updates `<html lang>` (`es-CO` / `en`) at runtime without a reload.
- All copy lives in Transloco translation files (`es.json`, `en.json`) with identical keys. Spanish strings quoted in this spec are the source of truth for Spanish copy.
- Error messages come from `errors.<CODE>` keys, never from API text.
- The stage shows commentary in its own current language.

### 10.3 Themes and design
- Light and dark themes on every screen. Default follows the device; a two-state toggle overrides it and is stored per device. Rules, tokens and components in `DESIGN.md`.

### 10.4 Player (phone, 360×800 minimum)
- Join: title "Prompt Battle: ¡Compila tu Imaginación!", city name, nickname field, privacy notice (§6.1), button "Entrar" / "Join".
- Lobby: "Hola, {nickname}" / "Hi, {nickname}", claim code, "Espera a que empiece la ronda" / "Wait for the round to start".
- Round open: target image (tap to zoom), countdown, prompt textarea with character counter (300), button "Generar" / "Generate" (disabled while in flight), queue/progress status, "Intentos restantes: N" / "Attempts left: N", gallery of attempts with "Enviar esta" / "Submit this one" and a selected badge, clear messages for blocked/failed attempts.
- Round closed: "¡Ronda cerrada! La IA está evaluando…" / "Round closed! The AI is scoring…".
- Final: own rank and total; podium players see the claim-code message.
- Tap targets ≥ 44 px, readable in sunlight (high contrast), no horizontal scroll, works on slow mobile data (thumbnails in galleries).

### 10.5 Stage (projector, 1920×1080 and 1280×720)
- Lobby: city name, big QR, short URL, joined counter, nicknames appearing.
- Round open: target image large, huge countdown, submissions counter. No player images.
- Closing/scoring: "La IA está evaluando…" / "The AI is scoring…" animation.
- Mini-podium and podium: one entry per step — rank, nickname, the entry's prompt (D-016), entry image beside the target (final podium: the player's best-scoring entry, D-015), score counting up over ~1.5 s, commentary line. #1 gets confetti (bundled). After #1: each scored round's hidden prompt.
- The stage advances only through its city admin's actions.

### 10.6 Admin
Round builder (generate target preview from a prompt, or upload; shared), start/close/extend for own city, podium "Siguiente" / "Next" button (large), players list with rename/kick and flags, entries table per round (thumb, provider, model, cos, floor, score, hide), provider panel (health, p50/p95 latency, errors, active provider selector, probe button; shared), alerts list (shared), CSV export, event reset with typed confirmation.

## 11. Configuration

### 11.1 API (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `PUBLIC_UI_URL` | — | UI base URL used in QR codes and join links |
| `CORS_ALLOWED_ORIGINS` | — | Comma-separated UI origins (Cloudflare Pages, GitHub Pages, local) |
| `CITIES` | `mde:Medellín,bog:Bogotá` | Cities, `code:name` |
| `ADMIN_TOKEN_<CITY>` | — | One per city, required, ≥ 24 chars |
| `DATA_DIR` | `./data` | Snapshot + images |
| `IMAGE_PROVIDER_CHAIN` | `fal,bfl` | Failover order (D-011) |
| `IMAGE_LOAD_SPLIT` | `fal,bfl` | Same-model providers for overflow (D-012); empty = off |
| `FAL_KEY`, `FAL_MODEL`, `FAL_MAX_CONCURRENCY` | —, `fal-ai/flux-2/klein/9b`, `10` | Primary; concurrency = the dashboard limit |
| `BFL_API_KEY`, `BFL_MODEL`, `BFL_MAX_CONCURRENCY` | —, `flux-2-klein-9b`, `24` | Backup 1 and overflow |
| `GEMINI_API_KEY` | — | Gemini embeddings (free tier, D-013) |
| `EMBEDDING_PROVIDER_CHAIN` | `gemini,cohere` | Embedding failover; providers without a key are skipped |
| `EMBEDDING_MODE` | `entries` | `entries` or `eager` (D-013) |
| `GEMINI_EMBEDDING_MODEL`, `GEMINI_EMBEDDING_DIMENSIONS`, `GEMINI_EMBEDDING_RPM` | `gemini-embedding-2`, `768`, set from the AI Studio dashboard | Primary embeddings |
| `COHERE_API_KEY`, `COHERE_EMBEDDING_MODEL` | —, `embed-v4.0` | Optional backup embeddings |
| `ANTHROPIC_API_KEY`, `COMMENTARY_MODEL` | —, `claude-sonnet-5-5` | Commentary (alt `claude-haiku-5-5`) |
| `IMAGE_TIMEOUT_SECONDS` | `45` | Per call |
| `ATTEMPTS_PER_ROUND` | `3` | Default per round |
| `ROUND_GRACE_SECONDS` | `20` | After close |
| `CALIBRATION_ANCHORS` | `6` | Scoring floor |
| `MINI_PODIUM_ENABLED` | `true` | Top 3 after scored rounds |
| `PROMPT_TRANSLATE_TO_EN` | `false` | §5.6 |
| `PROMPT_LLM_MODERATION` | `false` | §6.3 |

Spring profile `fake`: every provider is fake; no keys needed; the app is fully playable offline.

### 11.2 UI
- `API_BASE_URL` through a runtime `config.json` (D-017). Nothing else; no secrets ever reach the UI.

## 12. Deployment and CI/CD
Summary; details, costs and setup steps in `docs/DEPLOYMENT.md`.
- **API → Railway:** Dockerfile build, one service, replicas = 1, serverless off, volume mounted at `DATA_DIR`, health check `/actuator/health`. Railway deploys `main` automatically after the GitHub Actions CI run passes ("Wait for CI").
- **UI → Cloudflare Pages** (primary) and **GitHub Pages** (backup): one GitHub Actions workflow builds and deploys both on every push to `main`.
- **CI on pull requests:** API runs `./mvnw verify`; UI runs lint, unit tests and production build.
- **Local:** `docker compose up` in the parent folder builds `prompt-battle-api/` and `prompt-battle-ui/` and runs them with the `fake` profile by default.
- Never deploy during the event: a redeploy with a volume has a short downtime.

## 13. Non-functional requirements
- 100 concurrent players (50 per city), 2 stages, 2 admins; 3 attempts each within an 8-minute round; both cities may run a round at the same time.
- p95 from "Generar" to image visible ≤ 15 s on the primary provider at 100 players; queue position visible while waiting.
- Close → results ready ≤ 15 s per city.
- Each client polls at most every 1.5 s (about 70 requests/s in total); stage and player state responses support ETag.
- Restart mid-event loses ≤ 10 s of state.
- The API runs as one Docker container with only env vars and a mounted `DATA_DIR` volume.
- Player page usable at 360×800; WCAG 2.2 AA contrast in both themes.

## 14. Verification and Definition of Done

### 14.1 API (must pass in `./mvnw verify`)
1. Unit: state machine transitions and 409s; per-city isolation (one city's actions never change the other city); attempt accounting (success consumes, failures and blocks don't); auto-entry at close; grace period; ranking and both tie-breaks; score normalization; nickname rules (uniqueness per city) and blocklist normalization; forbidden-model startup guard; admin token → city mapping and cross-city rejection; round definition lock.
2. Adapter tests with WireMock for every image and embedding adapter: success, 429-then-success, timeout, safety block mapping (including fal's black-image flag), malformed response; fal and BFL queue polling.
3. Failover: 3 failures switch the active provider; `SAFETY_BLOCKED` never switches; embeddings are never mixed within a city run (a forced embedding failure re-embeds the whole run); load split only uses listed providers.
4. Simulation (profile `fake`): 2 cities × 50 players, practice + 2 scored rounds, cities starting rounds at different times, with deterministic fake embeddings → expected podium order per city; podium endpoints reveal exactly one more entry per `next`; the stage never exposes unrevealed entries or the other city's data.
5. Snapshot: kill and restart → state of both cities restored.
6. CORS: allowed origins get `Access-Control-Allow-Origin` and `ETag` exposed; other origins are refused.

### 14.2 UI (must pass in the UI's CI)
1. Unit (Vitest): language switch and persistence, theme toggle logic (`DESIGN.md` rules), error-code → message mapping (every code in §9.5 has `es` and `en` keys), city route guard.
2. Translation files: `es.json` and `en.json` have the same keys (automated check).
3. Playwright smoke against the `fake` API: join → generate → submit → round closed, at 360×800, in both languages and both themes, with no horizontal scroll and no requests to third-party origins.

### 14.3 Integration
- `scripts/loadtest.sh` (or a small Java client) in the API repo: 2 cities × 50 virtual players × 3 attempts within 120 s against a running instance; prints p50/p95/max latency and errors per city. Must pass on `fake` (with the fake provider's concurrency limit set to the real fal.ai limit). A `--real` mode caps total real generations at 40.
- A full event played end to end with Docker Compose on the `fake` profile: two stages, two admins, a few phones.

### 14.4 Manual (documented in `docs/RUNBOOK.md`)
Player flow on a 360×800 viewport, stage at 1920×1080 and 1280×720, podium animation, admin controls for both cities, language and theme toggles on every screen, probe on real keys.

### 14.5 Deliverables
- API repo: source, `Dockerfile`, `.env.example`, `scripts/loadtest.sh`, fallback commentary files (es, en), blocklist, forbidden-models list, CI workflow, `CLAUDE.md`, `README.md`.
- UI repo: source, translation files, `Dockerfile` (nginx, for Compose), CI/CD workflow, `CLAUDE.md`, `README.md`.
- Parent repo: `docker-compose.yml`, `docs/RUNBOOK.md` (start, probe, failover, podium, reset, Plan B, both cities), `docs/API.md`, `docs/PLAN.md`.
