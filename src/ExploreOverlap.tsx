import React, { useEffect, useMemo, useState } from 'react';
import { EyebrowRow } from './parts';
import { whole, type Graph } from './types';

export function ExploreOverlap({ graph: given, aiEnabled = false, onExplain, onGraph, planIds = [] }: { graph?: Graph | null; aiEnabled?: boolean; onExplain?: () => void; onGraph?: (graph: Graph) => void; planIds?: string[] }) {
  const inPlan = new Set(planIds);
  // The Studio fetches the graph once and passes it down; the legacy layout still lets this component fetch for itself.
  const [own, setOwn] = useState<Graph | null>(null);
  const [error, setError] = useState('');
  const graph = given === undefined ? own : given;
  useEffect(() => {
    if (given !== undefined) return;
    const controller = new AbortController();
    fetch('/api/overlap', { signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error('Audience data could not be loaded.'); setOwn(await response.json()); })
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [given]);

  const [focus, setFocus] = useState('');
  const [labeling, setLabeling] = useState(false);
  const [labelStatus, setLabelStatus] = useState('');

  useEffect(() => {
    if (!graph) return;
    const biggest = [...graph.nodes].sort((a, b) => b.sampledCommenters - a.sampledCommenters)[0];
    setFocus((current) => (graph.nodes.some((n) => n.id === current) ? current : biggest?.id ?? ''));
  }, [graph]);

  const nodes = useMemo(() => new Map(graph?.nodes.map((n) => [n.id, n]) ?? []), [graph]);
  const center = nodes.get(focus);
  // Share of the focus creator's audience that is also the other creator's: easier to read than Jaccard.
  const neighbours = useMemo(() => {
    if (!graph || !center) return [];
    return graph.pairs
      .filter((p) => (p.a === focus || p.b === focus) && p.sharedCommenters > 0)
      .map((p) => {
        const other = nodes.get(p.a === focus ? p.b : p.a)!;
        return { other, shared: p.sharedCommenters, source: p.source, share: center.sampledCommenters ? p.sharedCommenters / center.sampledCommenters : 0 };
      })
      .sort((x, y) => y.share - x.share)
      .slice(0, 8);
  }, [graph, center, focus, nodes]);
  const maxShare = Math.max(...neighbours.map((n) => n.share), 0.0001);
  const groups = (graph?.clusters ?? []).filter((c) => c.members.length > 1);
  const followers = graph?.unit === 'estimated_followers';

  async function nameGroups() {
    setLabeling(true);
    setLabelStatus('');
    try {
      const response = await fetch('/api/overlap/labels', { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? 'Naming failed; the simple labels are unchanged.');
      if (graph) {
        const next = { ...graph, clusters: payload.clusters };
        if (given === undefined) setOwn(next); else onGraph?.(next);
      }
      setLabelStatus('Named from channel names and video titles, not from viewer data.');
    } catch (e) {
      setLabelStatus(e instanceof Error ? e.message : 'Naming failed.');
    } finally {
      setLabeling(false);
    }
  }

  return (
    <section id="map" className="app-section" aria-labelledby="aud-heading">
      <EyebrowRow label="Audience map" link="How estimates work" onLink={onExplain} />
      <p className="app-helper" id="aud-heading">Which creators share the same fans? {followers ? 'YouTube pairs count people who commented on both creators’ recent videos; pairs with Instagram or TikTok are estimated from audience profiles.' : 'We count people who commented on both creators’ recent videos.'}</p>
      {error && <p className="app-alert" role="alert">{error}</p>}
      {!graph && !error && <div className="app-card app-card-pad app-helper">Loading audience data…</div>}
      {graph && center && (
        <div className="app-aud-grid">
          <div className="app-card app-card-pad app-aud-card">
            <label className="app-aud-pick">
              <span>Pick a creator</span>
              <select className="app-select" value={focus} onChange={(e) => setFocus(e.target.value)} aria-label="Pick a creator">
                {[...graph.nodes].sort((a, b) => Number(inPlan.has(b.id)) - Number(inPlan.has(a.id)) || a.name.localeCompare(b.name)).map((n) => <option key={n.id} value={n.id}>{n.name}{inPlan.has(n.id) ? ' · recommended' : ''}</option>)}
              </select>
            </label>
            <p className="app-aud-lead">
              {followers
                ? <>Of about <b>{whole(center.sampledCommenters)}</b> followers of <b>{center.name}</b>, this share also follow:</>
                : <>Of <b>{whole(center.sampledCommenters)}</b> people we saw commenting on <b>{center.name}</b>, this share also comment on:</>}
            </p>
            {neighbours.length === 0 ? (
              <p className="app-helper">No shared audience with the other creators in this search. Their audiences look separate in our sample.</p>
            ) : (
              <ul className="app-aud-bars" key={focus}>
                {neighbours.map((n) => (
                  <li key={n.other.id}>
                    <button type="button" className={`app-aud-name ${inPlan.has(n.other.id) ? 'in-plan' : ''}`} onClick={() => setFocus(n.other.id)} title={`Show ${n.other.name}${inPlan.has(n.other.id) ? ' (recommended)' : ''}`}>{n.other.name}</button>
                    <div className="app-bar app-bar-10"><i style={{ width: `${Math.max((n.share / maxShare) * 100, 3)}%` }} /></div>
                    <span className="app-aud-value"><strong>{(n.share * 100).toFixed(n.share < 0.1 ? 1 : 0)}%</strong><small>{n.source && n.source !== 'measured' ? n.source : `${whole(n.shared)} people`}</small></span>
                  </li>
                ))}
              </ul>
            )}
            <p className="app-footnote">Higher % means more of the same fans, so pairing those two creators reaches fewer new people. {followers
              ? 'YouTube pairs are measured from shared commenters; pairs with Instagram or TikTok are estimated from audience profiles.'
              : 'Based on a sample of public commenters, not all viewers.'}</p>
          </div>
          <div className="app-card app-card-pad app-aud-card">
            <div className="app-aud-groups-head">
              <div><h3>Creator groups</h3><p>Creators whose fans overlap the most, grouped together.</p></div>
              {groups.length > 0 && (
                <button type="button" className="app-chip" onClick={() => void nameGroups()} disabled={!aiEnabled || labeling}>{labeling ? 'Naming…' : 'Name groups with AI'}</button>
              )}
            </div>
            {groups.length === 0 ? (
              <div className="app-empty">No clear groups: fans barely overlap across these creators.</div>
            ) : (
              <div className="app-aud-groups">
                {groups.map((g) => (
                  <div className="app-aud-group" key={g.id}>
                    <strong>{g.labelSource === 'model' ? g.label : g.label.replace(/ cluster$/, '')}</strong>
                    {g.summary && <p>{g.summary}</p>}
                    <div className="app-aud-members">
                      {g.members.map((id) => (
                        <button type="button" key={id} className={`app-chip small ${id === focus ? 'active' : ''} ${inPlan.has(id) ? 'in-plan' : ''}`} onClick={() => setFocus(id)} title={inPlan.has(id) ? 'Recommended' : undefined}>{nodes.get(id)?.name ?? id}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {labelStatus && <p className="app-footnote" role="status">{labelStatus}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
