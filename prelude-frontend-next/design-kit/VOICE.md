# Voice

How we write copy on Prelude. Applies to the marketing site, product UI, outbound emails, WeChat replies, Xiaohongshu posts — anything with Prelude's name on it.

**Version 2026.05** — Chinese register rules added (was implicit, now codified).

## Cadence

Write short. Fragments are fine. A factory boss reads fast and skims. A YC partner reads faster.

Example — the hero summary:

> We use US customs data to show Asian manufacturers exactly which American companies buy their products. Then we give them the decision-maker's email and write the English outreach.

Two sentences. A third isn't needed.

## Specificity earns trust

Always prefer a concrete number, name, or fact over an abstraction. This is how Prelude sounds credible.

| Don't | Do |
|---|---|
| "millions of buyers" | "250+ ranked buyers" |
| "fast response" | "48 hours" |
| "flexible MOQ" | "500-unit MOQ" |
| "top brands" | "Williams-Sonoma, Sur La Table" |
| "significant growth" | "+67.8% YoY" |
| "industry-leading data" | "US CBP public customs filings" |

If we can cite a number, we cite the number. If we can name the buyer, we name the buyer.

## Words and patterns we don't use

Never in our own voice. Each of these signals AI-generated SaaS copy, and each makes Prelude look like every other B2B tool.

- **Em dashes** ( — ). Use colons, periods, or commas. **One exception only:** simulated email content (the step-2 email mock, the report page-2 email previews) can use em dashes because real people write emails with them. Never in marketing headlines, UI copy, button labels, banners, empty states, or anything else.
- **"Leverage," "empower," "unlock," "supercharge," "harness," "elevate," "transform," "streamline," "seamless," "revolutionize," "game-changing," "cutting-edge," "next-gen," "best-in-class"**
- **"AI-powered," "AI-native"** in headlines or marketing copy. Fine as a transparency signal deep in product UI if the user benefits from knowing — but we usually pick a more honest label ("Draft · reviewed by you" beats "AI-generated").
- **Exclamation marks.** Even in warm contexts. Our warmth comes from specificity, not punctuation.
- **"Platform"** in hero or marketing copy. We're trade intelligence. Not a platform.
- **Hyperbole.** Claims must be checkable. If someone asked "prove it," could you?

## The italic-emphasis move

Our one consistent typographic signature: one phrase per headline in Instrument Serif italic, colored `--accent`. The phrase carries the twist.

Good examples from the marketing site:
- "Three bad options, *all of them old.*"
- "From data to deal in *three steps.*"
- "This is what every factory gets. *Free.*"
- "250 buyers. Refreshed monthly. *Specific to your products.*"

The italic line is the point. The setup sells the product; the italic sells the sentence.

When you draft a new headline, write the whole thing as plain prose, then ask: which phrase is doing the editorial work? That's the one that gets italicized.

**For Chinese headings**, italic doesn't render meaningfully on CJK glyphs. Use the `.em-zh` class instead — same accent color, font-weight 500 carries the emphasis. Examples:

- "美国精准买家：*姓名、邮箱、开发信，一手掌握。*"
- "三条老路。*全都走不通。*"
- "每家工厂都能领。*真的免费。*"

Same rule: one emphasis per heading, never two.

## Tone by surface

**Marketing site (preludeos.com)**
Confident, editorial, occasionally pointed. The problem cards can be cheeky ("Conversion rate *hope.*"). Never corporate.

**Product UI (webclient)**
Neutral, clear, helpful. No personality interjections. Labels are short and specific. Buttons are verbs. **Drawer titles can use one italic emphasis** — that's the one place product copy borrows the editorial move (see the buyer detail header pattern in COMPONENTS.md).

**English outreach emails (generated for customers)**
Warm, specific, professional. Written as a factory export rep would write it. Reference the buyer's actual purchasing data. Short — 3-4 sentences. Subject lines promise something specific and contextual to that buyer's business.

**System messages, errors, success states**
Direct. "Saved." "Couldn't connect to buyer list. Try again." Not "Oops!" or "Something went wrong :(" or "We're sorry for the inconvenience."

**WeChat and Xiaohongshu (Chinese)**
See Chinese copy rules below.

## Chinese copy rules (expanded in v2026.05)

### Pronouns and register

- **您, not 你.** Formal register everywhere — marketing, product, outreach. Prelude is selling a serious tool to factory owners and senior decision-makers. 您 is the floor, not the ceiling.
- **No 哦, 啦, 呢, 喔** at the end of sentences. These are conversational softeners that read as casual / consumer-app and undercut the credibility we're building.
- **No 亲** (vendor-speak for "dear" — Taobao seller register). We are not vendors.

### What stays English

- **璞序 appears alongside Prelude in brand lockup,** not below, not smaller by more than a few px.
- **Mono labels stay English** even in Chinese contexts. "TRADE INTELLIGENCE" works in both.
- **Numbers stay in Arabic numerals,** not 中文数字 (except cultural contexts like dates in formal documents).
- **Buyer names, company names, place names stay in their native form.** Williams-Sonoma is Williams-Sonoma in Chinese copy too. Don't translate "Sur La Table" to 沙龙.
- **HS codes, units, file IDs** — mono English always.

### Body copy

- **Body copy is entirely Chinese or entirely English.** We don't code-switch mid-sentence.
- **Avoid translationese.** If a concept doesn't translate cleanly, write a different Chinese sentence — don't translate the English word-for-word. The Chinese version can say different things in a different order.
- **No 全网最低 / 业界领先 / 重磅推出** style superlatives. Same hyperbole rule as English — claims must be checkable.

### The em-dash exception in Chinese

- **No 破折号 (——) in Chinese marketing or UI copy.** Same rule as English em-dash: use colons, periods, or commas. The exception (simulated emails) doesn't apply because outbound emails to American buyers are in English, not Chinese.
- **For headline emphasis, use the `.em-zh` class**, not punctuation tricks like 加粗 or 引号.

## Signing off

Anything going out under Prelude's name gets one scan against this doc before sending. It's not about policing voice. It's about making sure all our surfaces feel like one company.

When in doubt: shorter. More specific. No em dashes (Chinese or English). 您, never 你.
