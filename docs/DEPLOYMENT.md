# Deployment and CI/CD

Decisions: `docs/DECISIONS.md` D-003. Spec: `docs/SPEC.md` §12. Prices verified on 2026-11-20; confirm them when you sign up.

## Overview

| Piece | Where | How it deploys |
|---|---|---|
| API (`prompt-battle-api`) | **Railway**, Hobby plan, one service, one instance, volume at `/data` | Railway's GitHub integration deploys `main` after the GitHub Actions CI run passes ("Wait for CI") |
| UI (`prompt-battle-ui`) | **Cloudflare Pages** (primary) | GitHub Actions on push to `main`: build, then `wrangler pages deploy` |
| UI backup | **GitHub Pages** | Same workflow, second job: build with base href `/prompt-battle-ui/`, deploy to Pages |
| Local | Docker Compose in the parent folder | `docker compose up --build` |

No custom domain. Default addresses:
- UI: `https://prompt-battle-ui.pages.dev` (the Cloudflare project name decides it) and `https://ewcastroh.github.io/prompt-battle-ui/` (backup).
- API: `https://<service>.up.railway.app`.

The UI and API are on different origins, so the API sets CORS (`CORS_ALLOWED_ORIGINS`, SPEC §7.1). Both UI origins must be in that list, so switching to the backup needs no API change.

## API host: Railway vs Fly.io

Both fit the hard requirement: exactly one always-on instance with a persistent disk. Neither has a free plan that fits: Railway's trial caps volumes at 500 MB and its Free plan sleeps; Fly.io has no free tier for new organizations.

Estimate for about 10 days (2026-11-25 to 2026-12-03, 240 h), 1 GB RAM, ~0.1 vCPU average, 1 GB volume, ~5 GB egress:

