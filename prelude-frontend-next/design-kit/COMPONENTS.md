# Components

Copy-paste patterns for common building blocks. All classes reference `tokens.css` — import it and these work.

**Version 2026.05.** Marketing components from v2026.04 unchanged. Webclient sections added — search "**Webclient ·**" to find them.

---

## Marketing components

### Button

Three variants. Use `btn-primary` for the one thing you want the user to do per screen. Everything else is `btn-secondary` or `btn-ghost`.

```html
<button class="btn btn-primary">Get the report <span class="arrow">→</span></button>
<button class="btn btn-secondary">How it works</button>
<button class="btn btn-ghost">Cancel</button>

<!-- Sizes -->
<button class="btn btn-primary btn-lg">Large primary</button>
<button class="btn btn-secondary btn-sm">Small secondary</button>
```

The `arrow` span on primary CTAs nudges right on hover — small detail, keep it. Primary on hover also shifts to `--accent` green with a 1px lift. Both are signature interactions.

### Eyebrow + section heading

Every section opens with a monospace eyebrow above a serif display heading. One phrase in italic, almost always in `--accent` green. Lede paragraph in the right column.

```html
<section class="block">
  <div class="container">
    <div class="section-head">
      <div>
        <span class="eyebrow">How it works</span>
        <h2 class="display display-l">
          From data to deal<br>in <em>three steps.</em>
        </h2>
      </div>
      <p class="lede">
        Short subtitle paragraph. Muted color. Max 52ch width so it never runs long.
      </p>
    </div>
    <!-- section content -->
  </div>
</section>
```

For a Chinese version, swap the `<em>` for `<span class="em-zh">`:

```html
<h2 class="display display-l">从数据到成交，<span class="em-zh">三步搞定。</span></h2>
```

Rules:
- One italic phrase per heading. Never two.
- The italic phrase is the point. The setup sells the section; the italic sells the sentence.
- Use manual `<br>` tags to control line breaks at display sizes. Don't trust natural flow.

### Card (interactive, marketing default)

12px radius, 1px rule border, subtle hover lift. Default `.card` lifts on hover.

```html
<div class="card">
  <div class="eyebrow" style="margin-bottom: 16px;">01 · Category</div>
  <h3 class="display display-s" style="margin: 0 0 12px;">Card title goes here.</h3>
  <p style="color: var(--mute); margin: 0;">Body copy.</p>
</div>
```

For problem-style cards with a verdict line at the bottom:

```html
<div class="card problem-card">
  <div class="chan"><span class="num">01</span> Canton Fair</div>
  <h3>Fly to Guangzhou. Rent a booth. Hand out 500 cards. Wait.</h3>
  <div class="verdict">Conversion rate <em>hope.</em></div>
</div>
```

The verdict is a mono label with one italic-serif word at the end — the punchline treatment.

### Placeholder

Diagonal stripe pattern with dashed inner border and monospace label. Never a flat gray rectangle.

```html
<div class="ph" style="aspect-ratio: 4/3; min-height: 300px;">
  <div class="ph-label">
    <b>What goes here</b> · short description of the intended content
  </div>
</div>
```

### Verified chip

Accent-green pill with a glowing dot. For trust signals: verified manufacturer, certified product, confirmed contact.

```html
<span class="verified-chip">Verified</span>
```

### Dark surface

Inverse contrast block with a radial accent-green gradient in one corner. Used for CTA blocks and plan cards.

```html
<div class="dark-surface">
  <span class="eyebrow">Prelude · Full plan</span>
  <div class="display display-l">¥8,999<small>/ quarter</small></div>
  <p>Billed quarterly in RMB. No setup fee. Cancel any time.</p>
  <button class="btn" style="background: var(--bone); color: var(--deep); border-color: var(--bone);">
    Get started <span class="arrow">→</span>
  </button>
</div>
```

Inside a dark surface, buttons flip: primary becomes bone-on-deep. Never add a drop shadow to a dark surface — the radial gradient provides depth.

### Brandmark

Wordmark + Chinese name, separated by a vertical rule. Optional icon on the left.

