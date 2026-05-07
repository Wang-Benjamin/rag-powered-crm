# Prelude Design System

Prelude is a trade-intelligence product with a distinct editorial identity: paper-warm surfaces, Swiss-report typography, and a Chinese-rooted brand that speaks to both markets without translating one into the other. Every surface should feel like it could be printed on nice stock, not rendered in a SaaS dashboard.

**Entry-point for agents**: Read this file first. Consult `PRINCIPLES.md` for intent, `TOKENS.md` for values, `COMPONENTS.md` for markup patterns, and `VOICE.md` before writing any copy. This file is the overview — not a replacement for those sources.

**Version 2026.07** — extended signal vocabulary (threat + info). Covers marketing (preludeos.com, storefront, reports), webclient, and both themes. Same aesthetic at two scales and two themes. Four semantic signal tiers with rare-by-rule chip variants for destructive + system states.

---

## 1. Visual Theme & Atmosphere

Prelude communicates "editorial confidence backed by real data" through bone-cream warm surfaces (`--bone` / `--paper`), a deep navy (`--deep`) that replaces cold SaaS black, and a forest-green accent (`--accent`) used for trust signals and typographic emphasis. Cold `#ffffff` never appears.

The visual references are: a Swiss annual report, an economics journal, a well-typeset research document. Not a dashboard, not a three-column feature-grid SaaS page. Sections open with a monospace eyebrow, a serif display heading with exactly one italic phrase, and a short muted lede. Product capabilities are claimed in sentences with specific numbers, not bullet lists of adjectives. Density is a feature: tight data tables and three-column grids read as serious; sparse airy layouts read as content-light.

**Marketing vs webclient density**: The webclient is denser than the marketing site, but it's the same aesthetic at a smaller scale. Marketing uses 112px section padding because hero rhythm is the point. The webclient uses 16–24px gaps because data rhythm is the point. Same fonts, same colors, same rule borders, same italic emphasis pattern — only the spacing scale and type sizes shift down. A user moving from preludeos.com to the logged-in product should feel they walked from the lobby into the office of the same building.

---

## 2. Color Palette & Roles

### Primary surfaces
| Token | OKLCH | Hex (approx) | Role |
|---|---|---|---|
| `--bone` | `oklch(0.985 0.004 80)` | `#faf8f5` | Page background — default surface, never `#ffffff` |
| `--deep` | `oklch(0.180 0.020 265)` | `#0f1b3d` | Headings, primary buttons, brandmark navy |
| `--ink` | `oklch(0.240 0.015 260)` | `#2a2b35` | Body text |

### Accent (trust, italic emphasis, positive state)
| Token | OKLCH | Hex (approx) | Role |
|---|---|---|---|
| `--accent` | `oklch(0.420 0.070 160)` | `#2d6a4f` | Italic emphasis, verified chip, positive/trust state |
| `--accent-hi` | `oklch(0.480 0.090 160)` | — | Accent hover |
| `--accent-lo` | `oklch(0.960 0.020 160)` | `#edf5f0` | Verified chip bg, accent fills, positive state bg |

### Neutral surfaces
| Token | OKLCH | Hex (approx) | Role |
|---|---|---|---|
| `--paper` | `oklch(0.975 0.006 80)` | `#f5f2ed` | Alternate section background |
| `--cream` | `oklch(0.955 0.010 80)` | `#eeebe4` | Card hover fill, button hover bg |
| `--fog` | `oklch(0.920 0.008 80)` | `#dfdcd6` | Placeholder diagonal stripe, disabled states |

### Borders, muted text, signal
| Token | OKLCH | Hex (approx) | Role |
|---|---|---|---|
| `--rule` | `oklch(0.880 0.008 80)` | `#d1cec8` | All borders — always `1px solid var(--rule)` |
| `--mute` | `oklch(0.550 0.015 260)` | `#7a7b86` | Secondary text, labels, lede paragraphs, negative trend |
| `--gold` | `oklch(0.720 0.120 85)` | `#c99c37` | Medium-tier score, warn, threat, stale |

