# Runbook — event day (Medellín and Bogotá)

For the owner and the two city admins. Event: **2026-12-02**, both cities at the same time.
Decisions: `docs/DECISIONS.md` (images on **BFL only**, D-027). Setup: `docs/DEPLOYMENT.md`. Contract: `docs/API.md`.

Button names are the Spanish UI labels, with the English label in brackets.

## 0. Addresses and roles

| | Medellín (`mde`) | Bogotá (`bog`) |
|---|---|---|
| Players (QR) | `https://prompt-battle-ui.pages.dev/play/mde` | `https://prompt-battle-ui.pages.dev/play/bog` |
| Stage (projector) | `…/stage/mde` | `…/stage/bog` |
| Admin | `…/admin/mde` | `…/admin/bog` |
| Backup UI (GitHub Pages) | `https://ewcastroh.github.io/prompt-battle-ui/play/mde` (same paths) | `https://ewcastroh.github.io/prompt-battle-ui/play/bog` |
| Admin token | `ADMIN_TOKEN_MDE` (only this admin) | `ADMIN_TOKEN_BOG` (only this admin) |
| Plan B links | TODO owner: Slido event, Padlet board | TODO owner: Slido event, Padlet board |
| Admin / MC / backup person | TODO owner | TODO owner |

- API: `https://<service>.up.railway.app` (TODO owner: fill in). Tokens live in the parent's git-ignored `secrets/` folder. Never paste them into a chat or a slide.
- **Each city admin controls only their own city:** start, close, +60 s, mini-podium, podium, players, entries.
- **Shared, so coordinate on the call between cities:**
  - the round definitions (editable until any city starts them);
  - forcing the image provider;
  - the probe;
  - the alerts;
  - **the event reset, which deletes BOTH cities**.
- Keep a voice or chat line open between the two admins all day.
- **No deploys on 2026-12-02.** A Railway variable change is a deploy too.

## 1. Before the day (owner)

### Production configuration (BFL only, D-027)
In Railway → Variables:
- Set `IMAGE_PROVIDER_CHAIN=bfl`, `IMAGE_LOAD_SPLIT=bfl` and `BFL_MAX_CONCURRENCY=24`.
- Remove `FAL_KEY` (or leave it out of `secrets/railway.env`).
- Never save an empty value.
- `PUBLIC_UI_URL` = the Cloudflare URL.

Then check: `GET /api/admin/providers` must show `chain: ["bfl"]`, `loadSplit: ["bfl"]` and `bfl` with `configured: true` and `maxConcurrency: 24`. The probe (§3) must show one IMAGE row (`bfl`).

### Real load test (`--real`, ≤ 40 images ≈ US$0.60, deferred from I2)
Run it after the production deploy, never on event day:
```bash
cd prompt-battle-api
set -a; . ../secrets/railway.env; set +a
PB_ADMIN_TOKEN_MDE="$ADMIN_TOKEN_MDE" PB_ADMIN_TOKEN_BOG="$ADMIN_TOKEN_BOG" \
  scripts/loadtest.sh --real --base-url https://<service>.up.railway.app
```
- **It refuses to start** unless both cities are in `LOBBY`, `ROUND_SCORED` or `MINI_PODIUM`. Against a fresh deploy that's the case.
- **What it does:** creates the round "Load test …", plays 5 players per city, closes both cities at once and prints p50/p95/max and close → scored per city.
- **Write the numbers in `docs/reports/I2.md`.** p95 must be ≤ 15 s and close → scored ≤ 15 s.
- **Then run the event reset (§7).** The test leaves players and a round behind.

### Dry run (2026-11-27)
Run everything in `docs/WORKFLOW.md`, plus:
- **Both cities close a scored round at the same second**, with live Gemini and Claude. Time "Cerrar ronda" → stage shows the scores, in each city. It must be ≤ 15 s; the fake load test can't measure this (embeddings and comments are instant there).
- **The SPEC §14.4 checks:**
  - the player flow on a phone (360×800);
  - the stage at 1920×1080 and 1280×720;
  - the podium animation;
  - the admin controls in both cities;
  - language and theme toggles on every screen;
  - the probe on real keys.

