# Tokens

Every color, font, size, and spacing value used in Prelude. If you're building something new, these are the only values you should reach for.

**Version 2026.07 — extended signal vocabulary (threat + info).** Additive over v2026.06. Nothing removed. See the bottom of this file for dark-mode token table.

## Colors

| Token | OKLCH | Hex (approx) | Role |
|---|---|---|---|
| `--bone` | `oklch(0.985 0.004 80)` | `#faf8f5` | Page background |
| `--paper` | `oklch(0.975 0.006 80)` | `#f5f2ed` | Alternate section background |
| `--cream` | `oklch(0.955 0.010 80)` | `#eeebe4` | Card hover, subtle fills |
| `--fog` | `oklch(0.920 0.008 80)` | `#dfdcd6` | Placeholder pattern, disabled states |
| `--rule` | `oklch(0.880 0.008 80)` | `#d1cec8` | Borders, separators |
| `--mute` | `oklch(0.550 0.015 260)` | `#7a7b86` | Secondary text, labels |
| `--ink` | `oklch(0.240 0.015 260)` | `#2a2b35` | Body text |
| `--deep` | `oklch(0.180 0.020 265)` | `#0f1b3d` | Headings, primary buttons, brand navy |
| `--accent` | `oklch(0.420 0.070 160)` | `#2d6a4f` | Trust/verified, italic emphasis, positive state |
| `--accent-hi` | `oklch(0.480 0.090 160)` | — | Accent hover states |
| `--accent-lo` | `oklch(0.960 0.020 160)` | `#edf5f0` | Accent fill, verified badge bg, positive state bg |
| `--gold` | `oklch(0.720 0.120 85)` | `#c99c37` | Medium tier, warning, urgency, stale |
| `--gold-lo` | `oklch(0.955 0.020 85)` | `#f5f0e6` | Warn background, parallel to `--accent-lo` |
| `--threat` | `oklch(0.440 0.085 30)` | `#8a3e2c` | Destructive actions and terminal failure states — delete, revoke, failed payment, bounced email. Low-chroma oxblood, not spectral red. On chips: max one per row, terminal states only. |
| `--threat-hi` | `oklch(0.500 0.100 30)` | — | Destructive hover |
| `--threat-lo` | `oklch(0.955 0.018 30)` | `#f5ebe8` | Destructive banner bg |
| `--info` | `oklch(0.500 0.035 245)` | `#6a7687` | System / informational messages — syncing, indexing, updates, loading. Desaturated slate-blue, lower chroma than accent/gold so it reads as neutral informational. On chips: always pair with a motion dot or spinner to signal in-progress work. |
| `--info-hi` | `oklch(0.560 0.045 245)` | — | Info hover |
| `--info-lo` | `oklch(0.960 0.012 245)` | `#edf0f3` | Info banner bg |

### Color rules

- **Never use `#ffffff`.** Default page background is `--bone`.
- **`--deep` is the primary color,** not `--ink`. Headlines, primary buttons, brandmark wordmark all use `--deep`.
- **`--accent` is the only green we use.** No other greens anywhere.
- **Four-tier signal system.** `--accent` for positive / verified / opportunity. `--gold` for medium / warn / urgency. `--threat` for destructive actions and terminal failure (delete, revoke, bounced email). `--info` for system work in progress (syncing, indexing). `--mute` for neutral / negative / unknown. Destructive color is a low-chroma oxblood, not a spectral red. **All four tiers are available on chips, banners, and buttons** — but threat and info chips are rare by rule: max one threat chip per table row, info chips must always pair with motion. Negative trends use `--mute` — the minus sign and arrow do the work. If a state ever genuinely needs danger-red, escalate before adding a token.
- **Borders are always `1px solid var(--rule)`.** Never heavier, never a different color.

### Signal mapping cheat sheet

