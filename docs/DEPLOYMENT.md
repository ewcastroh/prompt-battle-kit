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

The repo's `Dockerfile` builds and runs the API (D-025): Temurin 25, the JVM as an unprivileged user, `DATA_DIR=/data`. Railway finds it at the repo root.

1. **Account.** Sign up and choose the **Hobby** plan. Set a usage limit in the workspace's usage settings (for example US$15) so a mistake can't run up a bill.
2. **Service.** New Project → **Deploy from GitHub repo** → `ewcastroh/prompt-battle-api`. Railway starts a first build at once. That deploy crashes because the admin tokens aren't set yet. This is expected and harmless.
3. **Settings** (service → Settings):
   - Source: branch `main`. Turn on **Wait for CI**: deploys wait until every GitHub Actions run on the commit has finished, and a failed run skips the deploy. The flag only shows once the workflow runs on `push` to `main` (ours does) and Railway's updated GitHub permissions are accepted (a banner links to them).
   - Region: US East (Virginia).
   - Replicas: **1**. Serverless: **off**.
   - Healthcheck path: `/actuator/health`. Railway calls it only during a deploy, from `healthcheck.railway.app`, and gives up after 300 s.
4. **Volume.** Add a volume (⌘K → "volume", or right-click the canvas), attach it to the service and mount it at `/data` (1 GB). Railway mounts volumes owned by root. The image's entrypoint hands it to the app user at each start, so **don't** set `RAILWAY_RUN_UID`.
5. **Variables** (service → Variables → Raw Editor). Every value from SPEC §11.1. Copy the keys from your local `.env`, never commit them, and use admin tokens different from your local ones:
   ```
   PUBLIC_UI_URL=https://prompt-battle-ui.pages.dev
   CORS_ALLOWED_ORIGINS=https://prompt-battle-ui.pages.dev,https://ewcastroh.github.io
   CITIES=mde:Medellín,bog:Bogotá
   ADMIN_TOKEN_MDE=<32 random characters>
   ADMIN_TOKEN_BOG=<32 other random characters>
   DATA_DIR=/data
   IMAGE_PROVIDER_CHAIN=bfl
   IMAGE_LOAD_SPLIT=bfl
   BFL_API_KEY=<key>
   GEMINI_API_KEY=<key>
   ANTHROPIC_API_KEY=<key>
   ```
   - A token: `openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-32`.
   - Keep the production values in the parent's git-ignored `secrets/` folder (mode 700, files 600): `railway.env` (pasted into the Raw Editor), `prod-tokens.env` (`PB_ADMIN_TOKEN_MDE`/`_BOG` for the production checks) and `cloudflare.env` (uploaded with `gh secret set -f`). Never leave a value empty: an empty number crashes the API at startup.
   - An origin has no path: the GitHub Pages origin is `https://ewcastroh.github.io`, not `…/prompt-battle-ui/`.
   - Don't set `SPRING_PROFILES_ACTIVE` (the `fake` profile ignores every key) or `PORT` (Railway injects it).
   - Images on BFL only (D-027): no `FAL_KEY`; `IMAGE_LOAD_SPLIT=bfl` (a one-provider split does nothing) avoids saving an empty value. `BFL_MAX_CONCURRENCY` keeps its default 24.
   - Optional: `COHERE_API_KEY`. The other variables have the SPEC defaults (`COMMENTARY_MODEL=claude-sonnet-5-5`, `PROMPT_LLM_MODERATION=false`, …).
   - Saving the variables redeploys.
6. **Domain.** Settings → Networking → Public Networking → **Generate Domain** (`*.up.railway.app`). Put it into the UI's `API_BASE_URL` (GitHub Actions variable in `prompt-battle-ui`).
7. **First-deploy checks** (`API=https://<domain>`, `T=<ADMIN_TOKEN_MDE>`):
   - Deploy logs show `Started PromptBattleApiApplication` and no warning that a provider chain has no adapter.
   - `curl -s $API/actuator/health` → `{"status":"UP",…}`. `curl -s $API/api/cities` → both cities.
   - `curl -s -H "X-Admin-Token: $T" $API/api/admin/me` → `mde`. Repeat with the Bogotá token → `bog`.
   - `curl -s -H "X-Admin-Token: $T" $API/api/admin/providers` → `chain: ["bfl"]`, `configured: true` for bfl, gemini and `commentary`.
   - `curl -s -X POST -H "X-Admin-Token: $T" $API/api/admin/providers/probe` → every row `ok: true`. This spends a few cents: one image and one comment.
   - Persistence: join a test player, restart the service from the dashboard, and check that `GET /api/admin/players` still lists it. Then run the event reset.
   - Client IP (D-022 #4): open one deployment's HTTP logs and confirm the source IP is your own public IP. If it isn't, set `FORWARD_HEADERS_STRATEGY=native`.
8. **After the event:** export both CSVs, run the event reset, then delete the service and its volume.

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

`docker-compose.yml` in the parent (phase I1):
- `api`: builds `./prompt-battle-api`, profile `fake` by default, volume `./data:/data`, env from `.env` (required: both `ADMIN_TOKEN_*`, 24+ characters), port 8080.
- `ui`: builds `./prompt-battle-ui` (`node:24.22.3-alpine3.24` build → `nginx:1.30.7-alpine`), port 4200 → 80. At start, `docker-entrypoint.d/40-config.sh` writes `config.json` from `API_BASE_URL=http://localhost:8080`. `nginx.conf` serves `index.html` for deep links and mirrors `public/_headers` (`config.json`, `index.html` and translations `no-cache`).
- `docker compose up --build`, then open `http://localhost:4200/play/mde`, `/stage/mde`, `/admin/mde` (and `bog`).
- To use real providers locally: set `SPRING_PROFILES_ACTIVE=` (empty, not removed) and fill the keys in `.env`. Unset means `fake`.
- **Full event test** (UI repo): with the stack up, `PB_ADMIN_TOKEN_MDE=… PB_ADMIN_TOKEN_BOG=… npm run e2e:compose` plays two cities through the real admin and player screens (two stages, two admins, two phones and two HTTP players per city) and saves screenshots and both results CSVs in `e2e/screenshots/compose/`. **It resets the event first.**

## Freeze rules
- Last deploy of both repos on **2026-11-26** (freeze), plus bug-fix deploys until 2026-12-01.
- **No deploys on 2026-12-02.** A redeploy restarts the API (short downtime; the snapshot restores state, losing ≤ 10 s).

## Sources
- [Railway pricing](https://railway.com/pricing) · [Railway plans](https://docs.railway.com/pricing/plans) · [Railway volumes](https://docs.railway.com/reference/volumes) · [Railway regions](https://docs.railway.com/reference/deployment-regions) · [Railway GitHub autodeploys](https://docs.railway.com/guides/github-autodeploys)
- [Fly.io 2026 pricing update](https://fly.io/pricing-update/) · [Fly.io pricing](https://fly.io/docs/about/pricing/) · [Fly.io regions](https://fly.io/docs/reference/regions/) · [Fly.io volumes](https://fly.io/docs/volumes/overview/) · [Fly.io autostop](https://fly.io/docs/launch/autostop-autostart/) · [Fly.io GitHub Actions](https://fly.io/docs/launch/continuous-deployment-with-github-actions/)
- [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) · [Custom 404 on GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-custom-404-page-for-your-github-pages-site)
