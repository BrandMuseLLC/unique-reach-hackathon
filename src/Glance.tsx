import React, { useEffect, useRef, useState } from 'react';

type RosterDiag = { ids: string[]; spend: number; coverage: number; standalone: number; shared: number; sharedRate: number };
type Step = { creatorId: string; creatorName: string; marginalProxyReach: number; cost: number };
type LeftOut = { creatorId: string; creatorName: string; alreadyCoveredShare: number; overlapsWith: { creatorName: string; sharedCommenters?: number }[]; reason?: string; cost?: number };

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
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || document.visibilityState === 'hidden') { setValue(target); from.current = target; return; }
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
      <p>New commenters each creator adds, in the order the plan picked them. Bars shrink as audiences start to overlap.</p>
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

const REASONS: [RegExp, string, string][] = [
  [/budget/i, 'Over budget', 'budget'],
  [/excluded/i, 'Excluded', 'excluded'],
  [/cap/i, 'Topic cap', 'cap'],
  [/.*/, 'Adds little', 'little'],
];

function reasonTag(reason = '') {
  const [, label, kind] = REASONS.find(([pattern]) => pattern.test(reason))!;
  return { label, kind };
}

export function AlreadyCovered({ rows }: { rows: LeftOut[] }) {
  const [showAll, setShowAll] = useState(false);
  if (!rows.length) return null;
  const sorted = [...rows].sort((a, b) => b.alreadyCoveredShare - a.alreadyCoveredShare || a.creatorName.localeCompare(b.creatorName));
  const overlapping = sorted.filter((r) => r.alreadyCoveredShare >= 0.005);
  const visible = showAll ? sorted : sorted.slice(0, 6);
  const scale = Math.max(...sorted.map((r) => r.alreadyCoveredShare), 0.01);
  const counts = sorted.reduce<Record<string, number>>((acc, r) => { const { label } = reasonTag(r.reason); acc[label] = (acc[label] ?? 0) + 1; return acc; }, {});

  return (
    <div className="left-out rise">
      <div className="left-out-head">
        <div>
          <h3>Why creators were left out</h3>
          <p>{overlapping.length
            ? `${overlapping.length} of ${sorted.length} skipped ${sorted.length === 1 ? 'creator shares' : 'creators share'} part of their audience with the plan. Bars show how much is already reached.`
            : sorted.length === 1
              ? 'This creator doesn\u2019t share audience with the plan, so overlap wasn\u2019t the reason. The tag shows why.'
              : `None of the ${sorted.length} skipped creators share audience with the plan, so overlap wasn\u2019t the reason. The tags show why.`}</p>
        </div>
        <div className="left-out-summary">
          {Object.entries(counts).map(([label, n]) => <span key={label} className={`tag tag-${reasonTag(label === 'Adds little' ? '' : label).kind}`}>{label} · {n}</span>)}
        </div>
      </div>
      <ul className="left-out-list">
        {visible.map((r, i) => {
          const share = r.alreadyCoveredShare;
          const tag = reasonTag(r.reason);
          const via = r.overlapsWith.slice(0, 2).map((o) => o.creatorName).join(' and ');
          return (
            <li key={r.creatorId} style={{ animationDelay: `${i * 40}ms` }}>
              <div className="lo-name">
                <strong title={r.creatorName}>{r.creatorName}</strong>
                <small>{share >= 0.005 && via ? `Overlaps with ${via}` : 'No shared commenters with the plan'}</small>
              </div>
              <div className="lo-bar" aria-hidden="true">
                <i className="grow-x" style={{ width: share >= 0.005 ? `${Math.max((share / scale) * 100, 4)}%` : '0%', animationDelay: `${i * 40}ms` }} />
              </div>
              <span className={`lo-value ${share < 0.005 ? 'zero' : ''}`}>{share < 0.005 ? '—' : `${Math.round(share * 100)}%`}</span>
              <span className={`tag tag-${tag.kind}`}>{tag.label}</span>
            </li>
          );
        })}
      </ul>
      {sorted.length > 6 && (
        <button className="btn-ghost left-out-more" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show fewer' : `Show all ${sorted.length}`}</button>
      )}
    </div>
  );
}

