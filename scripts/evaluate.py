"""Reproducible test-set ranking and separate scenario-based carbon analysis."""
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ecoswap import EcoSwap
from ecoswap.engine import HAND_PICKED_WEIGHTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'
METHODS=['carbon_only','flavor_only','frequency','combined']

def csv_write(path, rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def compare_weights(clean, resamples=2000, seed=0):
    """Test-set comparison of hand-picked and fitted evidence weights; the fit itself only saw validation."""
    rows=[];reciprocal={}
    for name,model in [('hand_picked',EcoSwap(evidence_weights=HAND_PICKED_WEIGHTS)),('fitted',EcoSwap(evidence_weights=json.loads((ROOT/'data/evidence_weights.json').read_text())['weights']))]:
        for ranking,alpha in [('evidence_only',0.0),('combined',.5)]:
            hits=[];rr=[]
            for r in clean:
                ids=[p['target'] for p in model.ranked_candidates(r['source'],context=r['context'],alpha=alpha)]
                rank=ids.index(r['target'])+1 if r['target'] in ids else None
                hits.append(rank==1);rr.append(1/rank if rank else 0)
            reciprocal[(name,ranking)]=rr
            rows.append({'weights':name,**model.evidence_weights,'ranking':ranking,'alpha':alpha,
                         'hit1_all_mapped':statistics.mean(hits),'mrr_all_mapped':statistics.mean(rr)})
    # Paired bootstrap over recipes, so records from one recipe are resampled together.
    groups=defaultdict(list)
    for i,r in enumerate(clean):groups[r['recipe_id']].append(i)
    keys=sorted(groups);rng=random.Random(seed);differences={}
    for ranking in ['evidence_only','combined']:
        a,b=reciprocal[('fitted',ranking)],reciprocal[('hand_picked',ranking)];draws=[]
        for _ in range(resamples):
            idx=[i for k in rng.choices(keys,k=len(keys)) for i in groups[k]]
            draws.append(sum(a[i]-b[i] for i in idx)/len(idx))
        draws.sort()
        differences[ranking]={'mrr_difference':statistics.mean(a)-statistics.mean(b),
                              'ci95_low':draws[int(.025*resamples)],'ci95_high':draws[int(.975*resamples)-1],'resamples':resamples}
    return rows,differences

def main():
    OUT.mkdir(exist_ok=True)
    model=EcoSwap();test=json.loads((ROOT/'data/test.json').read_text())
    from build_data import load_pickle,RAW
    processed_only='--processed-only' in sys.argv
    previous_audit=json.loads((OUT/'summary.json').read_text())['audit'] if processed_only else None
    if processed_only:
        assert previous_audit['excluded_train_recipe_id_overlap']==0
        assert len(test)==previous_audit['evaluated_test_records']
    train_ids=set() if processed_only else {r['id'] for r in load_pickle(RAW/'train_subs.pkl')}
    leaked=[r for r in test if r['recipe_id'] in train_ids]
    clean=[r for r in test if r['recipe_id'] not in train_ids]
    prediction_rows=[];metrics=[]
    for method in METHODS:
        hits=[];ranks=[];covered=0;lower_targets=0;feasible_hits=[];feasible_ranks=[];abstained=0
        for r in clean:
            ranked=model.ranked_candidates(r['source'],context=r['context'],method=method)
            ids=[p['target'] for p in ranked]
            rank=ids.index(r['target'])+1 if r['target'] in ids else None
            hits.append(rank==1);ranks.append(1/rank if rank else 0)
            covered+=rank is not None;abstained+=not ids
            if model.ingredients[r['target']]['factor']<model.ingredients[r['source']]['factor']:lower_targets+=1
            if rank is not None:feasible_hits.append(rank==1);feasible_ranks.append(1/rank)
            prediction_rows.append({'method':method,**{k:r[k] for k in ['recipe_id','source','target']},
                                    'prediction':ids[0] if ids else '', 'rank':rank or '',
                                    'hit1':int(rank==1),'hit5':int(bool(rank and rank<=5)),
                                    'reciprocal_rank':1/rank if rank else 0,'candidate_count':len(ids)})
        method_rows=[x for x in prediction_rows if x['method']==method]
        metrics.append({'method':method,'mapped_test_records':len(clean),'candidate_target_coverage':covered/len(clean) if clean else 0,
                        'abstentions':abstained,'hit1_all_mapped':statistics.mean(hits) if hits else 0,
                        'hit5_all_mapped':statistics.mean(x['hit5'] for x in method_rows) if method_rows else 0,
                        'mrr_all_mapped':statistics.mean(ranks) if ranks else 0,
                        'feasible_target_records':covered,'hit1_feasible':statistics.mean(feasible_hits) if feasible_hits else 0,
                        'mrr_feasible':statistics.mean(feasible_ranks) if feasible_ranks else 0})
    csv_write(OUT/'benchmark_metrics.csv',metrics);csv_write(OUT/'benchmark_predictions.csv',prediction_rows)
    weight_rows,weight_differences=compare_weights(clean);csv_write(OUT/'weight_comparison.csv',weight_rows)
    fitted_path=ROOT/'data/evidence_weights.json'
    weights={'selection':'Manually chosen base weights; fitted weights retained as a benchmark comparison.','in_use':model.evidence_weights,'hand_picked':HAND_PICKED_WEIGHTS,'test':weight_rows,'test_mrr_difference':weight_differences,
             'validation':json.loads(fitted_path.read_text())['validation'] if fitted_path.exists() else None}
    # Same 24 scenarios and exactly the same role-permitted option set for all policies.
    scenarios=[];frontiers=[];curves=[]
    for recipe in model.recipes:
        source=recipe['target'];options=model.options(recipe,source)
        feasible=[o for o in options if o['fraction']>0]
        for o in options:
            frontiers.append({'recipe_id':recipe['id'],'recipe':recipe['name'],'source':source,
                              **{k:o[k] for k in ['target','fraction','before','after','saved_kg_co2e','recipe_reduction_pct','change_penalty','evidence_score','objective','pareto']}})
        for method in METHODS:
            if method=='carbon_only':chosen=max(options,key=lambda o:o['saved_kg_co2e'])
            elif method=='combined':chosen=options[0]
            else:
                row=next(x for x in recipe['ingredients'] if x['id']==source)
                ranking=model.ranked_candidates(source,role=row['role'],context=[x['id'] for x in recipe['ingredients'] if x['id']!=source],method=method)
                chosen=max((o for o in feasible if ranking and o['target']==ranking[0]['target']),key=lambda o:o['fraction'],default=next(o for o in options if o['fraction']==0))
            modified=recipe if chosen['fraction']==0 else model.apply(recipe,source,chosen['target'],chosen['fraction'])
            actual=model.footprint(modified)['total_kg_co2e']
            if abs(actual-chosen['after'])>1e-8:raise AssertionError('Accounting mismatch')
            sens=model.sensitivity(recipe,source,chosen)
            scenarios.append({'recipe_id':recipe['id'],'recipe':recipe['name'],'method':method,'source':source,
                              **{k:chosen[k] for k in ['target','fraction','before','after','saved_kg_co2e','recipe_reduction_pct','evidence_score','chemical_similarity','chemical_coverage','train_count']},
                              'factor_stress_low_saved':sens['low'],'factor_stress_high_saved':sens['high']})
        for alpha in [0,.25,.5,.75,1]:
            o=model.options(recipe,source,alpha=alpha)[0]
            curves.append({'recipe_id':recipe['id'],'alpha':alpha,'target':o['target'],'fraction':o['fraction'],'reduction_pct':o['recipe_reduction_pct']})
    csv_write(OUT/'scenario_comparison.csv',scenarios);csv_write(OUT/'pareto_options.csv',frontiers);csv_write(OUT/'weight_sensitivity.csv',curves)
    aggregate=[]
    for method in METHODS:
        rows=[r for r in scenarios if r['method']==method]
        aggregate.append({'method':method,'scenarios':len(rows),'mean_recipe_reduction_pct':statistics.mean(r['recipe_reduction_pct'] for r in rows),
                          'median_recipe_reduction_pct':statistics.median(r['recipe_reduction_pct'] for r in rows),
                          'total_scenario_kg_co2e_saved':sum(r['saved_kg_co2e'] for r in rows),
                          'positive_savings_under_20pct_stress':sum(r['factor_stress_low_saved']>0 for r in rows),
                          'chemical_evidence_available':sum(r['chemical_similarity'] is not None for r in rows)})
    csv_write(OUT/'scenario_summary.csv',aggregate)
    raw_recipes=[] if processed_only else list(csv.DictReader((RAW/'recipe_information.csv').open()))
    audit={'original_gismo_test_records':(previous_audit['original_gismo_test_records'] if processed_only else len(load_pickle(RAW/'test_subs.pkl'))),'mapped_test_records':len(test),
           'excluded_train_recipe_id_overlap':len(leaked),'evaluated_test_records':len(clean),
           'unique_test_recipes':len({r['recipe_id'] for r in clean}),
           'recipe_emissions_records_inspected':previous_audit['recipe_emissions_records_inspected'] if processed_only else len(raw_recipes),
           'recipe_emissions_used_for_quantities':False,
           'reason':'Example recipe 79222: 14-ounce can is recorded as 28.35 g; dash cayenne as 142 g. Automatic quantity conversions not accepted.',
           'curated_scenarios':len(model.recipes),'taste_pilot_completed':False,
           'benchmark_scope':'Observed substitute recovery within a manually mapped catalogue; not taste accuracy. Unknown ingredients excluded; mapped but unreachable targets count as misses.',
           'candidate_design':'Only training-supported, same-family, role-compatible and lower-carbon pairs. No test pair added to catalogue rules.',
           'scenario_scope':'Author-defined scenarios, not an unbiased sample of real-world recipes.'}
    (OUT/'evaluation_audit.json').write_text(json.dumps(audit,indent=2))
    (OUT/'summary.json').write_text(json.dumps({'benchmark':metrics,'scenarios':aggregate,'audit':audit,'evidence_weights':weights},indent=2))
    make_plots(scenarios,frontiers)
    print(json.dumps({'benchmark':metrics,'scenarios':aggregate,'audit':audit,'evidence_weights':weights},indent=2))

def make_plots(scenarios,frontiers):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Plot generation skipped: install matplotlib. All numerical outputs saved.');return
    colors=['#7b9b82','#b69a60','#66849c','#146c50']
    fig,ax=plt.subplots(figsize=(9,4.5))
    for k,m in enumerate(METHODS):
        rs=[r for r in scenarios if r['method']==m]
        ax.bar(k,statistics.mean(r['recipe_reduction_pct'] for r in rs),color=colors[k],width=.65)
    ax.set_xticks(range(4),['Carbon only','Compound overlap','Frequency','Combined'])
    ax.set_ylabel('Mean estimated recipe reduction (%)');ax.set_title('24 authored scenarios | AGRIBALYSE 3.2')
    ax.spines[['top','right']].set_visible(False);fig.tight_layout();fig.savefig(OUT/'method_comparison.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.5))
    for target in ['turkey','chicken','tofu','lentils']:
        rs=sorted([r for r in frontiers if r['recipe_id']=='demo_01' and r['target']==target],key=lambda r:r['fraction'])
        ax.plot([0]+[100*r['fraction'] for r in rs],[0]+[r['recipe_reduction_pct'] for r in rs],marker='o',label=target.title())
    ax.set_xlabel('Source ingredient replaced (%)');ax.set_ylabel('Estimated whole-recipe reduction (%)')
    ax.set_title('Beef and tomato pasta | equal-mass model');ax.legend();ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();fig.savefig(OUT/'replacement_curve.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()

