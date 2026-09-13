"""Public aggregate provider for Daniel's f2cac2c camelCase API contract.

No UI or host files are modified. Source remains observed, eligibility is an
explicit editorial case-study rule, and scores are uncalibrated view-scaled
objectives. Aggregate masses are never expanded into invented commenter IDs.
"""
import hashlib
import json
from pathlib import Path

if __package__:
    from . import clusters as cluster_mod
    from .engine import Planner, PlanError
else:
    import clusters as cluster_mod
    from engine import Planner, PlanError


class RealDataProvider:
    def __init__(self, data, *, topics=None):
        if data.get('metadata', {}).get('kind') != 'observed':
            raise PlanError('The real-data provider requires explicitly observed source data.')
        campaign=data['metadata'].get('campaign')
        if topics is None:
            topics=tuple(campaign['eligibleCategories']) if campaign else ('Science', 'Technology')
        self.planner=Planner(data)
        if any(not c['cost'].is_integer() for c in self.planner.creators):
            raise PlanError('The host API requires whole-dollar dataset quotes.')
        self.topics=tuple(topics)
        fingerprint=json.dumps({'data':data,'eligibleTopics':self.topics},sort_keys=True,separators=(',',':')).encode()
        self.dataset_version='public-comment-exposure-'+hashlib.sha256(fingerprint).hexdigest()[:16]
        if not self.topics or set(self.topics)-{c['community'] for c in self.planner.creators}:
            raise PlanError('Case-study topics must exist in the supplied dataset.')
        self.eligible={c['id'] for c in self.planner.creators if c['community'] in self.topics}
        self.campaign=({key:campaign[key] for key in ('id','name','category','audience')} | {'eligibleCategories':list(self.topics)} if campaign else
                       {'id':'public-science-engineering-case-study','name':'Science & engineering · historical case study',
                        'category':'Science and technology content','audience':'Illustrative brief for curious adults; audience interests and geography unverified.',
                        'eligibleCategories':list(self.topics)})
        self.dataset_label='Observed public historical YouTube sample · %d channels · client-neutral case study.'%len(self.planner.creators)
        self.metric_label='Uncalibrated view-scaled commenter-overlap score; not validated unique viewers'
        self.creator_metric_labels={'views':'Historical median video views','price':'Hypothetical quote (USD)','rawViews':'Total historical median views'}

    @classmethod
    def bundled(cls):
        return cls(json.loads((Path(__file__).parent/'data/exposure-aggregate.json').read_text()))

    @classmethod
    def from_env(cls, environ):
        # MUSE_OBSERVED_DATA points at a collected aggregate (python3 -m collect build); default is the bundled sample.
        path=environ.get('MUSE_OBSERVED_DATA')
        return cls(json.loads(Path(path).read_text())) if path else cls.bundled()

    def _eligibility(self, c):
        if c['id'] in self.eligible:
            return 'eligible','Inside the explicit editorial case-study topic scope; consumer audience fit is unverified.'
        return 'ineligible','Outside the selected case-study topic scope. This is not a brand-safety or demographic judgment.'

    def public_provenance(self):
        # Keep raw aggregate evidence and internal import diagnostics server-side.
        fields=('kind','title','source','source_url','license','data_date','views_basis','quote_basis','group_basis')
        return {**{key:self.planner.metadata[key] for key in fields if key in self.planner.metadata},
                'datasetVersion':self.dataset_version,'estimate_type':self.metric_label,
                'validation':'Observed historical commenter overlap only; no viewer-level or campaign-outcome validation.',
                'eligibleTopics':list(self.topics)}

    def creators_payload(self):
        rows=[]
        for c in self.planner.creators:
            status,reason=self._eligibility(c)
            rows.append({'id':c['id'],'name':c['name'],'vertical':c['community'],
                         'audienceNote':'Topic inferred editorially from public channel content; individual audience interests and geography are unverified.',
                         'category':c['community'],'categorySource':'editorial-public-content',
                         'eligibilityStatus':status,'eligibilityReason':reason,
                         'evidenceState':'observed','sampleSize':c.get('comment_count',c['commenter_count']),
                         'sampleUnit':'top_level_comments' if 'comment_count' in c else 'unique_commenter_ids',
                         'source':'observed-public',
                         'estimatedViews':c['views'],'viewsBasis':'Median historical views per sampled video; view events, not sponsored reach.',
                         'baseCost':int(c['cost']),'costBasis':'Hypothetical case-study quote; editable, not a researched rate.',
                         'commenterCount':c['commenter_count'],'videoCount':c.get('video_count'),
                         'sponsorMentions':c.get('sponsor_mentions'),
                         'creatorCountry':c.get('creator_country'),'audioLanguages':c.get('audio_languages'),
                         'sourceUrl':self.planner.metadata.get('source_url')})
        baseline=self.planner.optimize({'budget':10000,'objective':'viewer_proxy',
                                       'exclude':[c['id'] for c in self.planner.creators if c['id'] not in self.eligible]})['baselines']['top_views']
        return {'campaign':self.campaign,'datasetLabel':self.dataset_label,'datasetKind':'observed','datasetVersion':self.dataset_version,
                'metricLabel':self.metric_label,'creatorMetricLabels':self.creator_metric_labels,'creators':rows,'defaultCurrentRoster':baseline['selected'],
                'defaultBudget':10000,'provenance':self.public_provenance()}

    def _ids(self, value, field):
        if not isinstance(value,list) or any(not isinstance(cid,str) or cid not in self.planner.by_id for cid in value):
            raise PlanError('%s must be a list of known IDs from /api/creators; synthetic IDs are not mapped to real creators.'%field)
        return list(dict.fromkeys(value))

    def _score(self, ids, ctx, *, notes=()):
        p=self.planner
        summary=p.summarize(ids,ctx)
        observed=p.summarize(ids,p.context({'objective':'observed_commenters'}))
        note='Historical commenter overlap within the source sample; view-scaled score is uncalibrated. Quotes are assumptions.' if ids else 'No creators selected.'
        return {'ids':list(ids),'spend':summary['spend'],'proxyReach':round(summary['reach_est'],2),
                'rawViews':sum(p.by_id[cid]['views'] for cid in ids),
                'overlappingCommenters':round(observed['naive_sum']-observed['reach_est']),
                'evidenceNote':note,'flaggedIds':[cid for cid in ids if cid not in self.eligible],'notes':list(notes),
                'observedCommenterCoverage':round(observed['reach_est']),
                'metricUnit':'uncalibrated_view_scaled_score','observedUnit':'unique_sampled_commenter_ids'}

    def _topic_distribution(self, ids, ctx):
        topics={}
        for cid in ids:
            creator=self.planner.by_id[cid]
            topic=topics.setdefault(creator['community'], {'name':creator['community'],'count':0,'spend':0,'views':0})
            topic['count']+=1
            topic['spend']+=ctx['costs'][cid]
            topic['views']+=creator['views']
        return sorted(topics.values(), key=lambda item:(-item['count'], item['name']))

    def _pair_overlaps(self, ids):
        ordered=list(dict.fromkeys(ids))
        pairs=[]
        for left_index,left_id in enumerate(ordered):
            left=self.planner.by_id[left_id]
            for right_id in ordered[left_index+1:]:
                right=self.planner.by_id[right_id]
                pairs.append({'a':left_id,'b':right_id,'count':self.planner.mass(left['commenters'] & right['commenters'])})
        return pairs

    def overlap_payload(self):
        """Public aggregate graph only: no IDs of commenters or membership sets."""
        nodes=[{'id':c['id'], 'name':c['name'],
                'sampledCommenters':round(self.planner.mass(c['commenters']))}
               for c in self.planner.creators]
        counts={n['id']:n['sampledCommenters'] for n in nodes}
        pairs=[]
        for pair in self._pair_overlaps(list(counts)):
            shared=round(pair['count'])
            union=counts[pair['a']]+counts[pair['b']]-shared
            pairs.append({'a':pair['a'],'b':pair['b'],'sharedCommenters':shared,
                          'jaccard':shared/union if union else 0})
        jaccard={(min(p['a'],p['b']),max(p['a'],p['b'])):p['jaccard'] for p in pairs}
        by_id=self.planner.by_id
        groups=cluster_mod.detect(list(counts), jaccard)
        return {'datasetVersion':self.dataset_version,
                'nodes':nodes, 'pairs':pairs,
                'clusters':cluster_mod.summarize(groups, by_id, jaccard),
                'clusterMethod':'Greedy modularity on commenter Jaccard. A cluster is overlapping sampled commenters, not a demographic segment.',
                'metric':'Jaccard = shared sampled commenters / sampled commenters in either channel.'}

    def _roster_diagnostic(self, ids, ctx):
        p=self.planner
        observed_ctx=p.context({'objective':'observed_commenters'})
        coverage=round(p.summarize(ids,observed_ctx)['reach_est'])
        standalone=sum(p.mass(p.by_id[cid]['commenters']) for cid in ids)
        shared=max(round(standalone-coverage),0)
        return {'ids':list(ids),'spend':round(sum(ctx['costs'][cid] for cid in ids)),
                'coverage':coverage,'standalone':round(standalone),'shared':shared,
                'sharedRate':round(shared/standalone,4) if standalone else 0,
                'topics':self._topic_distribution(ids,ctx),
                'evidence':[{'state':'observed','count':len(ids)}] if ids else []}

    def _diagnostics(self, current, recommended, baseline, ctx):
        rosters={'current':current,'recommended':recommended,'viewsBaseline':baseline}
        pairs={name:self._pair_overlaps(ids) for name,ids in rosters.items()}
        max_pair=max((pair['count'] for roster_pairs in pairs.values() for pair in roster_pairs), default=0)
        return {'unitLabel':'sampled commenters',
                'caveat':'Observed public comment overlap is historical sample evidence; it is not viewer-level reach or campaign outcome validation.',
                'comparisonNote':'Recommended and views-ranked rosters share budget, required creators, exclusions, eligible topics, quotes, topic caps and relevance weights. Current roster may have different spend.',
                'maxPairOverlap':max_pair,
                'rosters':{name:self._roster_diagnostic(ids,ctx) for name,ids in rosters.items()},
                'pairOverlaps':pairs}

    def plan_payload(self, request):
        allowed={'budget','currentRoster','include','exclude','costs','planningContext'}
        if not isinstance(request,dict) or set(request)-allowed or not {'budget','currentRoster'}<=set(request):
            raise PlanError('Plan requires budget/currentRoster and accepts include/exclude/costs only.')
        budget=request['budget']
        if isinstance(budget,bool) or not isinstance(budget,int) or budget<0:
            raise PlanError('Budget must be a nonnegative whole-dollar amount.')
        current=self._ids(request['currentRoster'],'currentRoster')
        required=self._ids(request.get('include',[]),'include')
        excluded=self._ids(request.get('exclude',[]),'exclude')
        blocked=[cid for cid in required if cid not in self.eligible]
        if blocked:
            raise PlanError('Required creator is outside the case-study eligible topics: '+', '.join(blocked))
        costs=request.get('costs',{})
        if not isinstance(costs,dict) or set(costs)-set(self.planner.by_id) or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in costs.values()):
            raise PlanError('Costs must map known creator IDs to nonnegative whole dollars.')
        campaign_excluded=sorted(set(excluded)|(set(self.planner.by_id)-self.eligible))
        planning=request.get('planningContext',{})
        if not isinstance(planning,dict) or set(planning)-{'brandDescription','relevance','maxPerGroup'}:
            raise PlanError('Unsupported planning context.')
        ctx=self.planner.context({'budget':budget,'objective':'viewer_proxy','must_include':required,'exclude':campaign_excluded,'costs':costs,
                                 'brand_description':planning.get('brandDescription',''),'relevance':planning.get('relevance',{}),'max_per_group':planning.get('maxPerGroup',{})})
        if ctx['relevance'] and set(ctx['relevance'])!={c['community'] for c in self.planner.creators}:
            raise PlanError('Relevance must cover every topic.')
        plan=self.planner.optimize(ctx)
        steps=[{'creatorId':t['id'],'creatorName':t['name'],'marginalProxyReach':round(t['marginal_gain'],2),'cost':t['cost'],
                'reason':('%s required by the campaign; '%t['name'] if t['required'] else '%s selected; '%t['name'])+
                         'adds %.2f uncalibrated score at this step after modeled overlap.'%t['marginal_gain']} for t in plan['trace']]
        why_not=[{'creatorId':r['id'],'creatorName':r['name'],'reason':r['reason'],'cost':ctx['costs'][r['id']],
                  'marginalProxyReach':round(r['marginal_gain'],2),'alreadyCoveredShare':round(r['represented_fraction'],4),
                  'overlapsWith':[{'creatorId':o['id'],'creatorName':o['name'],'sharedCommenters':round(o['shared_commenters'])} for o in r['overlaps_with']]}
                 for r in plan['rejected'] if r['id'] in self.eligible]
        why_not.sort(key=lambda r:(-r['alreadyCoveredShare'], r['creatorName']))
        current_summary=self.planner.summarize(current,ctx)
        baseline=plan['baselines']['top_views']
        current_flags=[self.planner.by_id[cid]['name']+': '+self._eligibility(self.planner.by_id[cid])[1] for cid in current if cid not in self.eligible]
        if current_summary['spend']!=budget:
            current_flags.append('Current roster spend differs from the requested budget cap; this is not an equal-spend lift comparison.')
        size_change=plan['naive_sum']-current_summary['naive_sum']
        overlap_reduction=(current_summary['naive_sum']-current_summary['reach_est'])-(plan['naive_sum']-plan['reach_est'])
        return {'campaign':self.campaign,'datasetLabel':self.dataset_label,'datasetKind':'observed','datasetVersion':self.dataset_version,'metricLabel':('Topic-relevance-weighted ' + self.metric_label if ctx['relevance'] else self.metric_label),
                'planningContext':{'brandDescription':ctx['brand_description'],'relevance':ctx['relevance'],'maxPerGroup':ctx['max_per_group']},
                'creatorMetricLabels':self.creator_metric_labels,'budget':budget,
                'current':self._score(current,ctx),'recommended':self._score(plan['selected'],ctx,notes=[s['reason'] for s in steps]),
                'viewsBaseline':self._score(baseline['selected'],ctx),
                'rosterDiagnostics':self._diagnostics(current,plan['selected'],baseline['selected'],ctx),
                'steps':steps,'whyNot':why_not,'currentFlags':current_flags,'remainingBudget':budget-plan['spend'],
                'gainDecomposition':{'standaloneSizeChange':size_change,'overlapPenaltyReduction':overlap_reduction,'netScoreChange':plan['reach_est']-current_summary['reach_est'],
                                     'note':'Accounting identity on selected rosters; not causal lift. Inspect eligibility and spend differences.'},
                'planningMethod':plan['method'],
                'comparisonPolicy':'Recommendation and view-ranked baseline share budget, required creators, exclusions, eligible topics, quotes, topic caps and relevance weights.',
                'provenance':self.public_provenance()}
