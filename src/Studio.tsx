import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BarChart3, Check, ChevronRight, CircleHelp, ExternalLink, Globe, LayoutGrid, Loader2, Map as MapIcon, MessageCircle, Search, Send, Sparkles, Users, X } from 'lucide-react';
import { Glance } from './Glance';
import { ExploreOverlap } from './ExploreOverlap';
import { WhyNotPanel, type WhyNot } from './WhyNotPanel';
import whiteWordmark from '../brandmuse/assets/brand-muse-wordmark-white.jpg';

type Creator = { id: string; name: string; category: string; estimatedViews: number; baseCost: number; eligibilityStatus: string;
  sponsorMentions?: { brands: { brand: string }[] } | null; creatorCountry?: string | null; foundBy?: 'upriver' | 'youtube_search' };
type Lookalike = { creatorId?: string; name: string; platform: string; handle?: string; url?: string; followers?: number | null; followerBucket?: string | null; score: number | null; otherChannels: { platform: string; handle?: string }[] };
type LookalikeGroup = { anchorId: string; anchorName: string; results: Lookalike[]; incomplete: boolean; cached: boolean };
type UpriverStatus = { configured: boolean; creditsReservedThisSession: number; creditCap: number; creditsRemaining: number };
type Campaign = { id: string; name: string; category: string; audience: string };
type RosterDiag = { ids: string[]; spend: number; coverage: number; standalone: number; shared: number; sharedRate: number };
type Plan = {
  campaign: Campaign; budget: number; remainingBudget: number;
  recommended: { ids: string[] }; current: { ids: string[] };
  steps: { creatorId: string; creatorName: string; marginalProxyReach: number; cost: number }[];
  whyNot?: WhyNot[];
  countNote?: string | null;
  rosterDiagnostics?: { rosters: { current: RosterDiag; recommended: RosterDiag; viewsBaseline: RosterDiag } };
};
type Context = { brandDescription: string; relevance: Record<string, number>; maxPerGroup: Record<string, number>; creatorCount?: number };
type Inputs = { budget: number; currentRoster: string[]; include: string[]; exclude: string[]; costs: Record<string, number>; planningContext: Context };
type Dataset = { id: string; name: string; prompt?: string | null; dataDate?: string | null; active: boolean };
type Job = { id: string; status: 'running' | 'done' | 'error'; step: string; progress: number; message: string; dataset_id: string | null; error: string | null; units: number };
type Evidence = { medianSampledCommenters: number; eligibleCreators: number; thinCreators: number; strength: 'strong' | 'moderate' | 'thin' };
type Delta = { subject: 'plan' | 'roster'; overlapFrom: number; overlapTo: number; reachFrom: number; reachTo: number; spendFrom: number; spendTo: number; added: string[]; removed: string[]; previous: Inputs };
type ChatMessage = { role: 'user' | 'assistant'; text: string; change?: { changed: boolean; text: string }; section?: string | null; discoverPrompt?: string | null; error?: boolean };

const EMPTY: Context = { brandDescription: '', relevance: {}, maxPerGroup: {}, creatorCount: 0 };
const SECTIONS = [
  { id: 'discover', label: 'New search', icon: Search },
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'creators', label: 'Creators', icon: Users },
  { id: 'map', label: 'Audience map', icon: MapIcon },
  { id: 'platforms', label: 'Beyond YouTube', icon: Globe },
  { id: 'whynot', label: 'Why not', icon: CircleHelp },
] as const;
const STEPS = [['plan', 'Understanding brief'], ['search', 'Searching YouTube'], ['videos', 'Reading videos'], ['comments', 'Sampling comments'], ['build', 'Mapping overlap']] as const;
const SUGGESTIONS = ['More latte art', 'Less overlap', 'Make it cheaper', 'Where do I see why a creator was left out?'];

const money = (v: number) => v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compact = (v: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Math.round(v));

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error ?? `Request failed (${response.status})`);
  return payload as T;
}

