import React, { useEffect, useRef } from 'react';
import { ChevronRight, FileText, Paperclip, Search, Send, Sparkles, X } from 'lucide-react';
import { Mark } from './parts';
import type { Attachment, ChatMessage } from './types';

export function MusePanel({ open, onToggle, messages, busy, aiEnabled, draft, onDraft, onSend, suggestions, sectionLabel, onSection, discoveryEnabled, onDiscover,
  rosterEnabled = false, attachment = null, onAttach, onDetach }: {
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
  // A creator list attached to the next message: Muse maps overlap for exactly those channels.
  rosterEnabled?: boolean;
  attachment?: Attachment | null;
  onAttach?: (file: File) => void;
  onDetach?: () => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy, open]);
  const canType = aiEnabled || Boolean(attachment);
  const canSend = !busy && (attachment ? rosterEnabled : aiEnabled && Boolean(draft.trim()));

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
                {m.attachment && <span className="app-msg-file"><FileText size={13} /> {m.attachment}</span>}
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
          {attachment ? (
            <div className="app-muse-suggest">
              <span className="app-attachment"><FileText size={13} /> {attachment.name} &middot; {attachment.roster.length} creators
                <button type="button" onClick={onDetach} aria-label="Remove the attached list"><X size={12} /></button></span>
            </div>
          ) : (
            <div className="app-muse-suggest">
              {suggestions.map((s) => <button type="button" key={s} className="app-chip small" onClick={() => onSend(s)} disabled={!aiEnabled || busy}>{s}</button>)}
            </div>
          )}
          <form className="app-muse-input" onSubmit={(e) => { e.preventDefault(); if (canSend) onSend(); }}>
            <input ref={file} type="file" accept=".csv,.txt,text/csv,text/plain" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onAttach?.(f); e.target.value = ''; }} />
            <button type="button" className="app-attach" onClick={() => file.current?.click()} disabled={!rosterEnabled || busy} aria-label="Attach a creator list"
              title={rosterEnabled ? 'Attach a creator list (.csv: one YouTube handle or URL per line)' : 'Attaching a creator list needs the YouTube key on the server'}>
              <Paperclip size={18} />
            </button>
            <input value={draft} onChange={(e) => onDraft(e.target.value)} maxLength={1000} aria-label="Message Muse" disabled={!canType}
              placeholder={attachment ? 'Ask Muse to map overlap for these creators' : aiEnabled ? 'Ask Muse to change the plan' : rosterEnabled ? 'Attach a creator list to begin' : 'Live AI is not configured'} />
            <button type="submit" className="app-send" disabled={!canSend} aria-label="Send"><Send size={18} /></button>
          </form>
        </aside>
      )}
      {!open && (
        <button type="button" className="app-fab" onClick={() => onToggle(true)} aria-label="Open Muse"><Sparkles size={22} /></button>
      )}
    </>
  );
}