```html
<a href="/" class="brandmark">
  <span class="mark" aria-hidden="true">
    <!-- svg or initial tile -->
  </span>
  <span class="wordmark">Prelude</span>
  <span class="zh">璞序</span>
</a>
```

Always pair English and Chinese. 璞序 is never an afterthought. Small variant `.brandmark.sm` for the webclient sidebar top.

---

# Webclient components (new in v2026.05)

Patterns specific to the logged-in product surface. Denser than marketing. Built on the same tokens — same fonts, same colors, same radii — so a webclient view sitting next to a marketing page reads as one company.

## Webclient · Static card

For KPI cards, drawer panels, and other surfaces that aren't clickable. No hover transform.

```html
<div class="card-static">
  <span class="eyebrow">买家总数</span>
  <div class="title-page">105</div>
  <p class="mono" style="color: var(--mute); font-size: 12px;">正在进口您的产品</p>
</div>

<!-- Tighter padding -->
<div class="card-static tight">…</div>

<!-- On paper background -->
<div class="card-static paper">…</div>
```

## Webclient · Sidebar nav

220px width, paper background. Mono group labels above nav-item clusters. Selected item: cream fill + 2px accent rule on the left. Brand lockup top-left, user footer bottom.

```html
<aside class="shell-nav">
  <div class="shell-top">
    <a href="/" class="brandmark sm">
      <span class="mark"><!-- icon --></span>
      <span class="wordmark">Prelude</span>
      <span class="zh">璞序</span>
    </a>
    <div class="tools">
      <button class="btn-icon ghost sm" title="通知"><!-- bell --></button>
      <button class="btn-icon ghost sm" title="折叠"><!-- panel-left --></button>
    </div>
  </div>

  <div class="nav-label">市场</div>
  <div class="nav-item on">买家</div>
  <div class="nav-item">竞争对手</div>

  <div class="nav-label">商机</div>
  <div class="nav-item">我的线索</div>
  <div class="nav-item">Storefront · 店铺</div>

  <div style="height: 12px;"></div>
  <div class="nav-item">邮件推广</div>
  <div class="nav-item">设置 <span class="chev"><!-- chevron-right --></span></div>

  <div class="shell-foot">
    <span class="avatar sm">B</span>
    <span class="name">Benjamin Ma…</span>
    <button class="lang-toggle">中</button>
    <button class="btn-icon ghost sm" title="退出"><!-- log-out --></button>
  </div>
</aside>
```

Rules:
- `.nav-label` is a mono group label, all-caps with 0.14em letter-spacing.
- Only one `.nav-item.on` per nav at a time.
- The selected accent rule animates in on click via the same `--t-fast` transition.
- `.shell-foot` sticks to the bottom via flexbox `margin-top: auto`.

## Webclient · KPI card

The most-used component in the webclient. Display-font number for report-page gravitas.

```html
<div class="card-static" style="min-height: 112px;">
  <span class="kpi-eyebrow">买家总数</span>
  <div class="kpi-num">105</div>
  <div class="kpi-sub">正在进口您的产品</div>
</div>

<!-- Accent variant for high-tier metrics -->
<div class="card-static">
  <span class="kpi-eyebrow">高意向买家</span>
  <div class="kpi-num accent">3</div>
  <div class="kpi-sub">评分 80+</div>
</div>

<!-- Lite variant — nested inside a drawer overview -->
<div class="card-static tight" style="min-height: 82px;">
  <span class="kpi-eyebrow">中国集中度</span>
  <div class="kpi-num accent" style="font-size: 28px;">13.8%</div>
</div>
```

Rules:
- `.kpi-num` is Instrument Serif at 40px (28px for lite) — the serif gives gravitas at a size where the sans would read flat.
- `.kpi-eyebrow` is mono uppercase, top of the card.
- `.kpi-sub` is body-font, muted, bottom of the card.
- KPI strips are typically 4-up in a `display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px`.

## Webclient · State chip

Four-tier signal system. Chips go neutral / accent / gold / threat / info / outline / dark. `chip-threat` is reserved for terminal failure row states (bounced, revoked, payment failed) — max one per row. `chip-info` is for in-progress system work (syncing, indexing, processing) and should always pair with a motion dot or spinner. Stale data or "needs attention" still goes to `chip-gold`, not threat. CJK content uses `.chip.zh`.

