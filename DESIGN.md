# DESIGN.md — Prompt Battle

Design rules for every screen of `prompt-battle-ui` (player, stage, admin). Decisions: `docs/DECISIONS.md` D-006, D-007. Spec: `docs/SPEC.md` §10.

Status: **v0.1 draft (2026-11-20)**. Token names and rules are binding; exact color values, fonts and icons are proposals until confirmed in UI phase U1 (see "Open choices" at the end).

Before writing any HTML, CSS or client-side JS, run the `modern-web-guidance` skill for the specific pattern. The rules below already follow its `dark-mode`, `dark-mode-toggle`, `color`, `typography`, `respect-os-text-scale` and `motion` guides; do not contradict them.

---

## 1. Direction: "Compiler / Terminal"

The event is called "Prompt Battle: ¡Compila tu Imaginación!". The UI plays on that: a prompt is source code, generating an image is compiling it, the score is the build result.

- **Images are the hero.** Chrome stays quiet so the target and the generated images carry the screen.
- **Editor flavor, not a hacker movie.** Monospace accents, syntax-colored highlights, status-bar style counters, "compiling…" progress. Body text stays in a highly legible sans serif so non-technical players are never confused.
- **Readable in sunlight and on a washed-out projector.** High contrast in both themes, large type on the stage, nothing important in thin or light weights.
- **Playful, kind, fast.** Short copy, clear states, one obvious action per screen.

Avoid: gradient blobs, glassmorphism, neon glows, Matrix rain, fake terminal typing effects on real content, emoji used as icons, all-caps for emphasis, cards inside cards.

## 2. Theme mechanics (light and dark)

Follow `modern-web-guidance` `dark-mode` and `dark-mode-toggle` exactly:

1. In `index.html` `<head>`:
   ```html
   <meta name="color-scheme" content="light dark">
   <script>
     try { document.querySelector('meta[name="color-scheme"]').content = localStorage.getItem("color-scheme") ?? "light dark"; } catch {}
   </script>
   ```
   The inline script (not a module, not deferred) exists only to prevent a flash of the wrong theme.
2. On `:root`: `color-scheme: light dark;` as the base. Never hardcode `light` or `dark` as the root default. Map the meta tag back to CSS:
   ```css
   :root {
     color-scheme: light dark;
     &:has(> head > meta[name="color-scheme"][content="dark"]) { color-scheme: dark; }
     &:has(> head > meta[name="color-scheme"][content="light"]) { color-scheme: light; }
   }
   ```
3. Every color token is defined as a raw light value and a raw dark value, combined with `light-dark()`, **plus** the mandatory `@media (prefers-color-scheme: dark)` fallback for browsers without `light-dark()` (older iPhones are common among attendees).
4. **Two-state toggle** (it sits in the screen header, where space is limited):
   - States: *system* (no stored value, meta `light dark`) and *override* (stored literally as `light` or `dark`).
   - On toggle: target = the opposite of what is rendered now. If the target equals the current system preference, **remove** the stored value; otherwise store it.
   - Never remove a stored value just because the system preference later matches it.
   - Listen to the `storage` event to stay in sync across tabs. Any JS reading `matchMedia('(prefers-color-scheme: dark)')` must also handle its `change` event.
   - The control shows an icon plus visually hidden action text ("Cambiar a tema oscuro" / "Switch to dark theme"); the inactive option is hidden with CSS selectors, so the control is correct even before JS runs.
5. The stage follows the same rules (device default plus the toggle).
6. `accent-color` and `scrollbar-color` use the theme tokens. Never transition `scrollbar-color`.
7. Support forced colors (`@media (forced-colors: active)`): borders and outlines use system colors; never convey state only through shadows, gradients or background images.

## 3. Color tokens

Two layers: **raw palette** (`--palette-*-light`, `--palette-*-dark`) and **semantic tokens** (what components use). Components never use raw palette values.

Proposed values (verify every pair in U1; adjust values, never token names):

| Semantic token | Use | Light | Dark |
|---|---|---|---|
| `--color-bg` | Page background | `#FAFAF7` (paper) | `#0E1117` (editor) |
| `--color-surface` | Panels, cards | `#FFFFFF` | `#161B22` |
| `--color-surface-raised` | Menus, dialogs | `#FFFFFF` | `#1F2630` |
| `--color-text` | Body text | `#1A1D23` | `#E6EDF3` |
| `--color-text-muted` | Secondary text | `#4A5160` | `#A3AEBB` |
| `--color-border` | Dividers (decorative) | `#D8DBE0` | `#2A313C` |
| `--color-border-strong` | Input and control boundaries (≥ 3:1) | `#6B7280` | `#6E7A8A` |
| `--color-accent` | Primary action background ("keyword" violet) | `#5B2BD9` | `#B69CFF` |
| `--color-accent-text` | Text on accent | `#FFFFFF` | `#1A0B3D` |
| `--color-focus` | Focus ring | `#5B2BD9` | `#D2C2FF` |
| `--color-success` | Done, selected ("string" green) | `#1B7F3B` | `#56D364` |
| `--color-warning` | Queue, time running out ("number" amber) | `#8A5A00` | `#E3B341` |
| `--color-danger` | Blocked, failed, errors | `#B42318` | `#FF7B72` |
| `--color-info` | Neutral info ("function" blue) | `#0B5CAD` | `#79C0FF` |

