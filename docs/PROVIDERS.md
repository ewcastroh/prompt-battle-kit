# AI providers, models and API keys

Prices, limits and dates verified on **2026-11-19** and **2026-11-20**. Confirm them when you create each account: they change often.
Replaces `PROVEEDORES.md` (Spanish). Decisions: `docs/DECISIONS.md` D-009, D-011 (funded providers), D-012 (overflow split), D-013 (Gemini free tier). API details per provider: `docs/PLAN.md` §5.

**What is funded and built (D-011):** fal.ai (US$10 of credit → 10 concurrent) and Black Forest Labs for images, Gemini free tier for embeddings, Anthropic for commentary. Runware, OpenAI, Gemini image and Pollinations are documented below for reference but **not built**.

## First: models that no longer exist or die before the event

| Model | Status |
|---|---|
| `gpt-image-1` (OpenAI) | Retired 2026-10-23 |
| `gpt-image-1.5`, `gpt-image-1-mini`, `chatgpt-image-latest` (OpenAI) | Retire **2026-12-01**, one day before the event |
| Nano Banana 2 (Google) | Shut down 2026-10-29 |
| Imagen 4 on the Gemini API | Discontinued 2026-08-17 |

Most tutorials and examples online still use these IDs. That is why model IDs live only in configuration and the API refuses to start if it finds one from this list.

## Image generation

Every player in a city run must use the same model. The chain therefore prefers keeping the same model (FLUX.2 [klein] 9B) on another provider before switching models.

| Order | Provider | Model | Approx. price (1024×1024) | Fixed seed | Simultaneous requests | Key variable |
|---|---|---|---|---|---|---|
| **Primary** | fal.ai | `fal-ai/flux-2/klein/9b` | ≈ US$0.0063 (US$0.006 per megapixel) | Yes | **10 with the owner's US$10 of credit** (2 for new accounts, up to 40) | `FAL_KEY` |
| Backup 1 and overflow (same model) | Black Forest Labs (direct API) | `flux-2-klein-9b` | US$0.015 | Yes | 24 | `BFL_API_KEY` |
| Same model, position after load test | Runware | FLUX.2 [klein] 9B | from ≈ US$0.0014 (billed by compute time) | Yes | Not published | `RUNWARE_API_KEY` |
| Last resort (other vendor) | OpenAI | `gpt-image-2.5-flare`, quality `low` | ≈ US$0.006 | No | Account limits | `OPENAI_API_KEY` |
| Last resort | Google Gemini API | `gemini-nano-banana-2.1` | US$30 per million output tokens | Check | Account limits | `GEMINI_API_KEY` |
| Emergency | Pollinations | — | Free, no key | Yes | No SLA | — |

### Why concurrency matters now
One klein image takes about 3 s. If 100 players press Generate together, the last one waits roughly:

| Simultaneous requests | Last image ready after |
|---|---|
| 2 (new fal.ai account) | ≈ 150 s |
| 24 (BFL) | ≈ 15 s (at the limit) |
| 40 (fal.ai maximum self-serve) | ≈ 9 s |
| 64 (fal.ai + BFL load split) | ≈ 6 s |

In practice players spend 30–60 s writing first, and two cities rarely open a round in the same second, so real bursts are softer. Plan for the worst case anyway.

