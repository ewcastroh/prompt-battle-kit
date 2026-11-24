# Prompt Battle kit

Parent project for **"Prompt Battle: ¡Compila tu Imaginación!"**, a live game for EPAM Community Palooza on 2026-12-02, played at the same time in Medellín and Bogotá.

Players write prompts on their phones, the platform generates every image with the same model and seed, an AI scores how close each image is to a target, and each city's top 5 are revealed one by one on a projector.

This repo holds the architecture and business decisions, the specs, the design rules and the Claude Code configuration. It contains **no application code**: that lives in two separate repos.

## Repositories

| Repo | What | Stack | Hosted on |
|---|---|---|---|
| [prompt-battle-kit](https://github.com/ewcastroh/prompt-battle-kit) (this one) | Decisions, docs, Claude Code config | Markdown | — |
| [prompt-battle-api](https://github.com/ewcastroh/prompt-battle-api) | Game server | Java 25, Spring Boot 4.2, Spring AI 2.1 | Railway |
| [prompt-battle-ui](https://github.com/ewcastroh/prompt-battle-ui) | Player, stage and admin screens | Angular 22 | Cloudflare Pages (GitHub Pages backup) |

## Set up

```bash
git clone https://github.com/ewcastroh/prompt-battle-kit.git
cd prompt-battle-kit
git clone https://github.com/ewcastroh/prompt-battle-api.git
git clone https://github.com/ewcastroh/prompt-battle-ui.git
cp .env.example .env   # fill in keys; never commit .env
docker compose up --build   # available after the integration phase
```

To open it from your phone on the same Wi-Fi, add `LAN_HOST=<your computer's LAN IP>` to `.env` (macOS: `ipconfig getifaddr en0`), run `docker compose up -d`, and open `http://<LAN IP>:4200/play/mde`. Details and troubleshooting: `docs/DEPLOYMENT.md` → "Testing on your phone".

The two child folders are git-ignored here, so each keeps its own history.

## What's here

| File | For | What it is |
|---|---|---|
| `CLAUDE.md` | Claude Code | Short rules loaded in every session |
| `DESIGN.md` | Claude Code, designers | Visual direction, design tokens, theming, components, accessibility |
| `docs/SPEC.md` | Claude Code | Full spec: game rules, cities, scoring, providers, API, UI, deployment, tests, Definition of Done |
| `docs/DECISIONS.md` | Everyone | Every architecture and business decision, with dates and reasons |
| `docs/PROVIDERS.md` | Owner | AI providers, models, keys, concurrency limits, budget |
| `docs/DEPLOYMENT.md` | Owner, Claude Code | Railway, Cloudflare Pages, GitHub Pages, CI/CD, Docker Compose, costs |
| `docs/WORKFLOW.md` | Owner | Day-by-day calendar, quality gates, dry run and event day |
| `docs/PROMPTS.md` | Owner → Claude Code | Ready-to-paste prompts, one per phase |
| `docs/API.md`, `docs/PLAN.md`, `docs/RUNBOOK.md` | Claude Code, owner | Written during phase 0 and the hardening phase |
| `.claude/agents/spec-reviewer.md` | Claude Code | Subagent that reviews each phase against the spec in a clean context |
| `.claude/settings.json` | Claude Code | Default model and permissions (blocks reading `.env` files) |
| `.claude/skills/` | Claude Code | Project skills (see below) |
| `.env.example` | Owner | Environment variables for Docker Compose and the API |

## Claude Code skills

Installed with `npx skills` (locked in `skills-lock.json`):
- `angular-developer`, `angular-new-app` — official Angular team skills.
- `java-springboot`, `create-spring-boot-java-project`, `spring-boot-testing` — from `github/awesome-copilot`.
- `modern-web-guidance` — from `GoogleChrome/modern-web-guidance`; mandatory before HTML/CSS/JS work.

## How to use it

1. Read `docs/PROVIDERS.md` and create the keys.
2. Follow `docs/WORKFLOW.md`.
3. In each phase, paste the matching prompt from `docs/PROMPTS.md` into a Claude Code session started in this folder.
