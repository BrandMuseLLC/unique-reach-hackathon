import React, { useEffect, useState } from 'react';
import { ChevronRight, Search } from 'lucide-react';
import { Avatar, Chip, Insight } from './parts';
import { WhyNotPanel } from './WhyNotPanel';
import { ExploreOverlap } from './ExploreOverlap';
import { PLATFORMS, PLATFORM_LABEL, compact, pct, platformOf, topicOf, type Creator, type Delta, type Graph, type Inputs, type Plan, type Platform } from './types';

export type RosterStatus = 'excluded' | 'required' | 'recommended' | 'left' | 'none';
export type CreatorsFilter = 'recommended' | 'yours' | 'left';

export function CreatorsScreen({ creators, inputs, plan, stale, crossPlatform, rosterList, rosterMissing = [], rosterSkipped = [], rosterBasis, graph, graphError = '', aiEnabled, delta, initialFilter, statusOf, platformOn, onUpdate, onAsk, onExplain, onGraph }: {
  creators: Creator[];
  inputs: Inputs;
  plan: Plan | null;
  stale: boolean;
  crossPlatform: boolean;
  rosterList: boolean;
  rosterMissing?: string[];
  rosterSkipped?: { channel: string; reason: string }[];
  rosterBasis: string;
  graph: Graph | null;
  graphError?: string;
  aiEnabled: boolean;
  delta: Delta | null;
  initialFilter?: CreatorsFilter;
  statusOf: (id: string) => RosterStatus;
  platformOn: (platform: Platform) => boolean;
  onUpdate: (patch: Partial<Inputs>) => void;
  onAsk: (question: string) => void;
  onExplain: () => void;
  onGraph: (graph: Graph) => void;
}) {
  const [filter, setFilter] = useState<CreatorsFilter>(initialFilter ?? 'recommended');
  const [platformFilter, setPlatformFilter] = useState<'all' | Platform>('all');
  const [query, setQuery] = useState('');
  const [openRow, setOpenRow] = useState('');
  useEffect(() => { if (initialFilter) setFilter(initialFilter); }, [initialFilter]);

  const eligible = creators.filter((c) => c.eligibilityStatus !== 'ineligible');
  // On an uploaded list every creator stays visible: the unmeasurable ones are shown with the reason instead of vanishing.
  const yours = rosterList ? creators : eligible;
  const unmeasured = yours.length - eligible.length;
  const planIds = plan ? new Set(plan.recommended.ids) : null;
  const leftOut = new Map((plan?.whyNot ?? []).map((w) => [w.creatorId, w]));
  const yoursLabel = rosterList ? 'Your creators' : 'All creators';
  const rows = yours
    .filter((c) => !query.trim() || c.name.toLowerCase().includes(query.trim().toLowerCase()))
    .filter((c) => platformFilter === 'all' || platformOf(c) === platformFilter)
    .filter((c) => filter === 'yours'
      || (filter === 'recommended' && ((planIds?.has(c.id) ?? false) || inputs.include.includes(c.id) || openRow === c.id))
      || (filter === 'left' && (statusOf(c.id) === 'left' || statusOf(c.id) === 'excluded' || c.eligibilityStatus === 'ineligible')))
    .sort((a, b) => Number(a.eligibilityStatus === 'ineligible') - Number(b.eligibilityStatus === 'ineligible') || Number(!(planIds?.has(a.id))) - Number(!(planIds?.has(b.id))) || (b.followers ?? b.estimatedViews) - (a.followers ?? a.estimatedViews));
  const rec = plan?.rosterDiagnostics?.rosters.recommended;
  const cur = plan?.rosterDiagnostics?.rosters.current;
  const leftCount = yours.filter((c) => c.eligibilityStatus === 'ineligible' || statusOf(c.id) === 'left' || statusOf(c.id) === 'excluded').length;
  const watch = pairToWatch(plan, graph);
  const unit = crossPlatform ? 'followers' : 'commenters';

  return (
    <div className="app-screen">
      <section id="creators" className="app-section">
        <div className="app-screen-head">
          <div>
            <span className="eyebrow-wide app-eyebrow">Creators</span>
            <h1 className="hero-question app-title">{rosterList ? `${yours.length} creators in your list` : `${eligible.length} creators in the plan pool`}</h1>
            <p className="app-helper">{rosterList
              ? `The recommendation is the subset of your list that reaches the most people with the least shared audience. Require, exclude or untick a creator and everything below updates.${unmeasured ? ` ${unmeasured} ${unmeasured === 1 ? 'creator has' : 'creators have'} too few public comments to measure and ${unmeasured === 1 ? 'is' : 'are'} shown but not planned.` : ''}${rosterSkipped.length ? ` No public comments could be sampled for ${rosterSkipped.map((s) => s.channel).join(', ')}, so ${rosterSkipped.length === 1 ? 'it is' : 'they are'} not on the map.` : ''}${rosterMissing.length ? ` Not found on YouTube: ${rosterMissing.join(', ')}.` : ''}`
              : `Require, exclude or untick a creator and everything below updates.${rosterBasis ? ` Your starting roster is ${rosterBasis.charAt(0).toLowerCase()}${rosterBasis.slice(1).replace(/\.$/, '')}.` : ''}`}</p>
          </div>
          <label className="app-search"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search creators" aria-label="Search creators" /></label>
        </div>

        {plan && rec && cur && (
          <div className={`app-live ${stale ? 'busy' : ''}`} aria-live="polite">
            <LiveStat label={`${crossPlatform ? 'Estimated ' : ''}overlap`} value={pct(rec.sharedRate)} from={delta?.subject === 'plan' && Math.abs(delta.overlapFrom - delta.overlapTo) >= 0.0005 ? pct(delta.overlapFrom) : null} good={delta ? delta.overlapTo <= delta.overlapFrom : undefined} accent />
            <LiveStat label={`Unique ${unit}`} value={compact(plan.recommended.proxyReach)} from={delta?.subject === 'plan' && delta.reachFrom !== delta.reachTo ? compact(delta.reachFrom) : null} good={delta ? delta.reachTo >= delta.reachFrom : undefined} />
            <LiveStat label="Recommended" value={`${rec.ids.length} of ${yours.length}`} />
            <LiveStat label={rosterList ? 'Your list reaches' : 'Your roster reaches'} value={cur.ids.length ? `${compact(plan.current.proxyReach)} · ${pct(cur.sharedRate)} overlap` : 'nothing ticked'} />
            <span className="app-live-note">{stale ? 'Updating…' : 'Live'}</span>
          </div>
        )}
        {plan && rec && (
          <Insight>
            {watch ? <>{watch.a} and {watch.b} share the most audience in the recommendation: {pct(watch.share)} {watch.source === 'measured' ? 'measured' : 'estimated'} overlap. That is the pair to watch if you add another similar creator.</>
              : 'No two creators in the recommendation share a measurable audience in this sample.'}
          </Insight>
        )}
        <div className="app-filters">
          <div className="app-chip-row">
            <Chip active={filter === 'recommended'} onClick={() => setFilter('recommended')} count={plan?.recommended.ids.length ?? 0}>Recommended</Chip>
            <Chip active={filter === 'yours'} onClick={() => setFilter('yours')} count={yours.length}>{yoursLabel}</Chip>
            <Chip active={filter === 'left'} onClick={() => setFilter('left')} count={leftCount}>Left out</Chip>
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
          {rows.length === 0 && <div className="app-empty">{filter === 'left' ? 'Every creator is in the recommendation.' : 'No creators here.'}</div>}
          {rows.map((c) => {
            const status = statusOf(c.id);
            const why = leftOut.get(c.id);
            const open = openRow === c.id;
            const platform = platformOf(c);
            const off = crossPlatform && !platformOn(platform);
            const unmeasurable = c.eligibilityStatus === 'ineligible';
            const covered = why ? Math.round(why.alreadyCoveredShare * 100) : 0;
            return (
              <div key={c.id} className={`app-row s-${unmeasurable ? 'none' : status} ${open ? 'open' : ''}`}>
                <div className="app-row-main">
                  <input type="checkbox" checked={inputs.currentRoster.includes(c.id)} aria-label={`${c.name} is in your ${rosterList ? 'list' : 'roster'}`} disabled={off || unmeasurable}
                    title={rosterList ? 'Untick to compare against your list without this creator' : 'Tick to add this creator to your own roster'}
                    onChange={() => onUpdate({ currentRoster: inputs.currentRoster.includes(c.id) ? inputs.currentRoster.filter((x) => x !== c.id) : [...inputs.currentRoster, c.id] })} />
                  <Avatar name={c.name} platform={crossPlatform ? platform : undefined} />
                  <div className="app-row-name">
                    <strong>{c.name}{c.foundBy === 'upriver' && <span className="app-found-by">Upriver lookalike</span>}</strong>
                    <span>{PLATFORM_LABEL[platform]} · {topicOf(c)} · {compact(c.followers ?? c.estimatedViews)} {crossPlatform || c.followers ? 'followers' : 'views'}</span>
                  </div>
                  <span className={`app-status st-${unmeasurable ? 'off' : off ? 'off' : status}`}>
                    {unmeasurable ? 'Not measurable' : off ? 'Platform off' : status === 'recommended' ? 'Recommended' : status === 'required' ? 'Required' : status === 'excluded' ? 'Excluded'
                      : status === 'left' ? (covered >= 1 ? `${covered}% already reached` : 'Not picked') : ''}
                  </span>
                  <button type="button" className="app-icon-btn" onClick={() => setOpenRow(open ? '' : c.id)} aria-expanded={open} aria-label={`${open ? 'Close' : 'Open'} ${c.name}`}>
                    <ChevronRight size={16} className={open ? 'rot' : ''} />
                  </button>
                </div>
                {open && (
                  <div className="app-row-detail">
                    {crossPlatform && c.audienceDescription && <p className="app-helper">Upriver: {c.audienceDescription}</p>}
                    {crossPlatform && <p className="app-helper">Audience: {c.audienceSummary || 'No audience data from Upriver'} · overlap with others is {c.overlapEvidence === 'estimated' ? 'estimated from audience profiles' : 'measured with other YouTube creators, estimated with Instagram and TikTok'}</p>}
                    <p>{unmeasurable ? (c.eligibilityReason || 'Too few public comments to measure audience overlap, so this creator is shown but not planned.')
                      : off ? `${PLATFORM_LABEL[platform]} is switched off in the platform settings, so this creator is not planned.`
                      : status === 'recommended' ? 'Recommended because it adds the most new audience the others do not already reach.'
                        : why ? (why.overlapsWith.length ? `${covered}% of its audience is already reached through ${why.overlapsWith.map((o) => o.creatorName).join(', ')}. ${why.reason}` : why.reason)
                          : 'Run the plan to see how this creator compares.'}</p>
                    {c.sponsorMentions?.brands.length ? <p className="app-helper">Mentions in descriptions: {c.sponsorMentions.brands.map((b) => b.brand).join(', ')}</p> : null}
                    {!unmeasurable && <div className="app-row-actions">
                      <Chip active={status === 'required'} disabled={off} onClick={() => onUpdate({ include: inputs.include.includes(c.id) ? inputs.include.filter((x) => x !== c.id) : [...inputs.include, c.id], exclude: inputs.exclude.filter((x) => x !== c.id) })}>
                        {status === 'required' ? 'Required' : 'Require'}
                      </Chip>
                      <Chip active={status === 'excluded'} onClick={() => onUpdate({ exclude: inputs.exclude.includes(c.id) ? inputs.exclude.filter((x) => x !== c.id) : [...inputs.exclude, c.id], include: inputs.include.filter((x) => x !== c.id) })}>
                        {status === 'excluded' ? 'Excluded' : 'Exclude'}
                      </Chip>
                      <button type="button" className="app-link" onClick={() => onAsk(`Why is ${c.name} ${status === 'recommended' ? 'in' : 'not in'} the recommendation?`)} disabled={!aiEnabled}>Ask Muse why</button>
                    </div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {plan?.whyNot && <WhyNotPanel rows={plan.whyNot} stale={stale} crossPlatform={crossPlatform} onExplain={onExplain} />}
      {creators.some((c) => c.source === 'observed-public') && <ExploreOverlap graph={graph} error={graphError} aiEnabled={aiEnabled} onExplain={onExplain} onGraph={onGraph} planIds={plan?.recommended.ids ?? []} />}
    </div>
  );
}

function LiveStat({ label, value, from = null, good, accent = false }: { label: string; value: string; from?: string | null; good?: boolean; accent?: boolean }) {
  return (
    <div className="app-live-stat">
      <span>{label}</span>
      <strong className={accent ? 'accent' : ''}>{from ? <><s>{from}</s> <i className={good ? 'good' : 'bad'}>{value}</i></> : value}</strong>
    </div>
  );
}

/** The highest pairwise share inside the recommended roster, from the overlap graph. */
export function pairToWatch(plan: Plan | null, graph: Graph | null) {
  if (!plan || !graph) return null;
  const inPlan = new Set(plan.recommended.ids);
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  let best: { a: string; b: string; share: number; source: string } | null = null;
  for (const p of graph.pairs) {
    if (!inPlan.has(p.a) || !inPlan.has(p.b) || p.sharedCommenters <= 0) continue;
    const na = nodes.get(p.a), nb = nodes.get(p.b);
    if (!na || !nb) continue;
    const smaller = Math.min(na.sampledCommenters, nb.sampledCommenters) || 1;
    const share = p.sharedCommenters / smaller;
    if (!best || share > best.share) best = { a: na.name, b: nb.name, share, source: p.source ?? 'measured' };
  }
  return best;
}
