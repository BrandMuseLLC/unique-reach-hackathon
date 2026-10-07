import React from 'react';
import { Tag } from './parts';
import type { Method } from './types';

export function MethodsScreen({ method }: { method: Method | null }) {
  const w = (key: string, fallback: number) => Math.round((method?.weights?.[key] ?? fallback) * 100);
  return (
    <div className="app-screen">
      <section className="app-section">
        <div className="app-eyebrow-row">
          <span className="eyebrow-wide app-eyebrow">How estimates work</span>
          <span className="app-eyebrow-note">Where every overlap number comes from, and how much to trust it.</span>
        </div>
        <div className="app-grid-2">
          <article className="app-card app-method">
            <Tag tone="measured">Measured</Tag>
            <h3>YouTube to YouTube</h3>
            <p>We read public comments on each channel&rsquo;s recent videos. If the same account comments on both channels, that&rsquo;s a shared audience member. Overlap = shared commenters &divide; the smaller channel&rsquo;s commenters. It&rsquo;s a sample of real accounts, not every viewer.</p>
          </article>
          <article className="app-card app-method">
            <Tag tone="estimated">Estimated</Tag>
            <h3>Any pair with Instagram or TikTok</h3>
            <p>Instagram and TikTok don&rsquo;t let us read other creators&rsquo; comments or followers, so we estimate. Upriver provides each creator&rsquo;s <b>audience profile</b>: main gender and its share, age range, main countries, main language, a short description, and a confidence rating for each part. Treat them as Upriver&rsquo;s best estimate of who follows the creator.</p>
          </article>
          <article className="app-card app-method">
            <h3>Audience profile match</h3>
            <p>We compare two profiles: <b>countries</b> ({w('geography', 0.4)}% of the score), <b>gender mix</b> ({w('gender', 0.2)}%), <b>age range</b> ({w('age', 0.2)}%) and <b>language</b> ({w('language', 0.2)}%). A part Upriver marks low confidence counts for less. 100% means the profiles look the same, which makes overlap possible, not certain.</p>
          </article>
          <article className="app-card app-method">
            <h3>From match to estimated overlap</h3>
            <p>A profile match isn&rsquo;t a count of shared followers, so we scale it. Where two YouTube creators have both a measured overlap and a profile match, we learn how the two relate. Current factor: <b>{method ? method.kappa.toFixed(2) : '—'}</b>{method ? (method.calibrationPairs >= 3 ? `, learned from ${method.calibrationPairs} YouTube pairs` : ' (default; too few YouTube pairs with both numbers to learn it)') : ''}. Creators with no Upriver audience data are assumed to be a {Math.round((method?.unknownMatch ?? 0.35) * 100)}% match and labeled <b>assumed</b>.</p>
          </article>
          <article className="app-card app-method">
            <h3>Estimated unique followers</h3>
            <p>Reach is followers on every platform, so creators compare fairly. For a roster we add everyone&rsquo;s followers, then subtract the estimated shared followers for each pair (overlap &times; the smaller audience). The plan picks the lowest-overlap roster that still reaches at least as many estimated unique followers as yours.</p>
          </article>
          <article className="app-card app-method">
            <h3>Quotes and limits</h3>
            <p>When planning across platforms, every quote is modeled per 1,000 followers so platforms compare fairly: about ${method?.quotePer1k?.youtube ?? 20} on YouTube, ${method?.quotePer1k?.instagram ?? 10} on Instagram and ${method?.quotePer1k?.tiktok ?? 7.5} on TikTok. These are rough market rates, not quotes. Edit any quote in the creators list. Upriver&rsquo;s &ldquo;similar creators&rdquo; score only suggests lookalikes and never feeds these numbers.</p>
          </article>
        </div>
      </section>
    </div>
  );
}
