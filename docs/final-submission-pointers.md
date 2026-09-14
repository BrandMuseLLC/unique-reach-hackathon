# Final submission pointers

Structure follows judge feedback: the video covers problem, solution, differentiation, and impact; the technical
write-up covers what is hard to replicate and what the data, method, and system make defensible.

Wording rules for both: overlap is **shared sampled commenters** (YouTube) or **estimated from audience profiles**
(Instagram, TikTok). Never call it unique viewers, wasted spend, duplicated viewers, or lift. No client names.

---

## Video (about 90 seconds)

### 1. Problem (0:00–0:15)
- Brands pick creators one at a time, mostly by follower count and fit.
- Nobody checks whether those creators share the same fans until the campaign is over.
- The result: a roster that looks large on paper can keep reaching the same people.
- *Screen:* Overview, your size-picked roster ticked.

### 2. Solution (0:15–0:45)
- Unique Reach plans the **roster**, not the creator: it picks the lowest-overlap set that reaches at least as many
  people as yours, within budget.
- Type a campaign brief in plain English; Gemini turns it into a creator search across YouTube, Instagram, TikTok.
- The headline number is audience overlap, with the actual shared count underneath.
- Every edit re-plans live; Muse (chat) can change the plan and says what moved.
- *Screen:* New search prompt → Overview hero card → untick a creator → ask Muse "make it cheaper".

### 3. Why this approach is different (0:45–1:10)
- **Measured, not guessed:** on YouTube, overlap comes from people who actually commented on both creators.
- **One plan across platforms:** YouTube pairs are measured; Instagram and TikTok pairs are estimated from audience
  profiles and calibrated against the measured YouTube pairs.
- **It shows its work:** every pair is labeled measured, estimated, or assumed; "Why this plan" says when it trades
  overlap for reach; "Why not" explains every creator left out.
- Most creator tools score creators one at a time, and overlap reports cover pairs; this plans the whole roster under a budget.
- *Screen:* evidence bar (measured / estimated / assumed) → Why this plan box → Why not.

### 4. Impact and value (1:10–1:30)
- Answers a question CMOs ask before spending: "Am I paying several creators to reach the same fans?"
- Turns creator selection from a list of favorites into a budgeted plan with a reason for every pick.
- Works on any category from a one-line brief, in minutes, from public data.
- Close: "Unique Reach by BrandMuse: know your reach before you spend."
- *Screen:* Creators list with recommended picks, then back to the hero number.

**Before recording:** use a search where overlap is clearly above 1% (a tight niche with a few big channels). If both
rosters are under 1%, the page will say overlap is negligible, which undercuts the story.

---

## Technical write-up

### What makes this hard to replicate

1. **Roster-level overlap is a combinatorial problem.**
   Choosing N creators to minimize shared audience under a budget is a budgeted set-cover problem. We use greedy
   selection plus local search (add, drop, swap) with a reach floor set by the user's own roster, so the
   recommendation never quietly loses reach. Per-creator scores cannot express this.

2. **The overlap signal has to be built, not bought.**
   - Pipeline: brief → Gemini search plan → YouTube Data API search → recent videos → sampled comment threads →
     exact membership patterns across creators.
   - Commenter IDs are salted and hashed at collection; only aggregate membership counts ("N people commented on
     exactly this set of creators") leave the collector. The planner never sees an identity.
   - Thin creators (too few sampled commenters to measure) are set aside and labeled, not silently scored.

3. **Blending measured and estimated evidence honestly.**
   - YouTube pairs: shared commenters ÷ the smaller creator's commenters.
   - Instagram / TikTok pairs: an audience profile match (countries, gender, age, language; confidence-weighted)
     multiplied by a factor calibrated on YouTube pairs that have both a measured overlap and a profile.
   - Unique reach uses a pairwise correction that never falls below the largest single audience.
   - Every number carries its evidence mix so the UI can mark assumptions instead of hiding them.

4. **Metered vendor data under a hard budget.**
   Upriver calls reserve worst-case credits before sending, treat timeouts as billed (never retried), retry 5xx
   once, cache results, and stop at a per-search cap (about 200 credits). Lookups run in parallel and a single
   failure does not stop the rest.

5. **Explanations grounded in the plan, not generated freely.**
   "Why this plan" and "Why not" are computed from the planner's own diagnostics (budget, creator count, caps,
   evidence mix). The model interprets briefs and edits settings; it does not invent the numbers.

### What creates defensibility

- **Data that compounds.** Each search adds an overlap aggregate for a new category. Over time this becomes a map of
  which creators share audiences, which no single search, and no follower-count database, provides.
- **Calibration that improves with use.** The cross-platform estimate is tuned on measured YouTube pairs; more
  measured pairs make Instagram and TikTok estimates better. A competitor starting today starts uncalibrated.
- **Decision history.** Saved campaigns record what was chosen, what was left out, and why. Paired with campaign
  results later, that becomes training and validation data for roster planning specifically.
- **Method, not a model wrapper.** The value is the pipeline, the optimizer, and the evidence labeling. Swapping the
  LLM does not change the plan; copying it requires rebuilding the collection, aggregation, and calibration.
- **Fits a larger product.** It slots into BrandMuse's strategist workflow as a portfolio-level check next to
  per-creator fit.

### Limits to state plainly (judges will ask)

- Commenters are a sample of engaged viewers, not all viewers; overlap on broad topics is often under 1%.
- Instagram and TikTok overlap is estimated, not measured; pairs with no audience data are marked assumed.
- Not yet validated against a third-party overlap tool; that comparison is the next step.
- Quotes are modeled rates per 1,000 followers and are editable.
