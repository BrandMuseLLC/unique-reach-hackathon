Unique Reach is BrandMuse's roster planner: describe a campaign, get a creator roster whose audiences overlap as little as possible, and see the evidence behind every number. The interface is a dark, glassy workspace — sidebar, stage, Muse chat — where purple means *the plan*, orange means *your roster*, and every other hue is a status. Tokens here use the app's own CSS custom-property names (`brandmuse-*`, `bm-*`); class names in these rules are the ones in `src/styles.css`.

## Content fundamentals

- Plain, direct, second person. "Describe what you're launching. We find relevant YouTube creators, measure where their audiences overlap, and pick a roster." The product speaks as *we*, the reader owns *your roster* and *your budget*.
- Sentence case everywhere: titles ("Plan a creator campaign", "Why creators were left out"), buttons ("Find creators", "Save campaign", "Show all 17"), tabs ("In the plan", "Left out"). Uppercase is reserved for the `label` style — eyebrow labels like CAMPAIGN, BUDGET, ESTIMATED AUDIENCE OVERLAP.
- Say what a number is and which way is good: "Estimated audience overlap · lower is better", "Better on both", "Less overlap without losing reach: 22.4% vs your 23.4%, reaching 961K followers vs 947K."
- Overlap is **"shared sampled commenters"** (YouTube) or **"estimated from audience profiles"** (Instagram, TikTok). Never call it unique viewers, wasted spend or lift.
- Every pair carries a source — **measured**, **estimated** or **assumed** — and it stays visible: the `evidence-mix` bar, the `found-by` pill, an `.hv.assumed` value losing its gradient. Caveats are written out, not hidden: "Limited evidence: a typical creator here has about 100 sampled commenters, so small overlap differences are rough."
- Quotes are modeled assumptions and stay editable in place (`.money`, `.money.small`), with the note "Quotes are per 1,000 followers … rough market rates, not quotes."
- No emoji anywhere in the UI. Icons are lucide-react glyphs.
- Client names never appear in anything committed to the public repo; sample data is synthetic ("Home refresh roster", "Channel 9mdQ").

## Color

- The ground is `brandmuse-light-background` with two fixed radial glows, `ground-glow-1` (top-left) and `ground-glow-2` (top-right), on `body`. Everything sits on this, so every surface is translucent: cards are `bm-surface`, raised rows and chips `bm-raised`, and every hairline is `bm-border` at 1px. Glass cards (`.card`, `.kpi`, `.chart-card`, `.panel`) add `backdrop-filter: blur(var(--blur-card))`; the two rails use `side-glass` / `chat-glass` with `blur-rail`.
- Insets that need to read *below* the card go darker, not lighter: `black-22` for nested cards, `black-25` for the why card and duo columns, `black-30` for search fields and the `.tabs` track, `black-40` for the hero search field and the chat input.
- Text is `brandmuse-light-text` on any surface, `brandmuse-light-muted-text` for everything secondary, `slate-500` only for placeholders and decoration (it is 4.1:1 on the ground — below 4.5:1, kept exact from the source). Lavender text (`purple-200`) marks links and the hero label.
- **Purple is the plan.** `brandmuse-purple` → `purple-500` at 135deg is the primary gradient: `.btn-primary`, the user's chat bubble, the recommended avatar, the active nav item (at `purple-tint-55` → `purple-tint-35`). Bars that show the plan run `brandmuse-purple-dark` → `purple-500` at 90deg. Every "selected", "active" or "recommended" state is a purple tint: fills from `purple-tint-08` (audience groups) through `purple-tint-18` (active pill tab) and `purple-tint-30` (active segmented tab) to `purple-tint-40` (recommended badge); borders at `purple-tint-35` (cards) and `purple-tint-60` (focus, pressed). White (`brandmuse-dark-text`) sits on purple fills — note it is 4.2:1 on the primary button, a source pair kept exact.
- **Orange is your roster.** `bm-chart-current` is the only orange, used for the "Your roster" bar, swatch and legend dot — never for a warning. `bm-chart-baseline` (green) is the views baseline, `bm-chart-repeat` the striped overlap segment. These four `bm-chart-*` tokens are the chart palette; nothing else goes in a chart.
- Status hues are tint-plus-text pairs, always with a word: success `green-tint-08..12` + `green-300` ("In the plan", "Plan is up to date", "better"); danger `red-tint-08..16` + `red-300` ("Excluded", "Over budget", errors); caution `yellow-tint-08..10` + `yellow-300`/`yellow-200` ("Over budget" tag, "Limited evidence", stale results); thin evidence `orange-tint-08` + `orange-300`; cap reached `blue-tint-08` + `blue-300`; "adds little" `purple-tint-08` + `purple-200`; a lookalike's "found by" `teal-tint-12` + `teal-200`. Success and danger differ in lightness as well as hue (14.5:1 vs 10.7:1 on the ground) and never stand alone without their label.
- Hover is a step of white: `white-05` on nav items, `white-08` on secondary and ghost buttons, `white-02` → `white-04` on creator rows. Disabled primary buttons go outlined (`bm-border`, `slate-300` label), not washed out: disabled reads as "not yet", not broken.
- Keyboard focus is `outline: 3px solid var(--brandmuse-purple)` with 2px offset on buttons, inputs and selects; text fields inside tool cards instead take a `purple-tint-60` border plus `shadow-focus`.
- The BrandMuse light palette in `brand-tokens.css` (`#f2f3f5` ground, `#ffffff` surface, `#d6d9df` border, `#111827` text, `#5b6472` muted) is overridden to dark in `styles.css`; this app has no light theme.