Syntax accents for decoration only (prompt editor chrome, status line, podium details): `--syntax-keyword` (= accent), `--syntax-string` (= success), `--syntax-number` (= warning), `--syntax-function` (= info), `--syntax-comment` (= text-muted).

Contrast rules (from `color`):
- Text ≥ 4.5:1 against its background; large text (≥ 24 px, or ≥ 18.66 px bold) ≥ 3:1.
- Control boundaries, focus indicators and state indicators ≥ 3:1.
- Never use color alone for state: pair it with an icon and text (✓ Selected, ⛔ Blocked, … in queue).
- Generating tints: prefer an existing token. If you must, use `color-mix(in oklab, …)`; never `in oklch` with neutrals; never only shift oklch lightness.
- Use `@media (prefers-contrast: more)` only to strengthen muted text and decorative borders.

## 4. Typography

Proposed families (both SIL Open Font License, self-hosted as `woff2`, no CDN):
- **Body / UI:** Atkinson Hyperlegible Next. Designed for legibility, which suits sunlight, projectors and mixed audiences.
- **Mono / display:** JetBrains Mono. Used for headings, countdowns, scores, counters, claim codes and editor chrome. Never for long paragraphs.

Tokens:
- `--font-body: "Atkinson Hyperlegible Next", system-ui, sans-serif;`
- `--font-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;`
- Apply `font-size-adjust: from-font` so fallbacks don't shift layout while fonts load; `font-display: swap`.
- Numbers that change (countdown, score, queue position): `font-variant-numeric: tabular-nums`.

Rules (from `typography` and `respect-os-text-scale`):
- `<meta name="text-scale" content="scale">` in `index.html`. **Never** set `font-size` on `:root` or `html`.
- All font sizes in `rem` (or `em`); unitless `line-height` (1.5 for body).
- Fluid sizes use `clamp(min-rem, rem + vw, max-rem)` with max ≤ 2.5 × min.
- `text-wrap: balance` on headings; `text-wrap: pretty` on paragraphs; never on `*`.
- `overflow-wrap: anywhere` on nicknames and prompts (long words, emoji).
- Line length ≤ 60ch for paragraphs. No justified text. No fixed heights on anything containing text.

Type scale (proposal):
| Token | Size | Use |
|---|---|---|
| `--text-sm` | `0.875rem` | Helper text, captions |
| `--text-md` | `1rem` | Body |
| `--text-lg` | `1.25rem` | Section titles on phone |
| `--text-xl` | `clamp(1.5rem, 1.2rem + 1.5vw, 2.25rem)` | Screen titles |
| `--text-stage-title` | `clamp(2.5rem, 1.5rem + 3vw, 5rem)` | Stage headings |
| `--text-stage-hero` | `clamp(5rem, 3rem + 8vw, 12rem)` | Stage countdown and score |

## 5. Space, shape, elevation

- Spacing scale in `rem`: `--space-1: 0.25rem`, `--space-2: 0.5rem`, `--space-3: 0.75rem`, `--space-4: 1rem`, `--space-6: 1.5rem`, `--space-8: 2rem`, `--space-12: 3rem`.
- Radii (terminal-like, restrained): `--radius-sm: 4px`, `--radius-md: 8px`, `--radius-pill: 999px` (badges only).
- Elevation: prefer borders and surface steps over shadows. At most one shadow token (`--shadow-raised`) for menus and dialogs, with a border fallback in forced colors.
- Tap targets: `min-block-size: 2.75rem` (44 px) and the same minimum inline size for icon buttons; at least `--space-2` between adjacent targets.

## 6. Layout

- Mobile first. The player screen must work at **360×800** with no horizontal scroll; also check reflow at 320 px wide and at 200% text size.
- Use container queries and intrinsic layouts (`repeat(auto-fit, minmax(min(100%, 10rem), 1fr))` for galleries) instead of pixel breakpoints. If a media query is needed, use `em` units.
- Use logical properties (`margin-inline`, `padding-block`).
- Stage layouts target **1920×1080** and **1280×720** and must be readable from the back of a room: no body text smaller than `--text-xl` on the stage.
- CSS architecture: `@layer reset, tokens, base, layout, components, utilities;`. Global tokens in one `tokens.css`; component styles in Angular component stylesheets (emulated encapsulation), consuming tokens only.

