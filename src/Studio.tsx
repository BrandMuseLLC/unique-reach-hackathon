import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BarChart3, Bell, Check, ChevronRight, CircleHelp, Home, Loader2, Map as MapIcon, Send, SlidersHorizontal, Sparkles, Upload, User, Users } from 'lucide-react';
import { CreatorsScreen, type RosterStatus } from './CreatorsScreen';
import { MethodsScreen } from './MethodsScreen';
import { MusePanel } from './MusePanel';
import { Avatar, Chip, EyebrowRow, Insight, Mark, PlatformGlyph, StatCard } from './parts';
import {
  PLATFORMS, PLATFORM_COMMUNITY, PLATFORM_LABEL, compact, money, pct, platformOf, topicOf,
  type Attachment, type Campaign, type ChatMessage, type Creator, type Dataset, type Evidence, type Graph, type Inputs, type Job, type Method, type Plan, type Platform, type RosterDiag, type RosterItem, type SavedCampaign,
} from './types';
import whiteWordmark from '../brandmuse/assets/brand-muse-wordmark-white.jpg';
import './studio.css';

type Screen = 'overview' | 'creators' | 'methods';
type Route = { screen: Screen; anchor: string };
type Delta = { subject: 'plan' | 'roster'; added: string[]; removed: string[]; previous: Inputs };
type UpriverStatus = { configured: boolean; creditsReservedThisSession: number; creditCap: number; creditsRemaining: number };

const EMPTY = { brandDescription: '', relevance: {}, maxPerGroup: {}, creatorCount: 0 };
const DEFAULT_CREATORS = 10;
const NAV: { label: string; icon: typeof Home; screen: Screen; anchor?: string }[] = [
  { label: 'Overview', icon: Home, screen: 'overview' },
  { label: 'Creators', icon: Users, screen: 'creators' },
  { label: 'Audience map', icon: MapIcon, screen: 'creators', anchor: 'map' },
  { label: 'Why not', icon: CircleHelp, screen: 'creators', anchor: 'whynot' },
  { label: 'Methods', icon: BarChart3, screen: 'methods' },
];
// Where the assistant's section names land in the new layout.
const SECTION_TARGET: Record<string, { screen: Screen; anchor?: string; label: string }> = {
  discover: { screen: 'overview', label: 'Overview' },
  overview: { screen: 'overview', label: 'Overview' },
  creators: { screen: 'creators', label: 'Creators' },
  map: { screen: 'creators', anchor: 'map', label: 'Audience map' },
  platforms: { screen: 'creators', label: 'Creators' },
  whynot: { screen: 'creators', anchor: 'whynot', label: 'Why not' },
  method: { screen: 'methods', label: 'Methods' },
};
const STEPS = [['plan', 'Understanding brief'], ['search', 'Finding channels'], ['videos', 'Reading videos'], ['comments', 'Sampling comments'], ['build', 'Mapping overlap']] as const;

/** A creator list from a CSV or text file: one YouTube handle, channel id or URL per line, optional topic in a second column. */
export function parseRoster(text: string): RosterItem[] {
  const rows: RosterItem[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.split('#')[0].trim();
    if (!line) continue;
    const cells = line.split(/[,\t;]/).map((c) => c.trim().replace(/^"|"$/g, ''));
    const handle = cells[0];
    if (!handle || /^(handle|channel|creator|url|link|name|youtube|platform|profile)s?$/i.test(handle)) continue;  // header row
    rows.push({ handle, topic: (cells[1] ?? '').slice(0, 60) });
  }
  return rows;
}

