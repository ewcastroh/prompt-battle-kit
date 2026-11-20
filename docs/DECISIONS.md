# Decision log

Architecture and business decisions for Prompt Battle. Newest last. Each entry records what was decided, why, and what it replaced. Decisions are made by the project owner; Claude proposes, the owner confirms.

Status values: **Accepted** (in force), **Superseded** (replaced by a later entry), **Open** (waiting for a decision).

---

## D-001 · Parent project plus two isolated repos — Accepted (2026-11-20)
- `prompt-battle-kit` (this repo) is the parent: architecture and business decisions, specs, design rules, workflow, and all Claude Code configuration (skills, agents, settings).
- `prompt-battle-api` and `prompt-battle-ui` are separate GitHub repos, cloned **inside** the parent folder as `prompt-battle-api/` and `prompt-battle-ui/`. The parent's `.gitignore` excludes both folders: the parent never contains their code.
- All three repos are public under the `ewcastroh` GitHub account. Nothing secret or personal is committed to any of them.
- Shared rules live in the parent `CLAUDE.md`. Each child repo has a short `CLAUDE.md` with its own commands, so it also works when cloned alone.
- **Replaces:** the original kit's single Spring Boot app that served the frontend.

## D-002 · Technology stack — Accepted (2026-11-20); versions superseded by D-014
- **API:** Java 25 (LTS), Spring Boot 4.1.x, Spring AI 2.0.x, Maven wrapper. Latest **stable** releases only; check the exact latest patch when scaffolding. As of 2026-11-20: Spring Boot 4.1.1 is the newest confirmed patch, Spring AI 2.0.1 is the latest stable (2.1 is still at RC), Spring AI 2.0.x supports Boot 4.0.x and 4.1.x.
- **UI:** Angular 22 (latest stable 22.2.x as of 2026-11-20), standalone components, signals, Signal Forms, plain single-page app (no SSR), Vitest.
- **Replaces:** Java 21, static HTML/CSS/vanilla JS with no build step.

## D-003 · Deployment — Accepted (2026-11-20)
- **API:** Railway (Hobby plan), one service, exactly one instance, a persistent volume for `DATA_DIR`, always on. Fly.io is the documented alternative (see `docs/DEPLOYMENT.md`).
- **UI:** Cloudflare Pages (primary), GitHub Pages (backup, deployed from the same pipeline).
- **CI/CD:** GitHub Actions in each child repo. Pull requests run build and tests; a merge to `main` deploys.
- **Local:** Docker + Docker Compose from the parent folder runs both projects together.
- **Why:** low budget for a one-day event; neither host has a free plan that keeps a single always-on instance with a persistent disk.

## D-004 · Load: 100 concurrent players in two cities — Accepted (2026-11-20)
- The event runs at the same time in **Medellín** and **Bogotá**: 50 players, 1 admin and 1 projector stage per city. Total 100 concurrent players, 2 admins, 2 stages.
- **Replaces:** 30–40 players in one room.

## D-005 · Two-city event model — Accepted (2026-11-20)
- **One shared event, separate city runs.** Both cities play the same list of rounds: same target image, hidden prompt, duration, attempts and seed.
- **Each city's admin controls their own city:** start, close, extend, mini-podium and podium reveal. Cities do not need to start a round at the same moment.
- **Rankings and podiums are per city.** No combined "city vs city" score.
- **Either admin** can create and edit the shared round definitions before the event. A round definition is locked once any city has started it.
- **Shared controls:** either admin can force the active image provider or run the probe; all admins see the resulting alert. The event reset is global and requires typing a confirmation.
- **One admin token per city**, so one city's admin cannot act on the other city.
- **One QR code and link per city.** Nicknames are unique within a city only.
- **The list of cities is configurable** (`CITIES` environment variable). Default `mde:Medellín,bog:Bogotá`.

## D-006 · Languages — Accepted (2026-11-20)
- The UI is bilingual: **Spanish (default)** and English. Each device picks its own language with a toggle; the choice is remembered. This applies to the player, stage and admin screens.
- i18n library: **Transloco** (runtime switch, single build).
- The API returns **error codes**, not translated text; the UI translates them.
- Podium commentary is generated in **both languages** in one call before the reveal; each stage shows the language it is set to.
- All code, comments, logs, commits and documentation are in **English**.
- **Replaces:** Spanish-only UI; "other languages" was out of scope.

## D-007 · Themes and design — Accepted (2026-11-20)
- Light and dark themes on every screen. Default follows the device; a toggle overrides it and is remembered.
- Visual direction: **"Compiler / Terminal"**, a play on "¡Compila tu Imaginación!". Rules in `DESIGN.md`.
- Styling: **plain modern CSS with design tokens** (custom properties, `light-dark()`, `color-scheme`, cascade layers, container queries), following the `modern-web-guidance` skill. No Tailwind, no component library.