### 2026-12-01 (pre-flight)
1. Run the probe (§3). Top up the BFL credit and check the spending limits (Railway usage limit, BFL, Anthropic).
2. Run the event reset (§7). Then load the final rounds: practice + 2 scored rounds ("Rondas" [Rounds] → "Nueva ronda" [New round]).
3. Wait until each scored round's "Calibración" [Calibration] reads "Lista" [Ready].
4. Each admin signs in on their own laptop with their own token and opens their stage.
5. Print each city's QR big (the stage lobby shows it). Make a **backup QR** for each city's GitHub Pages `/play/<city>` URL with any offline QR tool, and print it too (§6).
6. Prepare Plan B (§9).

## 2. Start (each city, 60 minutes before)

1. **Projector laptop:** open `/stage/<city>` full screen (F11). The lobby shows the city name, the QR, the short URL and the joined counter. Choose the stage's language and theme with its own toggles.
2. **Admin laptop:** open `/admin/<city>`, paste the token, "Entrar" [Sign in].
   - "Este token es de …" [This token is for …] means the wrong city's token. Use your own.
3. **Check the panels:**
   - "Control en vivo" [Live controls] shows "Sala de espera" [Lobby] and 0 players.
   - "Alertas" [Alerts] has nothing new.
   - "Proveedores" [Providers]: `bfl` "Funcionando" [Working], Embeddings `gemini` "Saludable" [Healthy], Comentarios [Commentary] "IA en vivo" [Live AI].
4. **One admin** runs the probe (§3). Agree on who; it is shared.
5. Join from your own phone with a test nickname; check it shows on the stage lobby. Kick it afterwards: "Jugadores" [Players] → kick.
6. If anything fails here, see §4 or §6. If the API itself doesn't answer (`/actuator/health`), restart the service in Railway (§8).

## 3. Probe

"Proveedores" [Providers] → "Probar proveedores" [Probe providers] → confirm.
- It takes up to a minute and spends real credit: one image, two embeddings and one comment.
- If both admins press it, they share one run.

Expected rows:
| Kind | Provider | OK when |
|---|---|---|
| IMAGE | `bfl` | OK, latency a few seconds |
| EMBEDDING | `gemini` | OK, "diferencia máx." [max diff] close to 0 |
| COMMENTARY | `anthropic` | OK |

What a failure means:
- **IMAGE fails:** retry once. If it fails again, check the BFL dashboard (credit, status page); without images the game can't run, so go to §9.
- **EMBEDDING fails:** check the Gemini key and the daily quota. An `EMBEDDING_QUOTA_LOW` alert means 80 % of the 1,000 calls/day are used. Don't run load tests or extra probes that day.
- **COMMENTARY fails:** nothing to do. The podium uses canned comments, and the `COMMENTARY_FALLBACK` alert shows how many.

API equivalent (owner): `curl -s -X POST -H "X-Admin-Token: $T" $API/api/admin/providers/probe`.

## 4. A provider fails mid-round

### Images (BFL)
What players see: an attempt ends "failed". **A failed generation doesn't use an attempt**, so they press "Generar" [Generate] again.

What the API does:
- After 3 failures in 30 s it opens BFL's circuit for 60 s (alert `CIRCUIT_OPEN`).
- There is no second image provider (D-027), so new generations wait in the queue. After 60 s one trial runs; when it succeeds, the circuit closes (`CIRCUIT_CLOSED`) and the queue drains.

What the admin does:
1. **Say it out loud:** "the AI is slow, keep your prompt, try again in a minute".
2. **Watch "Proveedores"** [Providers]: the circuit state, "Éxitos / fallos" [Successes / failures], "Último error" [Last error], "En cola" [Queued].
3. **Once BFL works again,** "Usar este proveedor" [Use this provider] on `bfl` closes its circuit at once, without waiting for the trial. It is shared and alerts the other admin.
4. **Give the time back:** "+60 s" once per lost minute, before the round ends.
5. **If BFL is still down after about 5 minutes:**
   - "Cerrar ronda" [Close round]. Players who already have an image get it as their entry automatically, and the round is scored with what exists.
   - Decide with the other city: continue with the next round once BFL is back, go straight to the final podium (it needs ≥ 1 scored round), or go to Plan B (§9).
   - A round can't start while no image provider is healthy (`PROVIDER_UNAVAILABLE`).