## The app look (adopted from app.brandmuse.io)

The Studio is moving to the look of the BrandMuse app itself: calm and flat, no glass or glows. The `app-*` tokens are its palette, sampled from the product.

- Ground is `app-ground`; every card, row and panel is `app-card` with a 1px `app-card-border`, `radius-14`; fields are `app-field` with `radius-app-field` (16px); chips are `app-chip`. Nothing blurs, nothing glows except the two purple gradients.
- Navigation is a 68px top bar, not a sidebar: the white wordmark left, the sections centred as pills (16px/500, `app-muted`; the active one the `app-nav-start` → `app-nav-end` gradient with white text and `shadow-app-nav`), a bell and the account avatar right. Muse lives in a floating `app-fab-start` → `app-fab-end` square (52px, `radius-14`) bottom-right, and opens as a panel.
- The home screen is centred: the logo mark (`app-mark` disc, white sparkle) and wordmark, a one-line question in `hero-question` (34px, weight 300, `app-text-2`), one wide prompt field (64px, `app-field`, with a kbd hint and icon buttons inside), then a row of suggestion chips. Content sits in a 1104px column.
- Numbers are quiet: stat cards centre a 24px/500 value (`app-accent` for the one that matters, else `app-text`), a 15px `app-muted` label and a 14px `app-muted-2` caption. Sections open with an `eyebrow-wide` label and a "View all ›" link, then a one-line Muse insight in `app-insight` with an `app-sparkle` icon.
- Creator cards: a 44px `app-avatar` disc with the initial and a black platform badge, name 15px/500 `app-text-2`, handle 13px `app-muted`, status 12px `app-status-teal`, and a row of value/label pairs.
- Type weights drop: 300 for the question, 400–500 for everything else, 600 only for values. Titles lose their tight tracking.
- The purple-is-the-plan rule holds; the older `bm-*` glass surfaces, glows and the sidebar remain documented below for the legacy screens until the port is complete.

## Typography

- One family: `sans` — "Plus Jakarta Sans", falling back to Inter, then system-ui. The app references the face but never loads it (no `@font-face`, no Google Fonts link), so it renders in the fallback; load it from Google Fonts at weights 400–800 or self-host it before the look is judged.
- Weights: 400 body, 500 idle tab labels, 600 headings, labels, badges and button text, 700 titles and numbers, 800 the hero number only. The legacy single-page layout used 800–900 for labels; new work does not.
- Big numbers are tight and tabular: `hero-number` (56px/800/−0.03em) with a white → `purple-200` text gradient, `kpi-value` (30px/−0.02em), `duo-value` (22px). Anything numeric sets `font-variant-numeric: tabular-nums`.
- Titles: `page-title` once per screen, `section-title` per stage section, `panel-title` for the creators panel, `card-title` on cards, `subhead` and `chart-title` inside them. All negative-tracked by −0.01em to −0.03em.
- Copy: `lead` (15px) under the page title, `body` (14px) for sentences and chat, `helper` (13px) for descriptions and secondary buttons, `meta` (12px) for meta lines and badges, `label` (11px, uppercase, 0.08em) for eyebrows, `micro` (10px) for the found-by pill only.

## Spacing, layout, radii

