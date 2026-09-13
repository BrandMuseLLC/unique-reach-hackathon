import React, { useEffect, useMemo, useState } from 'react';

type Node = { id: string; name: string; sampledCommenters: number };
type Pair = { a: string; b: string; sharedCommenters: number; jaccard: number };
type Graph = { datasetVersion: string; nodes: Node[]; pairs: Pair[]; metric: string };
const number = (value: number) => value.toLocaleString('en-US');
const percent = (value: number) => `${(value * 100).toFixed(2)}%`;

export function ExploreOverlap() {
  const [open, setOpen] = useState(false);
  return <section className="explore-panel" aria-labelledby="explore-heading">
    <div className="panel-heading">
      <div><h2 id="explore-heading">Explore overlap</h2><p>Explore observed connections between creators in the historical comment sample.</p></div>
      <button aria-expanded={open} aria-controls="explore-content" onClick={() => setOpen(!open)}>{open ? 'Close explorer' : 'Open explorer'}</button>
    </div>
    {open && <div id="explore-content"><OverlapNetwork /></div>}
  </section>;
}

function OverlapNetwork() {
  const [data, setData] = useState<Graph | null>(null);
  const [error, setError] = useState('');
  const [focus, setFocus] = useState('');
  const [partner, setPartner] = useState('');
  const [minimum, setMinimum] = useState(0);
  const [sort, setSort] = useState('jaccard');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/overlap', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Overlap data could not be loaded. Check your session and try reopening the explorer.');
      const graph: Graph = await response.json();
      setData(graph); setFocus(graph.nodes[0]?.id ?? '');
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);
  const nodes = useMemo(() => new Map(data?.nodes.map(n => [n.id, n]) ?? []), [data]);
  const pairs = useMemo(() => (data?.pairs ?? []).filter(p => p.a === focus || p.b === focus)
    .map(p => ({ ...p, other: (p.a === focus ? p.b : p.a) }))
    .sort((a, b) => sort === 'count' ? b.sharedCommenters - a.sharedCommenters || b.jaccard - a.jaccard : b.jaccard - a.jaccard || b.sharedCommenters - a.sharedCommenters), [data, focus, sort]);
  const filtered = pairs.filter(p => p.sharedCommenters >= minimum);
  const visible = filtered.filter(p => p.sharedCommenters > 0).slice(0, 8);
  const active = pairs.find(p => p.other === partner) ?? visible[0] ?? pairs[0];
  const center = nodes.get(focus);
  const other = nodes.get(active?.other ?? '');
  const chooseFocus = (id: string) => { setFocus(id); setPartner(''); };
  if (error) return <p role="alert">{error}</p>;
  if (!data || !center) return <p role="status">Loading observed pair summaries…</p>;
  return <>
    <p className="explore-note">Shared commenters are commenter IDs appearing in both sampled channels, not all viewers. Node positions are arranged for readability; proximity is not validated audience similarity. No inferred communities or demographics are shown.</p>
    <div className="explore-controls">
      <label>Focus creator<select value={focus} onChange={e => chooseFocus(e.target.value)}>{data.nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
      <label>Minimum shared commenters<input type="number" min="0" step="1" value={minimum} onChange={e => setMinimum(Math.max(0, Math.floor(Number(e.target.value) || 0)))} /></label>
      <label>Rank connections by<select value={sort} onChange={e => setSort(e.target.value)}><option value="jaccard">Jaccard percentage</option><option value="count">Shared-commenter count</option></select></label>
    </div>
    <p className="explore-note">{data.nodes.length} sampled channels. Network shows up to eight strongest nonzero connections for the selected creator; the table includes all {filtered.length} matching pairs. Line width represents Jaccard percentage; nodes have equal size. {data.metric}</p>
    <div className="explore-layout">
      <div className="explore-canvas" role="region" aria-label="Creator connection network" tabIndex={0}>
        <svg viewBox="0 0 920 580" aria-label={`Observed connections for ${center.name}`} role="group">
          {visible.map((p, i) => {
            const angle = -Math.PI / 2 + i * Math.PI * 2 / visible.length;
            const x = 460 + Math.cos(angle) * 310, y = 290 + Math.sin(angle) * 205;
            return <line key={p.other} x1="460" y1="290" x2={x} y2={y} stroke={p.other === active?.other ? '#6b44c6' : '#c7bddc'} strokeWidth={1 + 9 * p.jaccard} />;
          })}
          <circle cx="460" cy="290" r="24" fill="#252033" />
          <text x="460" y="335" textAnchor="middle" className="explore-node-label">{center.name}</text>
          {visible.map((p, i) => {
            const angle = -Math.PI / 2 + i * Math.PI * 2 / visible.length;
            const x = 460 + Math.cos(angle) * 310, y = 290 + Math.sin(angle) * 205;
            const selected = p.other === active?.other;
            return <g key={p.other} className="explore-node" role="button" tabIndex={0} aria-pressed={selected}
              aria-label={`Inspect ${center.name} and ${nodes.get(p.other)?.name}: ${number(p.sharedCommenters)} shared commenters, ${percent(p.jaccard)} Jaccard`}
              onClick={() => setPartner(p.other)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPartner(p.other); } }}>
              <circle cx={x} cy={y} r="24" fill={selected ? '#6b44c6' : '#eee8f8'} stroke="#6b44c6" strokeWidth={selected ? 3 : 1} />
              <text x={x} y={y + 43} textAnchor="middle" className="explore-node-label">{nodes.get(p.other)?.name}</text>
              <text x={x} y={y + 62} textAnchor="middle" className="explore-edge-label">{number(p.sharedCommenters)} shared · {percent(p.jaccard)}</text>
            </g>;
          })}
          {!visible.length && <text x="460" y="385" textAnchor="middle">No nonzero connections match this filter.</text>}
        </svg>
      </div>
      <aside className="explore-inspector" aria-live="polite" aria-atomic="true">
        <h3>Selected pair</h3>
        {active && other ? <><p><strong>{center.name}</strong><br />↔ {other.name}</p>
          <dl><dt>Shared sampled commenters</dt><dd>{number(active.sharedCommenters)}</dd><dt>Commenter Jaccard</dt><dd>{percent(active.jaccard)}</dd><dt>Sampled commenters in either channel</dt><dd>{number(center.sampledCommenters + other.sampledCommenters - active.sharedCommenters)}</dd></dl>
          <p>{center.name}: {number(center.sampledCommenters)} sampled commenters.<br />{other.name}: {number(other.sampledCommenters)} sampled commenters.</p>
          {active.sharedCommenters < minimum && <p>This selected pair is below the current filter.</p>}
          <button aria-label={`Explore ${other.name}`} onClick={() => chooseFocus(other.id)}>Make focus creator</button>
          <p className="explore-note">Zero observed overlap does not prove separate viewer audiences. Counts are historical sample evidence, not campaign reach.</p></> : <p>No pair available.</p>}
      </aside>
    </div>
    <div className="explore-table-wrap"><table className="explore-table"><caption>Connections for {center.name}. Select a pair to inspect it; filters never change your campaign.</caption>
      <thead><tr><th scope="col">Creator pair</th><th scope="col">Shared commenters</th><th scope="col">Jaccard</th></tr></thead>
      <tbody>{filtered.map(p => <tr key={p.other} className={p.other === active?.other ? 'explore-selected' : ''}><td><button aria-pressed={p.other === active?.other} onClick={() => setPartner(p.other)}>Inspect {nodes.get(p.other)?.name}</button></td><td>{number(p.sharedCommenters)}</td><td>{percent(p.jaccard)}</td></tr>)}
      {!filtered.length && <tr><td colSpan={3}>No connections match. Lower the minimum shared-commenter count.</td></tr>}</tbody>
    </table></div>
  </>;
}
