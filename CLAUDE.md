# Prompt Battle — parent project

Live game for EPAM Community Palooza (2026-12-02), played at the same time in Medellín and Bogotá: ~50 players per city on phones write prompts, the API generates images with one shared model and seed, an embedding model scores similarity to a target, and each city's top 5 are revealed 5 → 1 on that city's projector.

This folder is the **parent project**: decisions, specs, design rules and Claude Code configuration. Code lives in two child repos cloned inside it (and git-ignored here):
- `prompt-battle-api/` → github.com/ewcastroh/prompt-battle-api (Java 25, Spring Boot 4.2.x, Spring AI 2.1.x; see D-014)
- `prompt-battle-ui/` → github.com/ewcastroh/prompt-battle-ui (Angular 22 single-page app)

## Read before planning or changing a feature
- `docs/SPEC.md` (the requirements), `docs/DECISIONS.md` (why), `docs/API.md` (the contract, once it exists), `docs/PLAN.md` (phases, once it exists).
- UI work: `DESIGN.md`. Provider work: `docs/PROVIDERS.md`. Deploy work: `docs/DEPLOYMENT.md`.
- Each child repo has its own `CLAUDE.md` with its commands.

## Rules for every repo
- Don't make assumptions: when a decision is open, ask the owner. Record accepted decisions in `docs/DECISIONS.md`.
- Never commit child code to the parent repo, and never commit secrets anywhere: all three repos are public.
- English for code, comments, logs, commits and docs. UI copy in Spanish (default) and English via translation files only.
- The API and UI change together only through `docs/API.md`. If the contract changes, update it first.
- Ask before adding a dependency that is not in the spec or the plan.
- Latest **stable** versions only; never upgrade a version implicitly.
- IMPORTANT: **one branch per change, never work on `main`** (D-028). Before editing anything in any of the three repos, check the branch with `git branch --show-current`; if it is `main`, create a branch first (`<phase-or-type>/<short-topic>`, e.g. `a4/queue-fix`, `fix/stage-overflow`, `docs/branch-per-change`). Never commit, merge, rebase or force-push on `main`. Changes reach `main` only through a pull request that the owner merges after CI passes.

## API rules (`prompt-battle-api`)
- IMPORTANT: model IDs live only in configuration (`application.yml` + env vars). Before writing a provider adapter, read that provider's current API docs. Never use a model ID listed in `forbidden-models.txt`.
- Tests never call real providers. Use the `fake` profile and WireMock.
- One instance, in-memory state, snapshot to `DATA_DIR`. No database, Redis or message broker.
- All state mutations go through the single serialized path in `game`. No mutation from controllers or provider callbacks directly. `game` has no Spring imports.
- Per-city isolation: one city's actions never change another city's state.
- Errors are `ProblemDetail` with a `code`; never return user-facing text.
- Never log API keys, player or admin tokens, or prompt text above DEBUG.
- Players never upload images. Do not add that feature.

## UI rules (`prompt-battle-ui`)
- Follow `DESIGN.md`. Run the `modern-web-guidance` skill before writing HTML, CSS or client-side JS for any pattern; use `angular-developer` for Angular code.
- Mobile first (360×800), no horizontal scroll, tap targets ≥ 44 px, WCAG 2.2 AA in both themes.
- No runtime CDN calls: fonts, icons and libraries are bundled.
- Every string in `es.json` and `en.json` with identical keys.

## Workflow
- Start Claude Code in this folder; each phase then works inside one child folder (see `docs/WORKFLOW.md` and `docs/PROMPTS.md`).
- After each change, run the relevant tests. Before saying a phase is done, run the child repo's full verification and show the output.
- Each phase is a branch in its child repo (e.g. `a1/game-core`). Commit at the end of the phase on that branch, as `<phase>: <summary>` (e.g. `a1: game core`). Push the branch and open a pull request only when the owner confirms. Never merge it: the owner does.
- IMPORTANT: every commit is made on behalf of the owner (Eimer Castro) using the local git identity. Never add `Co-Authored-By: Claude` or any other Claude/AI attribution trailer to commits, and never add "Generated with Claude Code" to pull request descriptions.
- When compacting, keep the list of modified files, failing tests, and open decisions.

## Local run (once I1 is done)
- `docker compose up --build` → UI on http://localhost:4200, API on http://localhost:8080, `fake` profile.
