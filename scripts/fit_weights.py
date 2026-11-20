"""Fit the evidence-score weights on the GISMo validation split.

The test split is never read. The evidence score is used mixed with carbon reduction
(ranking `alpha * reduction + (1 - alpha) * evidence`, and the optimizer penalty), so its
scale matters as well as its ordering. Every weight combination on a 0.05 simplex grid is
therefore scored by the validation MRR of the recorded substitute averaged over carbon
priorities 0, 0.25, 0.5 and 0.75 (at 1 the evidence has no effect). Ties go to the
combination closest to the hand-picked weights. The result is written to
data/evidence_weights.json, which the engine loads automatically.

    python scripts/fit_weights.py
"""
import json
import statistics
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ecoswap import EcoSwap
from ecoswap.engine import HAND_PICKED_WEIGHTS, evidence_score
from build_data import RAW, load_pickle

STEP=.05
ALPHAS=(0,.25,.5,.75)

def mrr(data, weights, alpha):
    total=0
    for target,candidates in data:
        ranked=sorted(candidates,key=lambda c:(-(alpha*c['ingredient_reduction_fraction']+(1-alpha)*evidence_score(c,weights)),-c['train_count'],c['target']))
        ids=[c['target'] for c in ranked]
        total+=1/(ids.index(target)+1) if target in ids else 0
    return total/len(data)

def profile(data, weights):
    per={str(a):mrr(data,weights,a) for a in ALPHAS}
    return {'mean_mrr':statistics.mean(per.values()),'mrr_by_alpha':per}

def grid(step=STEP):
    n=round(1/step)
    return [{'support':round(i*step,2),'context':round(j*step,2),'chemistry':round((n-i-j)*step,2)}
            for i in range(1,n+1) for j in range(n+1-i)]

def main():
    model=EcoSwap(evidence_weights=HAND_PICKED_WEIGHTS)
    train_ids={r['id'] for r in load_pickle(RAW/'train_subs.pkl')}
    val=[r for r in json.loads((ROOT/'data/val.json').read_text()) if r['recipe_id'] not in train_ids]
    data=[(r['target'],model.candidates(r['source'],context=r['context'])) for r in val]
    distance=lambda w:sum(abs(w[k]-HAND_PICKED_WEIGHTS[k]) for k in w)
    scored=sorted(((profile(data,w),w) for w in grid()),key=lambda x:(-round(x[0]['mean_mrr'],12),distance(x[1])))
    ordering=max(grid(),key=lambda w:(round(mrr(data,w,0),12),-distance(w)))
    best_profile,best=scored[0]
    out={'weights':best,'hand_picked':HAND_PICKED_WEIGHTS,
         'selection':f'Maximum validation MRR averaged over carbon priorities {list(ALPHAS)} on a {STEP} simplex grid; ties by closeness to the hand-picked weights. Support weight kept above zero.',
         'validation':{'records':len(data),'reachable_targets':sum(t in {c['target'] for c in cs} for t,cs in data),'grid_points':len(scored),
                       'learned':best_profile,'hand_picked':profile(data,HAND_PICKED_WEIGHTS)},
         'evidence_only_optimum':{'weights':ordering,**profile(data,ordering),
                                  'note':'Best weights when ranking on evidence alone (carbon priority 0). Not used: their smaller score scale makes the carbon term dominate at the default carbon priority.'},
         'next_best':[{'weights':w,**m} for m,w in scored[1:6]]}
    (ROOT/'data/evidence_weights.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['weights','validation','evidence_only_optimum']},indent=2))

if __name__=='__main__':main()
