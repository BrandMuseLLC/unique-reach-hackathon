import React, { useEffect, useState } from 'react';

export type WhyNot = {
  creatorId: string;
  creatorName: string;
  reason: string;
  cost: number;
  marginalProxyReach: number;
  alreadyCoveredShare: number;
  overlapsWith: { creatorId: string; creatorName: string; sharedCommenters: number }[];
};

const money = (value: number) => value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const count = (value: number) => value.toLocaleString('en-US', { maximumFractionDigits: 0 });

export function WhyNotPanel({ rows, stale }: { rows: WhyNot[]; stale: boolean }) {
  const [selected, setSelected] = useState(rows[0]?.creatorId ?? '');
  useEffect(() => {
    if (!rows.some((row) => row.creatorId === selected)) setSelected(rows[0]?.creatorId ?? '');
  }, [rows, selected]);
  if (rows.length === 0) return null;
  const row = rows.find((item) => item.creatorId === selected) ?? rows[0];
  const covered = Math.round(row.alreadyCoveredShare * 100);

  return (
    <section className="panel steps-panel" aria-label="Why not this creator">
      <div className="panel-heading compact">
        <h2>Why not…?</h2>
        <p>Pick an eligible creator the plan left out to see what the roster already covers.{stale ? ' Inputs changed since this plan ran.' : ''}</p>
      </div>
      <label className="why-not-select">
        <span className="sr-only">Creator left out of the plan</span>
        <select value={row.creatorId} onChange={(event) => setSelected(event.target.value)} aria-label="Creator left out of the plan">
          {rows.map((item) => (
            <option key={item.creatorId} value={item.creatorId}>
              {item.creatorName} · {Math.round(item.alreadyCoveredShare * 100)}% already covered
            </option>
          ))}
        </select>
      </label>
      <div className="steps">
        <div className="step">
          <span>{covered}%</span>
          <p>
            <strong>{row.creatorName}</strong>: {covered}% of its modeled sampled audience is already represented by the recommended roster
            {row.overlapsWith.length > 0 && <>, mostly through {row.overlapsWith.map((o) => `${o.creatorName} (${count(o.sharedCommenters)} shared commenters)`).join(', ')}</>}.
            {' '}Adding it at {money(row.cost)} would add {count(row.marginalProxyReach)} to the score. {row.reason}
          </p>
        </div>
      </div>
    </section>
  );
}