| Webclient state | Color | Why |
|---|---|---|
| Score 80+ (high priority) | `--accent` | Positive |
| Score 60-79 (medium) | `--gold` | Medium tier |
| Score <60 (low) | `--mute` | Neutral, doesn't scream |
| Trend `↗ +N%` | `--accent` | Growth |
| Trend `↘ -N%` | `--mute` | The minus sign carries it |
| Stale date warning (60+ days) | `--gold` | Warn |
| Buyer status `新建` (new) | `--cream` neutral | Default |
| Buyer status `报价中` (quoting) | `--accent` | In progress |
| Buyer status `立即回复` (reply now) | `--gold` | Action needed |
| Competitor `下滑中` (declining) | `--accent` | **Opportunity** for our user |
| Competitor `增长中` (growing) | `--gold` | **Threat** to our user |
| Email `已发送` (sent) | `--deep` chip-dark | Complete |
| Email failed | `--gold` | Warn, not alarm |
| Email bounced / revoked / terminally failed | `--threat` chip | Terminal failure — rare by rule |
| Row syncing / indexing / processing | `--info` chip + motion dot | In-progress system work |

The competitor row is intentionally inverted — declining = good news for the manufacturer using Prelude.

## Typography

Three Latin typefaces + two CJK fallbacks. Nothing else.

| Face | Role | Weights used |
|---|---|---|
| Instrument Serif | Display headlines, italic emphasis, prices, data numbers | 400 regular, 400 italic |
| Geist | Body copy, UI labels, buttons | 300, 400, 500, 600, 700 |
| JetBrains Mono | Eyebrows, data labels, IDs, system annotations | 400, 500 |
| **Noto Serif SC** | CJK fallback for Instrument Serif (display headings) | 400, 500, 600 |
| **Noto Sans SC** | CJK fallback for Geist (body, UI) | 300, 400, 500, 600 |

CJK fallbacks are **explicit, not system-default**. Without them, Chinese text renders as PingFang on macOS, Microsoft YaHei on Windows, and whatever-the-system-has on Linux — three different brand presentations. Noto guarantees consistent rendering across every client OS.

### Font stacks

```css
--font-display: 'Instrument Serif', 'Noto Serif SC', 'Times New Roman', serif;
--font-body:    'Geist', 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif;
--font-mono:    'JetBrains Mono', ui-monospace, monospace;
```

### Marketing type scale (preludeos.com, reports, public surfaces)

| Class | Size | Usage |
|---|---|---|
| `.display-xl` | `clamp(52px, 7.6vw, 104px)` | Hero headline only |
| `.display-l` | `clamp(40px, 5vw, 68px)` | Major section headings |
| `.display-m` | `clamp(32px, 3.6vw, 48px)` | Subordinate section headings |
| `.display-s` | `clamp(24px, 2.4vw, 32px)` | Card titles |
| Body | `16px / 1.55`, Geist 400 | Default paragraph copy |
| Lede | `17-18px / 1.55, --mute` | Subtitle paragraphs under section heads |

### In-product type scale (webclient — new in v2026.05)

| Class | Size | Token | Usage |
|---|---|---|---|
| `.title-page` | `28px` | `--ip-page` | Page-level title in drawer header |
| `.title-panel` | `22px` | `--ip-panel` | Panel title inside a view |
| `.title-block` | `15px` | `--ip-block` | Section block title |
| Body | `14px / 1.55`, Geist 400 | `--ip-body` | Default product body |
| Meta | `12.5px`, `--mute` | `--ip-meta` | Secondary text, hint |
| Caption | `11px`, `--mute` | `--ip-cap` | Mono labels, eyebrows |

In-product titles are **smaller than marketing** because they live in toolbars, drawer headers, and panels — not hero sections. Italic-emphasis pattern still applies.

### The italic-emphasis pattern

In every display heading, **one** phrase is set in Instrument Serif italic, colored `--accent`. The brand's visual signature.

```html
<h2 class="display display-l">Three bad options,<br><em>all of them old.</em></h2>
```

**For Chinese headings**, italic doesn't render meaningfully on CJK glyphs. Use `.em-zh` instead — same accent color, font-weight 500 carries the emphasis:

```html
<h2 class="display display-l">三条老路，<span class="em-zh">全都走不通。</span></h2>
```

