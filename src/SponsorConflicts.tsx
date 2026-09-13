import React, { useMemo, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export type SponsorMentions = {
  brands: { brand: string; videos: number; last_seen: string | null; signals: string[] }[];
  disclosed_videos: number;
  basis: string;
};

type ConflictCreator = { id: string; name: string; sponsorMentions?: SponsorMentions | null };

export type SponsorMatch = { id: string; name: string; brands: string[] };

export function parseBrandList(text: string): string[] {
  return [...new Set(text.split(/[,\n]/).map((item) => item.trim().toLowerCase()).filter((item) => item.length >= 2))];
}

export function matchSponsorConflicts(creators: ConflictCreator[], avoid: string[]): SponsorMatch[] {
  if (avoid.length === 0) return [];
  return creators.flatMap((creator) => {
    const brands = (creator.sponsorMentions?.brands ?? [])
      .map((entry) => entry.brand)
      .filter((brand) => avoid.some((term) => brand.toLowerCase().includes(term)));
    return brands.length ? [{ id: creator.id, name: creator.name, brands }] : [];
  });
}

export function SponsorConflicts({ creators, exclude, disabled, onExclude }: {
  creators: ConflictCreator[];
  exclude: string[];
  disabled: boolean;
  onExclude: (ids: string[]) => void;
}) {
  const [avoidText, setAvoidText] = useState('');
  const withEvidence = useMemo(() => creators.filter((creator) => creator.sponsorMentions?.brands.length), [creators]);
  const matches = useMemo(() => matchSponsorConflicts(creators, parseBrandList(avoidText)), [creators, avoidText]);
  const pending = matches.filter((match) => !exclude.includes(match.id));

  if (!creators.some((creator) => creator.sponsorMentions)) return null;

  return (
    <section className="card tool-card" aria-label="Sponsor conflicts">
      <div className="tool-head">
        <h2>Avoid competitor sponsors</h2>
        <span className="pill">{withEvidence.length} of {creators.length} mention a sponsor</span>
      </div>
      <p className="tool-help">Type brands to avoid. We check recent video descriptions and drop creators who mention them.</p>
      <input aria-label="Brands to avoid" maxLength={500} value={avoidText}
        onChange={(event) => setAvoidText(event.target.value)} placeholder="Brand names, separated by commas" />
      <div className="tool-actions">
        <button className="btn-primary" disabled={disabled || pending.length === 0} onClick={() => onExclude(pending.map((match) => match.id))}>
          <AlertTriangle size={15} />
          {pending.length ? `Exclude ${pending.length} ${pending.length === 1 ? 'creator' : 'creators'}` : 'Exclude matches'}
        </button>
      </div>
      <div className="chips" role="status">
        {avoidText.trim() && matches.length === 0 && <span className="tool-reply">No creator mentions those brands.</span>}
        {matches.map((match) => (
          <span className={`chip ${exclude.includes(match.id) ? 'chip-off' : ''}`} key={match.id}>
            {match.name} <b>{match.brands.join(', ')}</b>{exclude.includes(match.id) ? ' · excluded' : ''}
          </span>
        ))}
      </div>
      {withEvidence.length > 0 && !avoidText.trim() && (
        <p className="tool-foot">Found in descriptions: {withEvidence.map((c) => `${c.name} (${c.sponsorMentions!.brands.map((b) => b.brand).join(', ')})`).join(' · ')}. Matches are text patterns, so check before excluding.</p>
      )}
    </section>
  );
}
