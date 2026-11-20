"""Build auditable offline data from the downloaded source snapshots.

No model fitting or catalogue selection uses the GISMo validation/test splits.
Pickle loading deliberately rejects all executable globals/classes.
"""
import csv
import hashlib
import io
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'data'

class DataOnlyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f'Executable pickle global rejected: {module}.{name}')

def load_pickle(path):
    return DataOnlyUnpickler(io.BytesIO(path.read_bytes())).load()

def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

# Explicit human-readable mapping choices live in data/catalogue.csv, not automatic fuzzy matches.
# Columns: id, status, AGRIBALYSE code, FlavorGraph node name, functional family, roles, aliases, notes.
# Only status=reviewed rows are built unless --include-proposed is passed for a preview.
# A row with only id and aliases filled adds aliases to an ingredient defined earlier.
CATALOGUE = OUT / 'catalogue.csv'

# Ingredient groups used by the explicit pair rules below.
PURE_FATS = ['olive_oil','canola_oil','vegetable_oil','coconut_oil','shortening']
DRIED = ['garlic_powder','onion_powder','oregano','thyme','italian_seasoning']
FRESH = ['garlic','onion','shallot','green_onion','parsley','cilantro','basil','chive']
MEATS = ['beef','chicken','pork','turkey','lamb','sausage','cooked_chicken']
LEGUMES = ['lentils','chickpeas','kidney_beans','black_bean']
PLANT_MILKS = ['soy_milk','almond_milk','oat_milk','coconut_milk']

def load_blocked_pairs():
    return {(r['source'],r['target']):r['reason'] for r in csv.DictReader((OUT/'blocked_pairs.csv').open(encoding='utf-8'))}

def load_catalogue(include_proposed=False):
    statuses={'reviewed','proposed'} if include_proposed else {'reviewed'}
    rows=[r for r in csv.DictReader(CATALOGUE.open(encoding='utf-8')) if r['status'] in statuses]
    for r in rows:
        alias_only=r['id'] and r['aliases'] and not (r['agb_code'] or r['family'] or r['roles'])
        if not alias_only and not (r['id'] and r['agb_code'] and r['family'] and r['roles']):raise ValueError(f"Incomplete catalogue row: {r['id']}")
    return rows