### fal.ai (primary)
- **Concurrency:** "Every new account starts with a concurrency limit of **2** concurrent requests." The limit rises automatically based on credits purchased in the last four weeks, up to **40** self-serve; above 40, contact sales. The public docs give no thresholds; the [Concurrency dashboard](https://fal.ai/dashboard/usage-billing/concurrency) showed on 2026-11-20: **US$10 → 10, US$100 → 20, US$500 → 30, US$1,000+ → 40**. The owner's budget is US$10, so `FAL_MAX_CONCURRENCY=10` until about 2026-12-18 (four weeks after purchase).
- **Use the queue API.** Queued requests (`IN_QUEUE`) do not count against the limit and are not rejected. Synchronous `fal.run` calls over the limit get `429` (`concurrent_requests_limit`, header `X-Fal-needs-retry: 1`).
- **Request:** `seed` (int), `image_size` (default is `landscape_4_3`: send square 1024×1024), `output_format` (default `png`: send `jpeg`), `num_inference_steps` (default 4), `enable_safety_checker` (default `true`).
- **Safety:** flagged images come back as **black images**, with `has_nsfw_concepts` in the response. Map that to `SAFETY_BLOCKED`.
- **Decision (D-011, D-012):** US$10 of credit → 10 concurrent; `IMAGE_LOAD_SPLIT=fal,bfl` is on in overflow mode, so BFL only takes what doesn't fit in fal.ai's 10 slots. Develop and test on the `fake` profile to save credit.

### Black Forest Labs (backup 1)
- `POST https://api.bfl.ai/v1/flux-2-klein-9b` with header `x-key`. Returns `id` and `polling_url`; you **must** poll that `polling_url`.
- Fields: `prompt`, `seed`, `width`/`height`, `output_format` (default `jpeg`), `safety_tolerance`.
- "Maximum 24 concurrent requests for most endpoints." Use exponential backoff on 429.
- "Generated images expire after 10 minutes": download immediately.

### Runware (new)
- Same model (`runware:400@2` per their model page; confirm before configuring `RUNWARE_MODEL`). Seed supported, JPG output, about 2 s per 1024×1024 image at 4 steps.
- No published concurrency limit; their docs recommend 2–4 concurrent requests for standard use. Over the per-organization rate limit: `429` with `Retry-After`; when a model's queue is full: `serviceOverloaded` with `retryAfter`.
- Load-test it before trusting it: start with `RUNWARE_MAX_CONCURRENCY=4`.

### Rejected: Cloudflare Workers AI
Hosts FLUX.2 [klein] 9B at US$0.015 per image with a generous 720 requests/minute, but a fixed `seed` is not documented. Without a fixed seed, players in a round would not be compared fairly.

### OpenAI and Gemini (last resorts)
- OpenAI: 14–17 s per image at `low`/`medium` in published tests, no seed. Check today whether your OpenAI organization needs verification for image models; it can take time.
- Gemini Nano Banana 2.1: no free plan; needs a project with billing enabled.
- Neither can meet the 15 s target with 100 players. They exist so the event can continue if the whole FLUX family is down.

### Pollinations (emergency only)
No SLA. Disabled unless `ALLOW_KEYLESS_EMERGENCY=true`.

## Similarity scoring (embeddings)

| Order | Provider | Model | Variable |
|---|---|---|---|
| Primary | Google Gemini API | `gemini-embedding-2` (GA since 2026-04-22, accepts images) | `GEMINI_API_KEY` |
| Backup | Cohere | `embed-v4.0` (multimodal) | `COHERE_API_KEY` |

- **Decision (D-013): free tier.** On the free tier Google may use the inputs to improve its products and human reviewers may read them; on the paid tier it does not. Only AI-generated images are sent (no prompts, no photos). Colombia is an allowed region.
- Free-tier rate limits are **not published**; they appear only at [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit). **Owner action:** write them here and set `GEMINI_EMBEDDING_RPM`. If the daily limit is below about 1,000 requests, enable billing (the paid tier costs US$0.00012 per image, cents for the event).
- To save calls, `EMBEDDING_MODE=entries` embeds only entries (≈ 250 calls for the whole event) instead of every attempt.
- Cohere: no key for now. A trial key allows only 5 image embeddings per minute and can't score an event.
- Embedding cost for the whole event is cents.
- Providers are never mixed within a city run. With no Cohere key, a Gemini failure at scoring time leaves the run in `SCORING_FAILED`; the admin retries with `rescore` (D-013).

## Podium commentary

| Provider | Model | Variable |
|---|---|---|
| Anthropic (through Spring AI) | `claude-sonnet-5-5` (cheaper alternative: `claude-haiku-5-5`) | `ANTHROPIC_API_KEY` |

About 22 calls for the whole event (2 cities × (5 podium + 2 × 3 mini-podium)); each call returns Spanish and English. If it fails, the API uses canned phrases. Comments never affect the score.

## Estimated budget (100 players)

| Item | Approx. quantity | Approx. cost |
|---|---|---|
| Event images on fal.ai (most of ~920: 100 players × up to 9 attempts, plus targets and anchors) | ~700–900 | US$4.5–6 |
| Overflow images on BFL during bursts | ~0–200 | US$0–3 |
| Development (mostly `fake`), `--real` load test (≤ 40), probes, dry run | ~200 | US$1.5–3 |
| Embeddings (free tier) and commentary | — | < US$1 |
| **AI total** | | **≈ US$10 fal.ai + ≤ US$5 BFL + Anthropic** |
| Hosting (Railway ≈ US$5–10, Cloudflare Pages free) | | US$5–10 |

The fal.ai credit purchase that raises your concurrency limit is spent on these same images, not an extra cost. Set a **spending limit** in every console.

## What to do today with the keys

1. Create the accounts and keys: fal.ai, Black Forest Labs, Runware, OpenAI, Google AI Studio (with billing), Cohere and Anthropic Console.
2. Set a spending limit in each one.
3. Buy fal.ai credits and note the concurrency limit shown in the dashboard.
4. Copy `.env.example` to `.env` (parent folder, for Docker Compose) and paste the keys. `.env` is in `.gitignore`: never commit it. The repos are public.
5. Quick fal.ai test through the queue API (returns a `request_id` and status/response URLs):
   ```bash
   curl -s -X POST "https://queue.fal.run/fal-ai/flux-2/klein/9b" \
     -H "Authorization: Key $FAL_KEY" -H "Content-Type: application/json" \
     -d '{"prompt":"a red bicycle on a Caribbean beach","seed":42,"image_size":"square_hd","output_format":"jpeg"}'
   ```
   Confirm the exact queue URLs and the square size value in the fal.ai docs before writing the adapter.
6. Quick OpenAI test:
   ```bash
   curl -s https://api.openai.com/v1/images/generations \
     -H "Authorization: Bearer $OPENAI_API_KEY" -H "Content-Type: application/json" \
     -d '{"model":"gpt-image-2.5-flare","prompt":"a red bicycle on a Caribbean beach","size":"1024x1024","quality":"low"}' | head -c 300
   ```
7. Test the rest with `POST /api/admin/providers/probe` once the API is deployed.
8. Ask EPAM's AI program whether the community may use a corporate gateway (such as AI DIAL) instead of personal keys. If they approve, change the adapters, not the design.

After the event: rotate or delete every key and run the event reset to delete the images.

## Sources
- [fal.ai — concurrency limits](https://fal.ai/docs/documentation/model-apis/concurrency-limits)
- [fal.ai — FLUX.2 [klein] 9B](https://fal.ai/models/fal-ai/flux-2/klein/9b/llms.txt)
- [fal.ai — FLUX.2 [klein] prompt guide (seed)](https://fal.ai/learn/devs/flux-2-klein-prompt-guide)
- [Black Forest Labs — FLUX.2 [klein] 9B API](https://docs.bfl.ml/api-reference/models/generate-or-edit-an-image-with-flux2-[klein]-9b.md)
- [Black Forest Labs — integration guidelines](https://docs.bfl.ml/api_integration/integration_guidelines.md)
- [Black Forest Labs — pricing](https://docs.bfl.ai/quick_start/pricing)
- [Runware — FLUX.2 [klein] 9B](https://runware.ai/docs/models/bfl-flux-2-klein-9b)
- [Runware — rate limits](https://runware.ai/docs/models-api/rate-limits)
- [Cloudflare Workers AI — FLUX.2 [klein] 9B](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-9b)
- [Cloudflare Workers AI — limits](https://developers.cloudflare.com/workers-ai/platform/limits/)
- [OpenAI — GPT-Image-2.5 Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)
- [GPT-Image-2.5 costs by quality (Apidog)](https://apidog.com/blog/gpt-image-2-5-flare-vs-sunburst-vs-gpt-image-2/)
- [OpenAI image model retirements (Developers Digest)](https://www.developersdigest.tech/models/image-generation/openai)
- [Nano Banana 2.1 and Google retirements (Tech Insider)](https://tech-insider.org/nano-banana-2-1-launches-halves-image-price-2026/)
- [Nano Banana 2.1 on the Gemini API (DEV Community)](https://dev.to/hassann/how-to-use-the-nano-banana-21-api-b88)
- [Gemini Embedding 2 (Google Cloud)](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/embedding-2)
- [Gemini free vs paid data use (NOAA evaluation)](https://github.com/TerrenceMcGuinness-NOAA/global-workflow/wiki/Gemini-Embedding-Provider-Evaluation-and-Key-Request)
- [GPT-Image-2.5 Flare performance (Moda)](https://moda.app/resources/models/gpt-image-2-5-flare)
