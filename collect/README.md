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

## Sponsor mentions

Pattern matches such as "sponsored by X" or "use code Y at X", plus disclosure markers (`#ad`, "paid promotion").
They are exposed as `sponsorMentions` on `/api/creators` and passed to the AI brief interpreter, which can exclude
creators when a brief names a competitor to avoid. This is evidence for review, not a verdict.

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
