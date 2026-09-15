# Unique Reach

Technical write-up · September 14, 2026

Source checkpoint: [480a9ae](https://github.com/BrandMuseLLC/unique-reach-hackathon/tree/480a9aef8892ab8c916448808f560b101d4789a0). [Public repository and local-run instructions](https://github.com/BrandMuseLLC/unique-reach-hackathon).

## The problem and what we built

Choosing creators individually leaves a portfolio question unanswered: how much of their sampled audience is shared, and which combination fits a campaign's budget and constraints? Unique Reach makes that question interactive before a team commits spend.

The prototype connects natural-language campaign interpretation, creator discovery, audience evidence, constrained roster search, and explanations in a React/TypeScript workspace backed by Python/FastAPI. Users can change budgets and quotes, require or exclude creators, inspect tradeoffs, undo edits, and save and restore campaign inputs. The public default is a fictional dataset that runs without vendor credentials. Observed-data and live-model integrations are separate, credential-dependent paths.

## From brief to decision

A campaign brief becomes structured search and planning inputs. The discovery path finds candidate creators, samples available evidence, and builds a dataset with its own identity and version. Planning applies the budget, quotes, required/excluded creators, and other constraints. The workspace compares the selected roster with the user's roster and exposes each change in coverage, overlap, and spend. Users can inspect shared audiences and reasons for leaving creators out, revise inputs, undo an edit, and restore a saved campaign.

For a marketing team, the practical output is a shortlist with explicit assumptions and tradeoffs that can be discussed before negotiating partnerships. Revenue and campaign effectiveness motivate the problem; the prototype does not yet measure either outcome.

## Progress demonstrated across the event

Our first update introduced the historical 34-channel YouTube case study and the local planning prototype. The second demonstrated a coffee-category roster comparison, the overlap explorer, and explanations for creators left out. Updates three and four used explicitly labeled synthetic data to demonstrate automatic replanning, change summaries, Undo, campaign restoration, and required/excluded creator controls. Those synthetic percentages demonstrated application behavior, not measured campaign results.

The final demonstration returns to a discovered YouTube dataset for a football-product campaign and shows roster comparisons, live edits, an audience map, and the path to cross-platform similarity. Its selected roster shows negligible sampled overlap; that is a case where cost and coverage deserve more attention than a dramatic overlap-reduction claim. These demonstrations cover different datasets and evolving implementations, so their percentages are not a longitudinal performance benchmark.

## Where AI contributes

Gemini translates campaign language into structured search or planning inputs and supports conversational edits and explanations. Server-side validation and planning code compute the roster and its metrics. This separation lets the language interface adapt to a brief without accepting generated audience numbers as measurements. The combinatorial solver itself is conventional software; the AI contribution is connecting open-ended campaign intent to discovery and validated planning actions.

## What is technically difficult

**Building overlap evidence.** The YouTube collection path samples public comment threads through the official API. It salts and hashes author identifiers before local storage; the aggregate represents counts for creator-membership combinations. Those aggregate sets support union and intersection calculations without distributing raw comments or author identifiers in the public submission. Sampling coverage, thin evidence, and the distinction between commenters and viewers remain material limitations.

**Choosing a roster under interacting constraints.** In observed mode, the system starts from feasible candidate rosters and performs bounded add, drop, and swap search. It prefers lower repeated-membership rates while preserving a coverage floor derived from the user's feasible roster; when that roster is infeasible, the floor comes from a feasible reference plan. Budget, required/excluded creators, group caps, and creator-count settings constrain the search. This is a heuristic with no global-optimality certificate. Topic relevance, when used, affects the coverage objective, so a weighted floor is not an unconditional guarantee about raw audience counts.

**Keeping different evidence types distinguishable.** The cross-platform implementation combines YouTube commenter intersections with audience-profile estimates for Instagram and TikTok. It can fit a scaling factor from eligible YouTube pairs, but uses a default when fewer than three calibration pairs are available. Missing profile evidence produces assumed pairs. Pairwise subtraction approximates a roster's combined audience and is bounded below by its largest individual audience; it does not measure cross-platform identities or resolve higher-order intersections exactly. The UI exposes measured, estimated, and assumed evidence. This integration is implemented, not independently validated against true cross-platform reach.

**Making recommendations inspectable.** Deterministic diagnostics explain required or excluded creators, budget and count constraints, and changes in overlap, coverage, and spend. The latest checkpoint displays sub-1% percentages more precisely and calls out cases where overlap is small in both rosters. A negligible or negative improvement remains a legitimate result. Saved campaigns preserve planning inputs and dataset version; ownership behavior is covered by API tests.

## Metric interpretation

For the observed YouTube roster, repeated-membership rate is `(sum of individual commenter counts − union count) / sum of individual commenter counts`. A person present on several channels contributes repeated memberships; the metric is not the percentage of distinct viewers duplicated. Pairwise conditional overlap uses a different denominator. Cross-platform estimates are separately labeled and should not be compared as if they were the same directly observed population.

Quotes are editable assumptions. These signals do not establish wasted spend, incremental sales, validated unique viewers, or campaign lift.

## Defensibility: current substance and future hypothesis

The current substance is the integration of an evidence pipeline, constrained portfolio decisions, data-aware explanations, and a repeatable planning workflow. Reproducing the full experience requires more than adding a chat box to a creator list. However, the repository is public and the underlying algorithms are not claimed to be exclusive or novel research.

Potential defensibility would come from permitted, refreshed audience evidence across relevant categories; calibration tested against independent overlap measurements; and a consented link between planning decisions and campaign outcomes. None of these is established merely by accumulating searches. Public comment data is not exclusive, demographic similarity is not proof of shared individuals, and more calibration samples do not automatically make cross-platform estimates accurate. Outcome-linked decision history and external validation are future work, not completed assets.

Creator and brand-side experience also informs the methodology: which planning questions to ask, which constraints matter, and how to interpret audience patterns in a campaign's context. That judgment can help direct AI toward useful comparisons and identify recommendations that look plausible numerically but miss the realities of a niche. It complements the measured evidence; it does not validate the overlap proxy on its own.

We plan to develop this approach through niche specialists with both creator and brand-side backgrounds working directly with brands. Their assessments, corrections, and observed campaign outcomes could become structured evaluation cases for pattern matching and roster planning. The potential defensibility lies in consistently capturing and testing that judgment, building a body of decision evidence that improves the system over time. This specialist feedback process is a planned extension; the current prototype provides the planning and evidence workflow on which to build it.

## Verification and practical limits

At the pinned checkpoint, 43 collection/backend tests passed locally on September 14. GitHub CI also passed its collection tests and frontend build: [run34901506946](https://github.com/BrandMuseLLC/unique-reach-hackathon/actions/runs/34901506946). Tests support implementation correctness on their fixtures; they do not validate the audience proxy or business results.

A separate canonical local build passed a live Gemini 3.1 Pro preview planning check on September 12, including budget and required/excluded constraints. That is historical evidence, not proof that sponsored credentials still work on September 14 or that the latest discovery path has been tested end to end. No fresh paid/vendor call was made for this write-up. Hosted authenticated deployment and independent audience validation remain unverified here.

## Next steps

We intend to continue developing Unique Reach after the hackathon. Additional compute credits, access to independent audience-overlap data, and funding for small brand pilots would help us test whether the commenter-overlap signal improves roster decisions. We would use those resources to measure where the approach works, where it fails, and whether it adds value beyond selecting creators by size and fit alone.

The next validation work would compare the proxy with independent audience evidence, measure calibration error and stability over time, and evaluate planning decisions with brands. Alongside that work, we plan to develop the specialist feedback process described above. The current deliverable is a runnable prototype for making roster tradeoffs explicit.
