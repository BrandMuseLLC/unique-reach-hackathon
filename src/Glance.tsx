import React, { useEffect, useRef, useState } from 'react';

type RosterDiag = { ids: string[]; spend: number; coverage: number; standalone: number; shared: number; sharedRate: number };
type Step = { creatorId: string; creatorName: string; marginalProxyReach: number; cost: number };
type LeftOut = { creatorId: string; creatorName: string; alreadyCoveredShare: number; overlapsWith: { creatorName: string }[] };

export type GlanceInput = {
  budget: number;
  remainingBudget: number;
  steps: Step[];
  whyNot?: LeftOut[];
  rosterDiagnostics?: { rosters: { current: RosterDiag; recommended: RosterDiag; viewsBaseline: RosterDiag } };
};

const compact = (value: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
const whole = (value: number) => Math.round(value).toLocaleString('en-US');
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const money = (value: number) => value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

type Tip = { x: number; y: number; text: string } | null;

function useCountUp(target: number, duration = 900) {
  const [value, setValue] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setValue(target); return; }
    const start = performance.now(), origin = from.current;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(origin + (target - origin) * eased);
      if (t < 1) frame = requestAnimationFrame(tick); else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

function useTip() {
  const [tip, setTip] = useState<Tip>(null);
  const show = (event: React.MouseEvent, text: string) => {
    const card = (event.currentTarget as SVGElement).closest('.chart-card') as HTMLElement | null;
    if (!card) return;
    const box = card.getBoundingClientRect();
    setTip({ x: event.clientX - box.left + 12, y: event.clientY - box.top - 30, text });
  };
  const node = tip ? <div className="chart-tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div> : null;
  return { show, hide: () => setTip(null), node };
}

function RosterReach({ rosters }: { rosters: { current: RosterDiag; recommended: RosterDiag; viewsBaseline: RosterDiag } }) {
  const { show, hide, node } = useTip();
  const rows = [
    { key: 'current', label: 'Your roster', color: 'var(--bm-chart-current)', d: rosters.current },
    { key: 'recommended', label: 'Recommended', color: 'var(--bm-chart-recommended)', d: rosters.recommended },
    { key: 'viewsBaseline', label: 'Top by views', color: 'var(--bm-chart-baseline)', d: rosters.viewsBaseline },
  ];
  const max = Math.max(...rows.map((r) => r.d.standalone), 1);
  const left = 96, width = 420, rowH = 44;
  return (
    <div className="chart-card rise">
      <h3>How much each roster overlaps</h3>
      <p>Solid bar: commenters reached once. Striped end: the same commenters showing up on another creator in the roster.</p>
      <div className="legend"><span><i style={{ background: '#a3a3b8' }} />Reached once</span><span><i style={{ background: 'repeating-linear-gradient(45deg,#a3a3b8 0 2px,transparent 2px 5px)' }} />Overlap</span></div>
      <svg viewBox={`0 0 ${left + width + 70} ${rows.length * rowH + 8}`} role="img" aria-label="Sampled commenters counted once and repeated, by roster">
        <defs>
          {rows.map((r) => (
            <pattern key={r.key} id={`hatch-${r.key}`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill="transparent" />
              <line x1="0" y1="0" x2="0" y2="5" stroke={r.color} strokeWidth="2" />
            </pattern>
          ))}
        </defs>
        {rows.map((r, i) => {
          const y = i * rowH + 10;
          const once = (r.d.coverage / max) * width;
          const rep = (r.d.shared / max) * width;
          const tip = `${r.label}: ${whole(r.d.coverage)} reached once, ${whole(r.d.shared)} overlapping (${pct(r.d.sharedRate)})`;
          return (
            <g key={r.key} onMouseMove={(e) => show(e, tip)} onMouseLeave={hide}>
              <rect className="hit" x={0} y={y - 6} width={left + width + 70} height={rowH - 4} />
              <text x={left - 10} y={y + 15} textAnchor="end">{r.label}</text>
              <g className="grow-x" style={{ animationDelay: `${i * 90}ms` }}>
                <rect className="mark" x={left} y={y} width={Math.max(once - 2, 1)} height={22} rx={4} fill={r.color} />
                {rep > 1 && <rect x={left + once} y={y} width={rep} height={22} rx={4} fill={`url(#hatch-${r.key})`} stroke={r.color} strokeWidth="1" />}
              </g>
              <text className="value fade-in" style={{ animationDelay: `${300 + i * 90}ms` }} x={left + once + rep + 8} y={y + 15}>{pct(r.d.sharedRate)}</text>
            </g>
          );
        })}
      </svg>
      {node}
      <details><summary>Table</summary>
        <table><thead><tr><th>Roster</th><th>Reached once</th><th>Overlap</th><th>Overlap %</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.key}><td>{r.label}</td><td>{whole(r.d.coverage)}</td><td>{whole(r.d.shared)}</td><td>{pct(r.d.sharedRate)}</td></tr>)}</tbody></table>
      </details>
    </div>
  );
}

