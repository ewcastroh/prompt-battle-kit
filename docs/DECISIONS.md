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

## D-002 · Technology stack — Accepted (2026-11-20)
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

## D-010 · Schedule — Accepted (2026-11-20)
- Dates unchanged: code freeze **2026-11-26**, dry run **2026-11-27**, event **2026-12-02**.
- The API and UI phases run in parallel sessions against a shared API contract (`docs/API.md`, written in phase 0).

---

## Open
- None at the time of writing. New open questions are added here with an `Open` status.
