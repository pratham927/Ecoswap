"""Suggest catalogue rows for frequent GISMo ingredients that are not mapped yet.

Output is a review sheet only. Nothing here is written to data/catalogue.csv:
a person picks the AGRIBALYSE record, groups aliases and sets roles, then adds
the row with status=proposed (preview builds) or status=reviewed (normal builds).
Only the GISMo training split is read.

    python scripts/propose_mappings.py --top 200
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from build_data import CATALOGUE, OUT, RAW, load_pickle

# Starting roles per functional family. Reviewers may narrow them per ingredient.
ROLE_MAP = {
 'protein':['filling','stew'], 'fat':['saute','baking','spread'],
 'liquid':['sauce','batter','beverage'], 'cheese':['topping','filling'],
 'grain':['starch'], 'vegetable':['vegetable'], 'aromatic':['seasoning'],
 'baking':['structure'], 'egg':['binding'], 'seasoning':['seasoning'],
 'sweetener':['sweetener'], 'nut':['topping','baking'], 'fruit':['fruit'],
 'stock':['stock'], 'acid':['acid'], 'juice':['juice'], 'leavening':['leavening'],
 'herb':['herb'], 'salt':['salt'], 'condiment':['condiment'], 'chocolate':['baking','topping'],
}
# First matching keyword wins; a guess for the reviewer, never applied automatically.
FAMILY_HINTS = [
 ('stock',['broth','stock','bouillon','wine','water','beer']),
 ('sweetener',['sugar','honey','syrup','molasses','agave','splenda']),
 ('acid',['lemon','lime','vinegar']),
 ('juice',['juice']),
 ('leavening',['baking_powder','baking_soda','yeast']),
 ('cheese',['cheese','ricotta']),
 ('fat',['oil','shortening','margarine','lard']),
 ('liquid',['cream','milk','yogurt','buttermilk','half_and_half']),
 ('nut',['walnut','pecan','almond','peanut','cashew','hazelnut','pistachio','nut']),
 ('protein',['beef','pork','chicken','turkey','bacon','ham','sausage','lamb','shrimp','fish','tuna','salmon','bean','tofu','veal']),
 ('egg',['egg']),
 ('grain',['rice','pasta','noodle','bread','crumb','oat','quinoa','couscous','tortilla','cracker']),
 ('baking',['flour','cornstarch','cornmeal','bisquick']),
 ('fruit',['apple','raisin','cranberr','banana','berry','cherr','orange','pineapple','peach','date']),
 ('aromatic',['garlic','ginger','shallot']),
 ('herb',['oregano','basil','thyme','parsley','cilantro','dill','rosemary','chive','sage','mint']),
 ('condiment',['ketchup','mustard','soy_sauce','worcestershire','salsa']),
 ('salt',['salt']),
 ('seasoning',['pepper','powder','paprika','cumin','cinnamon','nutmeg','vanilla','extract','spice']),
]

def tokens(text):
    return [w[:-1] if len(w)>3 and w.endswith('s') and not w.endswith('ss') else w for w in re.findall(r'[a-z]+',text.lower())]

def family_hint(name):
    return next((family for family,words in FAMILY_HINTS if any(w in name for w in words)),'')

def agb_options(name,agb,limit=3):
    want=set(tokens(name));scored=[]
    for code,r in agb.items():
        have=tokens(r['LCI_Name'])
        hits=len(want&set(have))
        if not hits:continue
        # Coverage of the GISMo name, a bonus when the record's head noun matches, and a preference for plain records.
        scored.append((hits/len(want)+.5*(have[0] in want)-.02*len(have),code,r))
    scored.sort(key=lambda x:(-x[0],x[1]))
    return [f"{code} | {r['LCI_Name']} | {float(r['Changement_climatique']):.2f}" for _,code,r in scored[:limit]]

def main():
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--top',type=int,default=200,help='how many of the most frequent GISMo substitution names to consider')
    parser.add_argument('--out',default=str(OUT/'review'/'mapping_proposals.csv'))
    args=parser.parse_args()
    covered=set()
    for r in csv.DictReader(CATALOGUE.open(encoding='utf-8')):
        covered|={r['id'],*[x for x in r['aliases'].split('|') if x]}
    counts=Counter(name for r in load_pickle(RAW/'train_subs.pkl') for name in r['subs'])
    agb={str(r['Code_AGB']):r for r in json.loads((RAW/'agribalyse_api.json').read_text())['results']}
    nodes={r['name']:r['node_id'] for r in csv.DictReader((RAW/'nodes.csv').open()) if r['node_type']=='ingredient'}
    compounds=defaultdict(int)
    for e in csv.DictReader((RAW/'edges.csv').open()):
        if e['edge_type']=='ingr-fcomp':compounds[e['id_1']]+=1
    rows=[]
    for rank,(name,count) in enumerate(counts.most_common(args.top),1):
        if name in covered:continue
        family=family_hint(name);options=agb_options(name.replace('_',' '),agb)
        rows.append({'frequency_rank':rank,'gismo_name':name,'train_sub_mentions':count,'family_hint':family,
                     'role_hint':'|'.join(ROLE_MAP.get(family,[])),'flavor_name':name if name in nodes else '',
                     'flavor_compounds':compounds[nodes[name]] if name in nodes else 0,
                     **{f'agb_option_{k+1}':options[k] if k<len(options) else '' for k in range(3)}})
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(f'{len(rows)} unmapped names among the top {args.top}; review sheet written to {out}')

if __name__=='__main__':main()
