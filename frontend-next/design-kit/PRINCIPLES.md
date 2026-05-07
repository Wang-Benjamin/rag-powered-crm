# Principles

The ideas driving every design decision in Prelude. When you're not sure what to do, come back here.

**Version 2026.05** — Principle 9 added (product density complements editorial density).

## 1. Paper warmth, not SaaS white

Our backgrounds live in the bone-cream-paper range. Cold `#ffffff` never appears. The feel we're after is a research document, an economist magazine, a Swiss annual report. Not a dashboard. Not a SaaS app.

Every Prelude surface should feel like it could be printed on nice stock.

## 2. Editorial confidence, not feature grids

We avoid the three-icon-then-three-features layout that every B2B SaaS page uses. Our sections open with a monospace eyebrow, a serif display heading with one italic phrase, and a short lede. Then the content does the work.

Product capabilities are claimed in sentences. Not checkboxes, not bullet lists of adjectives.

## 3. Real artifacts beat placeholder screenshots

When we show the report on the site, we build the report in HTML. When we show the email, we render the email. Mock placeholders (the striped `ph` block) are a last resort for things genuinely not built yet.

A factory boss looking at a real-looking artifact gets it in three seconds. A YC partner sees a working output, not a promise.

## 4. Italic serif is our emphasis

When a phrase carries the editorial point, it goes in Instrument Serif italic, often tinted forest green. This is our highlighter. Bold is almost never used for emphasis.

Example: `Your buyers in America. <em>Names, contacts, outreach.</em>`

One italic phrase per heading. Not two. The italic phrase is the twist, the punchline, the differentiator.

For Chinese, the same emphasis is carried by `.em-zh` — weight 500 + accent color, since `font-style: italic` doesn't render meaningfully on CJK glyphs.

## 5. Monospace is precision, not decoration

JetBrains Mono appears on eyebrows, data labels, system annotations, IDs, and anything that reads as machine-grade information. It signals "this is real, verifiable, and specific."

We don't use it for body copy or flavor. If you're reaching for mono to add visual interest, stop.

## 6. The Chinese name is a peer, not a translation

璞序 appears alongside "Prelude" in the brand lockup, not below it as an afterthought. In body copy we don't translate everything — Chinese readers see Chinese, English readers see English. The name is the one place we consistently pair both.

This matters for the brand's identity: we're a Chinese-rooted product selling into America, not an American product localized for China. Pronoun register stays formal (您, never 你).

## 7. Specificity earns trust

$12.4M beats "millions." 48 hours beats "fast." 500-unit MOQ beats "flexible." The brand's credibility comes from naming specific things: buyers, categories, numbers, certifications.

Vague claims make the product look smaller than it is. If we can cite a number, we cite the number.

## 8. Density before decoration

Whitespace is earned. Tight data tables, three-column information grids, dense product tables — these read as serious and professional. Airy, sparse layouts with one element per screen read as content-light.

Prelude has a lot to say. The design should let us say it.

## 9. Product density complements editorial density

The webclient is denser than the marketing site, but it's not a different aesthetic — it's the same aesthetic at a smaller scale. The marketing site uses 112px section padding because hero rhythm is the point. The webclient uses 16-24px gaps because data rhythm is the point. Same fonts, same colors, same rule borders, same italic emphasis pattern. Only the spacing scale and type sizes shift down.

A user moving from preludeos.com to the logged-in product should feel they walked from the lobby into the office of the same building. Not into a different building.

This rules out: SaaS-dashboard tropes (bright colored chips for every state, alarm-red trends, gradient progress bars, illustration-heavy empty states), but also rules out treating the webclient as a stripped-down marketing page (oversized hero sections in a drawer, marketing-scale typography on a list view).
