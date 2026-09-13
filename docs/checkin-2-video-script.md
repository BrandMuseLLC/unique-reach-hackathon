# Check-in 2 · 60-second walkthrough (draft)

Record against the tagged build. Say only what the screen shows. Pick the variant that matches what actually works at T-45 minutes.

## Variant A: home-coffee data collected

| Time | Screen | Say |
|---|---|---|
| 0:00 | App header, dataset label | "Brands pick YouTube creators by size. In a tight niche the big creators share one audience, so part of a roster can reach the same audience more than once. Unique Reach looks for that in public comments." |
| 0:08 | Overlap explorer, audience clusters | "We collected [N] home-coffee channels with the official YouTube API. Channels whose commenters overlap form these clusters." |
| 0:18 | Roster audit: biggest roster by subscribers | "In our sample, [X]% of the biggest [K]-channel roster's commenter memberships are the same accounts showing up on another channel in that roster." (`collect headline`, `repeat_membership_fraction`) |
| 0:26 | Run audit and optimize; Marginal Contribution Trace | "Same budget, the planner picks the roster that adds the most new audience per dollar." State both baselines exactly as the headline report shows them. |
| 0:36 | Why not…? panel | "Why not this creator? [Y]% of its audience is already covered by these two." |
| 0:44 | Sponsor conflicts panel: type a competitor, Exclude | "A launch brand can drop creators who ran a competitor's deal. We found those mentions in public descriptions, and the plan updates." |
| 0:52 | Campaign brief box | Only if live AI worked in the tagged build: "Or describe the launch in plain English and the AI sets the constraints." Otherwise: "AI brief interpretation is built; live calls turn on once inference credits are configured." |
| 0:58 | End | "Decide before you spend." |

## Variant B: no home-coffee data yet

Same flow on the 34-channel public sample. Replace 0:08 with "a 34-channel public sample (1.3M comments)", use its audit number (6.4% of the biggest 6 channels' sampled commenter memberships repeat an account on another of those channels), and say plainly that the gain over the stronger baseline is small on a mixed-topic sample, which is why the next milestone is the collected home-coffee vertical. Skip the sponsor panel (the sample has no sponsor evidence).

## Never say

- "Unique viewers", "reach X people", "wasted spend", "duplicated viewers" or "lift". These are sampled commenter accounts and an uncalibrated score.
- That a passing overlap gate means the planner will beat the baselines.
- Any number from synthetic data.
- Any client, prospect or pipeline name.
- That AI works, unless a live call ran in the tagged build.