```html
<!-- Latin -->
<span class="chip chip-neutral">NEW</span>
<span class="chip chip-accent"><span class="dot"></span>QUOTING</span>
<span class="chip chip-gold">REPLY NOW</span>
<span class="chip chip-outline">DRAFT</span>
<span class="chip chip-dark">SENT</span>

<!-- Chinese -->
<span class="chip zh chip-outline">新建</span>
<span class="chip zh chip-accent"><span class="dot"></span>报价中</span>
<span class="chip zh chip-gold">立即回复</span>
<span class="chip zh chip-dark">已发送</span>
```

Variants: `chip-neutral` (cream bg), `chip-accent` (positive), `chip-gold` (medium/warn), `chip-outline` (1px rule, transparent), `chip-dark` (deep bg, bone text).

The `.dot` is a 5px circle in `currentColor` — useful for chips that need a leading status indicator.

## Webclient · Tag

Softer than chip. Used for category metadata: products, HS codes, logistics partners.

```html
<span class="tag">Lighting Fixtures</span>
<span class="tag mono">940542</span>
<span class="tag outline">Evergreen International Ltd</span>
```

`.mono` for codes/IDs. `.outline` for items inside a tag-input or removable contexts.

## Webclient · Form elements

All inputs share 8px `--radius-input` and 1px `--rule` border. **Focus state is an inset 2px accent rule at the bottom of the field** — like a form line on paper. No halo, no outer ring, no border-color flip. The neutral border stays put and the accent drops in underneath the text, where your cursor sits. Quiet and editorial; matches the flat architectural posture of the rest of the kit.

```css
.input:focus {
  outline: none;
  border-color: var(--rule);
  box-shadow: inset 0 -2px 0 var(--accent);
}
```

```html
<div class="field">
  <label class="field-label">产品名称</label>
  <input class="input" placeholder="例：硅胶厨具">
  <span class="field-hint">默认产品的英文名称</span>
</div>

<!-- Search -->
<div class="input-search">
  <span class="icon"><!-- lucide search --></span>
  <input class="input" placeholder="搜索买家…">
</div>

<!-- Select -->
<div class="select-wrap">
  <select class="select">
    <option>厨具 · 硅胶</option>
    <option>照明 · 灯具</option>
  </select>
  <span class="chev"><!-- lucide chevron-down --></span>
</div>

<!-- Textarea -->
<textarea class="textarea" placeholder="添加具体细节…"></textarea>

<!-- Tag input -->
<div class="tag-input">
  <span class="tag mono">ISO 9001:2015</span>
  <span class="tag mono">FDA 21 CFR 177.2600</span>
  <input placeholder="输入认证名称，按回车添加">
</div>

<!-- Checkbox -->
<span class="checkbox on"><!-- lucide check --></span>
```

Rules:
- `.input.readonly` for non-editable display fields — paper background, mute text.
- `.field-label` and `.field-hint` always pair around the control.
- Tag-input: child tags are `.tag` (any variant) and the trailing input has no border.

## Webclient · Toolbar

Above every table. Primary CTA on the left, search in the middle (grow), filter/columns/kebab on the right.

```html
<div class="toolbar">
  <button class="btn btn-primary btn-sm">+ 管理买家 <!-- chevron-down --></button>
  <div class="input-search grow" style="max-width: 320px;">
    <span class="icon"><!-- search --></span>
    <input class="input" placeholder="搜索买家…">
  </div>
  <button class="btn btn-secondary btn-sm">4 列 <!-- chevron-down --></button>
  <button class="btn btn-secondary btn-sm"><!-- filter -->筛选</button>
  <button class="btn-icon"><!-- more-vertical --></button>
</div>
```

The toolbar pattern is consistent across every list view in the webclient. Don't reorder.

## Webclient · Data table

Three densities. Mono headers. Two-line cells for company-with-address and score-with-reason. Pagination at the bottom-right.

