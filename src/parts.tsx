import React from 'react';
import { ChevronRight, Sparkles } from 'lucide-react';
import { PLATFORM_LABEL, initialOf, type Platform } from './types';

// Platform glyphs on the black discs the design uses for badges and the sourcing line.
export function PlatformGlyph({ platform, size = 20 }: { platform: Platform; size?: number }) {
  const inner = Math.round(size * 0.5);
  return (
    <span className="app-plat" style={{ width: size, height: size }} aria-hidden="true">
      {platform === 'youtube' && <svg width={inner - 1} height={inner - 1} viewBox="0 0 24 24" fill="currentColor"><path d="M6 3l14 9-14 9z" /></svg>}
      {platform === 'tiktok' && <svg width={inner} height={inner} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></svg>}
      {platform === 'instagram' && <svg width={inner} height={inner} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="5" /><circle cx="12" cy="12" r="4" /><path d="M17.5 6.5h.01" /></svg>}
    </span>
  );
}

export function Avatar({ name, platform, size = 44 }: { name: string; platform?: Platform; size?: number }) {
  return (
    <span className="app-avatar-wrap" style={{ width: size, height: size }}>
      <span className="app-avatar" style={{ width: size, height: size }}>{initialOf(name)}</span>
      {platform && <span className="app-avatar-badge"><PlatformGlyph platform={platform} size={20} /></span>}
    </span>
  );
}

export function Mark({ size = 32 }: { size?: number }) {
  return (
    <span className="app-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={Math.round(size / 2)} height={Math.round(size / 2)} viewBox="0 0 24 24" fill="currentColor"><path d="M9.9 3.2a1 1 0 0 1 1.9 0l1.2 3.6a1 1 0 0 0 .6.6l3.6 1.2a1 1 0 0 1 0 1.9l-3.6 1.2a1 1 0 0 0-.6.6l-1.2 3.6a1 1 0 0 1-1.9 0l-1.2-3.6a1 1 0 0 0-.6-.6L4.5 10.5a1 1 0 0 1 0-1.9l3.6-1.2a1 1 0 0 0 .6-.6Z" /></svg>
    </span>
  );
}

export function EyebrowRow({ label, link, onLink, right }: { label: string; link?: string; onLink?: () => void; right?: React.ReactNode }) {
  return (
    <div className="app-eyebrow-row">
      <span className="eyebrow-wide app-eyebrow">{label}</span>
      {right ?? (link && (
        <button type="button" className="app-link" onClick={onLink}>{link} <ChevronRight size={14} /></button>
      ))}
    </div>
  );
}

export function Insight({ children }: { children: React.ReactNode }) {
  return (
    <p className="app-insight"><Sparkles size={16} className="app-sparkle" aria-hidden="true" />{children}</p>
  );
}

export function StatCard({ value, label, caption, accent = false }: { value: string; label: string; caption: string; accent?: boolean }) {
  return (
    <div className="app-stat">
      <strong className={accent ? 'accent' : ''}>{value}</strong>
      <span>{label}</span>
      <small>{caption}</small>
    </div>
  );
}

export function Chip({ active = false, onClick, children, count, disabled = false, title }: { active?: boolean; onClick?: () => void; children: React.ReactNode; count?: number; disabled?: boolean; title?: string }) {
  return (
    <button type="button" className={`app-chip ${active ? 'active' : ''}`} onClick={onClick} disabled={disabled} title={title}>
      {children}{count !== undefined && <span className="app-chip-count">{count}</span>}
    </button>
  );
}

export function Tag({ tone, children }: { tone: 'budget' | 'little' | 'excluded' | 'cap' | 'measured' | 'estimated'; children: React.ReactNode }) {
  return <span className={`app-tag tone-${tone}`}>{children}</span>;
}

export function platformLabel(platform: Platform) {
  return PLATFORM_LABEL[platform];
}
