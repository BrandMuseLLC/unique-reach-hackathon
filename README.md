# Unique Reach — an Intuition tool

A hackathon prototype by BrandMuse for planning YouTube creator sponsorship rosters with budget constraints and overlap-aware comparisons.

## First progress update

Today we built a roster editor, editable budgets and hypothetical creator quotes, an optimizer with baseline comparisons, saved campaigns, and campaign-brief interpretation through Google Gemini. Our separate local research build also explores shared commenters in a historical public sample of 34 YouTube channels.

This public submission contains runnable application code and a **fictional, deterministic demo dataset**. The historical dataset and research evidence are excluded while their data-use review is pending. The observed overlap explorer and live AI are disabled in this public demo. Source code for those integrations is included, but the full local research build is not reproduced here.

Shared commenters are an experimental overlap signal, not validated unique viewers. Demo prices are illustrative. Optimization improvements are not guaranteed.

## Run locally

Use Node.js 22 and Python 3.11 or newer:

```sh
npm ci
npm run build
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
MUSE_DATASET=synthetic AUTH_MODE=local CAMPAIGN_STORE=local python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8033
```

Open http://127.0.0.1:8033. No API key is required. Local campaigns are saved in the ignored `data/` directory.

Alternatively:

```sh
docker build -t unique-reach-demo .
docker run --rm -p 127.0.0.1:8033:8080 unique-reach-demo
```

This is a first-milestone source submission, not a hosted service. Sponsored Google hosting is in progress.

## Real-data path (in progress)

Beyond the synthetic demo, the app runs on an observed aggregate of public YouTube comment overlap
(`MUSE_DATASET=observed`, optional `MUSE_OBSERVED_DATA=<aggregate>`). `collect/` builds that aggregate for a
vertical we collect ourselves with the official YouTube Data API; see `collect/README.md`. In observed mode the
app adds audience clusters, a "Why not…?" panel, and a sponsor-conflict filter. Live AI (brief interpretation,
cluster names, grounded explanations) needs a server-side model credential; verify it with
`python3 scripts/verify_live_ai.py`. Nothing in this section has been run against live YouTube or a live model yet.