```html
<div class="tbl-wrap">
  <table class="tbl">
    <thead>
      <tr>
        <th style="width: 32px;"><span class="checkbox"></span></th>
        <th><span class="sort">公司 <!-- chevrons --></span></th>
        <th class="num">货量</th>
        <th class="num">趋势</th>
        <th class="num">评分</th>
        <th>状态</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="checkbox"></span></td>
        <td>
          <div class="cell-2">
            <span class="p1">Ei Sprking Inc</span>
            <span class="p2">Denver, CO · greg.forrest@…</span>
          </div>
        </td>
        <td class="num">~0 个集装箱</td>
        <td class="num"><span class="trend up">↗ +127%</span></td>
        <td>
          <div class="cell-score">
            <span class="n">95</span>
            <span class="why zh">复购窗口开启·增长强劲</span>
          </div>
        </td>
        <td><span class="chip zh chip-outline">新建</span></td>
      </tr>
      <!-- more rows -->
    </tbody>
  </table>
  <div class="pagination">
    <span class="count">显示第 1–25 条，共 105 条买家</span>
    <div class="pagination-ctrl">
      <button disabled><!-- chevron-left --></button>
      <span class="count">第 1 页，共 5 页</span>
      <button><!-- chevron-right --></button>
    </div>
  </div>
</div>
```

### Density variants

| Class | Row height | Use |
|---|---|---|
| `.tbl` (default) | 44px | Buyers, competitors, default |
| `.tbl.tight` | 36px | Shipment records, super-dense data |
| `.tbl.comfy` | 52px | Leads, less frequent interaction |

### Cell patterns

- **`.cell-2`** — two-line cell, primary text + muted secondary. Used for company + address.
- **`.cell-score`** — right-aligned score number + mono reason line. **Every qualifying buyer row carries a score-reason.** Score color: `.n` (accent, default) / `.n.med` (gold, score 60-79) / `.n.low` (mute, <60).
- **`.trend.up`** — accent for growth. **`.trend.down`** — mute for decline. The minus sign carries the meaning; no alarm-red.
- **`.date-cell.warn`** — gold for stale dates (>60 days), with an `alert-circle` icon prefix.
- **`.truncate`** — max-width + ellipsis for long product descriptions. Always include a `title` attr for hover reveal.

## Webclient · Banner

Page-level voice-over. AI insights, warnings, success, info.

```html
<div class="banner banner-ai">
  <span class="icon"><!-- lucide sparkles --></span>
  <div class="body">
    <b>智能分析</b> · 该买家 12 个月进口量降 43.3%，但中国主供应商订单从 37 降至 13，
    <span class="em">切入时机好。</span>
  </div>
</div>

<div class="banner banner-warn">
  <span class="icon"><!-- alert-triangle --></span>
  <div class="body"><b>World Brite International</b> 出货量同比下降 100%。他们的客户可能正在寻找新供应商。</div>
  <button class="close"><!-- x --></button>
</div>

<div class="banner banner-success">
  <span class="icon"><!-- check --></span>
  <div class="body"><b>发送成功</b> · 3 封邮件已进入发送队列。</div>
</div>

<div class="banner banner-threat">
  <span class="icon"><!-- x-circle --></span>
  <div class="body"><b>Payment failed · Masterpiece Intl.</b> Invoice #4821 (USD 12,400) was declined 2d ago. Retry or contact buyer.</div>
</div>

<div class="banner banner-info">
  <span class="icon"><!-- info --></span>
  <div class="body"><b>Syncing 432 buyers from HS code 9405.</b> This usually takes 2–3 minutes. You can keep working.</div>
</div>

<div class="banner banner-footnote">
  <span class="icon"><!-- info --></span>
  <div class="body">数据源 · 美国海关 (CBP) 公开报关记录，每 24 小时更新一次。</div>
</div>
```