| | Railway (Hobby) | Fly.io |
|---|---|---|
| Plan | US$5/month, includes US$5 of usage | Pay as you go; bills under US$5/month may be waived (at Fly's discretion) |
| Compute | RAM US$10/GB-month, CPU US$20/vCPU-month, billed per second → ≈ US$4.01 | 1 GB preset ≈ US$0.0122/h → ≈ US$2.93 |
| Volume | US$0.15/GB-month → ≈ US$0.05 | US$0.15/GB-month → ≈ US$0.05 |
| Egress | US$0.05/GB → ≈ US$0.25 | US$0.04/GB (South America) → ≈ US$0.20 |
| **Total** | **≈ US$5** (≈ US$10 if the window spans two billing cycles) | **≈ US$3** |
| Region nearest Colombia | US East (Virginia). No South America region | São Paulo (`gru`). Not measured whether it is actually faster from Colombia: traffic often routes through Miami |
| Always on | Hobby runs always on; keep Serverless off | Set `auto_stop_machines = "off"`, `auto_start_machines = false`, `min_machines_running = 1` |
| Volume | One per service; "Replicas cannot be used with volumes"; up to 5 GB on Hobby | One per machine, pinned to one host; daily snapshots (5 days by default) |
| Redeploy downtime | Short downtime with a volume, even with a health check | Downtime on every deploy with one machine plus a volume |
| CI/CD | Native GitHub autodeploy with "Wait for CI": no deploy step to write | `flyctl deploy --remote-only` from Actions with a `FLY_API_TOKEN` secret |

**Recommendation: Railway.** The cost difference is at most about US$7 for the whole event. Railway's native autodeploy with "Wait for CI" means no deploy script to write or debug during a 6-day build, and its dashboard (logs, variables, volume) is simpler on event day. Choose Fly.io if the lowest cost matters more, or if a South America region becomes a requirement.

Latency to players matters little here: players poll small JSON every 1.5 s and load images once. Most of the time is spent waiting on the image providers, which are in the US.

## Railway setup (API)

1. Sign up, choose the **Hobby** plan, set a usage limit.
2. New project → **Deploy from GitHub repo** → `ewcastroh/prompt-battle-api`. Build from the repo's `Dockerfile`.
3. Settings:
   - Region: US East.
   - Replicas: **1**. Serverless: **off**.
   - Health check path: `/actuator/health`.
   - Branch: `main`. Turn on **Wait for CI**.
4. Add a **volume** mounted at `/data` (1 GB). Set `DATA_DIR=/data`.
5. Variables: every API variable from SPEC §11.1 (copy from your local `.env`; never commit it). Set `PUBLIC_UI_URL` to the Cloudflare Pages URL and `CORS_ALLOWED_ORIGINS` to both UI origins.
6. Generate a public domain (`*.up.railway.app`). Put it into the UI's `API_BASE_URL` (GitHub Actions variable in `prompt-battle-ui`).
   - Then check the client IP (D-022 #4): confirm in Railway's docs or HTTP logs that `X-Forwarded-For` carries the real client address. If it doesn't, switch `FORWARD_HEADERS_STRATEGY` to `native`.
7. After the event: export the CSVs, run the event reset, then delete the service and its volume.

## Cloudflare Pages setup (UI, primary)

1. Sign up (free). Create a Pages project named `prompt-battle-ui` using **Direct Upload** (GitHub Actions uploads the build; no Cloudflare Git integration needed).
2. Create an API token with permission **Cloudflare Pages: Edit**.
3. In `ewcastroh/prompt-battle-ui` → Settings → Secrets and variables → Actions:
   - Secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
   - Variables: `API_BASE_URL`.
4. Free plan limits that matter: 500 builds/month, 20,000 files per site. Single-page app routing works out of the box; a `_headers` file sets security and cache headers.

## GitHub Pages setup (UI, backup)

1. In `ewcastroh/prompt-battle-ui` → Settings → Pages → Source: **GitHub Actions**.
2. The workflow's backup job builds with `--base-href /prompt-battle-ui/` and copies `index.html` to `404.html` so deep links (`/play/mde`, `/stage/bog`) load the app.
3. Known limits: deep links are served with a 404 status (users don't notice); no custom HTTP headers (no CSP or cache control); soft limit of 100 GB bandwidth per month.
4. To switch to the backup during the event: the QR codes encode `PUBLIC_UI_URL`, so set it to the GitHub Pages URL in Railway (a variable change redeploys the API: do it before doors open, not mid-round) and reprint or re-project the QR codes.

## CI/CD workflows

### `prompt-battle-api/.github/workflows/ci.yml`
- Triggers: `pull_request`, `push` to `main`.
- Steps: checkout → set up Java 25 (Temurin) with Maven cache → `./mvnw -B verify`.
- Railway waits for this workflow on `main` before deploying.

### `prompt-battle-ui/.github/workflows/ci-cd.yml`
- Triggers: `pull_request` (job `verify`), `push` to `main` (jobs `verify`, `deploy-cloudflare`, `deploy-github-pages`).
- `verify`: checkout → Node (current LTS) with npm cache → `npm ci` → lint → unit tests → production build → translation-keys check.
- `deploy-cloudflare`: needs `verify`; build with `API_BASE_URL`; `cloudflare/wrangler-action` → `pages deploy dist/<app>/browser --project-name=prompt-battle-ui`.
- `deploy-github-pages`: needs `verify`; build with the backup base href; `actions/upload-pages-artifact` + `actions/deploy-pages`.

Pin every third-party action to a full commit SHA (the repos are public).

### Security for public repos
- Turn on **secret scanning** and **push protection** in all three repos.
- Secrets only in GitHub Actions secrets, Railway variables and Cloudflare. `.env` files are git-ignored everywhere.
- Turn on branch protection for `main` in the child repos: require the CI check to pass before merging.

## Local: Docker Compose (parent folder)

`docker-compose.yml` in the parent (written in the integration phase):
- `api`: builds `./prompt-battle-api`, profile `fake` by default, volume `./data:/data`, env from `.env`, port 8080.
- `ui`: builds `./prompt-battle-ui` (multi-stage: Node build → nginx with single-page app fallback), port 4200 → 80, `API_BASE_URL=http://localhost:8080`.
- `docker compose up --build`, then open `http://localhost:4200/play/mde`, `/stage/mde`, `/admin/mde` (and `bog`).
- To use real providers locally: set `SPRING_PROFILES_ACTIVE=` (empty) and fill the keys in `.env`.

## Freeze rules
- Last deploy of both repos on **2026-11-26** (freeze), plus bug-fix deploys until 2026-12-01.
- **No deploys on 2026-12-02.** A redeploy restarts the API (short downtime; the snapshot restores state, losing ≤ 10 s).

## Sources
- [Railway pricing](https://railway.com/pricing) · [Railway plans](https://docs.railway.com/pricing/plans) · [Railway volumes](https://docs.railway.com/reference/volumes) · [Railway regions](https://docs.railway.com/reference/deployment-regions) · [Railway GitHub autodeploys](https://docs.railway.com/guides/github-autodeploys)
- [Fly.io 2026 pricing update](https://fly.io/pricing-update/) · [Fly.io pricing](https://fly.io/docs/about/pricing/) · [Fly.io regions](https://fly.io/docs/reference/regions/) · [Fly.io volumes](https://fly.io/docs/volumes/overview/) · [Fly.io autostop](https://fly.io/docs/launch/autostop-autostart/) · [Fly.io GitHub Actions](https://fly.io/docs/launch/continuous-deployment-with-github-actions/)
- [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) · [Custom 404 on GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-custom-404-page-for-your-github-pages-site)
