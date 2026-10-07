export type Platform = 'youtube' | 'instagram' | 'tiktok';

export type Creator = {
  id: string;
  name: string;
  vertical?: string;
  category: string;
  platform?: Platform;
  url?: string | null;
  followers?: number;
  estimatedViews: number;
  baseCost: number;
  eligibilityStatus: string;
  eligibilityReason?: string;
  commenterCount?: number;
  audienceDescription?: string;
  audienceSummary?: string;
  hasAudienceData?: boolean;
  overlapEvidence?: string;
  source?: 'synthetic' | 'observed-public';
  sponsorMentions?: { brands: { brand: string }[] } | null;
  foundBy?: 'upriver' | 'youtube_search';
};

export type Campaign = { id: string; name: string; category: string; audience: string };
export type RosterDiag = { ids: string[]; spend: number; coverage: number; standalone: number; shared: number; sharedRate: number };
export type Score = { ids: string[]; spend: number; proxyReach: number; rawViews: number };
export type Step = { creatorId: string; creatorName: string; marginalProxyReach: number; cost: number; reason?: string };
export type WhyNot = {
  creatorId: string;
  creatorName: string;
  reason: string;
  cost: number;
  marginalProxyReach: number;
  alreadyCoveredShare: number;
  overlapsWith: { creatorId: string; creatorName: string; sharedCommenters: number; source?: string }[];
  platform?: Platform;
};
export type EvidenceMix = { measured: number; estimated: number; assumed: number; pairs: number; measuredShare: number | null };
export type Choice = { kind: string; headline: string; reasons: string[]; overlapConfidence: 'measured' | 'estimated' | 'assumed' };
export type Plan = {
  campaign: Campaign;
  budget: number;
  remainingBudget: number;
  datasetKind?: string;
  recommended: Score;
  current: Score;
  viewsBaseline?: Score;
  steps: Step[];
  whyNot?: WhyNot[];
  countNote?: string | null;
  choice?: Choice;
  evidenceMix?: EvidenceMix;
  rosterDiagnostics?: { rosters: { current: RosterDiag; recommended: RosterDiag; viewsBaseline: RosterDiag } };
};
export type Context = { brandDescription: string; relevance: Record<string, number>; maxPerGroup: Record<string, number>; creatorCount?: number };
export type Inputs = { budget: number; currentRoster: string[]; include: string[]; exclude: string[]; costs: Record<string, number>; planningContext: Context };
export type SavedCampaign = Inputs & { id: string; name: string; datasetVersion: string };
export type Dataset = { id: string; name: string; prompt?: string | null; dataDate?: string | null; active: boolean };
export type Job = { id: string; status: 'running' | 'done' | 'error'; step: string; progress: number; message: string; dataset_id: string | null; error: string | null; units: number };
export type Evidence = { medianSampledCommenters: number; eligibleCreators: number; thinCreators: number; strength: 'strong' | 'moderate' | 'thin' };
export type Method = { kappa: number; calibrationPairs: number; defaultKappa: number; unknownMatch: number; weights: Record<string, number>; quotePer1k: Record<string, number> };

export type GraphNode = { id: string; name: string; sampledCommenters: number; platform?: Platform };
export type GraphPair = { a: string; b: string; sharedCommenters: number; jaccard: number; source?: 'measured' | 'estimated' | 'assumed' };
export type Cluster = { id: string; members: string[]; label: string; labelSource: 'rule' | 'model'; summary?: string };
export type Graph = { datasetVersion: string; nodes: GraphNode[]; pairs: GraphPair[]; metric: string; clusters?: Cluster[]; unit?: string };

export type ChatMessage = { role: 'user' | 'assistant'; text: string; change?: { changed: boolean; text: string }; section?: string | null; discoverPrompt?: string | null; error?: boolean; attachment?: string };
export type RosterItem = { handle: string; topic: string };
export type Attachment = { name: string; roster: RosterItem[] };

export const PLATFORM_LABEL: Record<Platform, string> = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' };
// Planner groups ("communities") in a cross-platform dataset are the platform labels.
export const PLATFORM_COMMUNITY: Record<Platform, string> = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' };
export const PLATFORMS: Platform[] = ['youtube', 'tiktok', 'instagram'];

export const money = (v: number) => v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
export const compact = (v: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Math.round(v));
export const whole = (v: number) => Math.round(v).toLocaleString('en-US');
// Overlap in these samples is often well under 1%; one decimal would make 0.09% and 0.19% both read "0.1%".
export const pct = (v: number) => `${(v * 100).toFixed(v > 0 && v < 0.01 ? 2 : 1)}%`;
export const platformOf = (c: { platform?: Platform }): Platform => c.platform ?? 'youtube';
export const topicOf = (c: Creator) => c.vertical || c.category.split(' · ').pop() || c.category;
export const initialOf = (name: string) => name.replace(/^@/, '').slice(0, 1).toUpperCase() || '?';