## D-008 · Real-time updates — Accepted (2026-11-20)
- Keep HTTP polling with `ETag` / `If-None-Match` (at most every 1.5 s per client). No WebSockets or Server-Sent Events.
- **Why:** simpler and more robust on unreliable venue Wi-Fi and mobile data.

## D-009 · Image providers for 100 players — Accepted (2026-11-20)
- **fal.ai stays primary**, called through its **queue API**, not the synchronous `fal.run` endpoint. Reason: new fal.ai accounts allow only 2 concurrent requests (up to 40 self-serve by buying credits). Over the limit, sync calls get `429`, while queued requests wait and do not count against the limit.
- **Black Forest Labs** stays backup 1 (same model, 24 concurrent requests).
- **Runware is added** as a provider for the same model (FLUX.2 [klein] 9B). It is the cheapest and fastest option on paper, but its concurrency limit is not published, so its place in the chain is decided after the load test.
- **Splitting traffic between fal.ai and BFL** is implemented behind a flag and turned on only if fal.ai's limit stays under about 30 concurrent requests.
- **Cloudflare Workers AI rejected:** fixed seed not documented, which breaks round fairness.
- OpenAI and Gemini stay as last resorts only: 14–17 s per image cannot meet the 15 s target with 100 players.
- **Narrowed by D-011 and D-012:** only fal.ai and BFL are funded and built; the load split uses overflow, not "most free slots".

## D-010 · Schedule — Accepted (2026-11-20)
- Dates unchanged: code freeze **2026-11-26**, dry run **2026-11-27**, event **2026-12-02**.
- The API and UI phases run in parallel sessions against a shared API contract (`docs/API.md`, written in phase 0).

## D-011 · Funded providers and adapter scope — Accepted (2026-11-20)
- **Images:** fal.ai (primary) with **US$10** of credit. The fal.ai dashboard grants concurrency by credits bought in the last four weeks ($10 → 10, $100 → 20, $500 → 30, $1,000+ → 40), so `FAL_MAX_CONCURRENCY=10` until about 2026-12-18. **Black Forest Labs** is backup and overflow (24 concurrent). Chain `fal,bfl`.
- **Not built:** the Runware, OpenAI, Gemini image and Pollinations adapters. The `ImageGenerator` port stays, so any of them can be added later.
- **Embeddings:** Gemini only (D-013). The Cohere adapter is built last in A2 and is the first thing cut if A2 slips.
- **Commentary:** Anthropic.
- **Why:** budget. The owner funds only fal.ai, BFL and Anthropic, and adapters without keys can't run on event day.
- **Replaces:** the full SPEC §5.2 adapter list and the chain `fal,bfl,runware,openai,gemini`.

## D-012 · Load split in overflow mode, on by default — Accepted (2026-11-20)
- `IMAGE_LOAD_SPLIT=fal,bfl` is on by default. Each job goes to the **first listed healthy provider with a free slot**; when none is free, it waits in the shared FIFO.
- **Why:** fal.ai's limit (10) is below the ~30 threshold in D-009. Overflow gives the same burst capacity (34) as "most free slots", but BFL (≈ US$0.015/image) only takes bursts. fal.ai costs ≈ US$0.0063.
- **Accepted risk:** the same prompt and seed give different pixels on fal.ai and BFL. Every attempt records its provider, and admin shows it.
- **Replaces:** "most free slots" in SPEC §5.5 and "off by default".

## D-013 · Embeddings on the Gemini free tier — Accepted (2026-11-20)
- `gemini-embedding-2` on the **free tier**, with no embedding failover key.
- **Constraints:**
  - Free-tier limits are not published (only in the AI Studio dashboard, "not guaranteed").
  - Google may use free-tier inputs to improve its products, and human reviewers may read them.
  - Only AI-generated images are sent (no prompts, no photos), and the privacy notice already says images go to third-party AI services. Colombia is an allowed region.
- **Conserve calls:**
  - New `EMBEDDING_MODE`: `entries` (default) embeds an attempt when it becomes an entry, plus any missing entries at close; `eager` follows SPEC §4.3 and is meant for the paid tier.
  - A client-side limiter `GEMINI_EMBEDDING_RPM` and `GEMINI_EMBEDDING_DIMENSIONS=768`.
  - Backoff on 429.
- **When scoring fails:** the run stays `ROUND_CLOSING` with status `SCORING_FAILED`, admins get an alert, and the admin can `rescore`.
- **Owner action:** read the free-tier limits at aistudio.google.com/rate-limit. If the requests-per-day limit is below about 1,000, switch to the paid tier (cents for the event).
- **Replaces:** the Gemini paid tier, the Cohere backup, and eager embedding of every attempt.

## D-014 · Versions — Accepted (2026-11-20)
- **API:** Java 25, Spring Boot **4.2.0**, Spring AI **2.1.0** (built on Boot 4.2, Anthropic module on anthropic-java 3.x).
- **UI:** Angular **22.3.0**, Transloco **8.4.0**, Node 24 LTS.
- Boot 4.2 deprecates `RestTemplate`/`TestRestTemplate`: use `RestClient` and `RestTestClient`. Jackson 3 (`tools.jackson.*`) is the default.
- **Retreat:** if the new lines break during A1, the owner may choose Boot 4.1.3 + Spring AI 2.0.3.
- **Replaces:** the version lines in D-002 (Boot 4.1.x, Spring AI 2.0.x, Angular 22.2.x).