Variants:
- `banner-ai` — gold-tinted background, sparkle icon. AI-generated observations and recommendations. Always supports inline italic emphasis with `<span class="em">`.
- `banner-warn` — bone background with rule border, gold icon. Stale data, urgent but non-destructive. Dismissible.
- `banner-success` — accent-lo background, accent text. Confirmations.
- `banner-threat` — threat-lo background, oxblood text, x-circle icon. **Destructive or failed actions only** (payment failed, account revoked, data deleted). Never use for stale-data warnings — those go to `banner-warn`.
- `banner-info` — info-lo slate-blue background, info-circle icon. **System messages** (syncing, updates available, loading). Never use for AI observations — those go to `banner-ai`.
- `banner-footnote` — paper background, mute icon. Quiet data-source footnotes, attributions, caveats. (Renamed from `banner-info` in v2026.07 to free that class for the new slate-blue system-message variant.)

## Webclient · Tabs

Underline pattern. Optional Lucide icon prefix (use sparingly — text labels are usually clearer).

```html
<div class="tabs">
  <button class="tab on"><!-- lucide user -->概览</button>
  <button class="tab"><!-- lucide package -->发货记录</button>
  <button class="tab"><!-- lucide mail -->外联</button>
</div>
```

The active tab's underline is `--deep`, 2px, sits flush with the parent's bottom border (use `margin-bottom: -1px` on the tab).

## Webclient · Segmented toggle

Pick-one inside a cream tray. Used for draft/preview switchers.

```html
<div class="segment">
  <button class="on">我的邮件（中文）</button>
  <button>买家预览</button>
</div>
```

Selected option flips to `--deep` background, `--bone` text. Tray itself is `--cream`.

## Webclient · Filter pills

Soft round buttons for timeline filters and category narrowing.

```html
<div class="pills">
  <button class="pill on"><!-- filter -->全部</button>
  <button class="pill">沟通记录</button>
  <button class="pill">备注</button>
  <button class="pill">我的活动</button>
</div>
```

Active state: `--ink` background, `--bone` text.

## Webclient · Sample-status pill group

Pick-one control with fully-filled selection. Used in the outreach composer for sample state.

```html
<div class="pill-group">
  <button class="pill-choice on">样品已就绪</button>
  <button class="pill-choice">制作中</button>
  <button class="pill-choice">免费寄样</button>
</div>
```

## Webclient · Approval chip

Per-recipient approval state in bulk compose. Tick circle on the left, label on the right.

```html
<div class="approval on">
  <span class="tick"><!-- check --></span>
  <span class="lbl">Revel Home</span>
</div>
<div class="approval">
  <span class="tick"></span>
  <span class="lbl">Good Earth Lighting</span>
</div>
```

`.on` flips to deep background, bone text. The tick circle inverts.

## Webclient · Avatar + person block

Initial avatars in `--deep` background. Person block pairs avatar with name + role.

```html
<span class="avatar sm">B</span>
<span class="avatar">BM</span>
<span class="avatar lg">BM</span>

<div class="person">
  <span class="avatar lg">GF</span>
  <div class="meta">
    <span class="nm">Gregory Forrest</span>
    <span class="ro">Vice President, Sales · Good Earth Lighting</span>
  </div>
</div>
```

Sizes: `.sm` (24px), default (32px), `.lg` (40px).

## Webclient · Drawer / modal

Used for buyer detail, competitor detail, lead detail. Bone background, rounded card chrome, sticky action bar at the bottom.

```html
<div class="drawer">
  <div class="drawer-hd">
    <h2 class="drawer-title">Good Earth Lighting · <em>高优先级。</em></h2>
    <button class="drawer-close"><!-- x --></button>
  </div>
  <div class="drawer-sub">
    <span><!-- map-pin --> Mount Prospect, IL</span>
    <span><b>评分</b> 84</span>
    <span><b>更新于</b> <span class="mono">Apr 1</span></span>
  </div>

  <div class="drawer-tabs">
    <div class="tabs">
      <button class="tab on">概览</button>
      <button class="tab">发货记录</button>
      <button class="tab">外联</button>
    </div>
  </div>

  <div class="drawer-body">
    <!-- main detail content -->
  </div>

  <div class="action-bar">
    <div class="left"><button class="btn btn-ghost btn-sm">取消</button></div>
    <div class="right">
      <button class="btn btn-secondary btn-sm">定时发送</button>
      <button class="btn btn-primary btn-sm">发送邮件</button>
    </div>
  </div>
</div>
```