- The shell is `grid-template-columns: var(--sidebar-width) minmax(0, 1fr)` plus `var(--chat-width)` when the chat is open; both rails are sticky, full height. The stage pads `space-28` top, `space-32` sides, and stacks sections at `space-22`.
- Cards pad `space-16` vertically and `space-18` horizontally; nested cards `space-16`; rows `space-10` vertical by `space-12`–`space-16` horizontal. Grids gutter at `space-12`, setup cards at `space-14`.
- Controls are `control-height` (38px) tall with `space-16` side padding; the hero and topbar actions `control-height-lg`; the Run button `control-height-xl`; tabs `tab-height`.
- Radii scale with nesting: `radius-18` hero and stage sections, `radius-16` panels, `radius-14` cards and chat bubbles, `radius-12` lists and rows, `radius-10` buttons, inputs and alerts, `radius-pill` for anything that is a badge, tag, chip or bar, `radius-circle` for avatars and dots. The legacy layout's `radius-6`/`radius-8` are not used in the Studio.
- Borders are always 1px `bm-border` (or a status/purple tint); nothing is outlined heavier. Depth comes from `shadow-panel` and `shadow-hero` (black, soft, deep) and from purple glows that mean *active*: `shadow-primary`, `shadow-nav-active`, `shadow-orb`, `shadow-flash`.

## Motion

- Short and eased: 0.15s for hover and color (`background`, `border-color`, `color`), 0.2s for the chevron rotate, 0.25–0.35s for rows entering (`rowIn`: fade + 4px rise), 0.5s for cards (`rise`: fade + 8px rise, staggered 60ms across KPIs, 120ms across charts), 0.6s for the stepper bar width, 0.8s for bars growing (`growX`/`growY`), all on `cubic-bezier(0.22, 1, 0.36, 1)`.
- Loops: `spin` 0.9s linear on a busy icon, `blink` 1s on typing dots, `pulse` 1.2s on the current step's ring.
- `prefers-reduced-motion: reduce` turns every entrance animation off; keep that rule in any new keyframe.

## Charts and bars

- Bars are pills on a `bm-grid` track: 16px in the hero (`.hb-track`), 12px for audience bars (`.aud-track`), 8px for left-out and match bars, 6px for the stepper and evidence mix. Plan bars use the purple gradient, roster bars `bm-chart-current`, the low/mid/high match bars `green-500` / purple gradient / `orange-500`→`orange-400`.
- The evidence mix is one bar in three segments: `bm-chart-recommended` measured, `yellow-500` estimated, `gray-500` assumed, labeled in the same colors beside it.
- SVG charts set text in the `sans` family at 11px muted, values in `brandmuse-light-text` 600; legends are 10px squares with `radius-4`; tooltips are `brandmuse-dark-raised-surface` cards with `bm-border` and `shadow-tip`.

## Iconography

- lucide-react (0.561) at 14–18px, stroke inherits `currentColor`; purple (`brandmuse-purple-light`) in the hero search field and the chat orb, muted everywhere else. Sidebar nav items carry one icon each at 16px.
- Avatars are the creator's initial in a 32px `radius-circle`: soft (`purple-tint-35` → `purple-tint-12`, `purple-100` text, `purple-tint-35` border) by default, solid primary gradient with white text when recommended.
- No emoji, no illustration. The one decorative element is the Muse orb: a 34px radial `purple-400` → `brandmuse-purple-dark` disc with `shadow-orb`.

## Logos

- `brand-muse-wordmark-white.jpg` is the mark on dark: set it with `mix-blend-mode: screen` so its black ground disappears, 150px wide in the sidebar (`.side-logo`), 190×40 in the legacy topbar, with "UNIQUE REACH" in the `label` style (`brandmuse-purple-light`) beneath it as the product name.
- `brand-muse-wordmark-black.png` (transparent PNG) is for light grounds and exports only; this app never shows it.
- The wordmarks are BrandMuse's and were copied with authorization; never redraw, recolor or stretch them, and never set type that imitates them.

## Scope

- Built from the design package as uploaded (`src/styles.css`, `brandmuse/brand-tokens.css`, `DESIGN_NOTES.md`, the three reference screenshots). The app is React 19 with no component library, so every component here is hand-written from the stylesheet's classes as a static rendition; the legacy single-page layout in `main.tsx` (`.panel`, `.score-card`, `.creator-table`, `.heatmap`) is tokenized but not previewed. No font files: Plus Jakarta Sans is a hosted face.