**Color rules**:
- `--deep` is primary, not `--ink`. Headlines, primary buttons, brandmark wordmark all use `--deep`.
- `--accent` is the only green — no other greens anywhere.
- **Two-tier signal system.** `--accent` for positive / verified / opportunity. `--gold` for medium / warn / threat. `--mute` for neutral / negative / unknown.
- **No alarm-red token.** Negative trends use `--mute` — the minus sign and arrow do the work. If a state ever genuinely needs danger-red, escalate before adding a token.
- Borders are always `1px solid var(--rule)`. Never heavier, never a different color.

### Signal mapping
| Webclient state | Color | Why |
|---|---|---|
| Score 80+ | `--accent` | Positive |
| Score 60–79 | `--gold` | Medium |
| Score <60 | `--mute` | Neutral, doesn't scream |
| Trend `↗ +N%` | `--accent` | Growth |
| Trend `↘ -N%` | `--mute` | The minus sign carries it |
| Stale date (60+ days) | `--gold` | Warn |
| Competitor declining | `--accent` | **Opportunity** for our user (inverted) |
| Competitor growing | `--gold` | **Threat** to our user (inverted) |
| Email `已发送` / sent | `--deep` chip-dark | Complete |

---

## 3. Typography Rules

### Typefaces
| Face | Role | Weights |
|---|---|---|
| Instrument Serif | Display headings, italic emphasis, prices, data numbers | 400 regular, 400 italic |
| Geist | Body copy, UI labels, buttons | 300, 400, 500, 600, 700 |
| JetBrains Mono | Eyebrows, data labels, IDs, system annotations | 400, 500 |
| Noto Serif SC | CJK fallback for Instrument Serif | 400, 500, 600 |
| Noto Sans SC | CJK fallback for Geist | 300, 400, 500, 600 |

CJK fallbacks are **explicit, not system-default**. Without them, Chinese renders as PingFang on macOS, Microsoft YaHei on Windows, and whatever-the-system-has on Linux — three different brand presentations. Noto guarantees consistent rendering.

### Font stacks
```css
--font-display: 'Instrument Serif', 'Noto Serif SC', 'Times New Roman', serif;
--font-body:    'Geist', 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif;
--font-mono:    'JetBrains Mono', ui-monospace, monospace;
```

### Marketing type scale (preludeos.com, reports, public surfaces)
| Role | Size | Weight | Line Height | Letter Spacing | Notes |
|---|---|---|---|---|---|
| `display-xl` (hero) | `clamp(52px, 7.6vw, 104px)` | 400 | 1.02 | -0.015em | Hero only |
| `display-l` | `clamp(40px, 5vw, 68px)` | 400 | 1.02 | -0.015em | Major section headings |
| `display-m` | `clamp(32px, 3.6vw, 48px)` | 400 | 1.02 | -0.015em | Sub-section headings |
| `display-s` | `clamp(24px, 2.4vw, 32px)` | 400 | 1.02 | -0.015em | Card titles |
| Body | 16px | 400 | 1.55 | — | Default paragraph |
| Lede | 17–18px | 400 | 1.55 | — | `--mute`, max 52ch |
| Eyebrow | 11px | 500 | — | 0.14em | JetBrains Mono, uppercase |
| Label | 11px | 400–500 | — | 0.08em | JetBrains Mono, uppercase |

### In-product type scale (webclient)
| Class | Size | Usage |
|---|---|---|
| `.title-page` | 28px | Page-level title in drawer header |
| `.title-panel` | 22px | Panel title inside a view |
| `.title-block` | 15px | Section block title |
| Body | 14px / 1.55, Geist 400 | Default product body |
| Meta | 12.5px, `--mute` | Secondary text, hint |
| Caption | 11px, `--mute` | Mono labels, eyebrows |

