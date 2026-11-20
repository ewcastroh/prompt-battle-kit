# Prompt Battle — HTTP API contract

Version 1.0 · 2026-11-20 · Source: `docs/SPEC.md` §9, decisions D-008, D-013, D-015…D-020 in `docs/DECISIONS.md`.
Both tracks build against this file. If the contract has to change, change this file first, add a line to the change log at the end, and tell the other track.

---

## 1. Conventions

- **Base URL:** the API origin, e.g. `https://<service>.up.railway.app` (the UI reads it from `config.json`, D-017). JSON endpoints live under `/api`, images under `/img`.
- **Format:** JSON, UTF-8, `Content-Type: application/json`. Errors use `application/problem+json` (§2).
- **Time:** instants are ISO-8601 UTC strings with milliseconds: `"2026-12-02T15:04:05.123Z"`. Durations are integer seconds (`durationSec`).
- **IDs:** players, rounds, attempts, previews, alerts and images use random UUIDs (lowercase string). An entry is the attempt a player selected, so `entryId` = `attemptId`. Cities use their configured code (`mde`, `bog`).
- **Image URLs** in responses are **paths relative to the API base URL** (`"/img/3f1c….jpg"`). The UI prefixes them with `API_BASE_URL`.
- **Language:** the API never returns UI text. It returns codes that the UI translates (`errors.<CODE>`, `alerts.<CODE>`). User content (nicknames, prompts, round names, hidden prompts, commentary `{es,en}`) is returned as is.
- **Auth:**
  - Player: `Authorization: Bearer <token>`. The token's city is the player's city.
  - Admin: `X-Admin-Token: <token>`. The token decides the admin's city ("own city"). Tokens are compared in constant time.
  - Stage, cities, QR and images need no auth.
- **Nulls:** fields that don't apply are present with `null` (never omitted), so the UI can rely on shape.

## 2. Errors

Every 4xx/5xx is an RFC 9457 `ProblemDetail`:

```json
{
  "type": "about:blank",
  "title": "Conflict",
  "status": 409,
  "detail": "Round 7b0e… cannot start in phase ROUND_OPEN",
  "instance": "/api/admin/rounds/7b0e…/start",
  "code": "INVALID_TRANSITION",
  "params": { "phase": "ROUND_OPEN" }
}
```

`detail` is for logs and developers only; the UI never shows it. The UI maps `code` → `errors.<CODE>` and may interpolate `params`.