## 7. Components

| Component | Rules |
|---|---|
| **App header** | City name, screen title, settings button (language + theme). Compact on phone; low-emphasis corner control on the stage. |
| **Settings menu** | Opens from the header (popover). Language: ES / EN as a two-option control. Theme: the two-state toggle (§2). Changing the language updates `<html lang>` immediately. |
| **Prompt editor** | `<textarea>` in the body font (not mono) with editor chrome: a title bar reading `prompt.txt` and a status bar with the character counter (`142 / 300`, mono, tabular numbers) and attempts left. Counter turns warning near the limit, with text not only color. IME-safe Enter handling; Enter never submits. |
| **Generate button** | Primary accent button, full width on phone, disabled while a generation is in flight, with a visible reason. |
| **Generation status** | Status line in mono: "En cola · posición 4" / "Queued · position 4", "Compilando imagen…" / "Compiling image…", done, blocked, failed. Announced in an `aria-live="polite"` region; errors announced politely, never by moving focus. |
| **Attempt card** | Thumbnail (384 px source), status, "Enviar esta" / "Submit this one" button; the selected card shows a ✓ icon + "Seleccionada" / "Selected" badge and a strong border. |
| **Target image** | Tap to zoom in a `<dialog>` (light dismiss, focus returned on close). Always has alt text from the round name. |
| **Countdown** | Mono, tabular numbers. Last 60 s use the warning token plus a text cue. No flashing. |
| **Toast / inline message** | Icon + text, semantic color, dismissible, never the only place a critical error appears. |
| **Stage podium step** | Rank (mono, huge), nickname, entry image beside the target, score counting up over ~1.5 s, commentary in the stage's language. |
| **Confetti (#1 only)** | Bundled library or CSS. Only inside `prefers-reduced-motion: no-preference`; with reduced motion, show a static celebratory state. |
| **Admin tables** | Real `<table>` with header cells; thumbnails lazy-loaded; actions as buttons with text labels. |

Icons: inline SVG from one locally bundled icon set (proposal: Lucide, ISC license), `aria-hidden="true"` when next to text; icon-only buttons get a translated accessible name.

## 8. Motion

From `motion`:
- Animate only `opacity` and `transform` (individual `translate` / `scale` properties).
- Use View Transitions for screen changes and podium steps where supported; the UI must work without them.
- Default to the static state and add movement inside `@media (prefers-reduced-motion: no-preference)`. Use `@media (prefers-reduced-motion: reduce)` only to slow an animation down. Never globally set `animation-duration: 0.01ms`.
- Nothing flashes more than three times per second, in any motion setting.
- When an animation is off, the element still ends in its final state.
- Duration tokens: `--duration-fast: 120ms`, `--duration-base: 200ms`, `--duration-slow: 400ms`, `--duration-score: 1500ms`. Easing: `--ease-out: cubic-bezier(0.2, 0, 0, 1)`.
- Continuous indicators ("compiling…", "the AI is scoring…") must not run longer than needed; on the stage they stop when the phase changes.

## 9. Language and copy

- Spanish is the default and the source for Spanish copy is `docs/SPEC.md`; English is a faithful translation, not a rewrite.
- All copy in Transloco files with identical keys in `es.json` and `en.json`. No text baked into images or CSS `content`.
- Design for text up to 30% longer than the Spanish string; never truncate nicknames or prompts without a way to see the full text.
- Tone: friendly, short, second person (`tú` in Spanish). Errors say what happened and what to do next.
- Numbers and times use the active locale (`Intl` / Angular pipes with `es-CO` or `en`).

## 10. Accessibility checklist (WCAG 2.2 AA)

- Contrast per §3 in **both** themes.
- Visible focus on every interactive element (`:focus-visible`, `--color-focus`, ≥ 3:1, never removed).
- Every form field has a visible label; errors linked with `aria-describedby`.
- `<html lang>` always matches the active language.
- Live regions for generation status, round state changes and podium steps on the player screen.
- Works with OS text scaling, 200% zoom and 320 px reflow.
- Respects `prefers-reduced-motion`, `prefers-contrast`, `forced-colors`.
- Check with the `design:accessibility-review` and `break-ui` skills before UI phases close.

## 11. Open choices (confirm in U1)

1. Exact color values in §3: **kept** after contrast verification in U1 (D-021). Still check on a real phone and projector at the dry run.
2. Fonts: Atkinson Hyperlegible Next + JetBrains Mono: **confirmed** (D-021).
3. Icon set: Lucide, copied SVGs: **confirmed** (D-021).
4. Confetti: small bundled library vs CSS-only. Open, decided in U3.