In-product titles are **smaller than marketing** because they live in toolbars, drawer headers, and panels — not hero sections. The italic-emphasis pattern still applies (e.g. drawer titles).

### Italic-emphasis pattern
One italic phrase per heading, always. Wrap in `<em>` inside `.display` — it renders Instrument Serif italic in `--accent`. This is Prelude's typographic signature.

```html
<h2 class="display display-l">Three bad options,<br><em>all of them old.</em></h2>
```

**For Chinese headings**, italic doesn't render meaningfully on CJK glyphs. Use `.em-zh` — same accent color, font-weight 500 carries the emphasis:

```html
<h2 class="display display-l">三条老路，<span class="em-zh">全都走不通。</span></h2>
```

The italic phrase carries the editorial point: the twist, the punchline, the differentiator. Never two italic phrases in one heading.

---

## 4. Component Stylings

### Buttons
- **Primary** (`.btn-primary`): `--deep` bg, `--bone` text, 8px radius; hover shifts to `--accent` bg + `translateY(-1px)`
- **Secondary** (`.btn-secondary`): transparent bg, `--rule` border, `--ink` text; hover: `--cream` bg, `--ink` border
- **Ghost** (`.btn-ghost`): transparent bg + border; hover: `--cream` bg
- **Sizes**: `btn-sm` 8/14px · default 10/16px · `btn-lg` 14/22px
- Primary CTAs carry an `.arrow` span (→) that nudges `translateX(2px)` on hover
- Icon-only buttons: `.btn-icon` (32px) / `.btn-icon.sm` (28px), optional `.ghost` for borderless

### Cards
- **`.card`** (marketing, interactive): 12px radius, `--rule` border, `--bone` bg, 28px padding. Hover: border → `--ink`, `translateY(-2px)`, `var(--lift-card)`
- **`.card-static`** (webclient, non-interactive): same chrome, 20px padding, no hover transform. Variants: `.paper` (on `--paper` bg), `.tight` (16px padding)
- **`.problem-card`**: adds a mono `.verdict` line with one italic-serif word as punchline

### Placeholder (`.ph`)
- Diagonal stripe of `--cream` / `--fog` at 135deg, 14px/1px cycle
- 12px outer radius, inset 1px dashed border at 8px radius (`--mute` 30%)
- Mono label chip on `--bone` background, `<b>` for subject in `--ink`, rest in `--mute`
- Never a flat gray rectangle

### Verified chip (`.verified-chip`) and state chips (`.chip`)
- **`.verified-chip`**: `--accent` text on `--accent-lo` pill, mono 11px uppercase, accent-dot glow
- **`.chip`** variants: `chip-neutral` (cream), `chip-accent` (positive), `chip-gold` (warn), `chip-outline` (transparent), `chip-dark` (deep bg, bone text). CJK variant: `.chip.zh`
- `.chip .dot` — 5px `currentColor` circle for leading status indicator

### Data table
- Header row: JetBrains Mono, 9–11px, 0.09em letter-spacing, uppercase, `--mute`
- Row divider: `1px solid var(--rule)`
- Rank/ID: mono `--mute`, tabular numbers (`font-variant-numeric: tabular-nums`)
- Buyer name: Geist 500 `--deep`; city: Geist 13px `--mute`
- Volume: mono tabular-nums `--deep`
- Score color: `--accent` (80+), `--gold` (60–79), `--mute` (<60) — **never red**
- Density variants: `.tbl.tight` (36px rows), `.tbl` default (44px), `.tbl.comfy` (52px)
- Two-line cell: `.cell-2` for company + city. Score-with-reason: `.cell-score` with `.n` + mono `.why`

### Dark surface (`.dark-surface`)
- `--deep` bg, `--bone` text, 14px radius
- `::before` applies `radial-gradient(ellipse at 80% 120%, --accent 45%, transparent)` at 0.55 opacity
- Buttons inside flip: bone bg on deep text
- No drop shadows — the radial gradient is the depth signal