### Embeddings (scoring)
- **Symptom:** after close, the round stays in "Ronda cerrando" [Round closing] with "falló la puntuación" [scoring failed] and the alert `SCORING_FAILED`.
- **Fix:** press "Reintentar la puntuación" [Retry scoring] in "Control en vivo" [Live controls]. It can be repeated; nothing is lost.
- **If it keeps failing:** check the Gemini quota (`EMBEDDING_QUOTA_LOW`). Without scores there is no podium for that round, so tell the room the results come after the break and use Plan B's winner vote (§9) for that round.

### Commentary (Claude)
Nothing to do: every reveal has a canned comment for its score band. Reveals never wait for the AI.

### The whole API (Railway)
Restart the service (§8). State comes back from the snapshot, losing at most about 10 s. Phones, stages and admins reconnect by themselves.

## 5. Running a round and the podium (each city, independently)

Timeline per city (`docs/WORKFLOW.md`):
| Minutes | Step |
|---|---|
| 0–5 | Entry by QR |
| 5–9 | Practice |
| 9–18 | Round 1 |
| 18–21 | Mini-podium |
| 21–30 | Round 2 |
| 30–40 | Scoring and podium 5 → 1 |
| 40–45 | Prizes and photo |

The cities don't need to be in sync.

### A round
1. **Start:** "Iniciar: {round}" [Start: {round}]. The stage shows the target and the countdown, and the phones can generate. Practice first; a scored round needs "Calibración: Lista" [Calibration: Ready].
2. **While it's open:**
   - Watch "Entregas" [Entries] and "Generando ahora" [Generating now].
   - "+60 s" adds a minute; "¡Último minuto!" [Last minute!] shows at the end.
   - Hide an inappropriate image right away: "Entregas" [Entries] → "Ocultar" [Hide]. It stays hidden even if the player picks it again.
3. **Close:** at 0:00 the round closes by itself. Otherwise press "Cerrar ronda" [Close round] → confirm. Images already being made get a few seconds to finish, then the AI scores. "Ronda puntuada" [Round scored] follows.
4. **After practice:** optionally "Galería de práctica en el escenario" [Practice gallery on stage] shows 6 random images.