## D-015 · Final podium content — Accepted (2026-11-20)
- Each final-podium step shows the player's **highest-scoring non-hidden entry** (tie → earlier round), beside that round's target. Commentary is about that pair, together with the rank and total.
- The mini-podium shows that round's entry.

## D-016 · Prompts shown at reveals — Accepted (2026-11-20)
- Mini-podium and final-podium steps show the entry's prompt as the player typed it (not the translated version). Hidden entries never appear.

## D-017 · UI `API_BASE_URL` through a runtime `config.json` — Accepted (2026-11-20)
- The SPA loads `config.json` (relative to the base href) in `provideAppInitializer` before routing.
- **Where the file comes from:**
  - Local dev: `public/config.json`.
  - CI: the deploy jobs overwrite it from the GitHub Actions variable `API_BASE_URL`, for both Cloudflare Pages and GitHub Pages.
  - Docker: the nginx entrypoint writes it from env `API_BASE_URL`.
- It is served with `Cache-Control: no-cache`.
- **Why:** one build artifact for all three targets, and pointing the UI at another API needs no rebuild.
- **Replaces:** the open choice in SPEC §7.1 and §11.2.

## D-018 · Close, grace and scoring timing — Accepted (2026-11-20)
- On close, entry changes stop at once. Generations that finish within `ROUND_GRACE_SECONDS` count, and become the auto-entry only if the player has none.
- Scoring starts when the run has nothing queued or generating, or when grace ends, whichever comes first.
- The "close → results ≤ 15 s" target is measured from that moment.
- **Why:** SPEC §3.3 allows a 20 s grace while §4.3/§13 ask for 15 s from close. Both can't hold at once.

## D-019 · API contract additions in phase 0 — Accepted (2026-11-20)
- **Endpoints:**
  - `GET /api/admin/state`
  - `DELETE /api/admin/rounds/{id}`
  - `POST /api/admin/rounds/{id}/calibrate`
  - `POST /api/admin/rounds/{id}/rescore`
  - `POST /api/admin/mini-podium/start`
  - `POST /api/admin/podium/start` (goes through `FINAL_SCORING` while commentary is generated)
  - `POST /api/admin/practice/gallery`
- **Error codes:** `ROUND_NOT_FOUND`, `PLAYER_NOT_FOUND`, `ENTRY_NOT_FOUND`, `PREVIEW_NOT_FOUND`, `PROVIDER_NOT_FOUND`, `PROVIDER_UNAVAILABLE`, `ROUND_NOT_READY`, `UPLOAD_INVALID`, `VALIDATION_FAILED`, `SCORING_FAILED`, `NOT_FOUND`.
- **CORS** also exposes `Date` (countdown clock sync), `Retry-After` and `Content-Disposition`.
- **ETag** also applies to `GET /api/me` and `GET /api/admin/state`.
- Details are in `docs/API.md`.

## D-020 · Game flow details — Accepted (2026-11-20, approved with the phase 0 plan)
1. Players see only their final rank and total, never per-round scores.
2. Podium size is min(5, eligible) and mini-podium size is min(3, eligible). Eligible = not kicked and at least one non-hidden scored entry.
3. **Rounds:**
   - Each round definition runs once per city, with one open round per city.
   - A round can start from `LOBBY`, `ROUND_SCORED` or `MINI_PODIUM`.
   - The final podium can start after at least one scored round.
4. **Podium:**
   - Step 0 is an intro. `next` ×5 reveals #5 … #1, and one more `next` → `FINISHED` (hidden prompts). Phones show their own rank once #1 is revealed.
   - The ranking is frozen at podium start. Hiding an entry recomputes only the unrevealed steps.
5. **Calibration:**
   - Anchors are generated asynchronously after a round is created or edited. A scored round can't start until calibration is `READY`; practice needs none.
   - The floor is computed per city run with that run's embedding provider.
6. The practice gallery is 6 random non-hidden entries, shown when the admin toggles it on.
7. Kick invalidates the token; nothing prevents rejoining under a new nickname.
8. Admin target upload: JPEG, PNG or WebP up to 10 MB, center-cropped to a 1024² JPEG.
9. The admin token is kept in `localStorage` per city, with a log-out control.
10. Countdowns use the absolute `endsAt` plus the server `Date` header offset.
11. `GET /api/me` includes attempt status and queue position, so a phone polls one URL.
12. The limit of 30 writes per minute per token counts POSTs only.

---

## Open
- **Gemini free-tier limits** for `gemini-embedding-2` (D-013): the owner reads them from the AI Studio dashboard. They set `GEMINI_EMBEDDING_RPM` and decide whether to move to the paid tier.
