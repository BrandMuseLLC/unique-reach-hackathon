import React, { useEffect, useState } from 'react';
import { EyebrowRow, Insight, Tag } from './parts';
import { money, whole, type WhyNot } from './types';

export type { WhyNot } from './types';

type Tone = 'budget' | 'excluded' | 'cap' | 'little';
const REASONS: [RegExp, string, Tone][] = [
  [/budget/i, 'Over budget', 'budget'],
  [/excluded/i, 'Excluded', 'excluded'],
  [/cap/i, 'Platform off', 'cap'],
  [/.*/, 'Adds little', 'little'],
];

export function reasonTag(reason = '', crossPlatform = true) {
  const [, label, tone] = REASONS.find(([pattern]) => pattern.test(reason))!;
  return { label: tone === 'cap' && !crossPlatform ? 'Topic cap' : label, tone };
}

export function WhyNotPanel({ rows, stale, crossPlatform = true, onExplain }: {
  rows: WhyNot[];
  stale: boolean;
  crossPlatform?: boolean;
  onExplain?: () => void;
  // Accepted for the legacy single-page layout; the new screen asks Muse from the panel instead.
  aiEnabled?: boolean;
  onAsk?: (question: string) => Promise<string>;
}) {
  const [selected, setSelected] = useState(rows[0]?.creatorId ?? '');
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    if (!rows.some((row) => row.creatorId === selected)) setSelected(rows[0]?.creatorId ?? '');
  }, [rows, selected]);
  if (rows.length === 0) return null;

  const sorted = [...rows].sort((a, b) => b.alreadyCoveredShare - a.alreadyCoveredShare || a.creatorName.localeCompare(b.creatorName));
  const overlapping = sorted.filter((r) => r.alreadyCoveredShare >= 0.005);
  const visible = showAll ? sorted : sorted.slice(0, 6);
  const scale = Math.max(...sorted.map((r) => r.alreadyCoveredShare), 0.01);
  const counts = sorted.reduce<Record<string, { n: number; tone: Tone }>>((acc, r) => {
    const { label, tone } = reasonTag(r.reason, crossPlatform);
    acc[label] = { n: (acc[label]?.n ?? 0) + 1, tone };
    return acc;
  }, {});
  const row = sorted.find((item) => item.creatorId === selected) ?? sorted[0];
  const covered = Math.round(row.alreadyCoveredShare * 100);

  return (
    <section id="whynot" className="app-section" aria-label="Why creators were left out">
      <EyebrowRow label="Why not…?" link="How estimates work" onLink={onExplain} />
      <Insight>
        {overlapping.length
          ? `${overlapping.length} of ${sorted.length} skipped ${sorted.length === 1 ? 'creator shares' : 'creators share'} part of their audience with the plan. Bars show how much is already reached.`
          : sorted.length === 1
            ? 'This creator does not share audience with the plan, so overlap was not the reason. The tag shows why.'
            : `None of the ${sorted.length} skipped creators share audience with the plan, so overlap was not the reason. The tags show why.`}
        {stale ? ' Updating to your latest changes.' : ''}
      </Insight>
      <div className="app-card app-card-pad">
        <div className="app-tag-row">
          {Object.entries(counts).map(([label, { n, tone }]) => <Tag key={label} tone={tone}>{label} · {n}</Tag>)}
        </div>
        <ul className="app-leftout">
          {visible.map((r) => {
            const share = r.alreadyCoveredShare;
            const tag = reasonTag(r.reason, crossPlatform);
            const via = r.overlapsWith.slice(0, 2).map((o) => o.creatorName).join(' and ');
            return (
              <li key={r.creatorId}>
                <div className="app-leftout-name">
                  <strong title={r.creatorName}>{r.creatorName}</strong>
                  <small>{share >= 0.005 && via ? `Overlaps with ${via}` : 'No shared audience with the plan'}</small>
                </div>
                <div className="app-bar app-bar-8" aria-hidden="true"><i style={{ width: share >= 0.005 ? `${Math.max((share / scale) * 100, 4)}%` : '0%' }} /></div>
                <span className="app-leftout-value">{share < 0.005 ? '—' : `${Math.round(share * 100)}%`}</span>
                <Tag tone={tag.tone}>{tag.label}</Tag>
              </li>
            );
          })}
        </ul>
        {sorted.length > 6 && (
          <button type="button" className="app-chip app-self-start" onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show fewer' : `Show all ${sorted.length}`}</button>
        )}
      </div>
      <div className="app-card app-card-pad">
        <label className="app-field-label">
          <span>Pick any left-out creator for the full reason</span>
          <select className="app-select" value={row.creatorId} onChange={(event) => setSelected(event.target.value)} aria-label="Left-out creator">
            {sorted.map((item) => (
              <option key={item.creatorId} value={item.creatorId}>{item.creatorName} · {Math.round(item.alreadyCoveredShare * 100)}% already covered</option>
            ))}
          </select>
        </label>
        <div className="app-reason">
          <span className="app-reason-disc">{covered}%</span>
          <p>
            <b>{row.creatorName}</b>: {covered}% of its modeled audience is already represented by the recommended roster
            {row.overlapsWith.length > 0 && <>, mostly through {row.overlapsWith.map((o) => `${o.creatorName} (${whole(o.sharedCommenters)} shared${o.source && o.source !== 'measured' ? `, ${o.source}` : ''})`).join(', ')}</>}.
            {' '}Adding it at {money(row.cost)} would add {whole(row.marginalProxyReach)} to the score. {row.reason}
          </p>
        </div>
      </div>
    </section>
  );
}