const EMPTY_DIAG: RosterDiag = { ids: [], spend: 0, coverage: 0, standalone: 0, shared: 0, sharedRate: 0 };

export function Glance({ result, creatorCount }: { result: GlanceInput; creatorCount: number }) {
  const diag = result.rosterDiagnostics?.rosters;
  const rec = diag?.recommended ?? EMPTY_DIAG, cur = diag?.current ?? EMPTY_DIAG;
  const spend = result.budget - result.remainingBudget;
  const reached = useCountUp(rec.coverage);
  const overlap = useCountUp(rec.sharedRate * 1000) / 1000;
  const spent = useCountUp(spend);
  const count = useCountUp(rec.ids.length, 600);
  const mine = { reached: useCountUp(cur.coverage), overlap: useCountUp(cur.sharedRate * 1000) / 1000, spent: useCountUp(cur.spend), count: useCountUp(cur.ids.length, 600) };
  if (!diag) return null;
  const scale = Math.max(rec.sharedRate, cur.sharedRate, 0.001) * 1.15;
  const points = (value: number) => (value * 100).toFixed(1);
  const sentence = cur.ids.length === 0
    ? `The recommended roster repeats ${points(rec.sharedRate)}% of its commenters. Tick creators below to compare your own roster.`
    : rec.sharedRate < cur.sharedRate - 0.0005
      ? `The recommended roster cuts repeated commenters from ${points(cur.sharedRate)}% to ${points(rec.sharedRate)}%, so less of the budget reaches the same people twice.`
      : rec.sharedRate > cur.sharedRate + 0.0005
        ? `Your roster overlaps less (${points(cur.sharedRate)}% vs ${points(rec.sharedRate)}%)${rec.coverage > cur.coverage ? ', but the recommended roster reaches more commenters overall' : ''}.`
        : `Your roster and the recommended roster overlap about the same (${points(rec.sharedRate)}%).`;
  return (
    <section className="glance" aria-label="Plan at a glance">
      <div className="glance-head">
        <h2>Plan at a glance</h2>
        <p>Tick creators in the list below to build your roster. Both columns update live.</p>
      </div>
      <div className="hero-metric rise">
        <div className="hero-metric-copy">
          <span className="hero-label">Audience overlap <em>lower is better</em></span>
          <div className="hero-values">
            <div className="hv plan"><em>Recommended</em><strong>{pct(overlap)}</strong></div>
            <div className="hv mine"><em>Your roster</em><strong>{pct(mine.overlap)}</strong></div>
          </div>
          <p>{sentence}</p>
        </div>
        <div className="hero-bars" aria-hidden="true">
          <div className="hb"><em>Recommended</em><div className="hb-track"><i className="grow-x plan" style={{ width: `${(rec.sharedRate / scale) * 100}%` }} /></div></div>
          <div className="hb"><em>Your roster</em><div className="hb-track"><i className="grow-x mine" style={{ width: `${(cur.sharedRate / scale) * 100}%`, animationDelay: '120ms' }} /></div></div>
          <small>Share of commenters who also comment on another creator in the same roster</small>
        </div>
      </div>
      <div className="support">
        <Support label="Commenters reached" mine={compact(mine.reached)} plan={compact(reached)} better={rec.coverage > cur.coverage ? 'plan' : rec.coverage < cur.coverage ? 'mine' : 'tie'} />
        <Support label="Spend" mine={money(mine.spent)} plan={money(spent)} note={`of ${money(result.budget)}`} />
        <Support label="Creators" mine={String(Math.round(mine.count))} plan={String(Math.round(count))} note={`from ${creatorCount}`} />
      </div>
      <div className="charts charts-two">
        <RosterReach rosters={diag} />
        <MarginalPicks steps={result.steps} />
      </div>
    </section>
  );
}

function Support({ label, mine, plan, note, better = 'none' }: { label: string; mine: string; plan: string; note?: string; better?: 'mine' | 'plan' | 'tie' | 'none' }) {
  return (
    <div className="support-item rise">
      <span>{label}{note ? <small> {note}</small> : null}</span>
      <div>
        <b className={better === 'plan' ? 'win' : ''}><i className="dot plan" />{plan}</b>
        <b className={better === 'mine' ? 'win' : ''}><i className="dot mine" />{mine}</b>
      </div>
    </div>
  );
}
