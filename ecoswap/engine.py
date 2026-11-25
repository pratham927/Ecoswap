"""Dependency-free scoring, carbon accounting and discrete optimization."""
import copy
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
# Manually chosen default weights. Validation-fitted weights remain available for comparison.
HAND_PICKED_WEIGHTS = {'support':.6,'context':.2,'chemistry':.2}

def evidence_score(row, weights):
    """Weighted mean of the available evidence terms; a missing term drops out instead of counting as zero."""
    numerator=weights['support']*row['support_score'];denom=weights['support']
    if row['context_score'] is not None:numerator+=weights['context']*row['context_score'];denom+=weights['context']
    if row['chemical_similarity'] is not None:
        weight=weights['chemistry']*row['chemical_weight_reliability'];numerator+=weight*row['chemical_similarity'];denom+=weight
    return numerator/denom if denom else 0.0

def number(value, name, low=0, high=None):
    if isinstance(value, bool): raise ValueError(f'{name} must be a number')
    try: v=float(value)
    except (ValueError, TypeError): raise ValueError(f'{name} must be a number') from None
    if not math.isfinite(v) or v<low or (high is not None and v>high):
        raise ValueError(f'{name} must be finite and in [{low}, {high if high is not None else "infinity"}]')
    return v

class EcoSwap:
    def __init__(self, data_dir=DATA, evidence_weights=None):
        self.data_dir=Path(data_dir)
        self.ingredients=json.loads((self.data_dir/'ingredients.json').read_text(encoding='utf-8'))
        self.aliases=json.loads((self.data_dir/'aliases.json').read_text(encoding='utf-8'))
        self.pairs=json.loads((self.data_dir/'pairs.json').read_text(encoding='utf-8'))
        self.recipes=json.loads((self.data_dir/'recipes.json').read_text(encoding='utf-8'))
        # Support is scaled against the best-supported permitted swap overall, so a source's
        # only swap seen twice does not get the same evidence as one seen hundreds of times.
        self.max_train_count=max([p['train_count'] for p in self.pairs if p['roles']],default=1)
        if evidence_weights is None:
            evidence_weights=HAND_PICKED_WEIGHTS
        self.evidence_weights={k:number(evidence_weights[k],f'{k} weight',0,1) for k in HAND_PICKED_WEIGHTS}

    def canonical(self, ingredient):
        name=str(ingredient).strip().lower().replace(' ','_')
        if name not in self.aliases:raise ValueError(f'Unknown ingredient: {ingredient}. Add an audited mapping first.')
        return self.aliases[name]

    def validate_recipe(self, recipe):
        if not isinstance(recipe,dict):raise ValueError('Recipe must be a JSON object')
        r=copy.deepcopy(recipe)
        r['servings']=number(r.get('servings',1),'servings',low=1)
        if not isinstance(r.get('ingredients'),list) or not r['ingredients']:raise ValueError('Recipe needs a non-empty ingredients list')
        seen=set()
        for row in r['ingredients']:
            if not isinstance(row,dict) or 'id' not in row or 'grams' not in row:raise ValueError('Each row needs id and grams')
            row['id']=self.canonical(row['id'])
            if row['id'] in seen:raise ValueError('Combine duplicate ingredient rows before importing')
            seen.add(row['id']);row['grams']=number(row['grams'],'grams',low=0)
            if row['grams']==0:raise ValueError('Ingredient grams must be positive')
            role=row.get('role')
            if role is None or not isinstance(role,str):raise ValueError('Each ingredient needs an explicit role')
            # Non-target ingredients may have other roles; source ranking will abstain.
        r.setdefault('name','Custom recipe');r.setdefault('id','custom')
        return r

    def footprint(self, recipe):
        r=self.validate_recipe(recipe);rows=[]
        for row in r['ingredients']:
            item=self.ingredients[row['id']]
            rows.append({**row,'name':item['name'],'factor':item['factor'],
                         'kg_co2e':row['grams']/1000*item['factor'],'agb_code':item['agb_code'],
                         'mapped_food_state':item['agb_name']})
        total=sum(x['kg_co2e'] for x in rows)
        return {'total_kg_co2e':total,'per_serving_kg_co2e':total/r['servings'],'contributions':rows,'coverage':1.0}

    def chemistry(self, a, b):
        x=set(self.ingredients[a]['compounds']);y=set(self.ingredients[b]['compounds'])
        known=bool(x and y)
        return {'chemical_similarity':len(x&y)/len(x|y) if known else None,
                'source_compounds':len(x),'target_compounds':len(y),'shared_compounds':len(x&y) if known else None,
                'chemical_coverage':'missing' if not known else ('sparse' if min(len(x),len(y))<20 else 'both profiles available'),
                'chemical_weight_reliability':min(len(x),len(y))/(min(len(x),len(y))+20) if known else 0.0}

    def candidates(self, source, role=None, context=(), exclude=(), lower_carbon=True):
        a=self.canonical(source);context={self.canonical(x) for x in context if str(x).strip()}
        excluded={self.canonical(x) for x in exclude};source_item=self.ingredients[a]
        supported=[p for p in self.pairs if p['source']==a and p['roles']]
        result=[]
        for p in supported:
            b=p['target']
            if b in excluded or (role is not None and role not in p['roles']):continue
            eff=self.ingredients[b]['factor']*p['mass_ratio']
            reduction=(source_item['factor']-eff)/source_item['factor']
            if lower_carbon and reduction<=0:continue
            chem=self.chemistry(a,b)
            support=math.log1p(p['train_count'])/math.log1p(self.max_train_count)
            ctx=sum(p['context_counts'].get(x,0)/p['train_count'] for x in context)/len(context) if context else None
            row={**p,**chem,'source_name':source_item['name'],'target_name':self.ingredients[b]['name'],
                 'support_score':support,'context_score':ctx,
                 'ingredient_reduction_fraction':reduction,'target_factor':self.ingredients[b]['factor']}
            # Evidence weights are declared or fitted on the validation split; never on test.
            row['evidence_score']=evidence_score(row,self.evidence_weights)
            result.append(row)
        return result

    def ranked_candidates(self,source,role=None,context=(),method='combined',alpha=.5,exclude=()):
        alpha=number(alpha,'alpha',0,1)
        if method not in ['carbon_only','flavor_only','combined','frequency']:raise ValueError('Unknown ranking method')
        rows=self.candidates(source,role,context,exclude)
        for r in rows:
            if method=='carbon_only':s=r['ingredient_reduction_fraction']
            elif method=='frequency':s=r['support_score']
            elif method=='flavor_only':s=r['chemical_similarity'] if r['chemical_similarity'] is not None else -1
            else:s=alpha*r['ingredient_reduction_fraction']+(1-alpha)*r['evidence_score']
            r['ranking_score']=s
        return sorted(rows,key=lambda x:(-x['ranking_score'],-x['train_count'],x['target']))

    def apply(self,recipe,source,target,fraction):
        r=self.validate_recipe(recipe);a=self.canonical(source);b=self.canonical(target)
        f=number(fraction,'fraction',0,1)
        src=next((x for x in r['ingredients'] if x['id']==a),None)
        if src is None:raise ValueError('Source ingredient is absent from recipe')
        if f==0:return r
        permitted=self.candidates(a,src['role'])
        pair=next((p for p in permitted if p['target']==b),None)
        if pair is None:raise ValueError('Replacement has no permitted, lower-carbon, training-supported rule for this role')
        if f>pair['max_fraction']+1e-12:raise ValueError('Fraction exceeds this pair’s curated limit')
        add=src['grams']*f*pair['mass_ratio'];src['grams']*=1-f
        existing=next((x for x in r['ingredients'] if x['id']==b),None)
        if existing:existing['grams']+=add
        else:r['ingredients'].append({'id':b,'grams':add,'role':src['role']})
        r['ingredients']=[x for x in r['ingredients'] if x['grams']>1e-10]
        r['adaptation_note']=pair['note'];r['name']=r['name']+' — adapted ingredient list'
        return r

    def options(self,recipe,source,alpha=.5,max_fraction=1,exclude=()):
        r=self.validate_recipe(recipe);a=self.canonical(source);alpha=number(alpha,'alpha',0,1)
        cap=number(max_fraction,'max_fraction',0,1)
        src=next((x for x in r['ingredients'] if x['id']==a),None)
        if src is None:raise ValueError('Source ingredient is absent from recipe')
        original=self.footprint(r)['total_kg_co2e']
        context=[x['id'] for x in r['ingredients'] if x['id']!=a]
        rows=[{'source':a,'target':a,'target_name':'Keep original','fraction':0.0,'before':original,'after':original,
               'saved_kg_co2e':0.0,'recipe_reduction_pct':0.0,'change_penalty':0.0,'objective':0.0,
               'evidence_score':1.0,'chemical_similarity':None,'chemical_coverage':'unchanged','train_count':0,
               'note':'No substitution','mass_ratio':1.0}]
        for p in self.candidates(a,src['role'],context,exclude):
            for f in [.25,.5,.75,1.0]:
                if f>min(cap,p['max_fraction'])+1e-12:continue
                saved=src['grams']/1000*f*(self.ingredients[a]['factor']-p['mass_ratio']*self.ingredients[p['target']]['factor'])
                change=f*f*(1-p['evidence_score'])
                benefit=saved/original if original else 0
                rows.append({**p,'fraction':f,'before':original,'after':original-saved,'saved_kg_co2e':saved,
                             'recipe_reduction_pct':100*benefit,'change_penalty':change,
                             'objective':alpha*benefit-(1-alpha)*change})
        for x in rows:
            x['pareto']=not any(y['saved_kg_co2e']>=x['saved_kg_co2e']-1e-12 and y['change_penalty']<=x['change_penalty']+1e-12
                and (y['saved_kg_co2e']>x['saved_kg_co2e']+1e-12 or y['change_penalty']<x['change_penalty']-1e-12) for y in rows)
        return sorted(rows,key=lambda x:(-x['objective'],x['fraction'],x['target']))

    def sensitivity(self,recipe,source,option,relative_band=.2):
        """Illustrative factor perturbation bounds, NOT confidence intervals."""
        band=number(relative_band,'relative_band',0,.99)
        r=self.validate_recipe(recipe);a=self.canonical(source)
        grams=next(x['grams'] for x in r['ingredients'] if x['id']==a)
        if option['fraction']==0:return {'low':0,'high':0,'band':band}
        ea=self.ingredients[a]['factor'];eb=self.ingredients[option['target']]['factor']*option['mass_ratio']
        k=grams/1000*option['fraction']
        return {'low':k*(ea*(1-band)-eb*(1+band)),'high':k*(ea*(1+band)-eb*(1-band)),'band':band}

