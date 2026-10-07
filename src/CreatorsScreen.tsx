import React, { useState } from 'react';
import { ChevronRight, Search } from 'lucide-react';
import { Avatar, Chip, Insight } from './parts';
import { WhyNotPanel } from './WhyNotPanel';
import { ExploreOverlap } from './ExploreOverlap';
import { PLATFORMS, PLATFORM_LABEL, compact, money, pct, platformOf, topicOf, type Creator, type Graph, type Inputs, type Plan, type Platform } from './types';

export type RosterStatus = 'excluded' | 'required' | 'recommended' | 'left' | 'none';
type Filter = 'recommended' | 'roster' | 'left' | 'all';

export function CreatorsScreen({ creators, inputs, plan, stale, crossPlatform, rosterBasis, graph, aiEnabled, statusOf, platformOn, onUpdate, onAsk, onExplain, onGraph }: {
  creators: Creator[];
  inputs: Inputs;
  plan: Plan | null;
  stale: boolean;
  crossPlatform: boolean;
  rosterBasis: string;
  graph: Graph | null;
  aiEnabled: boolean;
  statusOf: (id: string) => RosterStatus;
  platformOn: (platform: Platform) => boolean;
  onUpdate: (patch: Partial<Inputs>) => void;
  onAsk: (question: string) => void;
  onExplain: () => void;
  onGraph: (graph: Graph) => void;
}) {
  const [filter, setFilter] = useState<Filter>('recommended');
  const [platformFilter, setPlatformFilter] = useState<'all' | Platform>('all');
  const [query, setQuery] = useState('');
  const [openRow, setOpenRow] = useState('');

  const eligible = creators.filter((c) => c.eligibilityStatus !== 'ineligible');
  const planIds = plan ? new Set(plan.recommended.ids) : null;
  const leftOut = new Map((plan?.whyNot ?? []).map((w) => [w.creatorId, w]));
  const rows = eligible
    .filter((c) => !query.trim() || c.name.toLowerCase().includes(query.trim().toLowerCase()))
    .filter((c) => platformFilter === 'all' || platformOf(c) === platformFilter)
    .filter((c) => filter === 'all'
      || (filter === 'recommended' && ((planIds?.has(c.id) ?? false) || inputs.exclude.includes(c.id) || inputs.include.includes(c.id) || openRow === c.id))
      || (filter === 'roster' && inputs.currentRoster.includes(c.id))
      || (filter === 'left' && statusOf(c.id) === 'left'))
    .sort((a, b) => Number(!(planIds?.has(a.id))) - Number(!(planIds?.has(b.id))) || (b.followers ?? b.estimatedViews) - (a.followers ?? a.estimatedViews));
  const recDiag = plan?.rosterDiagnostics?.rosters.recommended;
  const watch = pairToWatch(plan, graph);

  return (
    <div className="app-screen">
      <section id="creators" className="app-section">
        <div className="app-screen-head">
          <div>
            <span className="eyebrow-wide app-eyebrow">Creators</span>
            <h1 className="hero-question app-title">{eligible.length} creators in the plan pool</h1>
            <p className="app-helper">Exclude, require or re-price a creator and the plan updates instantly.{rosterBasis ? ` Your starting roster is ${rosterBasis.charAt(0).toLowerCase()}${rosterBasis.slice(1).replace(/\.$/, '')}.` : ''}</p>
          </div>
          <label className="app-search"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search creators" aria-label="Search creators" /></label>
        </div>
        {plan && recDiag && (
          <Insight>
            Spend is {money(recDiag.spend)} of {money(plan.budget)}.{' '}
            {watch ? <>{watch.a} carries {pct(watch.share)} {watch.source === 'measured' ? '' : 'estimated '}overlap with {watch.b}, the pair to watch if you add another {watch.topic} creator.</> : 'No two creators in the plan share a measurable audience in this sample.'}
          </Insight>
        )}
        <div className="app-filters">
          <div className="app-chip-row">
            {([['recommended', 'In the plan'], ['roster', 'Your roster'], ['left', 'Left out'], ['all', 'All']] as const).map(([id, label]) => (
              <Chip key={id} active={filter === id} onClick={() => setFilter(id)}>{label}</Chip>
            ))}
          </div>
          <div className="app-chip-row">
            <Chip active={platformFilter === 'all'} onClick={() => setPlatformFilter('all')}>All platforms</Chip>
            {PLATFORMS.map((p) => (
              <Chip key={p} active={platformFilter === p} onClick={() => setPlatformFilter(p)} count={eligible.filter((c) => platformOf(c) === p).length}
                title={crossPlatform && !platformOn(p) ? `${PLATFORM_LABEL[p]} is switched off for this plan` : undefined}>{PLATFORM_LABEL[p]}</Chip>
            ))}
          </div>
        </div>
        <div className="app-rows">
          {rows.length === 0 && <div className="app-empty">No creators here.</div>}
          {rows.map((c) => {
            const status = statusOf(c.id);
            const why = leftOut.get(c.id);
            const open = openRow === c.id;
            const platform = platformOf(c);
            const off = crossPlatform && !platformOn(platform);
            const quote = inputs.costs[c.id] ?? c.baseCost;
            return (
              <div key={c.id} className={`app-row s-${status} ${open ? 'open' : ''}`}>
                <div className="app-row-main">
                  <input type="checkbox" checked={inputs.currentRoster.includes(c.id)} aria-label={`${c.name} is in your roster`} disabled={off}
                    onChange={() => onUpdate({ currentRoster: inputs.currentRoster.includes(c.id) ? inputs.currentRoster.filter((x) => x !== c.id) : [...inputs.currentRoster, c.id] })} />
                  <Avatar name={c.name} platform={crossPlatform ? platform : undefined} />
                  <div className="app-row-name">
                    <strong>{c.name}{c.foundBy === 'upriver' && <span className="app-found-by">Upriver lookalike</span>}</strong>
                    <span>{PLATFORM_LABEL[platform]} · {topicOf(c)} · {compact(c.followers ?? c.estimatedViews)} {crossPlatform ? 'followers' : 'views'}</span>
                  </div>
                  <span className={`app-status st-${off ? 'off' : status}`}>
                    {off ? 'Platform off' : status === 'recommended' ? 'In the plan' : status === 'required' ? 'Required' : status === 'excluded' ? 'Excluded'
                      : status === 'left' ? (why && Math.round(why.alreadyCoveredShare * 100) >= 1 ? `${Math.round(why.alreadyCoveredShare * 100)}% already reached` : 'Not picked') : ''}
                  </span>
                  <span className="app-row-quote">{money(quote)}</span>
                  <button type="button" className="app-icon-btn" onClick={() => setOpenRow(open ? '' : c.id)} aria-expanded={open} aria-label={`${open ? 'Close' : 'Open'} ${c.name}`}>
                    <ChevronRight size={16} className={open ? 'rot' : ''} />
                  </button>
                </div>
                {open && (
                  <div className="app-row-detail">
                    {crossPlatform && c.audienceDescription && <p className="app-helper">Upriver: {c.audienceDescription}</p>}
                    {crossPlatform && <p className="app-helper">Audience: {c.audienceSummary || 'No audience data from Upriver'} · overlap with others is {c.overlapEvidence === 'estimated' ? 'estimated from audience profiles' : 'measured with other YouTube creators, estimated with Instagram and TikTok'}</p>}
                    <p>{off ? `${PLATFORM_LABEL[platform]} is switched off in the platform settings, so this creator is not planned.`
                      : status === 'recommended' ? 'Picked because it adds the most new audience for its quote at this budget.'
                        : why ? (why.overlapsWith.length ? `${Math.round(why.alreadyCoveredShare * 100)}% of its audience is already reached through ${why.overlapsWith.map((o) => o.creatorName).join(', ')}. ${why.reason}` : why.reason)
                          : 'Run the plan to see how this creator compares.'}</p>
                    {c.sponsorMentions?.brands.length ? <p className="app-helper">Mentions in descriptions: {c.sponsorMentions.brands.map((b) => b.brand).join(', ')}</p> : null}
                    <div className="app-row-actions">
                      <label className="app-money"><b>$</b><input inputMode="numeric" value={quote.toLocaleString('en-US')}
                        onChange={(e) => onUpdate({ costs: { ...inputs.costs, [c.id]: Number(e.target.value.replace(/[^0-9]/g, '')) || 0 } })} aria-label={`Quote for ${c.name}`} /></label>
                      <Chip active={status === 'required'} disabled={off} onClick={() => onUpdate({ include: inputs.include.includes(c.id) ? inputs.include.filter((x) => x !== c.id) : [...inputs.include, c.id], exclude: inputs.exclude.filter((x) => x !== c.id) })}>
                        {status === 'required' ? 'Required' : 'Require'}
                      </Chip>
                      <Chip active={status === 'excluded'} onClick={() => onUpdate({ exclude: inputs.exclude.includes(c.id) ? inputs.exclude.filter((x) => x !== c.id) : [...inputs.exclude, c.id], include: inputs.include.filter((x) => x !== c.id) })}>
                        {status === 'excluded' ? 'Excluded' : 'Exclude'}
                      </Chip>
                      <button type="button" className="app-link" onClick={() => onAsk(`Why is ${c.name} ${status === 'recommended' ? 'in' : 'not in'} the plan?`)} disabled={!aiEnabled}>Ask Muse why</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {plan?.whyNot && <WhyNotPanel rows={plan.whyNot} stale={stale} crossPlatform={crossPlatform} onExplain={onExplain} />}
      {creators.some((c) => c.source === 'observed-public') && <ExploreOverlap graph={graph} aiEnabled={aiEnabled} onExplain={onExplain} onGraph={onGraph} />}
    </div>
  );
}

/** The highest pairwise share inside the recommended roster, from the overlap graph. */
export function pairToWatch(plan: Plan | null, graph: Graph | null) {
  if (!plan || !graph) return null;
  const inPlan = new Set(plan.recommended.ids);
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  let best: { a: string; b: string; share: number; source: string; topic: string } | null = null;
  for (const p of graph.pairs) {
    if (!inPlan.has(p.a) || !inPlan.has(p.b) || p.sharedCommenters <= 0) continue;
    const na = nodes.get(p.a), nb = nodes.get(p.b);
    if (!na || !nb) continue;
    const smaller = Math.min(na.sampledCommenters, nb.sampledCommenters) || 1;
    const share = p.sharedCommenters / smaller;
    if (!best || share > best.share) best = { a: na.name, b: nb.name, share, source: p.source ?? 'measured', topic: 'similar' };
  }
  return best;
}