### Brandmark
- `.wordmark` (Instrument Serif 22px `--deep`) + `.zh` (Instrument Serif 18px `--mute`) as peers
- Separated by `border-left: 1px solid var(--rule)` with `padding-left: 12px`
- `.brandmark.sm` variant for webclient sidebar (17/14px)
- 璞序 is never smaller by more than a few px, never below, never an afterthought

### Navigation / shell
- **Marketing nav**: sticky, `color-mix(in oklab, var(--bone) 88%, transparent)` bg with `backdrop-filter: blur(14px)`, `border-bottom: 1px solid var(--rule)`, 64–68px tall
- **Webclient sidebar** (`.shell-nav`): 220px, paper bg, mono `.nav-label` group labels, `.nav-item.on` gets cream fill + 2px accent left-rule, brandmark top-left, user footer bottom

### Webclient-specific primitives
Full markup in `COMPONENTS.md`. Key additions:
- **KPI card** — Instrument Serif 40px number on static card chrome
- **Toolbar** — primary CTA left, search center (grow), columns/filter/kebab right
- **Banner** — `banner-ai` (gold, sparkle), `banner-warn` (bone + rule), `banner-success` (accent-lo), `banner-info` (paper)
- **Drawer / modal** — bone bg, sticky `.action-bar` bottom, italic-accent drawer title
- **Tabs** — 2px `--deep` underline, `margin-bottom: -1px` to overlap parent border
- **Segmented toggle** — cream tray, active option flips to `--deep` / `--bone`
- **Empty state** — one mono line on dashed border. No illustrations. No pep talk.
- **Skeleton** — shimmer rows, 3–5 max
- **Charts** — share bars (accent top, mute rest), stacked columns, line with accent gradient fill, sparkline rail, threat meter. No grid lines, no chartjunk.

### Icons
**Lucide.** Single library, every surface. No mixing. Sizes: 14px/1.5 (inline), 16px/1.5 (default UI), 20px/2 (banners), 24px/2 (empty state). Reference by Lucide name (`search`, `filter`, `chevron-down`, `x`, `check`, `sparkles`, etc.). Library at https://lucide.dev.

---

## 5. Layout Principles

### Marketing spacing
| Purpose | Desktop | Mobile |
|---|---|---|
| Section padding | 112px | 64px |
| Container max width | 1200px | — |
| Container side padding | 40px | 20px |
| Marketing card padding | 28px | — |
| Gap small | 12px | — |
| Gap medium | 24–32px | — |
| Gap large (grid columns) | 48–64px | — |

### Webclient spacing (4px scale)
| Token | Value | Use |
|---|---|---|
| `--s-1` | 4px | Icon-to-label gap inside chips |
| `--s-2` | 8px | Inline gap, button gap |
| `--s-3` | 12px | Toolbar gap |
| `--s-4` | 16px | Card content, KPI grid |
| `--s-5` | 20px | Card padding (product) |
| `--s-6` | 24px | Drawer body padding, between blocks |
| `--s-8` | 32px | Between sections in a long view |
| `--s-10` | 40px | KPI strip, top-of-page breathing |

### Card padding variants
- `--card-pad-marketing` = 28px (default `.card`)
- `--card-pad-product` = 20px (`.card-static`)
- `--card-pad-tight` = 16px (`.card-static.tight`)

### Row heights
- `--row-tight` 36px · `--row-default` 44px · `--row-comfy` 52px

### Radii
| Element | Radius | Token |
|---|---|---|
| Card | 12px | `--radius-card` |
| Button | 8px | `--radius-button` |
| Input | 8px | `--radius-input` |
| Pill / badge | 999px | `--radius-pill` |
| Placeholder outer | 12px | — |
| Placeholder inner dashed | 8px | — |

Section heads use a two-column grid (`1fr 1.3fr`, gap 48px): heading left, lede right. Stacks to single column below 820px.

---

## 6. Depth & Elevation