Rules:
- Drawer title uses `display` font with italic-accent emphasis.
- `.drawer-sub` is a horizontal metadata row, mute text with `<b>` for label-value pairs.
- `.action-bar` is `position: absolute; bottom: 0` — sticks to drawer bottom regardless of scroll.
- Drawer body should have `padding-bottom: 100px` to avoid action-bar overlap on the last content.

## Webclient · Charts

Live on `--paper` backgrounds with 1px `--rule` borders — same card chrome as everything else. Single accent color for primary data, fog for reference data. No grid lines, no chartjunk, no inline legends (use small mono footnotes instead).

### Supplier share (horizontal bars)

```html
<div class="share-list">
  <div class="share-row">
    <span class="name" style="font-weight: 500;">Ampco Technologies</span>
    <div class="bar"><div class="fill" style="width: 41.92%;"></div></div>
    <span class="pct">41.92%</span>
  </div>
  <div class="share-row">
    <span class="name mute">Ningbo Yito Optoelectronic</span>
    <div class="bar"><div class="fill mute" style="width: 8.84%;"></div></div>
    <span class="pct">8.84%</span>
  </div>
  <!-- ... -->
</div>
```

Top item gets full accent + ink-weight name. Subsequent items get mute name + mute fill (40% opacity).

### Stacked column chart

For monthly imports CN-vs-other.

```html
<div class="bars">
  <div class="bar-col"><div class="fg" style="height: 18%;"></div><div class="bg" style="height: 6%;"></div></div>
  <!-- 12 columns -->
</div>
<div class="bar-axis">
  <div>May</div><div>Jun</div><!-- ... --><div>Apr</div>
</div>
<div class="row-flex" style="margin-top: 14px;">
  <span><span style="background: var(--accent);"></span> 中国</span>
  <span><span style="background: var(--fog);"></span> 其他</span>
</div>
```

### Line chart

SVG inside a `.line-chart` container. Use `--deep` for the line, accent-fill gradient under the line.

### Sparkline rail

For inline progress (campaign open/reply rates).

```html
<span class="spark-rail"><span class="fill" style="width: 85%;"></span></span>
```

`.fill.mute` for low-priority data series.

### Threat meter

For competitor detail.

```html
<div class="meter">
  <span class="mono">THREAT</span>
  <div class="meter-bar"><div class="meter-fill" style="width: 58%;"></div></div>
  <span class="val">58</span>
</div>
```

## Webclient · Empty state

One mono line on a dashed-border block. **No illustrations, no "get started" graphics, no pep talk.** The brand stays editorial even when there's nothing to show.

```html
<div class="empty">暂无活动 · 线索互动记录将显示在这里</div>
```

If the empty state is in a primary content area and needs a CTA, follow the line with a single `btn-secondary btn-sm` underneath. Never a `btn-primary` in an empty state.

## Webclient · Skeleton

Loading rows with subtle shimmer.

```html
<div class="tbl-wrap">
  <div class="skeleton-row">
    <span class="skel" style="width: 14px;"></span>
    <span class="skel" style="width: 70%;"></span>
    <span class="skel" style="width: 80%;"></span>
  </div>
  <!-- 3-5 rows total -->
</div>
```

Skeleton rows match the actual row count of the loaded state where possible. 3-5 rows is enough — more starts to feel like the content is genuinely there.

## Webclient · Misc

### Keyboard shortcut

```html
<span class="kbd">⌘</span> <span class="kbd">K</span>
```

### Tooltip

Deep background, bone text, mono. Max 280px wide.

```html
<span class="tooltip">弱势竞争对手 · 出货量同比下滑 20%+ 的竞争对手。</span>
```

---

## A note on composition

These components compose. A webclient view is typically: **shell** (sidebar + canvas) → **toolbar** → **KPI strip** (4 KPI cards) → **table** with per-row chips and scores → **pagination**. Drawer detail views are: **drawer** → **drawer-sub** → **tabs** → **drawer-body** with banners + share-lists + tables + person blocks → **action-bar**.

Resist the urge to invent new primitives. Almost everything can be built from these.

If you do need something new, build it, ship it, and if it earns its keep, add it here. Anything that ships without going into the kit is a future maintenance debt.
