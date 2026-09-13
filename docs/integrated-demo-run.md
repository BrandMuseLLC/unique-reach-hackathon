# Integrated demo: current local verification

Base: public main e8b68d5. Use Studio; do not replace it with the older UI.

Verified additions: saved campaign controls using the existing owner-scoped backend; full reload and restoration in Chrome. Synthetic mode starts with a feasible illustrative budget, labels its data, hides the unavailable observed map and disables unsupported creator-count controls. Existing observed count targets, Muse chat, undo and live replanning are preserved.

Local demonstration order (under 60 seconds):

1. “Unique Reach is one tool in Intuition. Today we integrated the campaign workspace and made plans saveable.” Show the campaign and data label.
2. Edit budget or roster; show the live comparison. “The planner compares creator combinations within a budget.”
3. Save the campaign and load it. “We can keep the full planning state for later.”
4. If an approved observed dataset and tested model are available, show Muse changing a constraint and undoing it. Otherwise state that live inference was verified previously, but is disabled in this synthetic run.
5. “Next we are validating the evidence and finishing the hosted experience.”

Do not click Find creators during this verification: it starts new API collection. No live collection, model request, or historical-data display was performed for this integration.

Metric definitions:

- Headline repeated-membership rate = (sum of per-creator commenter counts minus their union) / sum of per-creator counts. It is not the fraction of distinct people duplicated.
- Conditional pair overlap = intersection / focus creator's commenter count. It changes when the focus changes.
- Jaccard = intersection / union, symmetric. Cluster internals can use Jaccard while the displayed pair percentage is conditional.
- Commenter accounts are sample evidence, not validated unique viewers; a view-scaled score is modeled, not observed reach. Synthetic results are interface examples, not empirical findings.

Outstanding risks: discovery datasets and active dataset selection are process-global and are not yet suitable for multiple independent hosted users. Campaign ownership is tested separately and remains enforced. Gemini 3.6 Flash is a teammate report, not independently verified here. No new public push is included.