| Name | Token | Use |
|---|---|---|
| Card hover lift | `--lift-card` | Cards on hover |
| Page-style lift | `--lift-page` | Report mocks, document artifacts |
| Drawer/modal lift | `--lift-drawer` | Slide-in drawers, modals |
| Dark surface depth | Radial `--accent` gradient (`::before`) | CTA blocks, plan cards — no shadow |

Shadows are always warm-tinted with a blue-cool undertone on the warm background. Never neutral gray. Dark surfaces get no drop shadows — the radial accent gradient provides the elevation signal.

### Motion
| Token | Value | Use |
|---|---|---|
| `--t-fast` | 0.12s ease | Hover state changes, button color shifts |
| `--t-base` | 0.18s ease | Most transitions, focus rings |
| `--t-slow` | 0.3s ease | Drawer slide-in, larger movements |

Keep motion subtle. Primary button gets a 1px lift on hover; that's the most movement anything makes. No bouncy easings, no large slides.

---

## 7. Do's and Don'ts

### Do
- Use `--deep` (not `--ink`) for headings, primary buttons, and brandmark
- Use `--bone` as the default page background — never `#ffffff`
- Wrap exactly one phrase per heading in `<em>` for italic-serif emphasis in `--accent`
- For Chinese headings, use `.em-zh` instead of `<em>` — CJK italic doesn't render meaningfully
- Use JetBrains Mono for system precision only: eyebrows, IDs, data labels, annotations
- Pair "Prelude" and "璞序" in every brand lockup as peers
- Cite specific numbers: $12.4M, 48 hours, 500-unit MOQ, not "millions" or "fast"
- Use 您, not 你, in all Chinese copy (marketing, product, outreach)
- Declare Noto Serif SC / Noto Sans SC fallbacks on every font stack that may render CJK

### Don't
- Use `#ffffff` anywhere on screen
- Use any green other than `--accent` (no other greens, no blue, no indigo)
- Add a red/danger token — negative trends use `--mute`, warn/stale use `--gold`
- Use bold for typographic emphasis — that role belongs to italic serif
- Translate everything: Chinese readers see Chinese, English readers see English
- Add drop shadows to dark (`.dark-surface`) blocks
- Use em dashes (—) in marketing headlines or UI copy. Same rule for 破折号 (——) in Chinese
- Build three-icon feature grids — write product capabilities in sentences
- Add a second italic phrase to a heading that already has one
- Use SaaS-dashboard tropes in the webclient: colored chips for every state, alarm-red trends, gradient progress bars, illustration-heavy empty states
- Treat the webclient as a stripped-down marketing page: oversized heroes in a drawer, marketing-scale type on a list view

---

## 8. Responsive Behavior

Single explicit breakpoint in `tokens.css`: **720px** — container padding drops from 40px to 20px, section padding drops from 112px to 64px. Section-head two-column grid stacks at **820px**.

No other breakpoints are defined in the kit. Fluid type scale (`clamp()`) handles display sizes continuously between those bounds. If a new component needs a breakpoint, use 720px or 820px to stay consistent — don't introduce a third value.

---

## 9. Agent Prompt Guide

### Quick-reference tokens
| Role | CSS var | OKLCH |
|---|---|---|
| Background | `var(--bone)` | `oklch(0.985 0.004 80)` |
| Body text | `var(--ink)` | `oklch(0.240 0.015 260)` |
| Headings / primary | `var(--deep)` | `oklch(0.180 0.020 265)` |
| Accent | `var(--accent)` | `oklch(0.420 0.070 160)` |
| Border | `var(--rule)` | `oklch(0.880 0.008 80)` |
| Muted text / negative trend | `var(--mute)` | `oklch(0.550 0.015 260)` |
| Medium tier / warn | `var(--gold)` | `oklch(0.720 0.120 85)` |
| Display font | `var(--font-display)` | Instrument Serif + Noto Serif SC |
| Body font | `var(--font-body)` | Geist + Noto Sans SC |
| Mono font | `var(--font-mono)` | JetBrains Mono |

