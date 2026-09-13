# Collecting a real vertical

Builds the observed dataset the planner and AI brief interpreter already accept, from public YouTube data
we collect ourselves with the official Data API v3. The output has no comment text and no commenter identifiers.

## Run

```sh
export YOUTUBE_API_KEYS=key1,key2    # server-side only; never commit, paste in chat, or put in the page
python3 -m collect resolve  --seeds collect/seeds/home-coffee.csv
python3 -m collect videos   --per-channel 10
python3 -m collect comments --max-per-video 500
python3 -m collect build    --out data/home-coffee-aggregate.json --report data/home-coffee-report.json \
                            --restricted ~/.config/brandmuse/restricted-names.txt
```

Then serve it:

```sh
MUSE_DATASET=observed MUSE_OBSERVED_DATA=data/home-coffee-aggregate.json AUTH_MODE=local CAMPAIGN_STORE=local \
  python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8033
```

Every step resumes from `data/collection.sqlite` (ignored by git). Page tokens are committed after every
page. A `quotaExceeded` response rotates to the next key; when all keys are spent the command stops cleanly and
the next run continues after the Pacific-midnight reset.

## Cost

About 1 unit per API call: 50 channels × (1 resolve + 1 upload list + 1 video batch) plus up to 5 comment pages
per video × 10 videos ≈ 2,650 units. That fits the default 10,000-unit daily quota of one key.

## Gate

`build` prints the median pairwise commenter Jaccard and writes the full report. Below 1.5%, widen the seed
list to adjacent coffee gear before switching verticals. The report also has a cleaning-sensitivity table
(high-volume author thresholds), commenter-to-view outliers (possible engagement pods), and top pairs.

## What gets published

- `creators`: channel title, handle, editorial topic, median views, subscriber count, uniform scenario quote,
  three recent video titles, and sponsor mentions found in public descriptions.
- `audience_segments`: exact channel-membership patterns with integer counts.

Commenter channel IDs are salted and hashed in the local database only. Names listed in the `--restricted`
file (keep it outside the repo) are replaced in sponsor mentions and titles before anything is written.
YouTube API Services terms limit retention: delete or refresh `data/collection.sqlite` within 30 days.

## Creator country and language

Each creator carries `creator_country` (the channel's self-declared country, often missing) and `audio_languages`
(declared audio language counts across sampled videos). The AI brief interpreter may exclude creators on these when
asked ("US-based creators", "English-language creators") and must say it filtered creators, not audience geography.

## Sponsor mentions

Pattern matches such as "sponsored by X" or "use code Y at X", plus disclosure markers (`#ad`, "paid promotion").
They are exposed as `sponsorMentions` on `/api/creators` and passed to the AI brief interpreter, which can exclude
creators when a brief names a competitor to avoid. This is evidence for review, not a verdict.

## Grow the pool without quota

```sh
python3 -m collect suggest --min-channels 2
```

Lists @handles mentioned in collected descriptions (collabs, shout-outs) that are not yet seeded, most-mentioned
first. Check each channel, give it a topic, append it to the seed file, then rerun `resolve`, `videos`, `comments`.

## Quotes

`build` models each quote at $15 CPM on median recent views, rounded to the nearest $250 with a $250 floor, the
same rule the planner app uses. Pass `--cpm 0 --default-quote 1000` for a uniform scenario. Quotes stay editable.

## Audience clusters

`/api/overlap` now returns `clusters`: greedy modularity on commenter Jaccard, labeled by the dominant editorial
topics. With live AI configured, "Name clusters with AI" in the overlap explorer asks the model to name each
cluster from channel names and public video titles only (`POST /api/overlap/labels`). Invalid model output keeps
the rule labels. Clusters describe overlapping sampled commenters, not demographics.

## Why not, and grounded explanations

`/api/plan` returns `whyNot` for eligible creators the plan left out: the share of their modeled audience already
represented, which selected creators overlap them, what adding them would add, and the reason. The "Why not…?" panel
shows it without AI. With live AI configured, "Ask AI" (`POST /api/explain`) answers questions about the plan from
that evidence only; the server recomputes the plan from the inputs and withholds any answer that cites a number
not present in the evidence.

## Validation

`build` reports `temporal_stability`: each channel's collected videos are split into older and newer halves, and the
rank correlation of pairwise commenter Jaccard between halves is reported (needs 3+ channels with 2+ commented videos).
It shows the signal is stable, not that commenters stand in for viewers.

When an overlap-tool trial is available, export 20-30 channel pairs spanning low to high overlap into a CSV with columns
`a,b,overlap` (handles, channel IDs or channel titles; `overlap` may end in `%`). Start from
`collect/seeds/benchmark-template.csv`, then:

```sh
python3 -m collect validate --aggregate data/home-coffee-aggregate.json --benchmark data/benchmark.csv --out data/validation.json
```

It prints matched pairs, unmatched rows and the Spearman correlation with our commenter Jaccard. Report n with rho.

## Headline numbers

```sh
python3 -m collect headline --aggregate data/home-coffee-aggregate.json --budgets 3000,6000,10000 --out data/headline.json
```

For each budget and both units (exact sampled commenters and the view-scaled proxy), it shows the planner's lift
over the largest-by-subscribers and largest-by-views rosters under identical quotes, and splits the gain
into bigger audiences versus less overlap. It also audits the biggest roster by subscribers: the share of
sampled commenters it pays to reach twice, and what the same budget buys instead. On the bundled 34-channel
sample this reproduces the known result (about 0.4% over the stronger baseline at $10,000), which is why
the vertical test matters.

## Sponsor conflicts in the app

When the active dataset carries `sponsorMentions`, a "Sponsor conflicts" panel lists matches for brands you
type and excludes those creators in one click, then re-plans. It works without live AI. The creator
inspector shows each creator's mentions.

## Restricted names

`scripts/check-restricted-names.sh` fails if any name from `~/.config/brandmuse/restricted-names.txt`
(or `RESTRICTED_NAMES_FILE`) appears in tracked files or unpushed commit messages. Install it as a pre-push
hook with `ln -s ../../scripts/check-restricted-names.sh .git/hooks/pre-push`.

## Test

```sh
python3 -m pytest collect/tests -q
```
