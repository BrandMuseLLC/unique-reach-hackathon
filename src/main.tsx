import React, { useEffect, useMemo, useId, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AlertTriangle, ArrowUpDown, BarChart3, ListFilter, Network, RefreshCw, Save, Search, Sparkles, Trash2, Users, X } from 'lucide-react';
import './styles.css';
import { ExploreOverlap } from './ExploreOverlap';
import blackWordmark from '../brandmuse/assets/brand-muse-wordmark-black.png';

type Creator = {
  id: string;
  name: string;
  vertical: string;
  audienceNote: string;
  category: string;
  categorySource: 'synthetic-observed' | 'synthetic-inferred' | 'editorial-public-content' | 'unknown';
  eligibilityStatus: 'eligible' | 'ineligible' | 'unknown';
  eligibilityReason: string;
  evidenceState: 'observed' | 'observed_zero' | 'not_collected' | 'unavailable_api' | 'quota_limited' | 'permission_limited' | 'parse_failed';
  sampleSize: number;
  sampleUnit?: string;
  source: 'synthetic' | 'observed-public';
  viewsBasis?: string;
  estimatedViews: number;
  costBasis?: string;
  baseCost: number;
  commenterCount: number;
  videoCount?: number;
  sourceUrl?: string;
};

type PlanningContext = { brandDescription: string; relevance: Record<string, number>; maxPerGroup: Record<string, number> };
const EMPTY_CONTEXT: PlanningContext = { brandDescription: "", relevance: {}, maxPerGroup: {} };

type Score = {
  ids: string[];
  spend: number;
  proxyReach: number;
  rawViews: number;
  overlappingCommenters: number;
  evidenceNote: string;
  flaggedIds: string[];
  notes: string[];
  metricUnit?: string;
};

type CreatorMetricLabels = {
  views: string;
  price: string;
  rawViews: string;
};

type DiagnosticTopic = {
  name: string;
  count: number;
  spend: number;
  views: number;
};

type DiagnosticEvidence = {
  state: Creator['evidenceState'];
  count: number;
};

type RosterDiagnostic = {
  ids: string[];
  spend: number;
  coverage: number;
  standalone: number;
  shared: number;
  sharedRate: number;
  topics: DiagnosticTopic[];
  evidence: DiagnosticEvidence[];
};

type PairOverlap = {
  a: string;
  b: string;
  count: number;
};

type RosterDiagnostics = {
  unitLabel: string;
  caveat: string;
  comparisonNote: string;
  maxPairOverlap: number;
  rosters: {
    current: RosterDiagnostic;
    recommended: RosterDiagnostic;
    viewsBaseline: RosterDiagnostic;
  };
  pairOverlaps: {
    current: PairOverlap[];
    recommended: PairOverlap[];
    viewsBaseline: PairOverlap[];
  };
};

type PlanResult = {
  campaign: {
    id: string;
    name: string;
    category: string;
    audience: string;
    eligibleCategories: string[];
  };
  datasetLabel: string;
  datasetKind?: string;
  datasetVersion?: string;
  metricLabel: string;
  creatorMetricLabels?: CreatorMetricLabels;
  planningMethod?: string;
  comparisonPolicy?: string;
  budget: number;
  current: Score;
  recommended: Score;
  viewsBaseline: Score;
  rosterDiagnostics?: RosterDiagnostics;
  steps: Array<{
    creatorId: string;
    creatorName: string;
    marginalProxyReach: number;
    cost: number;
    reason: string;
  }>;
  currentFlags: string[];
  remainingBudget: number;
};

type SavedCampaign = {
  id: string;
  name: string;
  budget: number;
  currentRoster: string[];
  include: string[];
  exclude: string[];
  costs: Record<string, number>;
  planningContext: PlanningContext;
  campaignBrief: PlanResult['campaign'];
  datasetVersion: string;
  sharedDemo: boolean;
  createdAt: string;
  updatedAt: string;
};

type CreatorsPayload = {
  campaign: PlanResult['campaign'];
  datasetLabel: string;
  datasetVersion: string;
  creatorMetricLabels?: CreatorMetricLabels;
  creators: Creator[];
  defaultCurrentRoster?: string[];
  defaultBudget?: number;
};

type PlanInputs = {
  budget: number;
  currentRoster: string[];
  include: string[];
  exclude: string[];
  costs: Record<string, number>;
  planningContext: PlanningContext;
};

type FitFilter = 'all' | Creator['eligibilityStatus'];
type SortKey = 'creator' | 'fit' | 'evidence' | 'views' | 'cost';
type SortDirection = 'asc' | 'desc';
type ConstraintMode = 'include' | 'exclude' | 'neutral';

const DEFAULT_CURRENT = ['lena-labs', 'maya-mirror', 'glow-and-go'];
const DATASET_VERSION = 'synthetic-youtube-beauty-v2';
const DEFAULT_CAMPAIGN_NAME = 'Judge demo SPF plan';
const DEFAULT_DATASET_LABEL = 'Deterministic synthetic YouTube roster dataset; fictional creators and commenter ids.';
const DEFAULT_CREATOR_METRIC_LABELS: CreatorMetricLabels = {
  views: 'Expected video views',
  price: 'Sponsorship fee (USD)',
  rawViews: 'Total expected views',
};
const FIT_RANK: Record<Creator['eligibilityStatus'], number> = { eligible: 0, unknown: 1, ineligible: 2 };
const EVIDENCE_RANK: Record<Creator['evidenceState'], number> = {
  observed: 0,
  observed_zero: 1,
  quota_limited: 2,
  permission_limited: 3,
  unavailable_api: 4,
  parse_failed: 5,
  not_collected: 6,
};

function formatMoney(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
}

function formatCompact(value: number) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 }).format(value);
}

