# Prelude Design Kit

Design reference for Prelude's product, marketing site, and internal tools. Distilled from the manufacturer storefront, the marketing site at preludeos.com, and the webclient.

**Version 2026.07.** Extended signal vocabulary (threat + info). Additive over v2026.06 — nothing removed.

## What's here

| File | What it's for |
|---|---|
| `DESIGN.md` | The agent entry point. Single-file summary for LLM-driven design work. |
| `PRINCIPLES.md` | The ideas behind every design decision. Read this first. |
| `TOKENS.md` | Color, type, spacing values as a reference table. |
| `tokens.css` | CSS custom properties, ready to import. |
| `COMPONENTS.md` | Copy-paste patterns for common building blocks. |
| `VOICE.md` | Copy rules. How we write. Words we don't use. |
| `reference.html` | Every pattern rendered live. Open in a browser. |

## How to use it

- Building a new page or component → read `PRINCIPLES.md`, then copy from `COMPONENTS.md`.
- Writing any new copy that goes out under Prelude's name → `VOICE.md` first.
- Hunting for a specific color, size, or font → `TOKENS.md`.
- Need to see something rendered → open `reference.html` in a browser.
- For agents / LLMs → point the LLM at `DESIGN.md` first — it has everything needed to render a Prelude surface.

## Using this kit in Claude Design

Drop this folder (or the zip) into a Claude Design project as the design system. Every prototype created inside that project then inherits the kit automatically — Claude Design will use the tokens, fonts, components, and voice rules without needing them re-stated in every prompt.

For prompt phrasing inside Claude Design:
- "Use the design system" → pulls everything from this kit.
- "Match the voice in VOICE.md" → enforces copy rules specifically.
- "Use the webclient density (44px rows, 14px body, etc.)" → triggers in-product scale rather than marketing scale.

## What v2026.07 added

Two new semantic tiers, upgrading the two-tier signal system to four-tier. Both are **rare-by-rule** on chips — they exist so destructive and system-work states have a principled home, not so every row gets more color.

- **`--threat` + `-hi` + `-lo`** — destructive actions and terminal failure (delete, revoke, bounced email, payment failed). Low-chroma oxblood, hue 30°. **Not spectral red** — a deliberate distinction from SaaS alarm colors. On chips: max one per row, terminal states only.
- **`--info` + `-hi` + `-lo`** — system / informational work in progress (syncing, indexing, updates available). Desaturated slate-blue, hue 245°, chroma lower than accent/gold so it reads neutral-informational, not as a third signal competing for attention. On chips: must always pair with a motion dot / spinner.
- **Dark-mode variants** for both tiers + `.chip-threat` / `.chip-info` edge-case overrides.

The rule remains: `--accent` for positive, `--gold` for warn, `--mute` for neutral/negative. Threat and info are rare escalations, not default choices.

## What v2026.06 added

Dark mode, designed to match the existing editorial aesthetic in inverse rather than a generic "dark theme":

- **`[data-theme="dark"]` attribute** on `<html>` activates it. Not a `.dark` class — Tailwind v4 apps configure `@custom-variant dark` against the attribute.
- **Cool-navy undertone** (`oklch(~0.19 0.012 260)`) instead of true black. Preserves the paper-warmth philosophy in inverse.
- **All 12 color tokens + 3 shadow tokens flip** automatically. Components using `var(--bone)` / `var(--deep)` / `var(--accent)` need no changes.
- **New token: `--gold-lo`** (dark-only). Low-saturation gold for chip fills, parallel to `--accent-lo`.
- **Six component overrides** for edge cases where pure token flip breaks: `.chip-gold`, `.verified-chip::before`, inputs, placeholders, `.ph`, scrims.
- **`.dark-surface` inverts without override** — navy-on-warm becomes cream-on-navy, same inverse-panel role in both themes.
- **`color-scheme: dark`** set so native form controls, scrollbars, and date pickers render correctly.
- **`.theme-toggle` icon-swap CSS** shipped in the kit. JS toggle is app-level.

## What v2026.05 added

Webclient surface needed patterns the v2026.04 marketing-derived kit didn't have. Additions:

- **CJK font fallbacks** (Noto Sans SC, Noto Serif SC) explicit in every stack — no more inconsistent rendering across client OSes.
- **In-product type scale** (`.title-page`, `.title-panel`, `.title-block`) sized for toolbars and drawer headers rather than hero sections.
- **State chip system** (neutral / accent / gold / threat / info / outline / dark) with CJK variant. Four-tier signal vocabulary available on chips; threat and info are rare by rule (terminal failure + in-progress system work only).
- **Sidebar nav, KPI card, drawer, action bar, toolbar, segmented toggle, filter pills, pagination, empty state, skeleton, banner, tabs, tag-input, search, chart primitives** — all the components a dense product UI needs.
- **Static card variant** (`.card-static`) that doesn't lift on hover, for KPI and panel use.
- **Icon library declared** — Lucide. No more freehand SVG.
- **CJK voice rules** — 您 over 你, no 哦/啦/呢, no 破折号. Was implicit, now codified.
- **Principle 9** — product density complements editorial density. Webclient is the same aesthetic at smaller scale, not a different aesthetic.

## Source of truth

The patterns here are distilled from three live builds:

1. The manufacturer storefront (Yuanhe Kitchenware demo).
2. The marketing site at preludeos.com.
3. The webclient (logged-in product).

If there's a conflict between this kit and the live builds, the live builds win and this kit gets updated.

## When to break the rules

This kit exists so every Prelude surface feels like one company. If a specific context needs something the kit doesn't cover, build it, show it to the team, and if it's worth keeping, add it here.

## Version history

- **2026.07** — Extended signal vocabulary. `--threat` (oxblood, destructive) + `--info` (slate-blue, system) with hi/lo variants and dark-mode flips. Chip variants `.chip-threat` / `.chip-info` are rare-by-rule.
- **2026.06** — Dark mode. `[data-theme="dark"]` activates; 12 color + 3 shadow tokens flip; new `--gold-lo`; 6 edge-case component overrides; `.theme-toggle` CSS.
- **2026.05** — Webclient-extended. CJK fallbacks, in-product type scale, state chips, sidebar/drawer/KPI/banner/tabs/charts/forms components, Lucide icon set declared, CJK voice rules.
- **2026.04** — Initial kit. Marketing + storefront only.
