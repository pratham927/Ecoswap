"""Summarize real pilot ratings once collected; does not generate responses."""
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

def analyze(path):
    rows=list(csv.DictReader(Path(path).open(encoding='utf-8')))
    if not rows:return {'status':'not conducted','participants':0,'ratings':0}
    grouped=defaultdict(list);seen=set()
    for r in rows:
        if not r.get('participant_id') or not r.get('recipe_id'):raise ValueError('Participant and recipe identifiers are required')
        key=(r['participant_id'],r['recipe_id'])
        if key in seen:raise ValueError('Duplicate participant/recipe rating')
        seen.add(key)
        if r.get('original_code') not in ['A','B']:raise ValueError('Analyst must enter original_code from sealed codebook')
        values={k:int(r[k]) for k in ['similarity_1to7','liking_A_1to7','liking_B_1to7']}
        if any(v<1 or v>7 for v in values.values()):raise ValueError('Ratings must be integers from 1 to 7')
        original=values['liking_'+r['original_code']+'_1to7'];other='B' if r['original_code']=='A' else 'A'
        grouped[r['recipe_id']].append({'similarity':values['similarity_1to7'],'liking_delta':values['liking_'+other+'_1to7']-original})
    return {'status':'descriptive pilot only','participants':len({r['participant_id'] for r in rows}),'ratings':len(rows),
            'by_recipe':{k:{'n':len(v),'mean_similarity':statistics.mean(x['similarity'] for x in v),
                            'mean_adapted_minus_original_liking':statistics.mean(x['liking_delta'] for x in v)} for k,v in grouped.items()}}

if __name__=='__main__':
    path=sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'results/taste_ratings_template.csv'
    print(json.dumps(analyze(path),indent=2))