function formatSigned(value: number) {
  const formatted = formatNumber(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

function evidenceLabel(state: Creator['evidenceState']) {
  return state.replace(/_/g, ' ');
}

function evidenceStatusLabel(state: Creator['evidenceState']) {
  return {
    observed: 'Observed',
    observed_zero: 'Observed zero',
    not_collected: 'Not collected',
    unavailable_api: 'Unavailable',
    quota_limited: 'Quota limited',
    permission_limited: 'Permission limited',
    parse_failed: 'Parse failed',
  }[state];
}

function sampleLabel(creator: Creator) {
  return creator.sampleUnit?.replace(/_/g, ' ') ?? 'samples';
}

function parseMoney(value: string) {
  const compact = value.trim().replace(/[$,\s]/g, '');
  if (/[−-]/.test(compact) || /^\(.*\)$/.test(compact)) return 0;
  const wholeDollars = compact.split('.')[0] ?? '';
  const digits = wholeDollars.replace(/[^\d]/g, '');
  if (!digits) return 0;
  const parsed = Number(digits);
  return Number.isSafeInteger(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}

function planInputsEqual(left: PlanInputs | null, right: PlanInputs | null) {
  if (!left || !right) return false;
  const sameIds = (a: string[], b: string[]) => a.length === b.length && a.every((id, index) => id === b[index]);
  const costKeys = Array.from(new Set([...Object.keys(left.costs), ...Object.keys(right.costs)])).sort();
  return left.budget === right.budget
    && sameIds(left.currentRoster, right.currentRoster)
    && sameIds(left.include, right.include)
    && sameIds(left.exclude, right.exclude)
    && costKeys.every((key) => left.costs[key] === right.costs[key])
    && JSON.stringify(left.planningContext) === JSON.stringify(right.planningContext);
}

function sameRosterSet(left: string[], right: string[]) {
  return left.length === right.length && left.every((id) => right.includes(id));
}

function formatMetricDelta(value: number, formatter: (amount: number) => string) {
  if (value > 0) return `up ${formatter(value)}`;
  if (value < 0) return `down ${formatter(Math.abs(value))}`;
  return `unchanged`;
}

function rosterOutcomeText(result: PlanResult) {
  const diagnostics = result.rosterDiagnostics;
  const currentIds = result.current.ids;
  const recommendedIds = result.recommended.ids;
  const sameCreators = sameRosterSet(currentIds, recommendedIds);
  const proxyDelta = result.recommended.proxyReach - result.current.proxyReach;
  const coverageDelta = diagnostics ? diagnostics.rosters.recommended.coverage - diagnostics.rosters.current.coverage : 0;
  const sharedDelta = diagnostics ? diagnostics.rosters.recommended.shared - diagnostics.rosters.current.shared : 0;
  const unitLabel = diagnostics?.unitLabel ?? 'commenters';

  if (sameCreators && proxyDelta === 0 && coverageDelta === 0 && sharedDelta === 0) {
    return `No metric change: the recommendation uses the same ${recommendedIds.length} creators as the current roster. Proxy score, ${unitLabel} covered, and shared-commenter penalty are unchanged.`;
  }

  const added = recommendedIds.filter((id) => !currentIds.includes(id)).length;
  const removed = currentIds.filter((id) => !recommendedIds.includes(id)).length;
  const rosterChange = sameCreators ? 'keeps the same creator set' : `swaps ${removed} out and ${added} in`;
  return `Recommendation ${rosterChange}. Proxy score is ${formatMetricDelta(proxyDelta, formatNumber)}; ${unitLabel} covered is ${formatMetricDelta(coverageDelta, formatNumber)}; shared-commenter penalty is ${formatMetricDelta(sharedDelta, formatNumber)}.`;
}

function App() {
  const [planningContext, setPlanningContext] = useState<PlanningContext>(EMPTY_CONTEXT);
  const [aiStatus, setAiStatus] = useState({ enabled: false, message: 'Checking live AI availability.' });
  const [aiMessage, setAiMessage] = useState('');
  const [aiReply, setAiReply] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [creators, setCreators] = useState<Creator[]>([]);
  const [budget, setBudget] = useState(139000);
  const [costs, setCosts] = useState<Record<string, number>>({});
  const [currentRoster, setCurrentRoster] = useState<string[]>(DEFAULT_CURRENT);
  const [include, setInclude] = useState<string[]>([]);
  const [exclude, setExclude] = useState<string[]>([]);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [plannedInputs, setPlannedInputs] = useState<PlanInputs | null>(null);
  const [savedCampaigns, setSavedCampaigns] = useState<SavedCampaign[]>([]);
  const [activeCampaignId, setActiveCampaignId] = useState('');
  const [campaignName, setCampaignName] = useState(DEFAULT_CAMPAIGN_NAME);
  const [defaultCampaignName, setDefaultCampaignName] = useState(DEFAULT_CAMPAIGN_NAME);
  const [datasetVersion, setDatasetVersion] = useState(DATASET_VERSION);
  const [datasetLabel, setDatasetLabel] = useState(DEFAULT_DATASET_LABEL);
  const [saveMessage, setSaveMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [fitFilter, setFitFilter] = useState<FitFilter>('all');
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('fit');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [creatorMetricLabels, setCreatorMetricLabels] = useState<CreatorMetricLabels>(DEFAULT_CREATOR_METRIC_LABELS);
  const [activeCreatorId, setActiveCreatorId] = useState('');
  const planRequestId = useRef(0);
  const latestInputs = useRef<PlanInputs>({ budget, currentRoster, include, exclude, costs, planningContext });

  const creatorById = useMemo(() => Object.fromEntries(creators.map((creator) => [creator.id, creator])), [creators]);
  const activeInputs = useMemo(() => ({ budget, currentRoster, include, exclude, costs, planningContext }), [budget, costs, currentRoster, exclude, include, planningContext]);
  const activeInputsRef = useRef(activeInputs);
  activeInputsRef.current = activeInputs;
  const resultIsStale = Boolean(result && !loading && !planInputsEqual(activeInputs, plannedInputs));
  const selectedSpend = useMemo(
    () => currentRoster.reduce((total, id) => total + (costs[id] ?? creatorById[id]?.baseCost ?? 0), 0),
    [costs, creatorById, currentRoster],
  );
  const filteredCreators = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    const filtered = creators.filter((creator) => {
      const selected = currentRoster.includes(creator.id);
      const matchesSearch = !query || [
        creator.name,
        creator.vertical,
        creator.audienceNote,
        creator.category,
        creator.eligibilityStatus,
        evidenceLabel(creator.evidenceState),
      ].some((value) => value.toLowerCase().includes(query));
      const matchesFit = fitFilter === 'all' || creator.eligibilityStatus === fitFilter;
      return matchesSearch && matchesFit && (!selectedOnly || selected);
    });
    return filtered.sort((a, b) => {
      const costA = costs[a.id] ?? a.baseCost;
      const costB = costs[b.id] ?? b.baseCost;
      const comparison = {
        creator: a.name.localeCompare(b.name),
        fit: FIT_RANK[a.eligibilityStatus] - FIT_RANK[b.eligibilityStatus] || a.name.localeCompare(b.name),
        evidence: EVIDENCE_RANK[a.evidenceState] - EVIDENCE_RANK[b.evidenceState] || b.sampleSize - a.sampleSize,
        views: b.estimatedViews - a.estimatedViews,
        cost: costA - costB,
      }[sortKey];
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [costs, creators, currentRoster, fitFilter, searchTerm, selectedOnly, sortDirection, sortKey]);
  const activeCreator = creatorById[activeCreatorId] ?? filteredCreators[0] ?? creators[0];

  useEffect(() => {
    latestInputs.current = activeInputs;
  }, [activeInputs]);

  useEffect(() => {
    fetch('/api/ai/status').then(response => {
      if (!response.ok) throw new Error();
      return response.json();
    }).then(setAiStatus).catch(() => setAiStatus({ enabled: false, message: 'Live AI unavailable. Manual planning remains available.' }));
    fetch('/api/creators')
      .then((response) => response.json())
      .then((payload: CreatorsPayload) => {
        const nextDefaultName = `${payload.campaign.name} plan`;
        setDatasetVersion(payload.datasetVersion);
        setDatasetLabel(payload.datasetLabel);
        setDefaultCampaignName(nextDefaultName);
        setCampaignName((name) => (name === DEFAULT_CAMPAIGN_NAME ? nextDefaultName : name));
        setCreators(payload.creators);
        setActiveCreatorId((id) => id || payload.creators[0]?.id || '');
        setCreatorMetricLabels({ ...DEFAULT_CREATOR_METRIC_LABELS, ...payload.creatorMetricLabels });
        if (payload.defaultBudget !== undefined) setBudget(payload.defaultBudget);
        if (payload.defaultCurrentRoster) setCurrentRoster(payload.defaultCurrentRoster);
        setCosts(Object.fromEntries(payload.creators.map((creator: Creator) => [creator.id, creator.baseCost])));
        void loadCampaigns();
      })
      .catch(() => setError('Could not load the local planner dataset. Is the FastAPI server running?'));
  }, []);

  useEffect(() => {
    if (creators.length > 0) {
      void runPlan();
    }
  }, [creators.length]);

  function currentInputs(overrides: Partial<PlanInputs> = {}): PlanInputs {
    return {
      ...latestInputs.current,
      ...overrides,
    };
  }

  async function runPlan(overrides: Partial<PlanInputs> = {}) {
    const inputs = currentInputs(overrides);
    const requestId = planRequestId.current + 1;
    planRequestId.current = requestId;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputs),
      });
      const payload = await response.json();
      if (requestId !== planRequestId.current) return;
      if (!response.ok) {
        setError(payload.error ?? 'Could not run planner.');
        setResult(null);
        return;
      }
      setCreatorMetricLabels({ ...DEFAULT_CREATOR_METRIC_LABELS, ...payload.creatorMetricLabels });
      setResult(payload);
      setPlannedInputs(inputs);
    } catch {
      if (requestId !== planRequestId.current) return;
      setError('Could not reach the local optimizer API.');
      setResult(null);
    } finally {
      if (requestId === planRequestId.current) setLoading(false);
    }
  }

  async function interpretBrief() {
    const inputs = currentInputs();
    setAiBusy(true);
    setAiReply('');
    setError('');
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: aiMessage, inputs }),
      });
      const payload = await response.json();
      if (!response.ok) { setAiReply(payload.error ?? 'AI request failed. Your inputs are unchanged.'); return; }
      if (!planInputsEqual(inputs, activeInputsRef.current)) {
        setAiReply('Your inputs changed while AI was working. Please retry with the current plan.'); return;
      }
      setAiReply(payload.reply);
      if (!payload.inputs || !payload.plan) return;
      planRequestId.current += 1;
      setLoading(false);
      setBudget(payload.inputs.budget);
      setInclude(payload.inputs.include);
      setExclude(payload.inputs.exclude);
      setPlanningContext(payload.inputs.planningContext);
      setResult(payload.plan);
      setPlannedInputs(payload.inputs);
    } catch { setAiReply('AI request failed. Your inputs are unchanged.'); }
    finally { setAiBusy(false); }
  }

  async function loadCampaigns() {
    try {
      const response = await fetch('/api/campaigns');
      const payload = await response.json();
      if (response.ok) setSavedCampaigns(payload.campaigns);
    } catch {
      setSaveMessage('Saved demo campaigns are unavailable while the API is offline.');
    }
  }

  async function saveCampaign() {
    const method = activeCampaignId ? 'PUT' : 'POST';
    const url = activeCampaignId ? `/api/campaigns/${activeCampaignId}` : '/api/campaigns';
    setSaveMessage('');
    setError('');
    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: campaignName,
          budget,
          currentRoster,
          include,
          exclude,
          costs,
          planningContext,
          campaignBrief: result?.campaign,
          datasetVersion,
          sharedDemo: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        setError(payload.error ?? 'Could not save campaign.');
        return;
      }
      setActiveCampaignId(payload.campaign.id);
      setCampaignName(payload.campaign.name);
      setSaveMessage(`Saved demo campaign${payload.snapshotUri ? ` and snapshot ${payload.snapshotUri}` : ''}.`);
      await loadCampaigns();
    } catch {
      setError('Could not reach the local campaign store.');
    }
  }

  async function loadCampaign(campaignId: string) {
    if (!campaignId) {
      setActiveCampaignId('');
      setCampaignName(defaultCampaignName);
      setSaveMessage('Ready to save a new demo campaign.');
      return;
    }
    const campaign = savedCampaigns.find((item) => item.id === campaignId);
    if (!campaign) return;
    if (campaign.datasetVersion !== datasetVersion) {
      setError('That saved campaign belongs to a different dataset. Reload the matching dataset first.');
      return;
    }
    setActiveCampaignId(campaign.id);
    setCampaignName(campaign.name);
    setBudget(campaign.budget);
    setCurrentRoster(campaign.currentRoster);
    setInclude(campaign.include);
    setExclude(campaign.exclude);
    setCosts(campaign.costs);
    setPlanningContext(campaign.planningContext ?? EMPTY_CONTEXT);
    setAiReply('');
    setSaveMessage('Loaded demo campaign.');
    await runPlan({
      budget: campaign.budget,
      currentRoster: campaign.currentRoster,
      include: campaign.include,
      exclude: campaign.exclude,
      costs: campaign.costs,
      planningContext: campaign.planningContext ?? EMPTY_CONTEXT,
    });
  }

  async function deleteCampaign() {
    if (!activeCampaignId) return;
    setSaveMessage('');
    try {
      const response = await fetch(`/api/campaigns/${activeCampaignId}`, { method: 'DELETE' });
      if (!response.ok) {
        const payload = await response.json();
        setError(payload.error ?? 'Could not delete campaign.');
        return;
      }
      setActiveCampaignId('');
      setCampaignName(defaultCampaignName);
      setSaveMessage('Deleted demo campaign.');
      await loadCampaigns();
    } catch {
      setError('Could not reach the local campaign store.');
    }
  }

  function toggle(list: string[], setter: (ids: string[]) => void, id: string) {
    setter(list.includes(id) ? list.filter((item) => item !== id) : [...list, id]);
  }

  function constraintFor(id: string): ConstraintMode {
    if (include.includes(id)) return 'include';
    if (exclude.includes(id)) return 'exclude';
    return 'neutral';
  }

  function setConstraint(id: string, mode: ConstraintMode) {
    setInclude((ids) => ids.filter((item) => item !== id));
    setExclude((ids) => ids.filter((item) => item !== id));
    if (mode === 'include') setInclude((ids) => [...ids, id]);
    if (mode === 'exclude') setExclude((ids) => [...ids, id]);
  }

  function updateSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((direction) => (direction === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === 'views' ? 'desc' : 'asc');
  }

  function updateSortControl(value: string) {
    const [key, direction] = value.split(':') as [SortKey, SortDirection];
    setSortKey(key);
    setSortDirection(direction);
  }

  function resetRosterFilters() {
    setSearchTerm('');
    setFitFilter('all');
    setSelectedOnly(false);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <img className="wordmark" src={blackWordmark} alt="Brand Muse" />
          <p>Unique Reach planner for YouTube sponsorship rosters</p>
        </div>
        <button className="primary" onClick={() => void runPlan()} disabled={loading || creators.length === 0}>
          {loading ? <RefreshCw className="spin" size={18} /> : <Sparkles size={18} />}
          Run audit and optimize
        </button>
      </header>

      <section className="panel" aria-label="Campaign brief assistant">
        <div className="panel-heading compact">
          <h2>Campaign brief</h2>
          <p>{aiStatus.message} Relevance weights assess topics, not individual interests or purchase intent.</p>
        </div>
        <div className="save-card">
        <label>
          <span>Describe the product and planning changes</span>
          <input aria-label="Campaign brief message" maxLength={2000} value={aiMessage}
            onChange={event => setAiMessage(event.target.value)}
            placeholder="Science kits for curious adults. Assess topic relevance; keep my required creators and quotes." />
        </label>
        <button className="primary" onClick={() => void interpretBrief()} disabled={!aiStatus.enabled || aiBusy || loading || !aiMessage.trim() || creators.length === 0}>
          {aiBusy ? 'Interpreting brief…' : 'Apply brief with AI'}
        </button>
        <p role="status">{aiReply}</p>
        </div>
        {planningContext.brandDescription && <p>Applied brief: {planningContext.brandDescription}</p>}
        {Object.keys(planningContext.relevance).length > 0 && <p>
          Topic weights: {Object.entries(planningContext.relevance).map(([topic, weight]) => `${topic}: ${weight.toFixed(2)}`).join(' · ')}
        </p>}
        {Object.keys(planningContext.maxPerGroup).length > 0 && <p>
          Topic caps: {Object.entries(planningContext.maxPerGroup).map(([topic, cap]) => `${topic}: ${cap}`).join(' · ')}
        </p>}
        {(planningContext.brandDescription || Object.keys(planningContext.relevance).length > 0 || Object.keys(planningContext.maxPerGroup).length > 0) &&
          <button disabled={aiBusy || loading} onClick={() => { setPlanningContext(EMPTY_CONTEXT); setAiReply(''); void runPlan({ planningContext: EMPTY_CONTEXT }); }}>Clear brief and topic adjustments</button>}
      </section>

      <section className="control-strip">
        <label className="budget-control">
          <span>Planning budget</span>
          <MoneyInput value={budget} onChange={setBudget} ariaLabel="Planning budget" />
        </label>
        <div className="metric-note">
          <strong>{result?.metricLabel ?? 'Overlap-adjusted reach proxy'}</strong>
          <span>{datasetLabel}</span>
        </div>
        {result && (
          <div className="campaign-card">
            <strong>{result.campaign.name}</strong>
            <span>{result.campaign.category} · {result.campaign.audience}</span>
          </div>
        )}
        <div className="save-card">
          <label>
            <span>Saved demo campaign</span>
            <input value={campaignName} onChange={(event) => setCampaignName(event.target.value)} />
          </label>
          <select value={activeCampaignId} onChange={(event) => void loadCampaign(event.target.value)} aria-label="Load saved campaign">
            <option value="">New campaign</option>
            {savedCampaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
            ))}
          </select>
          <div className="save-actions">
            <button onClick={saveCampaign} title="Save demo campaign">
              <Save size={15} />
              Save
            </button>
            <button onClick={deleteCampaign} disabled={!activeCampaignId} title="Delete selected demo campaign">
              <Trash2 size={15} />
              Delete
            </button>
          </div>
          <p className={saveMessage ? undefined : 'sr-only'} aria-live="polite">{saveMessage || 'Campaign status'}</p>
        </div>
        {error && <div className="error" role="alert">{error}</div>}
      </section>

      <section className="workspace">
        <div className="panel roster-panel">
          <div className="panel-heading">
            <h1>Roster Editor</h1>
            <p>Edit shortlist, price, and constraints from one dense grid.</p>
          </div>

          <div className="roster-toolbar" aria-label="Roster filters">
            <label className="search-control">
              <Search size={16} />
              <span className="sr-only">Search creators</span>
              <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search creators" />
            </label>
            <label className="filter-control">
              <ListFilter size={16} />
              <span className="sr-only">Filter by campaign fit</span>
              <select value={fitFilter} onChange={(event) => setFitFilter(event.target.value as FitFilter)} aria-label="Filter by campaign fit">
                <option value="all">All fits</option>
                <option value="eligible">Eligible</option>
                <option value="unknown">Unknown</option>
                <option value="ineligible">Ineligible</option>
              </select>
            </label>
            <label className="filter-control">
              <ArrowUpDown size={16} />
              <span className="sr-only">Sort roster</span>
              <select value={`${sortKey}:${sortDirection}`} onChange={(event) => updateSortControl(event.target.value)} aria-label="Sort roster">
                <option value="fit:asc">Fit</option>
                <option value="creator:asc">Creator A-Z</option>
                <option value="creator:desc">Creator Z-A</option>
                <option value="evidence:asc">Evidence quality</option>
                <option value="views:desc">Views high-low</option>
                <option value="views:asc">Views low-high</option>
                <option value="cost:asc">Quote low-high</option>
                <option value="cost:desc">Quote high-low</option>
              </select>
            </label>
            <button className={`toggle-filter ${selectedOnly ? 'active' : ''}`} type="button" aria-pressed={selectedOnly} onClick={() => setSelectedOnly((value) => !value)}>
              Selected only
            </button>
            <button className="icon-text-button" type="button" onClick={resetRosterFilters} title="Clear roster filters">
              <X size={15} />
              Clear
            </button>
            <div className={`roster-summary ${selectedSpend > budget ? 'over-budget' : ''}`} aria-live="polite">
              <strong>{currentRoster.length}</strong> selected · {formatMoney(selectedSpend)} spend · {filteredCreators.length} shown
            </div>
          </div>

          {activeCreator && (
            <CreatorInspector
              creator={activeCreator}
              selected={currentRoster.includes(activeCreator.id)}
              constraint={constraintFor(activeCreator.id)}
              metricLabels={creatorMetricLabels}
              onToggleCurrent={() => toggle(currentRoster, setCurrentRoster, activeCreator.id)}
              onConstraintChange={(mode) => setConstraint(activeCreator.id, mode)}
            />
          )}

          <div className="roster-table-wrap">
            <table className="creator-table">
              <caption className="sr-only">Creator roster controls</caption>
              <colgroup>
                <col className="current-col" />
                <col className="creator-col" />
                <col className="fit-col" />
                <col className="evidence-col" />
                <col className="views-col" />
                <col className="price-col" />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Current</th>
                  <th scope="col">
                    <button type="button" className="sort-button" onClick={() => updateSort('creator')} aria-label="Sort creators by name">
                      Creator <ArrowUpDown size={13} />
                    </button>
                  </th>
                  <th scope="col">
                    <button type="button" className="sort-button" onClick={() => updateSort('fit')} aria-label="Sort creators by campaign fit">
                      Fit <ArrowUpDown size={13} />
                    </button>
                  </th>
                  <th scope="col">Evidence</th>
                  <th scope="col">
                    <button type="button" className="sort-button" onClick={() => updateSort('views')} aria-label={`Sort creators by ${creatorMetricLabels.views.toLowerCase()}`} title={creatorMetricLabels.views}>
                      Views <ArrowUpDown size={13} />
                    </button>
                  </th>
                  <th scope="col">
                    <button type="button" className="sort-button" onClick={() => updateSort('cost')} aria-label={`Sort creators by ${creatorMetricLabels.price.toLowerCase()}`} title={creatorMetricLabels.price}>
                      Quote <ArrowUpDown size={13} />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredCreators.length === 0 ? (
                  <tr>
                    <td className="empty-row" colSpan={6}>No creators match the current filters.</td>
                  </tr>
                ) : (
                  filteredCreators.map((creator) => {
                    const selected = currentRoster.includes(creator.id);
                    const active = activeCreator?.id === creator.id;
                    return (
                      <tr className={`${selected ? 'selected' : ''} ${active ? 'active' : ''}`} key={creator.id}>
                        <td data-label="Current">
                          <label className="current-toggle compact">
	                            <input
                              type="checkbox"
                              checked={selected}
                              aria-label={`Toggle current roster selection for ${creator.name}`}
                              onChange={() => toggle(currentRoster, setCurrentRoster, creator.id)}
                            />
                            <span className="sr-only">Current roster</span>
                          </label>
                        </td>
                        <td data-label="Creator">
                          <div className="creator-meta">
                            <strong>{creator.name}</strong>
                            <span>{creator.vertical}</span>
                          </div>
                        </td>
	                        <td data-label="Fit">
                          <div className="fit-cell">
                            <span className={`fit-badge ${creator.eligibilityStatus}`}>{creator.eligibilityStatus}</span>
                            <small>{creator.category}</small>
                          </div>
                        </td>
                        <td data-label="Evidence">
                          <button
                            className={`evidence-button ${creator.evidenceState} ${active ? 'active' : ''}`}
                            type="button"
                            aria-pressed={active}
                            aria-label={`Show evidence and constraints for ${creator.name}`}
                            onClick={() => setActiveCreatorId(creator.id)}
                          >
                            <span>{evidenceStatusLabel(creator.evidenceState)}</span>
                            <small>{formatNumber(creator.sampleSize)} {sampleLabel(creator)}</small>
                          </button>
                        </td>
                        <td className="numeric-cell" data-label={creatorMetricLabels.views} title={creatorMetricLabels.views}>{formatNumber(creator.estimatedViews)}</td>
                        <td className="numeric-cell" data-label={creatorMetricLabels.price} title={creatorMetricLabels.price}>
                          <MoneyInput
                            value={costs[creator.id] ?? creator.baseCost}
                            onChange={(value) => setCosts({ ...costs, [creator.id]: value })}
                            ariaLabel={`${creatorMetricLabels.price} for ${creator.name}`}
                            compact
                          />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {creators.some(c => c.source === 'observed-public') && <ExploreOverlap />}

        {result?.rosterDiagnostics && (
          <RosterOverlapPanel result={result} creators={creatorById} stale={resultIsStale} />
        )}

        {result && (
          <section className="results-stack" aria-label="Roster comparison">
            {resultIsStale && (
              <p className="stale-results" role="status">Results are from previous inputs. Run audit and optimize to refresh.</p>
            )}
            <div className="comparison-grid">
              <ScoreCard title="Current roster" score={result.current} creators={creatorById} metricLabels={creatorMetricLabels} />
              <ScoreCard title="Recommended roster" score={result.recommended} creators={creatorById} metricLabels={creatorMetricLabels} highlighted />
              <ScoreCard title={`${creatorMetricLabels.views}-ranked baseline`} score={result.viewsBaseline} creators={creatorById} metricLabels={creatorMetricLabels} />
            </div>
            {result.currentFlags.length > 0 && (
              <section className="warning-panel">
                <AlertTriangle size={18} />
                <div>
                  <strong>Review current roster evidence and comparability.</strong>
                  <p>{result.currentFlags.join(' ')}</p>
                </div>
              </section>
            )}
          </section>
        )}

        {result && (
          <section className="panel steps-panel">
            <div className="panel-heading compact">
              <h2>Marginal Contribution Trace</h2>
              <p>{result.planningMethod ?? "Each step chooses the feasible creator with the best additional overlap-adjusted reach per dollar."}</p>
            </div>
            <div className="steps">
              {result.steps.length === 0 ? (
                <p className="empty-state">No feasible additions improved the roster under the current constraints.</p>
              ) : (
                result.steps.map((step, index) => (
                  <div className="step" key={`${step.creatorId}-${index}`}>
                    <span>{index + 1}</span>
                    <p>{step.reason}</p>
                  </div>
                ))
              )}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

function CreatorInspector({
  creator,
  selected,
  constraint,
  metricLabels,
  onToggleCurrent,
  onConstraintChange,
}: {
  creator: Creator;
  selected: boolean;
  constraint: ConstraintMode;
  metricLabels: CreatorMetricLabels;
  onToggleCurrent: () => void;
  onConstraintChange: (mode: ConstraintMode) => void;
}) {
  const unitLabel = creator.source === 'observed-public' ? 'sampled commenters' : 'synthetic commenters';
  return (
    <section className="creator-inspector" aria-labelledby="creator-inspector-title">
      <div className="inspector-title">
        <div>
          <h2 id="creator-inspector-title">{creator.name}</h2>
          <p>{creator.vertical} · {creator.category}</p>
        </div>
        <span className={`fit-badge ${creator.eligibilityStatus}`}>{creator.eligibilityStatus}</span>
      </div>

      <div className="inspector-controls" aria-label={`Roster controls for ${creator.name}`}>
        <label className="current-toggle">
          <input
            type="checkbox"
            checked={selected}
            aria-label={`Set ${creator.name} as current roster member from detail panel`}
            onChange={onToggleCurrent}
          />
          <span>Current roster</span>
        </label>
        <fieldset className="constraint-group">
          <legend>Optimizer rule</legend>
          <div className="constraint-buttons">
            {[
              ['neutral', 'Can add'],
              ['include', 'Require'],
              ['exclude', 'Exclude'],
            ].map(([mode, label]) => (
              <button
                key={mode}
                className={constraint === mode ? 'active' : undefined}
                type="button"
                aria-pressed={constraint === mode}
                onClick={() => onConstraintChange(mode as ConstraintMode)}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <dl className="inspector-facts">
        <div>
          <dt>{metricLabels.views}</dt>
          <dd>{formatNumber(creator.estimatedViews)}</dd>
        </div>
        <div>
          <dt>Evidence state</dt>
          <dd>{evidenceLabel(creator.evidenceState)}</dd>
        </div>
        <div>
          <dt>Evidence size</dt>
          <dd>{formatNumber(creator.sampleSize)} {sampleLabel(creator)}; {formatNumber(creator.commenterCount)} {unitLabel}{creator.videoCount ? `; ${formatNumber(creator.videoCount)} videos` : ''}</dd>
        </div>
        <div>
          <dt>Fit basis</dt>
          <dd>{creator.eligibilityReason}</dd>
        </div>
        <div>
          <dt>Audience note</dt>
          <dd>{creator.audienceNote}</dd>
        </div>
        {creator.viewsBasis && (
          <div>
            <dt>Views basis</dt>
            <dd>{creator.viewsBasis}</dd>
          </div>
        )}
        {creator.costBasis && (
          <div>
            <dt>Quote basis</dt>
            <dd>{creator.costBasis}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}

function ScoreCard({ title, score, creators, metricLabels, highlighted = false }: { title: string; score: Score; creators: Record<string, Creator>; metricLabels: CreatorMetricLabels; highlighted?: boolean }) {
  return (
    <section className={`score-card ${highlighted ? 'highlighted' : ''}`}>
      <div className="score-title">
        <h2>{title}</h2>
        <BarChart3 size={18} />
      </div>
      <div className="score-metric">
        <Users size={20} />
        <div>
          <strong>{formatNumber(score.proxyReach)}</strong>
          <span>proxy score</span>
        </div>
      </div>
      <dl>
        <div>
          <dt>Spend</dt>
          <dd>{formatMoney(score.spend)}</dd>
        </div>
        <div>
          <dt>{metricLabels.rawViews}</dt>
          <dd>{formatNumber(score.rawViews)}</dd>
        </div>
        <div>
          <dt>{score.metricUnit ? 'Repeated ID appearances' : 'Discounted overlap'}</dt>
          <dd>{formatNumber(score.overlappingCommenters)} {score.metricUnit ? 'extra memberships' : 'commenters'}</dd>
        </div>
      </dl>
      <details className="score-details">
        <summary>{score.ids.length} selected creators</summary>
        <div className="selected-list">
          {score.ids.length === 0 ? (
            <span>No creators selected</span>
          ) : (
            score.ids.map((id) => <span key={id}>{creators[id]?.name ?? id}</span>)
          )}
        </div>
        <p className="evidence-note">{score.evidenceNote}</p>
      </details>
    </section>
  );
}

function RosterOverlapPanel({ result, creators, stale }: { result: PlanResult; creators: Record<string, Creator>; stale: boolean }) {
  const diagnostics = result.rosterDiagnostics;
  if (!diagnostics) return null;
  const current = diagnostics.rosters.current;
  const recommended = diagnostics.rosters.recommended;
  const baseline = diagnostics.rosters.viewsBaseline;
  const sharedDelta = recommended.shared - current.shared;
  const coverageDelta = recommended.coverage - current.coverage;
  const currentSpendDiffers = current.spend !== result.budget;
  const displayMaxPairOverlap = Math.max(0, ...diagnostics.pairOverlaps.current.map((pair) => pair.count), ...diagnostics.pairOverlaps.recommended.map((pair) => pair.count));
  const maxTopicCount = Math.max(1, ...current.topics.map((topic) => topic.count), ...recommended.topics.map((topic) => topic.count), ...baseline.topics.map((topic) => topic.count));

  return (
    <section className="overlap-panel" aria-labelledby="overlap-heading">
      <div className="panel-heading overlap-heading">
        <div>
          <h2 id="overlap-heading">Roster Overlap</h2>
          <p>Before and after shared-commenter structure, using one color scale across matrices.</p>
        </div>
        <div className="overlap-deltas" aria-label="Before and after changes">
          <span><strong>{formatSigned(coverageDelta)}</strong> {diagnostics.unitLabel} covered</span>
          <span><strong>{formatSigned(sharedDelta)}</strong> shared-commenter penalty</span>
        </div>
      </div>
      <p className="overlap-outcome">{rosterOutcomeText(result)}</p>
      {stale && (
        <p className="stale-results" role="status">These overlap diagnostics are from previous inputs.</p>
      )}

      <div className="overlap-summary">
        <DiagnosticSummary title="Current" diagnostic={current} unitLabel={diagnostics.unitLabel} />
        <DiagnosticSummary title="Recommended" diagnostic={recommended} unitLabel={diagnostics.unitLabel} highlighted />
        <DiagnosticSummary title="Views Baseline" diagnostic={baseline} unitLabel={diagnostics.unitLabel} />
      </div>

      <div className="heatmap-grid">
        <OverlapHeatmap
          title="Current roster"
          diagnostic={current}
          pairs={diagnostics.pairOverlaps.current}
          creators={creators}
          maxPairOverlap={displayMaxPairOverlap}
        />
        <OverlapHeatmap
          title="Recommended roster"
          diagnostic={recommended}
          pairs={diagnostics.pairOverlaps.recommended}
          creators={creators}
          maxPairOverlap={displayMaxPairOverlap}
        />
      </div>

      <div className="diagnostic-detail">
        <TopicBars title="Current topics" topics={current.topics} maxCount={maxTopicCount} />
        <TopicBars title="Recommended topics" topics={recommended.topics} maxCount={maxTopicCount} />
        <EvidenceDistribution current={current.evidence} recommended={recommended.evidence} />
      </div>

      <p className="overlap-caveat">
        {diagnostics.comparisonNote} {currentSpendDiffers ? 'Current roster spend differs from the planning budget. ' : ''}
        {diagnostics.caveat}
      </p>
    </section>
  );
}

function DiagnosticSummary({ title, diagnostic, unitLabel, highlighted = false }: { title: string; diagnostic: RosterDiagnostic; unitLabel: string; highlighted?: boolean }) {
  return (
    <div className={`diagnostic-summary ${highlighted ? 'highlighted' : ''}`}>
      <span>{title}</span>
      <strong>{formatCompact(diagnostic.coverage)}</strong>
      <small>{unitLabel} covered</small>
      <dl>
        <div>
          <dt>Shared</dt>
          <dd>{formatCompact(diagnostic.shared)}</dd>
        </div>
        <div>
          <dt>Rate</dt>
          <dd>{formatPercent(diagnostic.sharedRate)}</dd>
        </div>
        <div>
          <dt>Spend</dt>
          <dd>{formatMoney(diagnostic.spend)}</dd>
        </div>
      </dl>
    </div>
  );
}

function EvidenceDistribution({ current, recommended }: { current: DiagnosticEvidence[]; recommended: DiagnosticEvidence[] }) {
  const rows = [
    ...current.map((item) => ({ ...item, roster: 'Current' })),
    ...recommended.map((item) => ({ ...item, roster: 'Recommended' })),
  ];
  return (
    <div className="evidence-tags" aria-label="Evidence states">
      <strong>Evidence states</strong>
      {rows.length === 0 ? (
        <span>No selected creators.</span>
      ) : (
        rows.map((item) => (
          <span key={`${item.roster}-${item.state}`}>{item.roster}: {evidenceLabel(item.state)} · {item.count}</span>
        ))
      )}
    </div>
  );
}

function OverlapHeatmap({ title, diagnostic, pairs, creators, maxPairOverlap }: { title: string; diagnostic: RosterDiagnostic; pairs: PairOverlap[]; creators: Record<string, Creator>; maxPairOverlap: number }) {
  const pairLookup = new Map(pairs.flatMap((pair) => [[`${pair.a}:${pair.b}`, pair.count], [`${pair.b}:${pair.a}`, pair.count]]));
  const ids = diagnostic.ids;
  const descriptionId = useId();
  const creatorNames = ids.map((id, index) => `${index + 1}. ${creators[id]?.name ?? id}`).join('; ');
  const pairDescription = pairs.length === 0
    ? 'No pair overlaps are present.'
    : pairs.map((pair) => `${creators[pair.a]?.name ?? pair.a} and ${creators[pair.b]?.name ?? pair.b}: ${formatNumber(pair.count)} shared commenters`).join('; ');

  return (
    <div className="heatmap-block">
      <div className="heatmap-title">
        <Network size={17} />
        <strong>{title}</strong>
        <span>{ids.length} creators</span>
      </div>
      {ids.length === 0 ? (
        <p className="empty-state">No creators selected.</p>
      ) : (
        <div className="heatmap-scroll">
          <p className="sr-only" id={descriptionId}>
            {title} order: {creatorNames}. Darker cells indicate more shared commenters; the visible scale maximum is {formatNumber(maxPairOverlap)}. {pairDescription}
          </p>
          <div className="heatmap" style={{ gridTemplateColumns: `132px repeat(${ids.length}, 26px)` }} role="img" aria-label={`${title} shared commenter overlap matrix`} aria-describedby={descriptionId}>
            <span className="heatmap-corner">Creator</span>
            {ids.map((id, index) => (
              <span className="heatmap-col-label" key={id} title={creators[id]?.name ?? id}>{index + 1}</span>
            ))}
            {ids.map((rowId, rowIndex) => (
              <React.Fragment key={rowId}>
                <span className="heatmap-row-label" title={creators[rowId]?.name ?? rowId}>{rowIndex + 1}. {creators[rowId]?.name ?? rowId}</span>
                {ids.map((colId) => {
                  const same = rowId === colId;
                  const count = same ? null : pairLookup.get(`${rowId}:${colId}`) ?? 0;
                  const intensity = count && maxPairOverlap ? Math.max(0.08, count / maxPairOverlap) : 0;
                  return (
                    <span
                      className={`heatmap-cell ${same ? 'self' : ''}`}
                      key={`${rowId}-${colId}`}
                      style={{ '--heat': intensity } as React.CSSProperties}
                      title={same ? creators[rowId]?.name ?? rowId : `${creators[rowId]?.name ?? rowId} + ${creators[colId]?.name ?? colId}: ${formatNumber(count ?? 0)} shared commenters`}
                    >
                      {same ? '·' : ''}
                    </span>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TopicBars({ title, topics, maxCount }: { title: string; topics: DiagnosticTopic[]; maxCount: number }) {
  return (
    <div className="topic-bars">
      <strong>{title}</strong>
      {topics.length === 0 ? (
        <span>No selected creators.</span>
      ) : (
        topics.map((topic) => (
          <div className="topic-row" key={topic.name}>
            <span>{topic.name}</span>
            <div aria-hidden="true"><span style={{ width: `${Math.max(8, (topic.count / maxCount) * 100)}%` }} /></div>
            <small>{topic.count}</small>
          </div>
        ))
      )}
    </div>
  );
}

function MoneyInput({ value, onChange, ariaLabel, compact = false }: { value: number; onChange: (value: number) => void; ariaLabel: string; compact?: boolean }) {
  const [draft, setDraft] = useState(formatNumber(value));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(formatNumber(value));
  }, [editing, value]);

  return (
    <label className={`money-input ${compact ? 'compact' : ''}`}>
      <span aria-hidden="true">$</span>
      <input
        type="text"
        inputMode="numeric"
        aria-label={ariaLabel}
        value={editing ? draft : formatNumber(value)}
        onFocus={() => setEditing(true)}
        onChange={(event) => {
          setDraft(event.target.value);
          onChange(parseMoney(event.target.value));
        }}
        onBlur={() => {
          setEditing(false);
          setDraft(formatNumber(value));
        }}
      />
    </label>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