function readRoute(): Route {
  const [screen, anchor = ''] = window.location.hash.replace(/^#\/?/, '').split('/');
  return { screen: screen === 'creators' || screen === 'methods' ? screen : 'overview', anchor };
}

// The dataset this page is showing; sent with every request so the server can say when another tab switched it.
let pageDataset = '';
class DatasetChanged extends Error {}

async function api<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = pageDataset ? { 'X-Dataset-Version': pageDataset } : {};
  const response = await fetch(path, body === undefined ? { headers } : { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 409 && payload.code === 'dataset_changed') throw new DatasetChanged(payload.error);
  if (!response.ok) throw new Error(payload.error ?? `Request failed (${response.status})`);
  return payload as T;
}

export function Studio() {
  const [route, setRoute] = useState<Route>(readRoute);
  const [saved, setSaved] = useState<SavedCampaign[]>([]);
  const [saveName, setSaveName] = useState('Demo campaign');
  const [saveStatus, setSaveStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const [datasetVersion, setDatasetVersion] = useState('');
  const [creators, setCreators] = useState<Creator[]>([]);
  const [inputs, setInputs] = useState<Inputs>({ budget: 10000, currentRoster: [], include: [], exclude: [], costs: {}, planningContext: EMPTY });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [plannedKey, setPlannedKey] = useState('');
  const [delta, setDelta] = useState<Delta | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [rosterBasis, setRosterBasis] = useState('');
  const [method, setMethod] = useState<Method | null>(null);
  const [datasetKind, setDatasetKind] = useState('');
  const [graph, setGraph] = useState<Graph | null>(null);
  const planRef = useRef<Plan | null>(null);
  const plannedInputsRef = useRef<Inputs | null>(null);
  const requestId = useRef(0);
  const skipAuto = useRef(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [aiEnabled, setAiEnabled] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [discoveryEnabled, setDiscoveryEnabled] = useState(false);
  const [rosterEnabled, setRosterEnabled] = useState(false);
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [prompt, setPrompt] = useState('');
  const [upriverStatus, setUpriverStatus] = useState<UpriverStatus | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Hi, I’m Muse. Ask me to change the plan ("less overlap", "drop a creator", "spend less"), explain a choice, or find where something is on the page.' }]);
  const [draft, setDraft] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const inputsRef = useRef(inputs);
  inputsRef.current = inputs;
  const promptRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const key = (i: Inputs) => JSON.stringify(i);
  // The server fills in default quotes itself and caps the costs map, so only send the quotes you changed.
  const outbound = (i: Inputs): Inputs => ({ ...i, costs: Object.fromEntries(Object.entries(i.costs).filter(([id, v]) => byId.get(id) && v !== byId.get(id)!.baseCost)) });
  const stale = Boolean(plan && plannedKey !== key(inputs));
  const names = useMemo(() => Object.fromEntries(creators.map((c) => [c.id, c.name])), [creators]);
  const byId = useMemo(() => new Map(creators.map((c) => [c.id, c])), [creators]);
  const eligible = useMemo(() => creators.filter((c) => c.eligibilityStatus !== 'ineligible'), [creators]);
  const crossPlatform = datasetKind === 'crossplatform';
  const observed = creators.some((c) => c.source === 'observed-public');
  const platformsPresent = PLATFORMS.filter((p) => eligible.some((c) => platformOf(c) === p));

  useEffect(() => {
    void api<{ enabled: boolean }>('/api/ai/status').then((s) => setAiEnabled(s.enabled)).catch(() => setAiEnabled(false));
    void refreshDatasets();
    void loadDataset();
    void api<UpriverStatus>('/api/upriver/status').then(setUpriverStatus).catch(() => setUpriverStatus(null));
    const onHash = () => setRoute(readRoute());
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); navigate('overview'); window.setTimeout(() => promptRef.current?.focus(), 50); }
      if (e.key === 'Escape') setSettingsOpen(false);
    };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('hashchange', onHash); window.removeEventListener('keydown', onKey); };
  }, []);

  // Route changes scroll to the anchor (Audience map, Why not) or back to the top of the screen.
  useEffect(() => {
    if (!route.anchor) { window.scrollTo({ top: 0 }); return; }
    const timer = window.setTimeout(() => document.getElementById(route.anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
    return () => window.clearTimeout(timer);
  }, [route]);

  useEffect(() => {
    if (!settingsOpen) return;
    const onClick = (e: MouseEvent) => { if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) setSettingsOpen(false); };
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, [settingsOpen]);

  // The overlap graph feeds the audience map and the per-creator overlap on the roster cards.
  useEffect(() => {
    if (!datasetVersion || !observed) { setGraph(null); return; }
    const controller = new AbortController();
    fetch('/api/overlap', { signal: controller.signal, headers: { 'X-Dataset-Version': datasetVersion } })
      .then(async (r) => { if (r.ok) setGraph(await r.json()); })
      .catch(() => { /* the map shows its own loading state */ });
    return () => controller.abort();
  }, [datasetVersion, observed]);

  function navigate(screen: Screen, anchor = '') {
    const hash = `#/${screen}${anchor ? `/${anchor}` : ''}`;
    if (window.location.hash === hash) setRoute({ screen, anchor }); else window.location.hash = hash;
  }

  async function refreshDatasets() {
    try {
      const payload = await api<{ datasets: Dataset[]; discovery: { enabled: boolean }; roster?: { enabled: boolean } }>('/api/datasets');
      setDatasets(payload.datasets);
      setDiscoveryEnabled(payload.discovery.enabled);
      setRosterEnabled(Boolean(payload.roster?.enabled));
    } catch { /* datasets are optional in synthetic mode */ }
  }

  async function loadDataset() {
    setError('');
    try {
      const payload = await api<{ campaign: Campaign; creators: Creator[]; datasetVersion: string; datasetKind?: string; method?: Method; defaultBudget?: number; defaultCurrentRoster?: string[]; evidence?: Evidence; defaultRosterBasis?: string }>('/api/creators');
      pageDataset = payload.datasetVersion;
      setDatasetVersion(payload.datasetVersion);
      setSaveName(`${payload.campaign.name} plan`.slice(0, 80));
      setSaveStatus('');
      void api<{ campaigns: SavedCampaign[] }>('/api/campaigns').then((p) => setSaved(p.campaigns)).catch(() => setSaveStatus('Saved campaigns unavailable.'));
      setEvidence(payload.evidence ?? null);
      setDatasetKind(payload.datasetKind ?? '');
      setMethod(payload.method ?? null);
      setRosterBasis(payload.defaultRosterBasis ?? '');
      setDelta(null);
      planRef.current = null;
      plannedInputsRef.current = null;
      skipAuto.current = true;
      setCreators(payload.creators);
      // Default plan size is ten creators (or the whole pool when smaller); the budget stretches to fit ten typical quotes.
      const quotes = payload.creators.filter((c) => c.eligibilityStatus !== 'ineligible').map((c) => c.baseCost).sort((a, b) => a - b);
      const count = Math.min(DEFAULT_CREATORS, quotes.length);
      const middle = Math.max(Math.floor((quotes.length - count) / 2), 0);
      const typical = quotes.slice(middle, middle + count).reduce((s, q) => s + q, 0);
      const base = payload.defaultBudget ?? (payload.creators.every((c) => c.source === 'synthetic') ? 139000 : 10000);
      const next: Inputs = { budget: Math.max(base, Math.ceil(typical / 250) * 250), currentRoster: payload.defaultCurrentRoster ?? [], include: [], exclude: [],
        costs: Object.fromEntries(payload.creators.map((c) => [c.id, c.baseCost])), planningContext: { ...EMPTY, creatorCount: count } };
      setInputs(next);
      await runPlan(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load creators.');
    }
  }

  async function saveCurrentCampaign() {
    setSaving(true);
    try {
      await api('/api/campaigns', { name: saveName.trim(), ...outbound(inputsRef.current) });
      const result = await api<{ campaigns: SavedCampaign[] }>('/api/campaigns');
      setSaved(result.campaigns);
      setSaveStatus('Saved.');
    } catch (e) {
      if (e instanceof DatasetChanged) { setSaveStatus('Not saved: ' + e.message); void reloadActive(e.message); return; }
      setSaveStatus(e instanceof Error ? e.message : 'Save failed.');
    } finally { setSaving(false); }
  }

  async function restoreCampaign(id: string) {
    const row = saved.find((c) => c.id === id && c.datasetVersion === datasetVersion);
    if (!row) return;
    const next: Inputs = { budget: row.budget, currentRoster: row.currentRoster, include: row.include, exclude: row.exclude, costs: row.costs, planningContext: row.planningContext ?? EMPTY };
    ++requestId.current;
    skipAuto.current = true;
    inputsRef.current = next;
    setInputs(next);
    setSaveName(row.name);
    setSaveStatus('Loaded.');
    setSettingsOpen(false);
    await runPlan(next);
  }

  function recordDelta(before: Plan | null, beforeInputs: Inputs | null, after: Plan, afterInputs: Inputs) {
    if (!before || !beforeInputs || !before.rosterDiagnostics || !after.rosterDiagnostics) return;
    // Ticking roster boxes only changes your roster; every other edit re-plans the recommendation.
    const rosterOnly = key({ ...beforeInputs, currentRoster: afterInputs.currentRoster }) === key(afterInputs);
    const subject = rosterOnly ? 'roster' : 'plan';
    const pick = (p: Plan) => (subject === 'roster' ? p.rosterDiagnostics!.rosters.current : p.rosterDiagnostics!.rosters.recommended);
    const b = pick(before), a = pick(after);
    setDelta({ subject, added: a.ids.filter((id) => !b.ids.includes(id)), removed: b.ids.filter((id) => !a.ids.includes(id)), previous: beforeInputs });
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
      const result = await api<Plan>('/api/plan', outbound(next));
      if (id !== requestId.current) return;
      applyPlan(next, result);
    } catch (e) {
      if (id !== requestId.current) return;
      if (e instanceof DatasetChanged) { void reloadActive(e.message); return; }
      setError(e instanceof Error ? e.message : 'Planning failed.');
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  // Every edit re-plans automatically after a short pause, so the numbers react to each change.
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

  // Platform choice: a platform is "off" when its planner cap is zero. Off platforms also leave your roster and requirements,
  // so the baseline you compare against respects the same choice.
  const platformOn = (p: Platform) => inputs.planningContext.maxPerGroup[PLATFORM_COMMUNITY[p]] !== 0;
  const parked = useRef<Partial<Record<Platform, { roster: string[]; include: string[] }>>>({});
  function togglePlatform(p: Platform) {
    const on = platformOn(p);
    if (on && platformsPresent.filter((q) => q !== p).every((q) => !platformOn(q))) return;  // keep at least one platform
    setInputs((current) => {
      const caps = { ...current.planningContext.maxPerGroup };
      const mine = (id: string) => platformOf(byId.get(id) ?? {}) === p;
      let { currentRoster, include } = current;
      if (on) {
        caps[PLATFORM_COMMUNITY[p]] = 0;
        parked.current[p] = { roster: currentRoster.filter(mine), include: include.filter(mine) };
        currentRoster = currentRoster.filter((id) => !mine(id));
        include = include.filter((id) => !mine(id));
      } else {
        delete caps[PLATFORM_COMMUNITY[p]];
        const back = parked.current[p];
        if (back) {
          currentRoster = [...currentRoster, ...back.roster.filter((id) => !currentRoster.includes(id))];
          include = [...include, ...back.include.filter((id) => !include.includes(id))];
          delete parked.current[p];
        }
      }
      return { ...current, planningContext: { ...current.planningContext, maxPerGroup: caps }, currentRoster, include };
    });
  }

  function goToSection(section: string) {
    const target = SECTION_TARGET[section];
    if (target) navigate(target.screen, target.anchor);
  }

  // Another tab or a finished search switched the server's active dataset: follow it instead of showing an ID error.
  async function reloadActive(note: string) {
    ++requestId.current;
    await refreshDatasets();
    await loadDataset();
    setMessages((m) => [...m, { role: 'assistant', text: note, section: 'overview' }]);
  }

  async function activate(id: string) {
    ++requestId.current;  // results of plans started for the previous dataset are ignored
    try {
      await api('/api/datasets/activate', { id });
      await refreshDatasets();
      await loadDataset();
      navigate('overview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not switch datasets.');
    }
  }

  // A prompt searches YouTube; a prompt with a roster maps overlap for exactly the listed channels and reports back in Muse.
  async function discover(text = prompt, roster?: RosterItem[]) {
    if (!text.trim()) return;
    if (!roster) setPrompt(text);
    setError('');
    navigate('overview');
    try {
      const started = await api<{ job: Job }>('/api/discover', { prompt: text.trim(), expandWithUpriver: false, crossPlatform: Boolean(upriverStatus?.configured),
        ...(roster ? { roster } : {}) });
      setJob(started.job);
      if (roster) setChatBusy(true);
      let failures = 0;
      const poll = async () => {
        let current: { job: Job };
        try {
          current = await api<{ job: Job }>(`/api/discover/${started.job.id}`);
          failures = 0;
        } catch {
          failures += 1;
          if (failures < 5) { window.setTimeout(() => void poll(), 3000); return; }
          setJob((j) => (j ? { ...j, status: 'error', error: 'Lost contact with the server during the search. Refresh to check your searches.' } : j));
          setChatBusy(false);
          return;
        }
        setJob(current.job);
        if (current.job.status === 'running') { window.setTimeout(() => void poll(), 1500); return; }
        setChatBusy(false);
        if (current.job.status === 'error') {
          if (roster) setMessages((m) => [...m, { role: 'assistant', text: current.job.error ?? 'Mapping your list failed.', error: true }]);
          return;
        }
        if (current.job.status === 'done' && current.job.dataset_id) {
          await activate(current.job.dataset_id);
          setMessages((m) => [...m, roster
            ? { role: 'assistant', text: `${current.job.message}. The recommended roster from your list is on the Overview and every creator is in the Creators tab. ${aiEnabled ? 'Tell me how to change it: a budget, a creator count, someone to require or drop.' : 'Use the sliders in the prompt field to set the budget and creator count.'}`, section: 'overview' }
            : { role: 'assistant', text: `${current.job.message}. The plan is now for “${text.trim()}”.`, section: 'overview' }]);
        }
      };
      window.setTimeout(() => void poll(), 1200);
    } catch (e) {
      setJob(null);
      setChatBusy(false);
      if (roster) setMessages((m) => [...m, { role: 'assistant', text: e instanceof Error ? e.message : 'Mapping your list failed.', error: true }]);
      else setError(e instanceof Error ? e.message : 'Creator search failed.');
    }
  }

  async function attachRoster(file: File) {
    const roster = parseRoster(await file.text());
    if (roster.length < 2) {
      setMessages((m) => [...m, { role: 'assistant', text: `${file.name} has fewer than two creators I can read. Use one YouTube handle, channel id or URL per line, with an optional topic in a second column.`, error: true }]);
      return;
    }
    setAttachment({ name: file.name, roster: roster.slice(0, 60) });
    setChatOpen(true);
  }

  async function send(text = draft) {
    const message = text.trim();
    if (chatBusy) return;
    if (attachment) {
      // The attached list is the brief: Muse maps overlap for those channels, then the conversation continues on the result.
      const ask = message || `Map audience overlap for the creators in ${attachment.name}`;
      const name = attachment.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim();
      const brief = (message.length >= 3 ? message : name.length >= 3 ? name : 'Creator list').slice(0, 300);
      setChatOpen(true);
      setDraft('');
      setMessages((m) => [...m, { role: 'user', text: ask, attachment: `${attachment.name} · ${attachment.roster.length} creators` },
        { role: 'assistant', text: `Reading ${attachment.roster.length} creators from your list. I look up each channel, sample who comments on their recent videos and map where those audiences overlap. This takes a few minutes; progress is on the Overview.`, section: 'overview' }]);
      const roster = attachment.roster;
      setAttachment(null);
      await discover(brief, roster);
      return;
    }
    if (!message) return;
    setChatOpen(true);
    setDraft('');
    const history = messages.slice(-6).map((m) => ({ role: m.role, text: m.text }));
    setMessages((m) => [...m, { role: 'user', text: message }]);
    setChatBusy(true);
    const sent = inputsRef.current;
    try {
      const reply = await api<{ intent: string; reply: string; section: string | null; discoverPrompt?: string | null; inputs?: Inputs; plan?: Plan; change?: { changed: boolean; text: string } }>(
        '/api/assistant', { message, inputs: outbound(sent), history });
      if (reply.inputs && reply.plan && key(inputsRef.current) !== key(sent)) {
        setMessages((m) => [...m, { role: 'assistant', text: 'You changed the plan while I was working, so I didn’t apply my change over yours. Ask again and I’ll start from your latest settings.', error: true }]);
        return;
      }
      if (reply.inputs && reply.plan) {
        applyPlan(reply.inputs, reply.plan);
        setInputs(reply.inputs);
      }
      setMessages((m) => [...m, { role: 'assistant', text: reply.reply, change: reply.change, section: reply.section, discoverPrompt: reply.discoverPrompt }]);
      if (reply.section && reply.intent !== 'discover') goToSection(reply.section);
    } catch (e) {
      if (e instanceof DatasetChanged) { void reloadActive(e.message + ' Ask again and I’ll use this search.'); return; }
      setMessages((m) => [...m, { role: 'assistant', text: e instanceof Error ? e.message : 'Something went wrong.', error: true }]);
    } finally {
      setChatBusy(false);
    }
  }

  const planIds = plan ? new Set(plan.recommended.ids) : null;
  const statusOf = (id: string): RosterStatus => inputs.exclude.includes(id) ? 'excluded' : inputs.include.includes(id) ? 'required' : !planIds ? 'none' : planIds.has(id) ? 'recommended' : 'left';
  const rec = plan?.rosterDiagnostics?.rosters.recommended;
  const cur = plan?.rosterDiagnostics?.rosters.current;
  const stepIndex = job ? STEPS.findIndex(([id]) => id === job.step) : -1;
  const savedHere = saved.filter((c) => c.datasetVersion === datasetVersion);
  const otherSearches = datasets.filter((d) => !d.active).slice(0, 3);
  const platformsOn = platformsPresent.filter(platformOn);
  const platformsOff = platformsPresent.filter((p) => !platformOn(p));
  const firstLeftOut = plan?.whyNot?.[0]?.creatorName;
  const suggestions = ['Less overlap', 'Make it cheaper', firstLeftOut ? `Why was ${firstLeftOut} left out?` : 'Where do I see why a creator was left out?'];

  // Share of a plan creator's audience that another plan creator also reaches, from the overlap graph.
  function overlapFor(id: string): { share: number; source: string } | null {
    if (!graph || !planIds) return null;
    const me = graph.nodes.find((n) => n.id === id);
    if (!me || !me.sampledCommenters) return null;
    let best: { share: number; source: string } | null = null;
    for (const p of graph.pairs) {
      if ((p.a !== id && p.b !== id) || p.sharedCommenters <= 0) continue;
      const other = p.a === id ? p.b : p.a;
      if (!planIds.has(other)) continue;
      const share = p.sharedCommenters / me.sampledCommenters;
      if (!best || share > best.share) best = { share, source: p.source ?? 'measured' };
    }
    return best;
  }

  const sourcing = !crossPlatform && !upriverStatus?.configured
    ? 'Pulls creators from YouTube; add UPRIVER_API_KEY on the server for TikTok and Instagram.'
    : platformsOff.length === 0 || platformsPresent.length <= 1
      ? 'Pulls creators from YouTube, TikTok and Instagram automatically. Overlap is measured where comments are public and estimated everywhere else.'
      : `Planning across ${listOf(platformsOn.map((p) => PLATFORM_LABEL[p]))} only; ${listOf(platformsOff.map((p) => PLATFORM_LABEL[p]))} ${platformsOff.length > 1 ? 'are' : 'is'} switched off.`;
  const caveat = evidence && evidence.strength !== 'strong'
    ? `${evidence.strength === 'thin' ? 'Thin evidence' : 'Limited evidence'}: a typical creator here has about ${evidence.medianSampledCommenters.toLocaleString('en-US')} sampled commenters, so small overlap differences are rough. Channels with comments turned off can’t be measured.`
    : plan?.countNote && !stale ? plan.countNote : '';
  const insight = plan && rec
    ? `${rec.ids.length} creators, ${pct(rec.sharedRate)} ${crossPlatform ? 'estimated ' : ''}overlap, ${money(rec.spend)} of ${money(plan.budget)}.${plan.choice?.headline ? ` ${plan.choice.headline}` : ''}${plan.steps[0]?.reason ? ` ${plan.steps[0].reason}` : plan.steps[0] ? ` Next move: check whether ${plan.steps[0].creatorName} should be required, re-priced or swapped.` : ''}`
    : '';

  return (
    <div className="app">
      <header className="app-topbar">
        <a className="app-brand" href="#/overview" aria-label="Unique Reach home">
          <img src={whiteWordmark} alt="Brand Muse" />
          <span className="eyebrow-wide">Unique Reach</span>
        </a>
        <nav className="app-nav" aria-label="Sections">
          {NAV.map(({ label, icon: Icon, screen, anchor }) => (
            <button type="button" key={label} className={route.screen === screen && (route.anchor || '') === (anchor ?? '') ? 'active' : ''} onClick={() => navigate(screen, anchor)}>
              <Icon size={16} />{label}
            </button>
          ))}
        </nav>
        <div className="app-topbar-right">
          <button type="button" className="app-icon-btn" aria-label="Notifications" title={loading || stale ? 'Updating the plan' : 'Plan is up to date'}>
            {loading || stale ? <Loader2 size={20} className="spin" /> : <Bell size={20} />}
          </button>
          <button type="button" className="app-account" aria-label="Account"><User size={22} /></button>
        </div>
      </header>

      {route.screen === 'overview' && (
        <div className="app-screen">
          <section className="app-hero">
            <div className="app-hero-brand"><Mark size={32} /><img src={whiteWordmark} alt="Brand Muse" /></div>
            <h1 className="hero-question">What are you launching?</h1>
            <form className="app-prompt" onSubmit={(e) => { e.preventDefault(); void discover(); }}>
              <input ref={promptRef} value={prompt} onChange={(e) => setPrompt(e.target.value)} aria-label="Campaign brief" maxLength={300} disabled={job?.status === 'running'}
                placeholder="Describe what you're launching: the product, who it's for, which platforms" />
              <kbd aria-hidden="true">&#8984;K</kbd>
              <button type="button" className={`app-prompt-btn ${settingsOpen ? 'on' : ''}`} aria-label="Platforms and budget" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}><SlidersHorizontal size={18} /></button>
              <button type="submit" className="app-prompt-btn solid" aria-label="Find creators" disabled={!discoveryEnabled || !prompt.trim() || job?.status === 'running'}
                title={discoveryEnabled ? 'Find creators' : 'Creator search needs the YouTube and Gemini keys on the server'}>
                {job?.status === 'running' ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
              </button>
              {settingsOpen && (
                <div className="app-popover" ref={popoverRef} role="dialog" aria-label="Platforms and budget">
                  <div className="app-popover-row">
                    <label className="app-field-label grow"><span>Budget</span>
                      <span className="app-money"><b>$</b><input inputMode="numeric" value={inputs.budget.toLocaleString('en-US')} aria-label="Budget"
                        onChange={(e) => update({ budget: Number(e.target.value.replace(/[^0-9]/g, '')) || 0 })} /></span>
                    </label>
                    <label className="app-field-label"><span>Creators</span>
                      <span className="app-count">
                        <button type="button" aria-label="Fewer creators" onClick={() => update({ planningContext: { ...inputs.planningContext, creatorCount: Math.max((inputs.planningContext.creatorCount ?? 0) - 1, 0) } })}>&minus;</button>
                        <b>{inputs.planningContext.creatorCount ? inputs.planningContext.creatorCount : 'Any'}</b>
                        <button type="button" aria-label="More creators" onClick={() => update({ planningContext: { ...inputs.planningContext, creatorCount: Math.min((inputs.planningContext.creatorCount ?? 0) + 1, Math.max(eligible.length, 1)) } })}>+</button>
                      </span>
                    </label>
                  </div>
                  {crossPlatform && platformsPresent.length > 1 && (
                    <div className="app-field-label"><span>Platforms in the plan</span>
                      <div className="app-platform-toggles">
                        {platformsPresent.map((p) => {
                          const on = platformOn(p);
                          return (
                            <label key={p} className={`app-toggle ${on ? 'on' : ''}`} title={on ? `Leave ${PLATFORM_LABEL[p]} out of the plan` : `Plan with ${PLATFORM_LABEL[p]} again`}>
                              <input type="checkbox" checked={on} onChange={() => togglePlatform(p)} />
                              <PlatformGlyph platform={p} size={20} />{PLATFORM_LABEL[p]}
                              <span className="app-chip-count">{eligible.filter((c) => platformOf(c) === p).length}</span>
                            </label>
                          );
                        })}
                      </div>
                      <span className="app-footnote">Switching a platform off removes its creators from the plan and from your roster; switching it back on restores them. At least one stays on.</span>
                    </div>
                  )}
                  <div className="app-popover-row">
                    <label className="app-field-label grow"><span>Save this plan as</span>
                      <input className="app-input" aria-label="Campaign name" maxLength={80} value={saveName} onChange={(e) => setSaveName(e.target.value)} />
                    </label>
                    <button type="button" className="app-btn-primary" disabled={saving || loading || chatBusy || !saveName.trim()} onClick={() => void saveCurrentCampaign()}>Save</button>
                  </div>
                  {savedHere.length > 0 && (
                    <label className="app-field-label"><span>Load a saved plan</span>
                      <select className="app-select" aria-label="Load campaign" value="" disabled={loading || chatBusy} onChange={(e) => void restoreCampaign(e.target.value)}>
                        <option value="">Choose a saved plan</option>
                        {savedHere.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </label>
                  )}
                  {saveStatus && <span className="app-footnote" role="status">{saveStatus}</span>}
                </div>
              )}
            </form>
            <p className="app-sourcing">
              <span className="app-sourcing-glyphs">{(platformsOn.length ? platformsOn : PLATFORMS).map((p) => <PlatformGlyph key={p} platform={p} size={20} />)}</span>
              {sourcing}
            </p>
            {job && (
              <div className={`app-stepper ${job.status}`} aria-live="polite">
                <div className="app-stepper-steps">
                  {STEPS.map(([id, label], i) => {
                    const state = job.status === 'done' || i < stepIndex ? 'done' : i === stepIndex ? (job.status === 'error' ? 'error' : 'now') : 'todo';
                    return <span key={id} className={`step ${state}`}>{state === 'done' ? <Check size={11} /> : null} {label}</span>;
                  })}
                </div>
                <div className="app-bar app-bar-6"><i style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
                <p>{job.status === 'error' ? job.error : job.message}{job.units ? ` · ~${job.units} API units` : ''}</p>
              </div>
            )}
            <div className="app-chip-row center">
              {savedHere.slice(0, 3).map((c) => <Chip key={c.id} onClick={() => void restoreCampaign(c.id)} title="Load this saved plan">{c.name}</Chip>)}
              {otherSearches.map((d) => <Chip key={d.id} onClick={() => void activate(d.id)} title={d.prompt ?? d.name}>{d.name}</Chip>)}
              <Chip onClick={() => void send('Pressure-test the current roster')} disabled={!aiEnabled} title={aiEnabled ? undefined : 'Live AI is not configured'}>Pressure-test the current roster</Chip>
              <Chip onClick={() => navigate('creators', 'whynot')}><Sparkles size={14} /> Why creators were left out</Chip>
            </div>
          </section>

          <section className="app-section" aria-label="Plan summary" style={{ gap: 16 }}>
            {error && <p className="app-alert" role="alert">{error}</p>}
            {plan && rec && cur ? (
              <div className="app-grid-3">
                <StatCard accent value={pct(rec.sharedRate)} label={crossPlatform ? 'Estimated overlap' : 'Audience overlap'} caption="Recommended plan · lower is better" />
                <StatCard value={compact(plan.recommended.proxyReach)} label={crossPlatform ? 'Unique followers' : 'Commenters reached'} caption={cur.ids.length ? `vs ${compact(plan.current.proxyReach)} in your roster` : 'Tick creators to compare your roster'} />
                <StatCard value={money(rec.spend)} label="Spend" caption={`of ${money(plan.budget)} budget`} />
              </div>
            ) : <div className="app-empty">{error ? 'The plan could not be computed.' : 'Planning…'}</div>}
            {caveat && <p className="app-caveat">{caveat}</p>}
            {delta && (delta.added.length > 0 || delta.removed.length > 0) && (
              <p className="app-caveat app-undo-line">
                <span>{delta.subject === 'roster' ? 'Your roster changed' : 'The plan changed'}: {[delta.added.length ? `added ${delta.added.map((id) => names[id] ?? id).join(', ')}` : '', delta.removed.length ? `removed ${delta.removed.map((id) => names[id] ?? id).join(', ')}` : ''].filter(Boolean).join(' · ')}.</span>
                <button type="button" className="app-link" onClick={() => { const prev = delta.previous; setDelta(null); setInputs(prev); }}>Undo</button>
              </p>
            )}
          </section>

          <section className="app-section" aria-label="Recommended roster">
            <EyebrowRow label="Recommended roster" link="View all" onLink={() => navigate('creators')} />
            {insight && <Insight>{insight}</Insight>}
            {plan && (
              <div className="app-grid-2">
                {plan.recommended.ids.map((id) => {
                  const c = byId.get(id);
                  if (!c) return null;
                  const ov = overlapFor(id);
                  const platform = platformOf(c);
                  const status = statusOf(id);
                  return (
                    <article className="app-card app-creator-card" key={id}>
                      <div className="app-creator-top">
                        <Avatar name={c.name} platform={crossPlatform ? platform : undefined} />
                        <div className="app-creator-id">
                          <strong>{c.name}</strong>
                          <span>{PLATFORM_LABEL[platform]} &middot; {topicOf(c)}</span>
                          <small>{status === 'required' ? 'Required' : 'In the plan'}</small>
                        </div>
                      </div>
                      <div className="app-creator-stats">
                        <div><strong>{compact(c.followers ?? c.estimatedViews)}</strong><span>{crossPlatform || c.followers ? 'Followers' : 'Views'}</span></div>
                        <div><strong>{money(inputs.costs[id] ?? c.baseCost)}</strong><span>Quote</span></div>
                        <div><strong>{ov ? pct(ov.share) : '—'}</strong><span>Overlap{ov && ov.source !== 'measured' ? ` · ${ov.source}` : ''}</span></div>
                      </div>
                    </article>
                  );
                })}
                {eligible.length > plan.recommended.ids.length && (
                  <button type="button" className="app-card app-more-card" onClick={() => navigate('creators', 'whynot')}>
                    {eligible.length - plan.recommended.ids.length} more in the pool. See why they were left out <ChevronRight size={14} />
                  </button>
                )}
              </div>
            )}
          </section>

          {plan?.rosterDiagnostics && (
            <section className="app-section" aria-label="Plan at a glance">
              <EyebrowRow label="Plan at a glance" link="How estimates work" onLink={() => navigate('methods')} />
              <div className="app-grid-2">
                <OverlapBars rosters={plan.rosterDiagnostics.rosters} cross={crossPlatform} />
                <PickBars steps={plan.steps} cross={crossPlatform} />
              </div>
            </section>
          )}
        </div>
      )}

      {route.screen === 'creators' && (
        <CreatorsScreen creators={creators} inputs={inputs} plan={plan} stale={stale} crossPlatform={crossPlatform} rosterBasis={rosterBasis} graph={graph} aiEnabled={aiEnabled}
          statusOf={statusOf} platformOn={platformOn} onUpdate={update} onAsk={(q) => void send(q)} onExplain={() => navigate('methods')} onGraph={setGraph} />
      )}

      {route.screen === 'methods' && <MethodsScreen method={method} />}

      <MusePanel open={chatOpen} onToggle={setChatOpen} messages={messages} busy={chatBusy} aiEnabled={aiEnabled} draft={draft} onDraft={setDraft} onSend={(t) => void send(t)}
        suggestions={suggestions} sectionLabel={(s) => SECTION_TARGET[s]?.label ?? null} onSection={goToSection} discoveryEnabled={discoveryEnabled && job?.status !== 'running'} onDiscover={(p) => void discover(p)}
        rosterEnabled={rosterEnabled && job?.status !== 'running'} attachment={attachment} onAttach={(f) => void attachRoster(f)} onDetach={() => setAttachment(null)} />
    </div>
  );
}

function listOf(items: string[]) {
  return items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

function OverlapBars({ rosters, cross }: { rosters: { current: RosterDiag; recommended: RosterDiag; viewsBaseline: RosterDiag }; cross: boolean }) {
  const rows = [
    { key: 'current', label: 'Your roster', color: 'var(--bm-chart-current)', d: rosters.current },
    { key: 'recommended', label: 'Recommended', color: 'var(--app-accent)', d: rosters.recommended },
    { key: 'viewsBaseline', label: cross ? 'Top by followers' : 'Top by views', color: 'var(--bm-chart-baseline)', d: rosters.viewsBaseline },
  ];
  const max = Math.max(...rows.map((r) => r.d.standalone), 1);
  return (
    <div className="app-card app-chart">
      <h3>How much each roster overlaps</h3>
      <p>Solid bar: {cross ? 'followers' : 'commenters'} reached once. Striped end: the same {cross ? 'followers' : 'commenters'} showing up on another creator in the roster.</p>
      <div className="app-chart-rows">
        {rows.map((r) => (
          <div className="app-chart-row" key={r.key} title={`${r.label}: ${compact(r.d.coverage)} reached once, ${compact(r.d.shared)} overlapping`}>
            <span>{r.label}</span>
            <div className="app-track" aria-hidden="true">
              <i style={{ width: `${(r.d.coverage / max) * 100}%`, background: r.color }} />
              <i style={{ width: `${(r.d.shared / max) * 100}%`, background: `repeating-linear-gradient(135deg, ${r.color} 0 3px, transparent 3px 7px)` }} />
            </div>
            <b>{r.d.ids.length ? pct(r.d.sharedRate) : '—'}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function PickBars({ steps, cross }: { steps: Plan['steps']; cross: boolean }) {
  const max = Math.max(...steps.map((s) => s.marginalProxyReach), 1);
  return (
    <div className="app-card app-chart">
      <h3>What each pick adds</h3>
      <p>New {cross ? 'followers' : 'commenters'} each creator adds, in the order the plan picked them.</p>
      {steps.length === 0 ? <div className="app-empty">Nothing fits this budget yet.</div> : (
        <>
          <div className="app-columns" aria-hidden="true">
            {steps.map((s, i) => <div key={`${s.creatorId}-${i}`} style={{ height: `${Math.max((s.marginalProxyReach / max) * 100, 4)}%` }} title={`#${i + 1} ${s.creatorName}: adds ${compact(s.marginalProxyReach)} for ${money(s.cost)}`} />)}
          </div>
          <div className="app-columns-axis">{steps.map((s, i) => <span key={`${s.creatorId}-${i}`}>{i + 1}</span>)}</div>
          <p className="app-columns-note">pick order &middot; first bar &asymp; {compact(steps[0].marginalProxyReach)}</p>
        </>
      )}
    </div>
  );
}