| Code | HTTP | When | `params` |
|---|---|---|---|
| `NICKNAME_INVALID` | 400 | Not 3–16 chars of letters/digits/space/`_`/`-` after trimming | `{min:3,max:16}` |
| `NICKNAME_TAKEN` | 409 | Same nickname already in this city (case- and accent-insensitive) | — |
| `NICKNAME_BLOCKED` | 422 | Nickname matches the blocklist | — |
| `CITY_NOT_FOUND` | 404 | Unknown city code | `{city}` |
| `UNAUTHORIZED` | 401 | Missing or unknown player/admin token (also after an event reset) | — |
| `PLAYER_KICKED` | 403 | The player token was kicked | — |
| `ROUND_NOT_OPEN` | 409 | Player write while the city phase is not `ROUND_OPEN`. Also the `code` of an attempt discarded after the grace period | — |
| `GENERATION_IN_FLIGHT` | 409 | The player already has a `QUEUED` or `GENERATING` attempt | — |
| `NO_ATTEMPTS_LEFT` | 409 | Successful attempts = `attemptsPerPlayer` | `{max}` |
| `PROMPT_INVALID` | 400 | Prompt empty or > 300 chars after normalization (admin target prompts: > 1000) | `{min:1,max:300}` |
| `PROMPT_BLOCKED` | 422 | Blocklist hit (synchronous). Also the `code` of a `BLOCKED` attempt (provider safety or LLM moderation) | — |
| `ATTEMPT_NOT_FOUND` | 404 | Unknown attempt, or it belongs to another player | — |
| `ATTEMPT_NOT_SELECTABLE` | 409 | Attempt not `DONE`, or not from the current open round | — |
| `GENERATION_FAILED` | 502 | Admin target preview failed. Also the `code` of a `FAILED` attempt | `{kind}` (`TIMEOUT`, `RATE_LIMITED`, `PROVIDER_ERROR`, `INVALID_RESPONSE`) |
| `INVALID_TRANSITION` | 409 | Action not allowed in the city's current phase (§4) | `{phase}` |
| `ROUND_LOCKED` | 409 | Edit, delete or recalibrate a round any city has started | — |
| `RATE_LIMITED` | 429 | Over 30 writes/min per player token, or 120 joins/min per IP. Has a `Retry-After` header | `{retryAfterSec}` |
| `ADMIN_FORBIDDEN` | 403 | Admin acts on a player, entry or run of another city | — |
| `RESET_NOT_CONFIRMED` | 400 | Event reset without `{"confirm":"RESET"}` | — |
| `INTERNAL_ERROR` | 500 | Unexpected error | — |
| `ROUND_NOT_FOUND` | 404 | Unknown round id | — |
| `PLAYER_NOT_FOUND` | 404 | Unknown player id | — |
| `ENTRY_NOT_FOUND` | 404 | Unknown entry id | — |
| `PREVIEW_NOT_FOUND` | 404 | `previewId` unknown or already used | — |
| `PROVIDER_NOT_FOUND` | 404 | Unknown provider id, or provider has no key | `{providerId}` |
| `PROVIDER_UNAVAILABLE` | 503 | No healthy image provider (all circuits open or none configured) | — |
| `ROUND_NOT_READY` | 409 | Scored round whose calibration is not `READY` | `{calibration}` |
| `UPLOAD_INVALID` | 400 | Target upload missing, > 10 MB, or not JPEG/PNG | `{maxMb:10}` |
| `VALIDATION_FAILED` | 400 | Any other invalid field | `{field}` |
| `SCORING_FAILED` | 409 | `rescore` called on a run that is not in `SCORING_FAILED`. Also an alert code | — |
| `NOT_FOUND` | 404 | Unknown path or image | — |

The first 20 codes are SPEC §9.5; the rest were added in phase 0 (D-019). Codes are never removed.

## 3. Caching, polling, ETag, CORS

**ETag** on `GET /api/me`, `GET /api/cities/{city}/stage/state` and `GET /api/admin/state`:
- The response carries a weak `ETag: W/"<hash of the JSON body>"` and `Cache-Control: no-cache` (`private, no-cache` for `/api/me` and admin).
- If the request's `If-None-Match` matches, the API returns **304** with the same `ETag` and no body.
- Countdowns use the absolute `endsAt` and never a "seconds left" field, so the body (and the ETag) stays the same between real changes.

**Clock sync:** every response carries the standard `Date` header (also on 304). The UI computes `offset = Date − local now` and shows `endsAt − (local now + offset)`.

**Polling** (D-008):
- Player `/api/me` and stage state: every 1.5 s at most.
- Admin state: every 2 s.
- On a network error or 5xx, back off ×2 up to 10 s, then return to normal after a success.
- Players pause polling while the tab is hidden; the stage never pauses.

