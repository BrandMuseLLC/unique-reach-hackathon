import React, { useEffect, useRef } from 'react';
import { ChevronRight, Search, Send, Sparkles, X } from 'lucide-react';
import { Mark } from './parts';
import type { ChatMessage } from './types';

export function MusePanel({ open, onToggle, messages, busy, aiEnabled, draft, onDraft, onSend, suggestions, sectionLabel, onSection, discoveryEnabled, onDiscover }: {
  open: boolean;
  onToggle: (open: boolean) => void;
  messages: ChatMessage[];
  busy: boolean;
  aiEnabled: boolean;
  draft: string;
  onDraft: (text: string) => void;
  onSend: (text?: string) => void;
  suggestions: string[];
  sectionLabel: (section: string) => string | null;
  onSection: (section: string) => void;
  discoveryEnabled: boolean;
  onDiscover: (prompt: string) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { if (open) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy, open]);

  return (
    <>
      {open && (
        <aside className="app-muse" aria-label="Muse">
          <div className="app-muse-head">
            <div className="app-muse-title"><Mark size={32} /><div><strong>Muse</strong><small className={aiEnabled ? 'live' : ''}>{aiEnabled ? 'AI live' : 'AI unavailable'}</small></div></div>
            <button type="button" className="app-icon-btn" onClick={() => onToggle(false)} aria-label="Close Muse"><X size={16} /></button>
          </div>
          <div className="app-muse-body">
            {messages.map((m, i) => (
              <div key={i} className={`app-msg ${m.role} ${m.error ? 'err' : ''}`}>
                <p>{m.text}</p>
                {m.change && <div className={`app-msg-change ${m.change.changed ? 'yes' : 'no'}`}>{m.change.text}</div>}
                {m.section && m.role === 'assistant' && sectionLabel(m.section) && (
                  <button type="button" className="app-msg-link" onClick={() => onSection(m.section!)}>Show {sectionLabel(m.section)!.toLowerCase()} <ChevronRight size={13} /></button>
                )}
                {m.discoverPrompt && (
                  <button type="button" className="app-msg-link" disabled={!discoveryEnabled} onClick={() => onDiscover(m.discoverPrompt!)}>
                    <Search size={13} /> Find creators for &ldquo;{m.discoverPrompt}&rdquo;
                  </button>
                )}
              </div>
            ))}
            {busy && <div className="app-msg assistant typing"><i /><i /><i /></div>}
            <div ref={end} />
          </div>
          <div className="app-muse-suggest">
            {suggestions.map((s) => <button type="button" key={s} className="app-chip small" onClick={() => onSend(s)} disabled={!aiEnabled || busy}>{s}</button>)}
          </div>
          <form className="app-muse-input" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
            <input value={draft} onChange={(e) => onDraft(e.target.value)} placeholder={aiEnabled ? 'Ask Muse to change the plan' : 'Live AI is not configured'} disabled={!aiEnabled} maxLength={1000} aria-label="Message Muse" />
            <button type="submit" className="app-send" disabled={!aiEnabled || busy || !draft.trim()} aria-label="Send"><Send size={18} /></button>
          </form>
        </aside>
      )}
      {!open && (
        <button type="button" className="app-fab" onClick={() => onToggle(true)} aria-label="Open Muse"><Sparkles size={22} /></button>
      )}
    </>
  );
}