### Copy-paste prompts

**1. Hero section**
"Create a hero on `--bone` with a JetBrains Mono `.eyebrow` (11px, 0.14em, uppercase, `--mute`), an Instrument Serif `.display.display-l` heading where exactly one phrase is wrapped in `<em>` (renders italic `--accent`), and a 17px `--mute` lede paragraph at max 52ch."

**2. Card**
"Build a card: 12px radius, `1px solid var(--rule)` border, `--bone` background. Use `.card` (28px padding) for marketing/interactive surfaces — hover lifts with border → `--ink`, `translateY(-2px)`, `var(--lift-card)`. Use `.card-static` (20px padding) for webclient KPI cards, drawer panels, non-interactive surfaces — no hover transform."

**3. Data table row**
"Data table: JetBrains Mono `--mute` 10px uppercase headers (0.09em tracking); buyer name Geist 500 `--deep`; city Geist 13px `--mute`; volume mono tabular-nums `--deep`. Score color: `--accent` (80+), `--gold` (60–79), `--mute` (<60). **No red token.** Trends: `--accent` up, `--mute` down — the minus sign carries the meaning."

**4. Italic emphasis (English + Chinese)**
"Wrap exactly one phrase per heading in `<em>` — renders Instrument Serif italic in `--accent`. Never two. For Chinese, use `<span class=\"em-zh\">` instead (CJK italic doesn't render meaningfully; font-weight 500 + `--accent` carries it). Mono eyebrow labels stay in English even in Chinese contexts. Pronoun register is 您, never 你."

**5. State chip**
"Emit a `.chip` with variant: `chip-accent` (positive/verified), `chip-gold` (warn/medium), `chip-outline` (neutral), `chip-dark` (complete/sent), `chip-neutral` (cream fill). CJK content adds `.zh`. Optional leading 5px `.dot` in `currentColor` for status indicator."

---

## 10. Dark Mode (v2026.06)

Activated by `[data-theme="dark"]` on `<html>`. **Not** a `.dark` class — Tailwind v4 apps should configure `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *))`.

Same aesthetic in inverse: cool-navy surfaces (`oklch(~0.19 0.012 260)`) instead of warm-cream, accent/gold lightened and more saturated to stay legible on dark paper. Not true black. Not a different aesthetic.

### How it works
- **Every semantic token flips automatically.** Components reading `var(--bone)`, `var(--deep)`, `var(--accent)` etc. need no changes.
- **`.dark-surface` inverts correctly without an override** — navy-on-warm in light becomes cream-on-navy in dark (same inverse-panel role).
- **Six edge-case overrides** live in `tokens.css` for components where pure token flip breaks: `.chip-gold`, `.verified-chip::before`, form inputs, placeholders, `.ph`, modal scrims.
- **New token: `--gold-lo`** (dark-only). Parallel to `--accent-lo`. Low-saturation gold for chip fills.
- **Shadows darken** — `--lift-card`, `--lift-page`, `--lift-drawer` all use heavier alpha and darker hue in dark mode.
- **`color-scheme: dark`** is set on `[data-theme="dark"]` so native form controls, scrollbars, and date pickers render correctly.

### Toggle

Kit ships `.theme-toggle` CSS (sun/moon icon swap). JS toggle logic is app-level. For Next.js apps, use `next-themes` with `attribute="data-theme"`:

```tsx
<ThemeProvider attribute="data-theme" defaultTheme="light">
```

### What to do when building for dark

- Default to the token — it flips for free.
- Only add a `[data-theme="dark"]` override if pure flip produces wrong contrast or broken legibility. Those cases are rare and should go in the kit, not in app code.
- Italic emphasis (`--accent`) stays accent in both themes. Typography scale unchanged. Spacing unchanged. Motion unchanged. Only colors + shadows flip.