**CORS** (`CORS_ALLOWED_ORIGINS`, comma-separated exact origins):
- `Access-Control-Allow-Origin: <the request origin>` only for listed origins; other origins get no CORS headers (the browser blocks them), and their preflight `OPTIONS` gets 403 with an empty body (D-022).
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE`
- `Access-Control-Allow-Headers: Authorization, X-Admin-Token, Content-Type, If-None-Match`
- `Access-Control-Expose-Headers: ETag, Date, Retry-After, Content-Disposition`
- `Access-Control-Max-Age: 600`. No credentials (no cookies are used).
- `/img/**` and `qr.png` are loaded by `<img>` and need no CORS, but get the same headers.

## 4. Phases and transitions (per city)

`Phase`: `LOBBY`, `ROUND_OPEN`, `ROUND_CLOSING`, `ROUND_SCORED`, `MINI_PODIUM`, `FINAL_SCORING`, `PODIUM_REVEAL`, `FINISHED`.

`RunStatus` (one city's run of one round): `NOT_STARTED`, `OPEN`, `CLOSING`, `SCORING`, `SCORED`, `SCORING_FAILED`, `CLOSED` (practice finished).

| From | Trigger | To |
|---|---|---|
| `LOBBY`, `ROUND_SCORED`, `MINI_PODIUM` | `POST /api/admin/rounds/{id}/start` (round not yet run in this city; scored rounds need calibration `READY`) | `ROUND_OPEN` |
| `ROUND_OPEN` | `close`, or the timer reaches `endsAt` | `ROUND_CLOSING` |
| `ROUND_OPEN` | `extend` | `ROUND_OPEN` (`endsAt` + 60 s) |
| `ROUND_CLOSING` (practice) | automatic, after in-flight generations finish or grace ends | `LOBBY` |
| `ROUND_CLOSING` (scored) | automatic, when scoring and commentary finish | `ROUND_SCORED` |
| `ROUND_CLOSING` (scored) | scoring fails after retries | stays `ROUND_CLOSING`, run `SCORING_FAILED`, alert `SCORING_FAILED` |
| `ROUND_SCORED` | `POST /api/admin/mini-podium/start` (`MINI_PODIUM_ENABLED`) | `MINI_PODIUM`, step 0 |
| `MINI_PODIUM` | `POST /api/admin/mini-podium/next` | step + 1 (up to its size) |
| `LOBBY`, `ROUND_SCORED`, `MINI_PODIUM` | `POST /api/admin/podium/start` (≥ 1 scored round `SCORED` in this city) | `FINAL_SCORING`, then automatically `PODIUM_REVEAL` step 0 when comments are ready |
| `PODIUM_REVEAL` | `POST /api/admin/podium/next` | step + 1; after step = size → `FINISHED` |
| `PODIUM_REVEAL`, `FINISHED` | `POST /api/admin/podium/reset` | `PODIUM_REVEAL` step 0 |

Anything else → 409 `INVALID_TRANSITION`.

Rules that shape the responses:
- **Close and grace (D-018):** on close, new attempts and entry changes are rejected at once. Generations already queued or running may finish within `ROUND_GRACE_SECONDS`; a result arriving later is discarded (attempt `FAILED`, code `ROUND_NOT_OPEN`). A player without an entry gets their last `DONE` attempt as the entry (`auto: true`). A generation that finishes within grace replaces an automatic entry (it is now the last `DONE`), never one the player chose (D-022). Scoring starts when nothing is in flight for the run, or when grace ends.
- **Steps:** step 0 is the intro (nothing revealed). Mini-podium size = min(3, eligible); podium size = min(5, eligible). Eligible = not kicked and has ≥ 1 non-hidden scored entry. Step *k* reveals rank *size − k + 1* (5, 4, 3, 2, 1).
- **Final ranking** is frozen at `podium/start` (total desc → best single-round score desc → earliest `selectedAt` of the player's last entry). Hiding an entry that is not yet revealed recomputes the unrevealed steps. Revealed steps never change rank; an entry hidden after its reveal is removed from the stage and its slot stays empty (D-022).
- **Final podium entry (D-015):** the player's highest-scoring non-hidden entry (tie → earlier round), shown beside that round's target.
- **Phones** get their own `final` rank once rank #1 is revealed (step = size) and in `FINISHED`.

## 5. Public and player

### `GET /api/cities` → 200
```json
[{ "code": "mde", "name": "Medellín" }, { "code": "bog", "name": "Bogotá" }]
```

### `POST /api/cities/{city}/players` → 201 (new) or 200 (same player)
Join. No auth needed. If the request carries a valid player token **for this city**, the API returns that player with 200 and ignores `nickname`. A token from another city is ignored, and a new player is created.
```json
// request
{ "nickname": "Ana_dev" }
// response
{ "playerId": "0b6e…", "token": "pt_9yQ…(43 chars)", "claimCode": "K7QX", "city": "mde" }
```
Claim code: 4 characters from `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no `0 O 1 I L`), unique within the city.
Errors: `CITY_NOT_FOUND`, `NICKNAME_INVALID`, `NICKNAME_BLOCKED`, `NICKNAME_TAKEN`, `RATE_LIMITED`.

### `GET /api/me` → 200 (ETag)
Everything a phone needs, from one URL.
```json
{
  "player": { "id": "0b6e…", "nickname": "Ana_dev", "claimCode": "K7QX", "city": "mde", "cityName": "Medellín" },
  "phase": "ROUND_OPEN",
  "round": {
    "id": "7b0e…", "name": "Café al amanecer", "scored": true,
    "targetUrl": "/img/a1d2….jpg", "targetThumbUrl": "/img/a1d2…_thumb.jpg",
    "startedAt": "2026-12-02T15:09:00.000Z", "endsAt": "2026-12-02T15:17:00.000Z",
    "attemptsPerPlayer": 3, "attemptsLeft": 2, "entryAttemptId": "c3f9…"
  },
  "attempts": [
    { "id": "c3f9…", "status": "DONE", "prompt": "una taza de café…", "queuePosition": null,
      "imageUrl": "/img/c3f9….jpg", "thumbUrl": "/img/c3f9…_thumb.jpg", "code": null,
      "createdAt": "2026-12-02T15:10:12.000Z" },
    { "id": "d47a…", "status": "QUEUED", "prompt": "café en Jardín…", "queuePosition": 4,
      "imageUrl": null, "thumbUrl": null, "code": null, "createdAt": "2026-12-02T15:12:40.000Z" }
  ],
  "final": null
}
```
- `round` is non-null in `ROUND_OPEN`, `ROUND_CLOSING`, `ROUND_SCORED` and `MINI_PODIUM` (the city's current or last round); otherwise `null`. `attempts` lists the player's attempts in that round, oldest first (empty when `round` is null).
- Attempt `status`: `QUEUED` (`queuePosition` ≥ 1, the position in the shared FIFO), `GENERATING`, `DONE`, `BLOCKED` (`code: PROMPT_BLOCKED`), `FAILED` (`code: GENERATION_FAILED` or `ROUND_NOT_OPEN`). `attemptsLeft` counts only `DONE`.
- `final`: `null` until the phone may show it (§4), then `{ "rank": 7, "total": 143.2, "podium": false }`. `rank` is `null` for players with no entry. Players never see scores before that.

Errors: `UNAUTHORIZED`, `PLAYER_KICKED`.

### `POST /api/rounds/current/attempts` → 202
```json
// request
{ "prompt": "una taza de café humeante al amanecer en un pueblo de Antioquia" }
// response
{ "attemptId": "d47a…", "queuePosition": 4 }
```
The prompt is trimmed, whitespace collapsed, and must be 1–300 chars. A blocklist hit returns 422 `PROMPT_BLOCKED`; it doesn't use up an attempt but counts toward the 3-block flag. Provider safety blocks show up later as attempt status `BLOCKED`.
Errors: `UNAUTHORIZED`, `PLAYER_KICKED`, `ROUND_NOT_OPEN`, `GENERATION_IN_FLIGHT`, `NO_ATTEMPTS_LEFT`, `PROMPT_INVALID`, `PROMPT_BLOCKED`, `RATE_LIMITED`.

### `GET /api/attempts/{id}` → 200
Same object as an item of `/api/me` `attempts`. Errors: `UNAUTHORIZED`, `PLAYER_KICKED`, `ATTEMPT_NOT_FOUND`.

### `POST /api/rounds/current/entry` → 204
```json
{ "attemptId": "c3f9…" }
```
Selects (or changes) the player's entry until close. Errors: `UNAUTHORIZED`, `PLAYER_KICKED`, `ROUND_NOT_OPEN`, `ATTEMPT_NOT_FOUND`, `ATTEMPT_NOT_SELECTABLE`, `RATE_LIMITED`.

## 6. Stage

### `GET /api/cities/{city}/stage/state` → 200 (ETag)
No auth, read-only. It exposes only what this city has already revealed; player images appear only in `reveal` and `practiceGallery`.
```json
{
  "city": { "code": "mde", "name": "Medellín" },
  "phase": "PODIUM_REVEAL",
  "joinUrl": "https://prompt-battle-ui.pages.dev/play/mde",
  "qrUrl": "/api/cities/mde/qr.png",
  "playersCount": 48,
  "nicknames": null,
  "round": null,
  "practiceGallery": null,
  "reveal": {
    "kind": "PODIUM", "roundId": null, "size": 5, "step": 2,
    "entries": [
      { "rank": 5, "nickname": "Pixel_Paisa", "prompt": "chiva colorida bajo la lluvia…",
        "imageUrl": "/img/e1….jpg", "targetUrl": "/img/t2….jpg", "roundName": "Chiva en la lluvia",
        "roundScore": 71.4, "total": 128.9,
        "commentary": { "es": "¡Esa chiva casi se sale de la pantalla!", "en": "That chiva nearly drove off the screen!" } },
      { "rank": 4, "nickname": "Ana_dev", "prompt": "…", "imageUrl": "/img/….jpg", "targetUrl": "/img/….jpg",
        "roundName": "Café al amanecer", "roundScore": 80.2, "total": 133.0,
        "commentary": { "es": "…", "en": "…" } }
    ]
  },
  "hiddenPrompts": null
}
```
- `nicknames`: every non-kicked nickname in join order, only in `LOBBY`; otherwise `null`.
- `round` (`ROUND_OPEN`, `ROUND_CLOSING`, `ROUND_SCORED`): `{ "id", "name", "scored", "targetUrl", "startedAt", "endsAt", "submissionsCount", "attemptsCount", "status" }`. `submissionsCount` = players with an entry. `status` is a `RunStatus`.
- `practiceGallery` (`LOBBY`, only while the admin shows it): up to 6 items `{ "nickname", "imageUrl", "thumbUrl" }`.
- `reveal` (`MINI_PODIUM`, `PODIUM_REVEAL`, `FINISHED`): `kind` is `MINI_PODIUM` (with `roundId`; `total` is `null`) or `PODIUM`. `entries` holds **only revealed steps**, in reveal order. `prompt` is the text the player typed (D-016). Hidden entries never appear.
- `hiddenPrompts` (`FINISHED` only): `[{ "roundId", "roundName", "prompt" }]` for each scored round played in this city.

Errors: `CITY_NOT_FOUND`.

### `GET /api/cities/{city}/qr.png` → 200 `image/png`
QR code for `{PUBLIC_UI_URL}/play/{city}`, 1024 px, error correction M. Errors: `CITY_NOT_FOUND`.

## 7. Admin

All endpoints need `X-Admin-Token` (missing or unknown → 401 `UNAUTHORIZED`). A resource of another city → 403 `ADMIN_FORBIDDEN`. Any body field that fails validation → 400 `VALIDATION_FAILED {field}`.

### `GET /api/admin/me` → 200
```json
{ "city": "mde", "cityName": "Medellín" }
```
The UI calls it after login and checks that `city` equals the route's `:city`.

### `GET /api/admin/state` → 200 (ETag) — added in phase 0
The own city's live state; run-control endpoints return the same object.
```json
{
  "city": "mde", "phase": "MINI_PODIUM", "playersCount": 48, "scoredRoundsDone": 1,
  "round": { "id": "7b0e…", "name": "Café al amanecer", "scored": true, "status": "SCORED",
             "startedAt": "…", "endsAt": "…", "extensions": 1, "imageProvider": "fal",
             "embeddingProvider": "gemini", "submissionsCount": 46, "inFlight": 0 },
  "miniPodium": { "roundId": "7b0e…", "size": 3, "step": 1,
    "preview": [ { "rank": 3, "playerId": "…", "nickname": "…", "entryId": "…", "score": 78.1, "revealed": true, "commentaryReady": true } ] },
  "podium": null,
  "practiceGalleryShown": false
}
```
`podium` has the same shape as `miniPodium` (without `roundId`; `score` is the total). Before `podium/start` it is a **preview** computed live (`step: null`), so the admin can hide entries before revealing.

### Shared round definitions (either admin)

`RoundDefinition` object:
```json
{
  "id": "7b0e…", "position": 2, "name": "Café al amanecer", "scored": true,
  "hiddenPrompt": "a steaming cup of coffee at dawn in a small Antioquia town, watercolor",
  "durationSec": 480, "attemptsPerPlayer": 3, "seed": 184467,
  "targetUrl": "/img/a1d2….jpg", "targetThumbUrl": "/img/a1d2…_thumb.jpg", "targetSource": "GENERATED",
  "locked": false,
  "calibration": { "status": "READY", "provider": "fal",
    "anchors": [ { "prompt": "a red bicycle", "imageUrl": "/img/….jpg", "thumbUrl": "/img/…_thumb.jpg", "excluded": false } ] },
  "runs": [
    { "city": "mde", "status": "SCORED", "startedAt": "…", "endsAt": "…", "extensions": 0,
      "imageProvider": "fal", "embeddingProvider": "gemini", "floor": 0.412, "mixedProviders": false },
    { "city": "bog", "status": "NOT_STARTED", "startedAt": null, "endsAt": null, "extensions": 0,
      "imageProvider": null, "embeddingProvider": null, "floor": null, "mixedProviders": false }
  ]
}
```
- `calibration.status`: `NOT_REQUIRED` (practice), `PENDING`, `READY`, `FAILED`. Anchors are generated asynchronously after create/edit with the active provider and the round's seed (§4.1 of SPEC).
- `locked` becomes true once any city starts the round.

**`POST /api/admin/rounds/generate-target`** → 200 (synchronous, up to `IMAGE_TIMEOUT_SECONDS`)
```json
// request (seed optional; random if absent)
{ "prompt": "a steaming cup of coffee at dawn…", "seed": 184467 }
// response
{ "previewId": "9e1f…", "imageUrl": "/img/9e1f….jpg", "thumbUrl": "/img/9e1f…_thumb.jpg",
  "seed": 184467, "provider": "fal", "model": "fal-ai/flux-2/klein/9b" }
```
Errors: `PROMPT_INVALID` (1–1000 chars), `PROMPT_BLOCKED`, `GENERATION_FAILED`, `PROVIDER_UNAVAILABLE`.

**`POST /api/admin/rounds`** → 201 `RoundDefinition`
- With a preview (`application/json`):
  ```json
  { "name": "Café al amanecer", "hiddenPrompt": "…", "durationSec": 480, "attemptsPerPlayer": 3,
    "scored": true, "seed": null, "previewId": "9e1f…" }
  ```
  `seed: null` takes the preview's seed.
- With an upload (`multipart/form-data`): part `round` (JSON, same fields without `previewId`) and part `target` (JPEG or PNG, ≤ 10 MB). The target is center-cropped to a square and stored as 1024² JPEG q85 plus a thumbnail. `seed: null` → random.
- Limits: `name` 1–60, `hiddenPrompt` 1–1000, `durationSec` 60–1800 (default 480; practice 180), `attemptsPerPlayer` 1–10 (default `ATTEMPTS_PER_ROUND`), `seed` 0–2147483647.
- Errors: `VALIDATION_FAILED`, `PREVIEW_NOT_FOUND`, `UPLOAD_INVALID`.

**`PUT /api/admin/rounds/{id}`** → 200 `RoundDefinition`. Same bodies as create (`previewId` or `target` optional: omit both to keep the target). If the target or seed changes, calibration restarts. Errors: those of create, plus `ROUND_NOT_FOUND`, `ROUND_LOCKED`.

**`DELETE /api/admin/rounds/{id}`** → 204. Errors: `ROUND_NOT_FOUND`, `ROUND_LOCKED`. *(added in phase 0)*

**`GET /api/admin/rounds`** → 200 `RoundDefinition[]` ordered by `position` (creation order).

**`POST /api/admin/rounds/{id}/calibrate`** → 202 `RoundDefinition` (calibration `PENDING`). Retries the anchors after a `FAILED` calibration. Errors: `ROUND_NOT_FOUND`, `ROUND_LOCKED`, `INVALID_TRANSITION` (practice round). *(added in phase 0)*

### Own city run (return `GET /api/admin/state` body, 200)

| Endpoint | Body | Errors |
|---|---|---|
| `POST /api/admin/rounds/{id}/start` | — | `ROUND_NOT_FOUND`, `INVALID_TRANSITION`, `ROUND_NOT_READY`, `PROVIDER_UNAVAILABLE` |
| `POST /api/admin/rounds/{id}/close` | — | `ROUND_NOT_FOUND`, `INVALID_TRANSITION` (not this city's open round) |
| `POST /api/admin/rounds/{id}/extend` | — | `ROUND_NOT_FOUND`, `INVALID_TRANSITION` |
| `POST /api/admin/rounds/{id}/rescore` *(phase 0)* | — | `ROUND_NOT_FOUND`, `SCORING_FAILED` (run not in `SCORING_FAILED`) |
| `POST /api/admin/mini-podium/start` *(phase 0)* | — | `INVALID_TRANSITION` (also when `MINI_PODIUM_ENABLED=false`) |
| `POST /api/admin/mini-podium/next` | — | `INVALID_TRANSITION` (not `MINI_PODIUM`, or already at size) |
| `POST /api/admin/podium/start` *(phase 0)* | — | `INVALID_TRANSITION` |
| `POST /api/admin/podium/next` | — | `INVALID_TRANSITION` (not `PODIUM_REVEAL`) |
| `POST /api/admin/podium/reset` | — | `INVALID_TRANSITION` |
| `POST /api/admin/practice/gallery` *(phase 0)* | `{ "show": true }` | `INVALID_TRANSITION` (not `LOBBY`, or no closed practice run) |

`podium/start` returns while in `FINAL_SCORING`. Comments are generated with an 8 s timeout per call (canned fallback), so `PODIUM_REVEAL` follows within ~10 s. `next` never waits on an AI call.

### Players (own city)

**`GET /api/admin/players`** → 200
```json
[ { "id": "0b6e…", "nickname": "Ana_dev", "claimCode": "K7QX", "joinedAt": "…", "kicked": false,
    "flagged": false, "blockedCount": 1, "attemptsCount": 5, "total": 133.0 } ]
```
`flagged` = 3 or more blocks in any round. `blockedCount` = blocks in the current or last round.

**`POST /api/admin/players/{id}/rename`** `{ "nickname": "Jugador_7" }` → 200 player object. Errors: `PLAYER_NOT_FOUND`, `ADMIN_FORBIDDEN`, `NICKNAME_INVALID`, `NICKNAME_TAKEN`, `NICKNAME_BLOCKED`.

**`POST /api/admin/players/{id}/kick`** → 204. The token stops working (`PLAYER_KICKED`) and the player leaves the ranking. Errors: `PLAYER_NOT_FOUND`, `ADMIN_FORBIDDEN`.

### Entries (own city)

**`GET /api/admin/entries?roundId={id}`** → 200, ordered by score desc (unscored last)
```json
[ { "entryId": "c3f9…", "playerId": "0b6e…", "nickname": "Ana_dev", "prompt": "…", "promptEn": null,
    "imageUrl": "/img/c3f9….jpg", "thumbUrl": "/img/c3f9…_thumb.jpg",
    "provider": "fal", "model": "fal-ai/flux-2/klein/9b", "embeddingProvider": "gemini",
    "cos": 0.8123, "floor": 0.4120, "score": 68.1, "hidden": false, "auto": false, "selectedAt": "…" } ]
```
`promptEn` is set only when `PROMPT_TRANSLATE_TO_EN=true`. Errors: `VALIDATION_FAILED` (no `roundId`), `ROUND_NOT_FOUND`.

**`POST /api/admin/entries/{id}/hide`** `{ "hidden": true }` (body optional, default `true`; `false` unhides) → 204. Errors: `ENTRY_NOT_FOUND`, `ADMIN_FORBIDDEN`.

**`GET /api/admin/results.csv`** → 200 `text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="results-mde.csv"`. The UI downloads it with `fetch` (the header is needed) and saves the blob.
```
city,rank,nickname,claimCode,total,<round name 1>,<round name 2>,kicked
mde,1,Pixel_Paisa,K7QX,171.3,88.0,83.3,false
```
One column per scored round played in the city. Prompts are not included.

### Shared controls (either admin; every change raises an alert for all admins)

**`GET /api/admin/providers`** → 200
```json
{
  "active": "fal", "chain": ["fal", "bfl"], "loadSplit": ["fal", "bfl"], "queueLength": 3,
  "image": [ { "id": "fal", "model": "fal-ai/flux-2/klein/9b", "configured": true, "circuit": "CLOSED",
               "inFlight": 10, "maxConcurrency": 10, "p50Ms": 3100, "p95Ms": 5400,
               "successCount": 412, "failureCount": 3, "lastError": { "kind": "TIMEOUT", "at": "…" } } ],
  "embedding": [ { "id": "gemini", "model": "gemini-embedding-2", "configured": true, "healthy": true,
                   "determinism": { "maxDiff": 0.0, "averaging": false, "checkedAt": "…" } } ],
  "commentary": { "model": "claude-sonnet-5-5", "configured": true }
}
```
`circuit`: `CLOSED`, `OPEN`, `HALF_OPEN`.

**`POST /api/admin/providers/active`** `{ "providerId": "bfl" }` → 200 providers object. Raises alert `PROVIDER_FORCED {providerId, byCity}`. Errors: `PROVIDER_NOT_FOUND`.

**`POST /api/admin/providers/probe`** → 200 (synchronous, may take up to ~60 s; it spends real credits)
```json
{ "startedAt": "…", "results": [
  { "kind": "IMAGE", "providerId": "fal", "model": "fal-ai/flux-2/klein/9b", "ok": true, "latencyMs": 3240, "errorKind": null, "determinismMaxDiff": null },
  { "kind": "EMBEDDING", "providerId": "gemini", "model": "gemini-embedding-2", "ok": true, "latencyMs": 610, "errorKind": null, "determinismMaxDiff": 0.0 },
  { "kind": "COMMENTARY", "providerId": "anthropic", "model": "claude-sonnet-5-5", "ok": true, "latencyMs": 2100, "errorKind": null, "determinismMaxDiff": null } ] }
```

**`GET /api/admin/alerts?since={instant}`** → 200, newest first, at most 100
```json
[ { "id": "…", "at": "…", "code": "PROVIDER_SWITCHED", "city": null, "params": { "from": "fal", "to": "bfl" } } ]
```
`city` is the city the alert is about (or `null` for event-wide). Alert codes (UI keys `alerts.<CODE>`): `PROVIDER_SWITCHED {from,to}`, `PROVIDER_FORCED {providerId,byCity}`, `CIRCUIT_OPEN {providerId}`, `CIRCUIT_CLOSED {providerId}`, `EMBEDDING_FAILOVER {from,to,roundId}`, `DETERMINISM_AVERAGING {providerId,maxDiff}`, `SCORING_FAILED {roundId}`, `CALIBRATION_FAILED {roundId}`, `PLAYER_FLAGGED {playerId,nickname}`, `COMMENTARY_FALLBACK {count}`, `EMBEDDING_QUOTA_LOW {used,limit}`.

**`POST /api/admin/event/reset`** `{ "confirm": "RESET" }` → 204. Deletes the snapshot, all images, all round definitions, players and runs of **every** city. Tokens stop working (401). Errors: `RESET_NOT_CONFIRMED`.

## 8. Images

- `GET /img/{uuid}.jpg`: 1024×1024 JPEG q85.
- `GET /img/{uuid}_thumb.jpg`: 384 px JPEG.
- Headers: `Cache-Control: public, max-age=31536000, immutable`. Unknown → 404 `NOT_FOUND`.
- Image ids are random UUIDs that appear only in responses allowed to show them (§6).

## 9. Change log
- 1.0 (2026-11-20, phase 0): first version from SPEC §9. Additions (D-019):
  - Endpoints: `GET /api/admin/state`, `DELETE /api/admin/rounds/{id}`, `…/calibrate`, `…/rescore`, `mini-podium/start`, `podium/start`, `practice/gallery`.
  - Error codes: those from `ROUND_NOT_FOUND` down in §2.
  - `Date`, `Retry-After` and `Content-Disposition` exposed in CORS.
  - ETag on `/api/me` and admin state.
  - `prompt` in reveal entries (D-016).
- 1.1 (2026-11-20): alert code `EMBEDDING_QUOTA_LOW` (Gemini free-tier daily quota, D-013).
