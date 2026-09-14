import React, { useEffect, useMemo, useState } from 'react';

type Node = { id: string; name: string; sampledCommenters: number };
type Pair = { a: string; b: string; sharedCommenters: number; jaccard: number; source?: 'measured' | 'estimated' | 'assumed' };
type Cluster = { id: string; members: string[]; label: string; labelSource: 'rule' | 'model'; summary?: string;
  topics: Record<string, number>; anchorCreators: string[]; medianInternalJaccard: number | null };
type Graph = { datasetVersion: string; nodes: Node[]; pairs: Pair[]; metric: string; clusters?: Cluster[]; unit?: string };

const whole = (value: number) => Math.round(value).toLocaleString('en-US');

export function ExploreOverlap({ aiEnabled = false }: { aiEnabled?: boolean }) {
  const [data, setData] = useState<Graph | null>(null);
  const [error, setError] = useState('');
  const [focus, setFocus] = useState('');
  const [labeling, setLabeling] = useState(false);
  const [labelStatus, setLabelStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/overlap', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Audience data could not be loaded.');
        const graph: Graph = await response.json();
        setData(graph);
        const biggest = [...graph.nodes].sort((a, b) => b.sampledCommenters - a.sampledCommenters)[0];
        setFocus(biggest?.id ?? '');
      })
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);

  const nodes = useMemo(() => new Map(data?.nodes.map((n) => [n.id, n]) ?? []), [data]);
  const center = nodes.get(focus);
  // Share of the focus creator's commenters who also comment on the other creator: easier to read than Jaccard.
  const neighbours = useMemo(() => {
    if (!data || !center) return [];
    return data.pairs
      .filter((p) => (p.a === focus || p.b === focus) && p.sharedCommenters > 0)
      .map((p) => {
        const other = nodes.get(p.a === focus ? p.b : p.a)!;
        return { other, shared: p.sharedCommenters, source: p.source, share: center.sampledCommenters ? p.sharedCommenters / center.sampledCommenters : 0 };
      })
      .sort((x, y) => y.share - x.share)
      .slice(0, 8);
  }, [data, center, focus, nodes]);
  const maxShare = Math.max(...neighbours.map((n) => n.share), 0.0001);
  const groups = (data?.clusters ?? []).filter((c) => c.members.length > 1);

  async function nameGroups() {
    setLabeling(true);
    setLabelStatus('');
    try {
      const response = await fetch('/api/overlap/labels', { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? 'Naming failed; the simple labels are unchanged.');
      setData((current) => (current ? { ...current, clusters: payload.clusters } : current));
      setLabelStatus('Named from channel names and video titles, not from viewer data.');
    } catch (e) {
      setLabelStatus(e instanceof Error ? e.message : 'Naming failed.');
    } finally {
      setLabeling(false);
    }
  }

  return (
    <section className="aud panel-lite" aria-labelledby="aud-heading">
      <div className="section-head">
        <div>
          <h2 id="aud-heading">Audience map</h2>
          <p>Which creators share the same fans? We count people who commented on both creators&rsquo; recent videos.</p>
        </div>
      </div>

      {error && <p className="alert">{error}</p>}
      {!data && !error && <p className="placeholder small">Loading audience data…</p>}

      {data && center && (
        <div className="aud-grid">
          <div className="aud-card">
            <label className="aud-pick">
              <span>Pick a creator</span>
              <select value={focus} onChange={(e) => setFocus(e.target.value)}>
                {[...data.nodes].sort((a, b) => a.name.localeCompare(b.name)).map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
            </label>
            <p className="aud-lead">
              {data.unit === 'estimated_followers'
                ? <>Of about <strong>{whole(center.sampledCommenters)}</strong> followers of <strong>{center.name}</strong>, this share also follow:</>
                : <>Of <strong>{whole(center.sampledCommenters)}</strong> people we saw commenting on <strong>{center.name}</strong>, this share also comment on:</>}
            </p>
            {neighbours.length === 0 ? (
              <p className="placeholder small">No shared commenters with the other creators in this search. Their audiences look separate in our sample.</p>
            ) : (
              <ul className="aud-bars" key={focus}>
                {neighbours.map((n, i) => (
                  <li key={n.other.id}>
                    <button className="aud-name" onClick={() => setFocus(n.other.id)} title={`Show ${n.other.name}`}>{n.other.name}</button>
                    <div className="aud-track"><i className="grow-x" style={{ width: `${Math.max((n.share / maxShare) * 100, 3)}%`, animationDelay: `${i * 60}ms` }} /></div>
                    <span className="aud-value"><strong>{(n.share * 100).toFixed(n.share < 0.1 ? 1 : 0)}%</strong> <small>{n.source && n.source !== 'measured' ? `${n.source}` : `${whole(n.shared)} people`}</small></span>
                  </li>
                ))}
              </ul>
            )}
            <p className="aud-foot">Higher % means more of the same fans, so pairing those two creators reaches fewer new people. {data.unit === 'estimated_followers'
              ? 'YouTube pairs are measured from shared commenters; pairs with Instagram or TikTok are estimated from audience profiles (see How estimates work).'
              : 'Based on a sample of public commenters, not all viewers.'}</p>
          </div>

          <div className="aud-card">
            <div className="aud-groups-head">
              <div><h3>Creator groups</h3><p>Creators whose fans overlap the most, grouped together.</p></div>
              {groups.length > 0 && (
                <button className="btn-secondary" onClick={() => void nameGroups()} disabled={!aiEnabled || labeling}>
                  {labeling ? 'Naming…' : 'Name groups with AI'}
                </button>
              )}
            </div>
            {groups.length === 0 ? (
              <p className="placeholder small">No clear groups: fans barely overlap across these creators.</p>
            ) : (
              <div className="aud-groups">
                {groups.map((g) => (
                  <div className="aud-group" key={g.id}>
                    <strong>{g.labelSource === 'model' ? g.label : g.label.replace(/ cluster$/, '')}</strong>
                    {g.summary && <p>{g.summary}</p>}
                    <div className="aud-members">
                      {g.members.map((id) => (
                        <button key={id} className={id === focus ? 'on' : ''} onClick={() => setFocus(id)}>{nodes.get(id)?.name ?? id}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {labelStatus && <p className="aud-foot" role="status">{labelStatus}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
