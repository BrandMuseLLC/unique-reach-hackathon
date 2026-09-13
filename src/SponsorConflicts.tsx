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
    <section className="panel" aria-label="Sponsor conflicts">
      <div className="panel-heading compact">
        <h2>Sponsor conflicts</h2>
        <p>
          {withEvidence.length} of {creators.length} creators mention a sponsor in recent public video descriptions.
          Pattern matches are evidence for review, not a verdict.
        </p>
      </div>
      <div className="save-card">
        <label>
          <span>Brands or categories to avoid (comma-separated)</span>
          <input aria-label="Brands to avoid" maxLength={500} value={avoidText}
            onChange={(event) => setAvoidText(event.target.value)} placeholder="Competing espresso machine brands" />
        </label>
        <button className="primary" disabled={disabled || pending.length === 0} onClick={() => onExclude(pending.map((match) => match.id))}>
          <AlertTriangle size={15} />
          Exclude {pending.length || ''} matching {pending.length === 1 ? 'creator' : 'creators'}
        </button>
        <p role="status">
          {avoidText.trim() && matches.length === 0 ? 'No creator mentions those brands in the collected descriptions.' : ''}
          {matches.map((match) => `${match.name}: ${match.brands.join(', ')}${exclude.includes(match.id) ? ' (excluded)' : ''}`).join(' · ')}
        </p>
      </div>
    </section>
  );
}