def main(include_proposed=False):
    agb = {str(r['Code_AGB']):r for r in json.loads((RAW/'agribalyse_api.json').read_text())['results']}
    nodes = list(csv.DictReader((RAW/'nodes.csv').open()))
    by_name = {r['name']:r for r in nodes}
    chemicals = defaultdict(set)
    for e in csv.DictReader((RAW/'edges.csv').open()):
        if e['edge_type']=='ingr-fcomp': chemicals[e['id_1']].add(e['id_2'])
    catalogue, aliases = {}, {}
    specs=load_catalogue(include_proposed)
    for spec in specs:
        ident,code,flavor,family=spec['id'],spec['agb_code'],spec['flavor_name'],spec['family']
        if not code:
            if ident not in catalogue:raise ValueError(f'Alias row for {ident} comes before its ingredient')
            for name in spec['aliases'].split('|'):
                if name in aliases and aliases[name]!=ident:raise ValueError(name)
                aliases[name]=ident
            continue
        if code not in agb:raise ValueError(f'{ident}: AGRIBALYSE code {code} is not in the snapshot')
        if ident in catalogue:raise ValueError(f'Duplicate catalogue id: {ident}')
        a=agb[code]; node=by_name.get(flavor) if flavor else None; compounds=sorted(chemicals.get(node['node_id'],set())) if node else []
        catalogue[ident]={
            'id':ident,'name':ident.replace('_',' ').title(),'family':family,'roles':spec['roles'].split('|'),
            'factor':float(a['Changement_climatique']),'factor_unit':'kg CO2e / kg food in mapped state',
            'agb_code':code,'agb_name':a['LCI_Name'],'dqr':a.get('DQR'),
            'flavor_node':node['node_id'] if node else None,'flavor_name':flavor,
            'compounds':compounds,'compound_count':len(compounds),'mapping_notes':spec['mapping_notes'],
            'factor_source':'AGRIBALYSE 3.2 / ADEME public API snapshot','mapping_status':spec['status'],
        }
        for name in [ident]+[x for x in spec['aliases'].split('|') if x]:
            if name in aliases and aliases[name]!=ident:raise ValueError(name)
            aliases[name]=ident
    def canon(s):return aliases.get(s.strip().lower().replace(' ','_'))
    counts=Counter(); contexts=defaultdict(Counter)
    train=load_pickle(RAW/'train_subs.pkl')
    for r in train:
        a,b=map(canon,r['subs'])
        if not a or not b or a==b:continue
        counts[(a,b)]+=1
        for names in r['ingredients']:
            ctx=next((canon(n) for n in names if canon(n)),None)
            if ctx and ctx not in (a,b):contexts[(a,b)][ctx]+=1
    pairs=[];blocked=load_blocked_pairs()
    for (a,b),count in sorted(counts.items()):
        same=catalogue[a]['family']==catalogue[b]['family']
        roles=sorted(set(catalogue[a]['roles'])&set(catalogue[b]['roles'])) if same and (a,b) not in blocked else []
        # Conservative explicit rules, not learned or externally validated labels.
        ratio=.82 if a=='butter' and b in PURE_FATS else 3.0 if a in DRIED and b in FRESH else 1/3 if a in FRESH and b in DRIED else 1.0
        max_fraction=.5 if a in MEATS and b in LEGUMES else 1.0
        note='Equal-mass replacement is a modelling assumption; adjust seasoning and preparation in the cooking pilot.'
        if a=='butter' and ratio!=1:note='Use 0.82 g oil or fat per gram of butter removed as a fat-mass approximation; not a universal cooking conversion.'
        if ratio==3.0:note='Use about 3 g fresh per gram of dried (common kitchen rule); not a measured conversion.'
        if ratio==1/3:note='Use about 1 g dried per 3 g fresh (common kitchen rule); not a measured conversion.'
        if (a,b) in blocked:note='Blocked pair: '+blocked[(a,b)]
        if b in ['yogurt','greek_yogurt']:note+=' Stir in off heat; acidity and thickening will differ.'
        if b in PLANT_MILKS:note+=' Use an unsweetened product; flavour and thickening may differ.'
        pairs.append({'source':a,'target':b,'train_count':count,'context_counts':dict(contexts[(a,b)]),
                      'roles':roles,'mass_ratio':ratio,'max_fraction':max_fraction,'note':note})
    write('ingredients.json',catalogue);write('aliases.json',aliases);write('pairs.json',pairs)
    for split in ['val','test']:
        source=load_pickle(RAW/f'{split}_subs.pkl'); rows=[]
        for r in source:
            a,b=map(canon,r['subs'])
            if not a or not b or a==b:continue
            ctx=sorted({c for names in r['ingredients'] for n in names if (c:=canon(n)) and c not in (a,b)})
            rows.append({'recipe_id':r['id'],'source':a,'target':b,'context':ctx})
        write(f'{split}.json',rows)
    manifest={
        'retrieved_date':'2026-10-01','environment_rows':len(agb),'catalogue_ingredients':len(catalogue),
        'catalogue_status_counts':dict(Counter(x['mapping_status'] for x in catalogue.values())),
        'flavor_ingredients_with_profiles':len(chemicals),'catalogue_with_profiles':sum(bool(x['compounds']) for x in catalogue.values()),
        'gismo_train_records':len(train),'gismo_val_records':len(load_pickle(RAW/'val_subs.pkl')),
        'gismo_test_records':len(load_pickle(RAW/'test_subs.pkl')),'mapped_train_pairs':len(pairs),
        'role_permitted_pairs':sum(bool(p['roles']) for p in pairs),
        'raw_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(RAW.iterdir()) if f.is_file()},
    }
    write('manifest.json',manifest)
    with (OUT/'ingredient_mapping.csv').open('w',newline='',encoding='utf-8') as h:
        fields=['id','mapping_status','agb_code','agb_name','factor','factor_unit','dqr','flavor_node','flavor_name','compound_count','mapping_notes']
        w=csv.DictWriter(h,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(catalogue.values())
    print(json.dumps({k:v for k,v in manifest.items() if k!='raw_sha256'},indent=2))

if __name__=='__main__':main(include_proposed='--include-proposed' in sys.argv[1:])