export function Studio() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [inputs, setInputs] = useState<Inputs>({ budget: 10000, currentRoster: [], include: [], exclude: [], costs: {}, planningContext: EMPTY });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [plannedKey, setPlannedKey] = useState('');
  const [delta, setDelta] = useState<Delta | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [rosterBasis, setRosterBasis] = useState('');
  const planRef = useRef<Plan | null>(null);
  const plannedInputsRef = useRef<Inputs | null>(null);
  const requestId = useRef(0);
  const skipAuto = useRef(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [aiEnabled, setAiEnabled] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [discoveryEnabled, setDiscoveryEnabled] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [upriverStatus, setUpriverStatus] = useState<UpriverStatus | null>(null);
  const [useUpriver, setUseUpriver] = useState(false);
  const [lookalikes, setLookalikes] = useState<LookalikeGroup[]>([]);
  const [lookalikeBusy, setLookalikeBusy] = useState(false);
  const [lookalikeNote, setLookalikeNote] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Hi, I’m Muse. Ask me to change the plan ("less overlap", "drop a creator", "spend less"), explain a choice, or find where something is on the page.' }]);
  const [draft, setDraft] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [activeSection, setActiveSection] = useState('discover');
  const [flash, setFlash] = useState('');
  const [filter, setFilter] = useState<'all' | 'recommended' | 'roster' | 'left'>('recommended');
  const [query, setQuery] = useState('');
  const [openRow, setOpenRow] = useState('');
  const inputsRef = useRef(inputs);
  inputsRef.current = inputs;
  const chatEnd = useRef<HTMLDivElement>(null);

  const key = (i: Inputs) => JSON.stringify(i);
  const stale = Boolean(plan && plannedKey !== key(inputs));
  const names = useMemo(() => Object.fromEntries(creators.map((c) => [c.id, c.name])), [creators]);

  useEffect(() => {
    void api<{ enabled: boolean }>('/api/ai/status').then((s) => setAiEnabled(s.enabled)).catch(() => setAiEnabled(false));
    void refreshDatasets();
    void loadDataset();
    void api<UpriverStatus>('/api/upriver/status').then(setUpriverStatus).catch(() => setUpriverStatus(null));
  }, []);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, chatBusy]);
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) setActiveSection(visible.target.id);
    }, { rootMargin: '-20% 0px -60% 0px' });
    SECTIONS.forEach((s) => { const el = document.getElementById(s.id); if (el) observer.observe(el); });
    return () => observer.disconnect();
  }, [plan]);

  async function refreshDatasets() {
    try {
      const payload = await api<{ datasets: Dataset[]; discovery: { enabled: boolean } }>('/api/datasets');
      setDatasets(payload.datasets);
      setDiscoveryEnabled(payload.discovery.enabled);
    } catch { /* datasets are optional in synthetic mode */ }
  }

  async function loadDataset() {
    setError('');
    try {
      const payload = await api<{ campaign: Campaign; creators: Creator[]; defaultBudget?: number; defaultCurrentRoster?: string[]; evidence?: Evidence; defaultRosterBasis?: string }>('/api/creators');
      setEvidence(payload.evidence ?? null);
      setRosterBasis(payload.defaultRosterBasis ?? '');
      setDelta(null);
      planRef.current = null;
      plannedInputsRef.current = null;
      skipAuto.current = true;
      setCreators(payload.creators);
      setCampaign(payload.campaign);
      const next: Inputs = { budget: payload.defaultBudget ?? 10000, currentRoster: payload.defaultCurrentRoster ?? [], include: [], exclude: [],
        costs: Object.fromEntries(payload.creators.map((c) => [c.id, c.baseCost])), planningContext: EMPTY };
      setInputs(next);
      setOpenRow('');
      setLookalikes([]);
      setLookalikeNote('');
      await runPlan(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load creators.');
    }
  }

  function recordDelta(before: Plan | null, beforeInputs: Inputs | null, after: Plan, afterInputs: Inputs) {
    if (!before || !beforeInputs || !before.rosterDiagnostics || !after.rosterDiagnostics) return;
    // Ticking roster boxes only changes your roster; every other edit re-plans the recommendation.
    const rosterOnly = key({ ...beforeInputs, currentRoster: afterInputs.currentRoster }) === key(afterInputs);
    const subject = rosterOnly ? 'roster' : 'plan';
    const pick = (p: Plan) => (subject === 'roster' ? p.rosterDiagnostics!.rosters.current : p.rosterDiagnostics!.rosters.recommended);
    const b = pick(before), a = pick(after);
    const added = a.ids.filter((id) => !b.ids.includes(id));
    const removed = b.ids.filter((id) => !a.ids.includes(id));
    setDelta({ subject, overlapFrom: b.sharedRate, overlapTo: a.sharedRate, reachFrom: b.coverage, reachTo: a.coverage, spendFrom: b.spend, spendTo: a.spend, added, removed, previous: beforeInputs });
  }

  function applyPlan(next: Inputs, result: Plan) {
    recordDelta(planRef.current, plannedInputsRef.current, result, next);
    planRef.current = result;
    plannedInputsRef.current = next;
    setPlan(result);
    setPlannedKey(key(next));
  }

  async function runPlan(next: Inputs = inputsRef.current) {
    const id = ++requestId.current;
    setLoading(true);
    setError('');
    try {
      const result = await api<Plan>('/api/plan', next);
      if (id !== requestId.current) return;
      applyPlan(next, result);
    } catch (e) {
      if (id === requestId.current) setError(e instanceof Error ? e.message : 'Planning failed.');
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  // Every edit re-plans automatically after a short pause, so metrics react to each change.
  useEffect(() => {
    if (creators.length === 0) return;
    if (skipAuto.current) { skipAuto.current = false; return; }
    if (key(inputs) === plannedKey) return;
    const timer = window.setTimeout(() => void runPlan(inputs), 450);
    return () => window.clearTimeout(timer);
  }, [inputs]);

  function update(patch: Partial<Inputs>) {
    setInputs((current) => ({ ...current, ...patch }));
  }

  function goTo(section: string) {
    document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setFlash(section);
    window.setTimeout(() => setFlash(''), 1600);
  }

  async function activate(id: string) {
    try {
      await api('/api/datasets/activate', { id });
      await refreshDatasets();
      await loadDataset();
      goTo('overview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not switch datasets.');
    }
  }

  async function discover(text = prompt) {
    if (!text.trim()) return;
    setPrompt(text);
    setError('');
    goTo('discover');
    try {
      const started = await api<{ job: Job }>('/api/discover', { prompt: text.trim(), expandWithUpriver: useUpriver && Boolean(upriverStatus?.configured) });
      setJob(started.job);
      let failures = 0;
      const poll = async () => {
        let current: { job: Job };
        try {
          current = await api<{ job: Job }>(`/api/discover/${started.job.id}`);
          failures = 0;
        } catch (e) {
          failures += 1;
          if (failures < 5) { window.setTimeout(() => void poll(), 3000); return; }
          setJob((j) => (j ? { ...j, status: 'error', error: 'Lost contact with the server during the search. Refresh and check Your searches.' } : j));
          return;
        }
        setJob(current.job);
        if (current.job.status === 'running') { window.setTimeout(() => void poll(), 1500); return; }
        if (current.job.status === 'done' && current.job.dataset_id) {
          await activate(current.job.dataset_id);
          setMessages((m) => [...m, { role: 'assistant', text: `${current.job.message}. The plan below is for “${text.trim()}”.`, section: 'overview' }]);
        }
      };
      window.setTimeout(() => void poll(), 1200);
    } catch (e) {
      setJob(null);
      setError(e instanceof Error ? e.message : 'Creator search failed.');
    }
  }

  async function findLookalikes() {
    if (!plan) return;
    setLookalikeBusy(true);
    setLookalikeNote('');
    try {
      const payload = await api<{ groups: LookalikeGroup[]; creditsCharged: number; status: UpriverStatus; note: string }>(
        '/api/upriver/similar', { creatorIds: plan.recommended.ids.slice(0, 3), platforms: ['instagram', 'tiktok'] });
      setLookalikes(payload.groups);
      setUpriverStatus(payload.status);
      setLookalikeNote(`${payload.creditsCharged ? `Used about ${payload.creditsCharged} Upriver credits.` : 'Used saved results, no credits.'} ${payload.note}`);
    } catch (e) {
      setLookalikeNote(e instanceof Error ? e.message : 'Upriver lookup failed.');
    } finally {
      setLookalikeBusy(false);
    }
  }

  async function send(text = draft) {
    const message = text.trim();
    if (!message || chatBusy) return;
    setDraft('');
    const history = messages.slice(-6).map((m) => ({ role: m.role, text: m.text }));
    setMessages((m) => [...m, { role: 'user', text: message }]);
    setChatBusy(true);
    const sent = inputsRef.current;
    try {
      const reply = await api<{ intent: string; reply: string; section: string | null; discoverPrompt?: string | null; inputs?: Inputs; plan?: Plan; change?: { changed: boolean; text: string } }>(
        '/api/assistant', { message, inputs: sent, history });
      if (reply.inputs && reply.plan && key(inputsRef.current) !== key(sent)) {
        setMessages((m) => [...m, { role: 'assistant', text: 'You changed the plan while I was working, so I didn\u2019t apply my change over yours. Ask again and I\u2019ll start from your latest settings.', error: true }]);
        return;
      }
      if (reply.inputs && reply.plan) {
        applyPlan(reply.inputs, reply.plan);
        setInputs(reply.inputs);
      }
      setMessages((m) => [...m, { role: 'assistant', text: reply.reply, change: reply.change, section: reply.section, discoverPrompt: reply.discoverPrompt }]);
      if (reply.section && reply.intent !== 'discover') goTo(reply.section);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: e instanceof Error ? e.message : 'Something went wrong.', error: true }]);
    } finally {
      setChatBusy(false);
    }
  }

  const planIds = plan ? new Set(plan.recommended.ids) : null;
  const leftOut = new Map((plan?.whyNot ?? []).map((w) => [w.creatorId, w]));
  const statusOf = (id: string) => inputs.exclude.includes(id) ? 'excluded' : inputs.include.includes(id) ? 'required' : !planIds ? 'none' : planIds.has(id) ? 'recommended' : 'left';
  const rows = creators
    .filter((c) => c.eligibilityStatus !== 'ineligible')
    .filter((c) => !query.trim() || c.name.toLowerCase().includes(query.trim().toLowerCase()))
    .filter((c) => filter === 'all'
      || (filter === 'recommended' && ((planIds?.has(c.id) ?? false) || inputs.exclude.includes(c.id) || inputs.include.includes(c.id) || openRow === c.id))
      || (filter === 'roster' && inputs.currentRoster.includes(c.id))
      || (filter === 'left' && statusOf(c.id) === 'left'))
    .sort((a, b) => Number(!(planIds?.has(a.id))) - Number(!(planIds?.has(b.id))) || b.estimatedViews - a.estimatedViews);
  const eligible = creators.filter((c) => c.eligibilityStatus !== 'ineligible');
  const activeDataset = datasets.find((d) => d.active);
  const recDiag = plan?.rosterDiagnostics?.rosters.recommended;
  const stepIndex = job ? STEPS.findIndex(([id]) => id === job.step) : -1;

  return (
    <div className={`studio ${chatOpen ? 'chat-open' : ''}`}>
      <aside className="side">
        <img className="side-logo" src={whiteWordmark} alt="Brand Muse" />
        <p className="side-product">Unique Reach</p>
        <nav>
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <button key={id} className={activeSection === id ? 'active' : ''} onClick={() => goTo(id)}><Icon size={17} />{label}</button>
          ))}
        </nav>
        {datasets.length > 0 && (
          <div className="side-datasets">
            <span>Your searches</span>
            {datasets.map((d) => (
              <button key={d.id} className={d.active ? 'active' : ''} onClick={() => !d.active && void activate(d.id)} title={d.prompt ?? d.name}>
                <i />{d.name}
              </button>
            ))}
          </div>
        )}
        <p className="side-foot">Overlap is measured from public commenters on recent videos. Counts are commenter accounts, not unique viewers.</p>
      </aside>

      <main className="stage">
        <section id="discover" className={`stage-section ${flash === 'discover' ? 'flash' : ''}`}>
          <div className="hello">
            <div>
              <h1>Plan a creator campaign</h1>
              <p>Describe what you&rsquo;re launching. We find relevant YouTube creators, measure where their audiences overlap, and pick a roster.</p>
            </div>
            {!chatOpen && <button className="btn-secondary" onClick={() => setChatOpen(true)}><MessageCircle size={16} />Ask Muse</button>}
          </div>
          <div className="hero">
            <div className="hero-input">
              <Sparkles size={18} />
              <input value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void discover(); }}
                placeholder="e.g. Launching a cold brew concentrate for people who make iced coffee at home" maxLength={300} disabled={job?.status === 'running'} />
              <button className="btn-primary" onClick={() => void discover()} disabled={!discoveryEnabled || !prompt.trim() || job?.status === 'running'}>
                {job?.status === 'running' ? <Loader2 className="spin" size={16} /> : <Search size={16} />}Find creators
              </button>
            </div>
            {upriverStatus?.configured && (
              <label className="hero-option">
                <input type="checkbox" checked={useUpriver} onChange={(e) => setUseUpriver(e.target.checked)} disabled={job?.status === 'running'} />
                Also add lookalike YouTube creators from Upriver <small>(up to ~48 credits · {upriverStatus.creditsRemaining} left this session)</small>
              </label>
            )}
            {!discoveryEnabled && <p className="hero-note">Creator search needs the YouTube and Gemini keys on the server. You can still plan with saved searches.</p>}
            {job && (
              <div className={`stepper ${job.status}`}>
                <div className="stepper-steps">
                  {STEPS.map(([id, label], i) => {
                    const state = job.status === 'done' || i < stepIndex ? 'done' : i === stepIndex ? (job.status === 'error' ? 'error' : 'now') : 'todo';
                    return <div key={id} className={`step ${state}`}><span>{state === 'done' ? <Check size={12} /> : i + 1}</span>{label}</div>;
                  })}
                </div>
                <div className="bar"><i style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
                <p>{job.status === 'error' ? job.error : job.message}{job.units ? ` · ~${job.units} API units` : ''}</p>
              </div>
            )}
          </div>
          <div className="campaign-strip">
            <div className="strip-item grow">
              <span>Campaign</span>
              <strong>{campaign?.name ?? 'Loading…'}</strong>
              <small>{activeDataset?.prompt ? `“${activeDataset.prompt}” · ` : ''}{eligible.length} creators in the plan pool{evidence?.thinCreators ? ` · ${evidence.thinCreators} set aside for too few comments` : ''}</small>
            </div>
            <label className="strip-item">
              <span>Budget</span>
              <div className="money"><b>$</b><input inputMode="numeric" value={inputs.budget.toLocaleString('en-US')}
                onChange={(e) => update({ budget: Number(e.target.value.replace(/[^0-9]/g, '')) || 0 })} aria-label="Budget" /></div>
            </label>
            <label className="strip-item">
              <span>Creators</span>
              <div className="count-step">
                <button type="button" aria-label="Fewer creators" onClick={() => update({ planningContext: { ...inputs.planningContext, creatorCount: Math.max((inputs.planningContext.creatorCount ?? 0) - 1, 0) } })}>−</button>
                <b>{inputs.planningContext.creatorCount ? inputs.planningContext.creatorCount : 'Any'}</b>
                <button type="button" aria-label="More creators" onClick={() => update({ planningContext: { ...inputs.planningContext, creatorCount: Math.min((inputs.planningContext.creatorCount ?? 0) + 1, Math.max(eligible.length, 1)) } })}>+</button>
              </div>
            </label>
            <div className={`live-pill ${loading || stale ? 'busy' : ''}`} aria-live="polite">
              {loading || stale ? <Loader2 className="spin" size={14} /> : <BarChart3 size={14} />}{loading || stale ? 'Updating plan…' : 'Plan is up to date'}
            </div>
          </div>
          {error && <p className="alert" role="alert">{error}</p>}
          {plan?.countNote && !stale && <p className="notice">{plan.countNote}</p>}
          {evidence && evidence.strength !== 'strong' && (
            <p className={`evidence-note ${evidence.strength}`}>
              {evidence.strength === 'thin' ? 'Thin evidence: ' : 'Limited evidence: '}
              a typical creator here has about {evidence.medianSampledCommenters.toLocaleString('en-US')} sampled commenters, so small overlap differences are rough. Channels with comments turned off (common for kids&rsquo; content) can&rsquo;t be measured.
            </p>
          )}
        </section>

        <section id="overview" className={`stage-section ${flash === 'overview' ? 'flash' : ''}`}>
          {delta && (
            <div className="delta rise" key={`${delta.added.join()}-${delta.removed.join()}-${delta.overlapTo}-${delta.spendTo}`}>
              <div className="delta-title"><strong>{delta.subject === 'roster' ? 'Your roster changed' : 'The plan changed'}</strong>
                <span>{delta.added.length || delta.removed.length
                  ? [delta.added.length ? `Added ${delta.added.map((id) => names[id]).join(', ')}` : '', delta.removed.length ? `Removed ${delta.removed.map((id) => names[id]).join(', ')}` : ''].filter(Boolean).join(' · ')
                  : delta.subject === 'roster' ? 'Same creators in your roster' : 'Same creators in the plan'}</span>
              </div>
              <div className="delta-stats">
                <DeltaStat label="Audience overlap" from={`${(delta.overlapFrom * 100).toFixed(1)}%`} to={`${(delta.overlapTo * 100).toFixed(1)}%`} good={delta.overlapTo <= delta.overlapFrom} same={Math.abs(delta.overlapTo - delta.overlapFrom) < 0.0005} />
                <DeltaStat label="Commenters reached" from={compact(delta.reachFrom)} to={compact(delta.reachTo)} good={delta.reachTo >= delta.reachFrom} same={delta.reachTo === delta.reachFrom} />
                <DeltaStat label="Spend" from={money(delta.spendFrom)} to={money(delta.spendTo)} good={delta.spendTo <= delta.spendFrom} same={delta.spendTo === delta.spendFrom} />
              </div>
              <button className="btn-ghost" onClick={() => { const prev = delta.previous; setDelta(null); setInputs(prev); }}>Undo</button>
            </div>
          )}
          {plan?.rosterDiagnostics ? (
            <Glance key={`${plan.recommended.ids.join('|')}-${plan.budget}`} result={plan} creatorCount={eligible.length} />
          ) : <div className="placeholder">Run the plan to see the overview.</div>}
          {recDiag && plan && (
            <div className="roster-cards">
              {plan.recommended.ids.map((id, i) => (
                <div className="roster-card rise" style={{ animationDelay: `${i * 50}ms` }} key={id}>
                  <span className="avatar">{(names[id] ?? '?').replace(/^@/, '').slice(0, 1).toUpperCase()}</span>
                  <div><strong>{names[id]}</strong><small>{creators.find((c) => c.id === id)?.category} · {money(inputs.costs[id] ?? 0)}</small></div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section id="creators" className={`stage-section panel-lite ${flash === 'creators' ? 'flash' : ''}`}>
          <div className="section-head">
            <div><h2>Creators</h2><p>Purple rows are in the plan. Exclude, require or re-price a creator and the plan updates instantly.{rosterBasis ? ` Your starting roster: ${rosterBasis.charAt(0).toLowerCase()}${rosterBasis.slice(1)}` : ''}</p></div>
            <label className="search-lite"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search" /></label>
          </div>
          <div className="tabs">
            {([['recommended', 'In the plan'], ['roster', 'Your roster'], ['left', 'Left out'], ['all', 'All']] as const).map(([id, label]) => (
              <button key={id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>{label}</button>
            ))}
          </div>
          <div className="clist">
            {rows.length === 0 && <p className="placeholder small">No creators here.</p>}
            {rows.map((c) => {
              const status = statusOf(c.id);
              const why = leftOut.get(c.id);
              const open = openRow === c.id;
              return (
                <div key={c.id} className={`crow s-${status} ${open ? 'open' : ''}`}>
                  <div className="crow-main">
                    <input type="checkbox" checked={inputs.currentRoster.includes(c.id)} aria-label={`${c.name} is in your roster`}
                      onChange={() => update({ currentRoster: inputs.currentRoster.includes(c.id) ? inputs.currentRoster.filter((x) => x !== c.id) : [...inputs.currentRoster, c.id] })} />
                    <span className="avatar">{c.name.replace(/^@/, '').slice(0, 1).toUpperCase()}</span>
                    <div className="crow-name"><strong>{c.name}{c.foundBy === 'upriver' && <span className="found-by">Upriver lookalike</span>}</strong><small>{c.category} · {compact(c.estimatedViews)} views</small></div>
                    <span className={`badge b-${status}`}>
                      {status === 'recommended' ? 'In the plan' : status === 'required' ? 'Required' : status === 'excluded' ? 'Excluded'
                        : status === 'left' ? (why && Math.round(why.alreadyCoveredShare * 100) >= 1 ? `${Math.round(why.alreadyCoveredShare * 100)}% already reached` : 'Not picked') : ''}
                    </span>
                    <span className="crow-quote">{money(inputs.costs[c.id] ?? c.baseCost)}</span>
                    <button className="btn-ghost" onClick={() => setOpenRow(open ? '' : c.id)} aria-expanded={open}>
                      <ChevronRight size={16} className={open ? 'rot' : ''} />
                    </button>
                  </div>
                  {open && (
                    <div className="crow-detail">
                      <p>{status === 'recommended' ? 'Picked because it adds the most new audience for its quote at this budget.'
                        : why ? (why.overlapsWith.length ? `${Math.round(why.alreadyCoveredShare * 100)}% of its commenters are already reached through ${why.overlapsWith.map((o) => o.creatorName).join(', ')}. ${why.reason}` : why.reason)
                        : 'Run the plan to see how this creator compares.'}</p>
                      {c.sponsorMentions?.brands.length ? <p className="muted">Mentions in descriptions: {c.sponsorMentions.brands.map((b) => b.brand).join(', ')}</p> : null}
                      <div className="crow-actions">
                        <label className="money small"><b>$</b><input inputMode="numeric" value={(inputs.costs[c.id] ?? c.baseCost).toLocaleString('en-US')}
                          onChange={(e) => update({ costs: { ...inputs.costs, [c.id]: Number(e.target.value.replace(/[^0-9]/g, '')) || 0 } })} aria-label={`Quote for ${c.name}`} /></label>
                        <button className={`btn-secondary ${status === 'required' ? 'on' : ''}`} onClick={() => update({ include: inputs.include.includes(c.id) ? inputs.include.filter((x) => x !== c.id) : [...inputs.include, c.id], exclude: inputs.exclude.filter((x) => x !== c.id) })}>
                          {status === 'required' ? 'Required' : 'Require'}
                        </button>
                        <button className={`btn-secondary ${status === 'excluded' ? 'on' : ''}`} onClick={() => update({ exclude: inputs.exclude.includes(c.id) ? inputs.exclude.filter((x) => x !== c.id) : [...inputs.exclude, c.id], include: inputs.include.filter((x) => x !== c.id) })}>
                          {status === 'excluded' ? 'Excluded' : 'Exclude'}
                        </button>
                        <button className="btn-ghost" onClick={() => void send(`Why is ${c.name} ${status === 'recommended' ? 'in' : 'not in'} the plan?`)} disabled={!aiEnabled}>Ask Muse why</button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <section id="map" className={`stage-section ${flash === 'map' ? 'flash' : ''}`}>
          {creators.length > 0 && <ExploreOverlap key={campaign?.id} aiEnabled={aiEnabled} />}
        </section>

        <section id="platforms" className={`stage-section panel-lite ${flash === 'platforms' ? 'flash' : ''}`}>
          <div className="section-head">
            <div>
              <h2>Beyond YouTube</h2>
              <p>Creators on Instagram and TikTok with a similar niche and audience to the ones in your plan, from Upriver. This is modeled similarity, not measured overlap.</p>
            </div>
            <button className="btn-primary" disabled={!upriverStatus?.configured || lookalikeBusy || !plan?.recommended.ids.length} onClick={() => void findLookalikes()}>
              {lookalikeBusy ? <Loader2 className="spin" size={16} /> : <Globe size={16} />}Find on Instagram &amp; TikTok
            </button>
          </div>
          <p className="muted-line">
            {!upriverStatus?.configured ? 'Add UPRIVER_API_KEY to the server .env to turn this on.'
              : `Looks up the top ${Math.min(plan?.recommended.ids.length ?? 0, 3)} creators in the plan · about ${Math.min(plan?.recommended.ids.length ?? 0, 3) * 16} credits · ${upriverStatus.creditsRemaining} of ${upriverStatus.creditCap} left this session · repeat lookups are free`}
          </p>
          {lookalikeNote && <p className="notice">{lookalikeNote}</p>}
          {lookalikes.map((g) => (
            <div className="look-group" key={g.anchorId}>
              <h3>Like <strong>{g.anchorName}</strong>{g.cached && <small> · saved result</small>}</h3>
              {g.results.length === 0 ? (
                <p className="placeholder small">{g.incomplete ? 'Upriver ran out of time before finishing. Try again later.' : 'No similar Instagram or TikTok creators found.'}</p>
              ) : (
                <div className="look-grid">
                  {g.results.map((r, i) => (
                    <a className="look-card rise" style={{ animationDelay: `${i * 40}ms` }} key={`${r.platform}-${r.handle}-${i}`} href={r.url} target="_blank" rel="noreferrer noopener">
                      <div className="look-top">
                        <span className={`plat plat-${r.platform}`}>{r.platform === 'tiktok' ? 'TikTok' : r.platform === 'instagram' ? 'Instagram' : r.platform}</span>
                        <ExternalLink size={13} />
                      </div>
                      <strong>{r.name}</strong>
                      <small>{r.handle ? `@${String(r.handle).replace(/^@/, '')}` : ''}{r.followers ? ` · ${compact(r.followers)} followers` : r.followerBucket ? ` · ${r.followerBucket.replace(/_/g, '–')} followers` : ''}</small>
                      {r.score !== null && <div className="look-score"><i style={{ width: `${Math.round(r.score * 100)}%` }} /><span>{Math.round(r.score * 100)}% similar</span></div>}
                      {r.otherChannels.length > 0 && <small className="muted">Also on {r.otherChannels.map((o) => o.platform).join(', ')}</small>}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </section>

        <section id="whynot" className={`stage-section ${flash === 'whynot' ? 'flash' : ''}`}>
          {plan?.whyNot && <WhyNotPanel rows={plan.whyNot} stale={stale} />}
        </section>
      </main>

      {chatOpen && (
        <aside className="chat" aria-label="Muse assistant">
          <div className="chat-head">
            <div className="chat-title"><span className="chat-orb"><Sparkles size={15} /></span><div><strong>Muse</strong><small>{aiEnabled ? 'Gemini connected' : 'AI unavailable'}</small></div></div>
            <button className="btn-ghost" onClick={() => setChatOpen(false)} aria-label="Close chat"><X size={16} /></button>
          </div>
          <div className="chat-body">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role} ${m.error ? 'err' : ''}`}>
                <p>{m.text}</p>
                {m.change && <div className={`msg-change ${m.change.changed ? 'yes' : 'no'}`}>{m.change.text}</div>}
                {m.section && m.role === 'assistant' && SECTIONS.some((s) => s.id === m.section) && (
                  <button className="msg-link" onClick={() => goTo(m.section!)}>Show {SECTIONS.find((s) => s.id === m.section)!.label.toLowerCase()} <ChevronRight size={13} /></button>
                )}
                {m.discoverPrompt && (
                  <button className="msg-link" disabled={!discoveryEnabled || job?.status === 'running'} onClick={() => void discover(m.discoverPrompt!)}>
                    <Search size={13} /> Find creators for &ldquo;{m.discoverPrompt}&rdquo;
                  </button>
                )}
              </div>
            ))}
            {chatBusy && <div className="msg assistant typing"><i /><i /><i /></div>}
            <div ref={chatEnd} />
          </div>
          <div className="chat-suggest">
            {SUGGESTIONS.map((s) => <button key={s} onClick={() => void send(s)} disabled={!aiEnabled || chatBusy}>{s}</button>)}
          </div>
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); void send(); }}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={aiEnabled ? 'Ask or tell Muse what to change' : 'Live AI is not configured'} disabled={!aiEnabled} maxLength={1000} />
            <button className="btn-primary icon" type="submit" disabled={!aiEnabled || chatBusy || !draft.trim()} aria-label="Send"><Send size={16} /></button>
          </form>
        </aside>
      )}
    </div>
  );
}

function DeltaStat({ label, from, to, good, same }: { label: string; from: string; to: string; good: boolean; same: boolean }) {
  return (
    <div className={`delta-stat ${same ? 'same' : good ? 'good' : 'bad'}`}>
      <span>{label}</span>
      <strong>{from} <em>{same ? '=' : '→'}</em> {to}</strong>
    </div>
  );
}
