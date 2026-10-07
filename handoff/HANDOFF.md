# Unique Reach Studio — front-end handoff

Restyle the Unique Reach roster planner (the React/TypeScript app in `src/`) to the look of the BrandMuse app, and make the structural changes below. The backend (FastAPI, `/api/*`) and its contracts are unchanged; so are the product rules in `DESIGN_NOTES.md` (overlap vocabulary, evidence sources always visible, quotes editable, no emoji, no client names).

What's in this folder:

- `mockups/overview.html`, `creators.html`, `methods.html` — the three screens as static HTML, pixel-for-pixel what to build. Open them in a browser. They are plain markup with inline styles; the structure and values are the spec. `overview.html` has the Muse panel hidden — remove `hidden` on `#muse-panel` to see it open.
- `mockups/screenshots/*.png` — the same screens rendered at 1440 wide (`overview-muse-open.png` shows the Muse panel).
- `mockups/tokens.css` — every design token as a CSS custom property (`--app-*` is the new palette; `--bm-*` / `--brandmuse-*` are the current app's, kept for the chart series and legacy screens). Use these names in the code.
- `design-system/README.md` — the brand book: rules for colour, type, spacing, states, charts, icons, logo. `tokens.json` is the same tokens as data; `components.css` is the current app's component CSS, tokenised (reference only).

## 1. Shell: top nav replaces the sidebar

`src/Studio.tsx` (`.studio`, `.side`, `.stage`, `.chat` in `styles.css`).

- One 68px top bar, full width, `border-bottom: 1px solid var(--app-card-border)`, padding `0 32px`:
  - left: the white wordmark (`brandmuse/assets/brand-muse-wordmark-white.jpg`, 132px wide, `mix-blend-mode: screen`) and `UNIQUE REACH` in the `eyebrow-wide` style (12px/500, 0.2em tracking, uppercase, `--app-accent`).
  - centre: the sections as pills — **Overview · Creators · Audience map · Why not · Methods** — 40px tall, `padding 0 16px`, `radius 12px`, 15px/500, lucide icon 16px, `--app-muted`; the active one is `linear-gradient(90deg, var(--app-nav-start), var(--app-nav-end))` with white text and `box-shadow: var(--shadow-app-nav)`. "New search" and "Beyond YouTube" are gone (see 6 and 7).
  - right: a bell button (40px, `--app-muted`) and the account avatar (44px disc, the `--app-fab-start → --app-fab-end` gradient).
- Content is a centred column: `max-width 1104px; padding 0 24px 120px`. No glass, no blur, no radial glows: the page is flat `--app-ground`.
- Muse: a 52px floating button bottom-right (`radius 14px`, the fab gradient, `box-shadow 0 10px 30px rgba(134,56,223,.35)`, white sparkle). It opens a 380×520 panel anchored above it (`--app-card`, 1px `--app-card-border`, `radius 16px`, `box-shadow 0 24px 48px rgba(0,0,0,.45)`) holding the existing chat: header (32px `--app-mark` orb, "Muse", status line in `--app-status-teal` when live, muted when not), messages (assistant bubbles `--app-field` with a hairline, user bubbles the fab gradient), suggestion chips, input (42px, `--app-field`) and a gradient send button. Keep the existing message/plan-change logic; only the container and styling change.
- Below 1000px the nav pills wrap; the panel becomes a bottom sheet.

## 2. Overview (`mockups/overview.html`)

Replaces the hero + campaign strip + save row + glance stack.

1. **Hero**, centred, `padding 96px 0 64px`, gap 28px: the logo mark (32px `--app-mark` disc with a white sparkle) beside the wordmark (160px); the question **"What are you launching?"** in `hero-question` (34px, weight 300, −0.01em, `--app-text-2`); the prompt field — 64px tall, max 1020px, `--app-field`, 1px `--app-card-border`, `radius 16px`, 17px placeholder "Describe what you're launching: the product, who it's for, which platforms", with a `⌘K` kbd hint (`--app-inset`, 26px, 11px `#818691`), a sliders icon button (platforms/budget) and a 36px send button (`--app-inset`) inside on the right. This field is the campaign brief input that used to be `.hero-input`; submitting it runs the search.
2. **Sourcing line** under the field: three 20px black discs with white platform glyphs (YouTube play, TikTok note, Instagram) and 13px `--app-muted-2` copy: "Pulls creators from YouTube, TikTok and Instagram automatically — overlap is measured where comments are public and estimated everywhere else."
3. **Suggestion chips**, centred, gap 12px: 40px tall, `padding 0 18px`, `radius 12px`, `--app-chip`, 1px `--app-card-border`, 15px `--app-muted-2`. Contents: each saved search ("Home refresh roster"), "Pressure-test the current roster", and "✦ Why creators were left out" (lucide sparkle, links to the Why not section). Clicking a saved search loads it; the others prefill the prompt.
4. **Stat cards**, 3-up grid, gap 16px: `--app-card`, 1px border, `radius 14px`, `padding 24px`, centred text — value 24px/500 (the overlap in `--app-accent`, the others `--app-text`, tabular numerals), label 15px `--app-muted`, caption 14px `--app-muted-2`. Values from `/api/plan`: recommended overlap (`rosterDiagnostics.rosters.recommended.sharedRate`) with "Recommended plan · lower is better"; recommended `proxyReach` as unique followers with "vs {current proxyReach} in your roster"; recommended `spend` with "of {budget} budget". The evidence caveat (`countNote`) goes under the cards as one centred 13px `--app-muted-2` line.
5. **Recommended roster** section: eyebrow row (`eyebrow-wide` label + "View all ›" 14px link to Creators), then one Muse insight line (16px sparkle in `--app-sparkle`, 14px text in `--app-insight`) built from `choice.headline` + the first `steps[]` reason, then a 2-column grid of **creator cards** (gap 24px): `--app-card`, `radius 14px`, `padding 20px`; top row = 44px avatar disc (`--app-avatar`, initial in `--app-avatar-text` 15px/500) with a 20px black platform badge bottom-right, name 15px/500 `--app-text-2`, "{platform} · {category}" 13px `--app-muted`, status 12px `--app-status-teal` ("In the plan"); bottom row = value/label pairs at gap 28px: followers, quote, overlap (the creator's top pair share from `/api/overlap`, "—" when none; append "· estimated" when the pair's `source` isn't `measured`). A trailing dashed card links to the left-out list: "{n} more in the pool — see why they were left out".
6. **Plan at a glance**: eyebrow row ("How estimates work ›" link to Methods) and the two existing charts (`Glance.tsx`) restyled as cards: title 15px/500, description 13px `--app-muted-2`, bar tracks `--app-inset`, series colours unchanged (`--bm-chart-current`, `--app-accent` for recommended, `--bm-chart-baseline`), striped overlap ends as `repeating-linear-gradient(135deg, <series> 0 3px, transparent 3px 7px)`, the column chart in the fab gradient. Drop the KPI row and the hero-metric block: the stat cards replace them.

Budget and creator-count controls (the old campaign strip) move behind the sliders icon in the prompt field as a small popover; the save/load campaign row becomes the "saved searches" chips plus a "Save" action in the same popover. Keep the `MoneyInput` component for the budget.

## 3. Creators (`mockups/creators.html`)

1. Header: eyebrow `CREATORS`, title "{n} creators in the plan pool" (28px, weight 300), 14px `--app-muted-2` helper, and a 44px search field on the right (`--app-field`, `radius 12px`).
2. The Muse insight line (spend + the pair to watch).
3. Filters as chips, 36px tall, `radius 12px`: left group In the plan · Your roster · Left out · All; right group All platforms · YouTube · Instagram · TikTok with counts in 11px pills (`--app-inset`). Active = the nav gradient with white text. No filter is ever disabled; a platform with 0 creators shows "0".
4. Rows as cards (gap 10px): grid `24px 44px 1fr 120px 110px 36px`, `padding 16px 20px`, `--app-card`, `radius 14px`: roster checkbox (`accent-color: var(--app-nav-start)`), avatar + badge, name + "{platform} · {category} · {followers} followers", status in teal, quote 15px/500 right-aligned (editable `MoneyInput` on focus), chevron button. The expanded row (require / exclude / re-price, the existing `CreatorInspector`) keeps its behaviour, restyled with the same card tokens.
5. **Why not…?** moves here, directly under the list (`WhyNotPanel.tsx`): eyebrow row ("How estimates work ›"), insight line ("{n} of {n} skipped creators share part of their audience with the plan…"), one card with the summary tags (24px pills on `--app-chip`: "Over budget · 5" in `--yellow-300`, "Adds little · 12" in `--app-accent`), the list rows (name + "Overlaps with …", 8px bar on `--app-inset` filled with `linear-gradient(90deg, var(--app-nav-start), var(--app-fab-start))`, percent 15px/500, reason tag), "Show all {n}" chip; then a second card with the creator picker (`<select>`, 40px, `--app-field`) and the full reason beside a 40px disc showing the covered share.
6. **Audience map** (`ExploreOverlap.tsx`) under that: eyebrow row, helper, two cards — the picker + "Of about {followers} followers of {name}, this share also follow:" + bars (10px tracks, gradient fill, 14px/500 percent with an 11px count or "estimated") and the footnote; and Creator groups with the dashed empty state.

## 4. Methods (`mockups/methods.html`)

Eyebrow `HOW ESTIMATES WORK` with the one-line description on the right, then the six existing method cards in a 2-column grid: `--app-card`, `radius 14px`, `padding 24px`, title 16px/500 `--app-text-2`, body 14px/1.6 `--app-muted-2`, bold terms in `--app-text-2` 500; the first two carry a 24px pill ("Measured" in `--app-accent`, "Estimated" in `--yellow-300`). Nothing else on this screen.

## 5. Tokens and type

- Load **Plus Jakarta Sans** (400, 500, 600, 700 and 300 for the question) from Google Fonts in `index.html`; the app currently names it but never loads it.
- Put `mockups/tokens.css` in place of the `:root` blocks at the top of `styles.css` (keep `brand-tokens.css` imported; its names are already in the file). Delete the `body` radial-gradient background, every `backdrop-filter`, `shadow-panel`/`shadow-hero` and the `.side`/`.chat` rail rules.
- Type: weights 300 (question), 400 body, 500 labels/names/buttons/values, 600 nothing new. Tracking: `eyebrow-wide` 0.2em; titles no longer negative-tracked except the question (−0.01em).
- Radii: cards 14px, chips/pills/buttons/inputs 12px, the prompt field 16px, tags 999px. Borders always 1px `--app-card-border`.
- Status colours stay tint + text + a word: teal for in-plan, `--yellow-300` for over budget, `--app-accent` for adds little, `--red-300` for excluded.

## 6. Cross-platform is automatic

Remove the "Plan across YouTube, Instagram and TikTok" checkbox (`.hero-option`) and the locked state. The pool always includes YouTube, TikTok and Instagram; `UPRIVER_API_KEY` is a server-side requirement, not a user toggle. If the key is missing the server still returns the YouTube pool and the sourcing line reads "Pulls creators from YouTube; add UPRIVER_API_KEY on the server for TikTok and Instagram" — never a disabled control.

## 7. Removed

- The sidebar and its "Your searches" list (saved searches are chips under the prompt).
- "New search" as a nav item (the prompt on Overview is the search).
- "Beyond YouTube" — the nav item and the `SponsorConflicts`/lookalike card. Keep the lookalike API code; it is just not surfaced.
- The hero-metric block, KPI row, campaign strip and save/load row (folded into the stat cards and the prompt popover).

## 8. Acceptance

- Open each screen at 1440 wide next to its screenshot: same structure, spacing, colours and copy.
- Overview, Creators and Methods are routes (or anchors) reached from the top nav; "Audience map" and "Why not" scroll to their sections on Creators.
- Muse opens from the floating button and still applies plan changes; the `AI live` / `AI unavailable` state comes from the server.
- Tick a creator, change a quote, exclude one: plan, stat cards, roster cards and Why not all update, as today.
- Keyboard: every control is a real button/input/link; focus ring is the 3px `--brandmuse-purple` outline.
- `npm run build` passes; no emoji anywhere; no client names in committed fixtures.

Suggested prompt for Claude Code, from the repo root with this folder dropped in as `handoff/`:

> Implement handoff/HANDOFF.md in the frontend (src/, styles.css). Open handoff/mockups/*.html for the exact layout and handoff/mockups/tokens.css for the token names. Keep the backend and the rules in DESIGN_NOTES.md unchanged. Work screen by screen (Overview, Creators, Methods), run `npm run build` after each, and show me a screenshot against handoff/mockups/screenshots before moving on.