### Mini-podium (after a scored round, optional)
1. **Check the three places first:** in "Entregas" [Entries], pick the round, and hide anything that shouldn't reach the projector.
2. **Start:** "Iniciar mini-podio" [Start mini-podium]. The stage shows the intro.
3. **Reveal:** "Revelar el puesto #3" [Reveal place #3], then #2, then #1. **One tap per step:** wait for the stage before tapping again; a second tap during a step is ignored.
4. **Next round:** after "Mini-podio completo" [Mini-podium complete], start the next round. Skipping the mini-podium is fine: start the next round straight from "Ronda puntuada" [Round scored].

### Final podium
1. **Check the preview first:** in "Control en vivo" [Live controls], "Vista previa del podio final" [Final podium preview] lists the top 5 by event total. Hide entries there or in "Entregas" [Entries] before starting.
2. **Start:** "Iniciar podio final" [Start final podium] → "Preparando el podio" [Preparing the podium] (about 10 s, while comments are written), then the intro on the stage.
3. **Reveal:** "Siguiente" [Next] / "Revelar el puesto #5" [Reveal place #5] … #1. One step per tap, as above. Confetti fires on #1, and phones show each player's final rank once #1 is revealed.
4. **Finish:** "Terminar y mostrar los prompts originales" [Finish and show the original prompts]. The stage shows each round's hidden prompt.
5. **Prizes:** podium phones show "¡Estás en el podio! Muestra tu código {code}" [You're on the podium! Show your code {code}]. Check the code against "Jugadores" [Players] → "Código" [Code].
6. **To replay:** "Reiniciar revelación" [Restart reveal] → confirm. The ranking doesn't change.

### Players
- **Rename or kick:** in "Jugadores" [Players]. A kicked player's token stops working and their entries leave the ranking; they can rejoin under a new nickname.
- **Flags:** a flag appears after 3 blocked prompts in a round (alert `PLAYER_FLAGGED`).

## 6. Switching to the GitHub Pages backup UI

Use it only if the Cloudflare UI doesn't load for most people. The API is the same and already allows both origins (CORS), so **nothing changes in the API**.

**What players lose:** a phone keeps its player token per site. A player who moves from Cloudflare to GitHub Pages starts with no token, must join again **under a new nickname**, and their earlier scores don't follow. So:
- **Before doors open:** switch freely; nobody has played yet.
- **During the event:** switch only between rounds, and only if Cloudflare is down for everyone. Tell the room "the old link stopped working, scan the new QR and join again with a new name".

Steps (each city):
1. **Stage:** open `https://ewcastroh.github.io/prompt-battle-ui/stage/<city>`.
2. **Admin:** open `https://ewcastroh.github.io/prompt-battle-ui/admin/<city>` and paste the token again (it is stored per site).
3. **Players:** show the printed **backup QR** (made on 12-01), or write the short URL on the slide.
   - **Important:** the QR on the stage lobby still points to `PUBLIC_UI_URL` (Cloudflare).
   - **Don't change `PUBLIC_UI_URL` during the event.** It is a Railway redeploy.
   - Change it only if the switch happens the day before.
4. **Check:** one phone joins on the backup and appears on the stage.

## 7. Reset

"Evento" [Event] → "Reiniciar evento" [Reset event] → type `RESET` → confirm.
- **What it deletes:** every round, player, image and result of **both cities**, plus the snapshot.
- **What survives:** the admin tokens (they come from Railway). Admin consoles sign out; sign in again with the same token. Players must join again.
- **Who and when:** only the owner, after telling the other city. Only:
  - after the `--real` load test;
  - after the dry run;
  - on 12-01 before loading the final rounds;
  - after the event, once both CSVs are downloaded.
- **Never between rounds of the real event.**

## 8. Restart (API)

- **How:** Railway → the service → Restart (or Redeploy without changes).
- **What's lost:** at most about 10 s of state. The snapshot in `/data` restores both cities.
- **Effect:** phones, stages and admins reconnect by themselves, and tokens keep working.
- **Mid-round:** the countdown continues from `endsAt`. Generations that were in flight are lost; those players press "Generar" [Generate] again, and no attempt is used.
- **During a calibration:** it shows "Falló" [Failed]. Press "Recalibrar" [Recalibrate] in "Rondas" [Rounds].

## 9. Plan B (no platform)

When: no images for more than about 5 minutes with no fix in sight, the API is down and a restart doesn't help, or nobody can load the UI (main or backup). Each city decides on its own, but tell the other city.

Prepared on 12-01 (TODO owner: fill in the links and the people per city in §0):
- **Slido** event per city, with Q&A open (for prompts) and one poll per round ready (for the winner).
- **Padlet** board per city, where the MC posts images, one column per round.
- The targets of each round saved as images (they are in the admin "Rondas" [Rounds]; download them on 12-01).
- An image tool the MC can use by hand (TODO owner: which one).

Flow per round:
1. Show the round's target image on the projector.
2. Players send their prompt with their nickname as a Slido question (Q&A), for 5 minutes.
3. The MC picks 5–8 prompts (by upvotes or variety), generates them by hand and posts each image on Padlet with the nickname.
4. A Slido poll among those nicknames picks the winner; show the result.
5. The final winner: the most round wins, then the Slido vote. The winner claims by nickname at the stage.

After the event, write down what happened in each city for `docs/reports/`.

## 10. After the event

1. Each admin: "Evento" [Event] → "Descargar resultados (CSV)" [Download results (CSV)]. Keep both files.
2. Owner: event reset (§7).
3. Rotate every key: BFL, Gemini, Anthropic and both admin tokens.
4. Delete the Railway service and its volume (`docs/DEPLOYMENT.md`).