Rules:
- One italic emphasis per heading. Not two.
- The italic phrase carries the editorial point — the twist, the punchline, the differentiator.
- Default emphasis color is `--accent`. Leave it `--deep` only when context is fully neutral and no warmth is wanted.

### The eyebrow + label

| Class | Size | Usage |
|---|---|---|
| `.eyebrow` | `11px / 500, 0.14em, upper` | JetBrains Mono, above every section heading |
| `.label` | `11px / 0.08em, upper` | JetBrains Mono, data column labels, small UI labels |

Both stay English even in Chinese contexts. Mono is the system voice and crosses languages.

## Spacing

### Marketing scale

| Purpose | Value |
|---|---|
| Section padding | `112px` desktop, `64px` mobile |
| Container max width | `1200px` with `40px` side padding |
| Marketing card padding | `28px` (`--card-pad-marketing`) |
| Gap small | `12px` |
| Gap medium | `24-32px` |
| Gap large | `48-64px` (grid columns) |

### Webclient scale (new in v2026.05)

4px-based scale for product UI. Tighter than marketing's 8/16/24/48 because dense data needs density.

| Token | Value | Typical use |
|---|---|---|
| `--s-1` | `4px` | Icon-to-label gap inside chips |
| `--s-2` | `8px` | Inline gap, button gap |
| `--s-3` | `12px` | Toolbar gap |
| `--s-4` | `16px` | Card content gap, KPI grid gap |
| `--s-5` | `20px` | Card padding (product) |
| `--s-6` | `24px` | Drawer body padding, between major blocks |
| `--s-8` | `32px` | Between sections in a long view |
| `--s-10` | `40px` | Around KPI strip, top-of-page breathing |

### Card padding variants

| Token | Value | Usage |
|---|---|---|
| `--card-pad-marketing` | `28px` | Marketing site cards (default `.card`) |
| `--card-pad-product` | `20px` | KPI cards, drawer panels (`.card-static`) |
| `--card-pad-tight` | `16px` | KPI lite, dense panels (`.card-static.tight`) |

### Row heights (tables — new in v2026.05)

| Token | Value | Usage |
|---|---|---|
| `--row-tight` | `36px` | Shipment records, super-dense data |
| `--row-default` | `44px` | Buyers, competitors, default tables |
| `--row-comfy` | `52px` | Leads, less frequent interaction |

## Borders, radii, shadows

| Element | Treatment |
|---|---|
| All borders | `1px solid var(--rule)` |
| Card radius | `12px` (`--radius-card`) |
| Button radius | `8px` (`--radius-button`) |
| Input radius | `8px` (`--radius-input`, same as button) |
| Pill / badge radius | `999px` (`--radius-pill`) |
| Placeholder radius | `12px` outer, `8px` inner dashed |
| Card hover lift | `--lift-card` |
| Page-style lift (report mocks) | `--lift-page` |
| Drawer/modal lift | `--lift-drawer` (new in v2026.05) |

Shadows are always warm-tinted (cool blue undertone on warm background). Never neutral gray.

Dark surfaces (`--deep` background) don't use shadows — they use a radial green gradient in one corner for depth instead.

## Motion

| Token | Value | Usage |
|---|---|---|
| `--t-fast` | `0.12s ease` | Hover state changes, button color shifts |
| `--t-base` | `0.18s ease` | Most transitions, focus ring animations |
| `--t-slow` | `0.3s ease` | Larger movements, drawer slide-in |

Keep motion subtle. Primary button gets a 1px lift on hover; that's the most movement anything in the system makes. No bouncy easings, no large slides.

## Icons

**Lucide.** Single library across all surfaces. No mixing icon sets.

| Size | Stroke width | Use |
|---|---|---|
| 14px | 1.5 | Inline with body text, button icons |
| 16px | 1.5 | Default UI icon, toolbar buttons |
| 20px | 2 | Banner icons, prominent affordances |
| 24px | 2 | Empty state, large feature icons |

Reference Lucide icons by name (e.g., `search`, `filter`, `chevron-down`, `x`, `check`, `bell`, `more-vertical`, `mail`, `eye`, `calendar`, `clock`, `alert-circle`, `info`, `sparkles`). The library is at https://lucide.dev — copy SVG paths from there.