function MarginalPicks({ steps }: { steps: Step[] }) {
  const { show, hide, node } = useTip();
  if (!steps.length) return null;
  const max = Math.max(...steps.map((s) => s.marginalProxyReach), 1);
  const h = 150, gap = 8, top = 14, width = 380;
  const barW = Math.min(40, (width - 20) / steps.length - gap);
  const offset = (width - steps.length * (barW + gap)) / 2;
  return (
    <div className="chart-card rise">
      <h3>What each pick adds</h3>
      <p>Reach score each creator adds, in the order the plan picked them. Bars shrink as audiences start to overlap.</p>
      <svg viewBox={`0 0 ${width + 4} ${h + top + 34}`} role="img" aria-label="Marginal score added by each selected creator in pick order">
        {[0.5, 1].map((t) => <line key={t} x1={0} x2={width} y1={top + h - h * t} y2={top + h - h * t} stroke="var(--bm-grid)" />)}
        <line x1={0} x2={width} y1={top + h} y2={top + h} stroke="var(--bm-border)" />
        {steps.map((s, i) => {
          const bh = Math.max((s.marginalProxyReach / max) * h, 2);
          const x = offset + i * (barW + gap) + gap / 2;
          return (
            <g key={`${s.creatorId}-${i}`} onMouseMove={(e) => show(e, `#${i + 1} ${s.creatorName}: adds ${compact(s.marginalProxyReach)} for ${money(s.cost)}`)} onMouseLeave={hide}>
              <rect className="hit" x={x - gap / 2} y={top} width={barW + gap} height={h} />
              <rect className="mark grow-y" style={{ animationDelay: `${i * 70}ms` }} x={x} y={top + h - bh} width={barW} height={bh} rx={4} fill="var(--bm-chart-recommended)" />
              <text x={x + barW / 2} y={top + h + 14} textAnchor="middle">{i + 1}</text>
            </g>
          );
        })}
        <text x={0} y={10}>{compact(max)}</text>
        <text x={width / 2} y={top + h + 30} textAnchor="middle">pick order</text>
      </svg>
      {node}
      <details><summary>Table</summary>
        <table><thead><tr><th>#</th><th>Creator</th><th>Adds</th><th>Quote</th></tr></thead>
          <tbody>{steps.map((s, i) => <tr key={`${s.creatorId}-${i}`}><td>{i + 1}</td><td>{s.creatorName}</td><td>{compact(s.marginalProxyReach)}</td><td>{money(s.cost)}</td></tr>)}</tbody></table>
      </details>
    </div>
  );
}

function AlreadyCovered({ rows }: { rows: LeftOut[] }) {
  const { show, hide, node } = useTip();
  const top = rows.slice(0, 7);
  if (!top.length) return null;
  const left = 120, width = 250, rowH = 26;
  return (
    <div className="chart-card rise">
      <h3>Why they were left out</h3>
      <p>How much of each skipped creator&rsquo;s audience the plan already reaches.</p>
      <svg viewBox={`0 0 ${left + width + 50} ${top.length * rowH + 4}`} role="img" aria-label="Already-covered share for creators left out of the plan">
        {top.map((r, i) => {
          const y = i * rowH + 4;
          const w = Math.max(r.alreadyCoveredShare * width, 2);
          const via = r.overlapsWith.slice(0, 2).map((o) => o.creatorName).join(', ');
          return (
            <g key={r.creatorId} onMouseMove={(e) => show(e, `${r.creatorName}: ${pct(r.alreadyCoveredShare)} covered${via ? ` via ${via}` : ''}`)} onMouseLeave={hide}>
              <rect className="hit" x={0} y={y - 3} width={left + width + 50} height={rowH} />
              <text x={left - 8} y={y + 12} textAnchor="end">{r.creatorName.length > 18 ? `${r.creatorName.slice(0, 17)}…` : r.creatorName}</text>
              <rect x={left} y={y} width={width} height={16} rx={4} fill="var(--bm-grid)" />
              <rect className="mark grow-x" style={{ animationDelay: `${i * 60}ms` }} x={left} y={y} width={w} height={16} rx={4} fill="var(--bm-chart-recommended)" />
              <text className="value fade-in" style={{ animationDelay: `${250 + i * 60}ms` }} x={left + width + 8} y={y + 12}>{Math.round(r.alreadyCoveredShare * 100)}%</text>
            </g>
          );
        })}
      </svg>
      {node}
    </div>
  );
}

export function Glance({ result, creatorCount }: { result: GlanceInput; creatorCount: number }) {
  const diag = result.rosterDiagnostics?.rosters;
  if (!diag) return null;
  const rec = diag.recommended, cur = diag.current;
  const spend = result.budget - result.remainingBudget;
  const reached = useCountUp(rec.coverage);
  const overlap = useCountUp(rec.sharedRate * 1000) / 1000;
  const spent = useCountUp(spend);
  const count = useCountUp(rec.ids.length, 600);
  return (
    <section className="glance" aria-label="Plan at a glance">
      <div className="glance-head">
        <h2>Plan at a glance</h2>
        <p>Recommended roster compared with yours</p>
      </div>
      <div className="kpis">
        <div className="kpi rise"><span>Commenters reached</span><strong>{compact(reached)}</strong><small>each account counted once</small></div>
        <div className="kpi rise"><span>Audience overlap</span><strong>{pct(overlap)}</strong><small>your roster: {pct(cur.sharedRate)} · lower is better</small></div>
        <div className="kpi rise"><span>Spend</span><strong>{money(spent)}</strong><small>of {money(result.budget)} budget</small></div>
        <div className="kpi rise"><span>Creators</span><strong>{Math.round(count)}</strong><small>chosen from {creatorCount} channels</small></div>
      </div>
      <div className="charts">
        <RosterReach rosters={diag} />
        <MarginalPicks steps={result.steps} />
        <AlreadyCovered rows={result.whyNot ?? []} />
      </div>
    </section>
  );
}