## Dark mode (new in v2026.06)

Dark mode is activated by `[data-theme="dark"]` on the `<html>` element — **not** by a `.dark` class. Every token in the light-mode table has a dark-mode counterpart; components flip automatically.

Aesthetic: same editorial feel, cool-navy undertone instead of warm-cream. Not a true black — surfaces stay at `oklch(~0.19 L)` with the `260` chroma axis, keeping the paper-warmth philosophy expressed in inverse.

### Dark values

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--bone` | `oklch(0.985 0.004 80)` | `oklch(0.185 0.012 260)` | Page background |
| `--paper` | `oklch(0.975 0.006 80)` | `oklch(0.225 0.013 260)` | Alt section bg |
| `--cream` | `oklch(0.955 0.010 80)` | `oklch(0.260 0.014 260)` | Card hover fill |
| `--fog` | `oklch(0.920 0.008 80)` | `oklch(0.305 0.015 260)` | Placeholder stripe |
| `--rule` | `oklch(0.880 0.008 80)` | `oklch(0.345 0.016 260)` | Borders |
| `--mute` | `oklch(0.550 0.015 260)` | `oklch(0.640 0.018 255)` | Secondary text |
| `--ink` | `oklch(0.240 0.015 260)` | `oklch(0.910 0.008 260)` | Body text |
| `--deep` | `oklch(0.180 0.020 265)` | `oklch(0.930 0.010 80)` | Primary — inverts to warm-cream |
| `--accent` | `oklch(0.420 0.070 160)` | `oklch(0.650 0.115 160)` | Lighter + more saturated in dark |
| `--accent-hi` | `oklch(0.480 0.090 160)` | `oklch(0.720 0.125 160)` | |
| `--accent-lo` | `oklch(0.960 0.020 160)` | `oklch(0.295 0.065 160)` | Chip bg |
| `--gold` | `oklch(0.720 0.120 85)` | `oklch(0.765 0.145 85)` | |
| `--gold-lo` | `oklch(0.955 0.020 85)` | `oklch(0.315 0.075 85)` | Warn fills |
| `--threat` | `oklch(0.440 0.085 30)` | `oklch(0.680 0.110 30)` | Destructive actions |
| `--threat-hi` | `oklch(0.500 0.100 30)` | `oklch(0.740 0.120 30)` | Destructive hover |
| `--threat-lo` | `oklch(0.955 0.018 30)` | `oklch(0.310 0.070 30)` | Destructive bg |
| `--info` | `oklch(0.500 0.035 245)` | `oklch(0.700 0.060 245)` | System messages |
| `--info-hi` | `oklch(0.560 0.045 245)` | `oklch(0.760 0.070 245)` | Info hover |
| `--info-lo` | `oklch(0.960 0.012 245)` | `oklch(0.305 0.050 245)` | Info bg |

Shadow tokens (`--lift-card`, `--lift-page`, `--lift-drawer`) also darken in dark mode — heavier alpha, darker hue.

### Component overrides in dark mode

Six components need explicit dark overrides because pure token flip produces wrong contrast:

- `.chip-gold` — uses `color-mix` for bg/text/border to stay legible on dark paper
- `.verified-chip::before` glow — accent glow strengthened from light-mode alpha
- `input` / `textarea` / `select` — paper bg, ink text, rule border
- `input::placeholder` / `textarea::placeholder` — `--mute` at 70% alpha
- `.ph` placeholder — stripes swap to paper/cream (no fog in dark)
- `.scrim` / `.modal-scrim` — near-black at 72% alpha

`.dark-surface` does **not** need an override — its tokens naturally invert (navy → cream), giving the same "inverse panel" role in both themes.

### `color-scheme` property

Kit declares `color-scheme: dark` on `[data-theme="dark"]` and `color-scheme: light` on `:root`. Tells the browser to use native dark form controls, scrollbars, and date pickers.

### Theme toggle

Kit ships `.theme-toggle` icon-swap CSS — sun icon in light, moon icon in dark. JS toggle logic is the app's responsibility (not kit).
