import csv
import json
import math
from pathlib import Path
import pytest
from ecoswap import EcoSwap
from ecoswap.engine import HAND_PICKED_WEIGHTS, evidence_score

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def model():return EcoSwap()

def test_gram_conversion(model):
    r={'ingredients':[{'id':'butter','grams':100,'role':'saute'}],'servings':2}
    f=model.footprint(r)
    assert f['total_kg_co2e']==pytest.approx(.794)
    assert f['per_serving_kg_co2e']==pytest.approx(.397)

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-10,True])
def test_invalid_quantity(model,bad):
    with pytest.raises(ValueError):model.footprint({'ingredients':[{'id':'butter','grams':bad,'role':'saute'}]})

def test_unknown_ingredient_not_zero(model):
    with pytest.raises(ValueError,match='Unknown ingredient'):model.footprint({'ingredients':[{'id':'mystery','grams':50,'role':'sauce'}]})

def test_missing_chemistry_not_zero(model):
    assert model.chemistry('milk','almond_milk')['chemical_similarity'] is None

def test_chemistry_identity(model):
    assert model.chemistry('butter','butter')['chemical_similarity']==1

def test_role_gate(model):
    assert 'olive_oil' not in {x['target'] for x in model.candidates('butter','baking')}
    assert 'olive_oil' in {x['target'] for x in model.candidates('butter','saute')}
    assert model.candidates('cream','whipping')==[]

def test_half_swap_aggregation_no_mutation(model):
    r={'ingredients':[{'id':'butter','grams':100,'role':'saute'},{'id':'olive_oil','grams':10,'role':'saute'}]}
    changed=model.apply(r,'butter','olive_oil',.5)
    grams={x['id']:x['grams'] for x in changed['ingredients']}
    assert grams=={'butter':50,'olive_oil':51}
    assert r['ingredients'][0]['grams']==100
    assert model.footprint(r)['total_kg_co2e']-model.footprint(changed)['total_kg_co2e']==pytest.approx(.05*(7.94-.82*1.63))

def test_fraction_limits(model):
    with pytest.raises(ValueError):model.apply(model.recipes[0],'beef','lentils',1)
    with pytest.raises(ValueError):model.apply(model.recipes[0],'beef','turkey',1.1)

def test_no_change_and_exclusions(model):
    r=model.recipes[0]
    assert model.options(r,'beef',alpha=0)[0]['fraction']==0
    assert len(model.options(r,'beef',max_fraction=0))==1
    options=model.options(r,'beef',exclude=list(model.ingredients))
    assert len(options)==1 and options[0]['fraction']==0

def test_options_match_recomputed_carbon(model):
    for r in model.recipes:
        for o in model.options(r,r['target']):
            modified=r if o['fraction']==0 else model.apply(r,r['target'],o['target'],o['fraction'])
            assert model.footprint(modified)['total_kg_co2e']==pytest.approx(o['after'])
            assert o['after']>=0 and o['saved_kg_co2e']>=0
            assert math.isfinite(o['objective'])

def test_pareto_frontier_contains_optimum(model):
    for r in model.recipes:
        assert model.options(r,r['target'],alpha=.5)[0]['pareto']

def test_duplicate_rows_rejected(model):
    r={'ingredients':[{'id':'milk','grams':100,'role':'sauce'},{'id':'whole_milk','grams':50,'role':'sauce'}]}
    with pytest.raises(ValueError,match='duplicate'):model.validate_recipe(r)

def test_deterministic_ranking(model):
    assert model.ranked_candidates('beef')==model.ranked_candidates('beef')

def test_no_test_only_pair(model):
    assert all(p['train_count']>0 for p in model.pairs)

def test_fitted_weights_loaded_and_overridable(model):
    assert model.evidence_weights==json.loads((ROOT/'data/evidence_weights.json').read_text())['weights']
    assert EcoSwap(evidence_weights=HAND_PICKED_WEIGHTS).evidence_weights==HAND_PICKED_WEIGHTS

def test_missing_evidence_terms_drop_out():
    row={'support_score':.5,'context_score':None,'chemical_similarity':None,'chemical_weight_reliability':0}
    assert evidence_score(row,HAND_PICKED_WEIGHTS)==pytest.approx(.5)

def test_rare_top_swap_has_low_support(model):
    # Cheddar's best-supported swap is seen only a few times, so it must not look fully supported.
    assert max(c['support_score'] for c in model.candidates('cheddar'))<.5
    assert max(c['support_score'] for c in model.candidates('beef'))>.9

def test_salt_and_sugar_not_spice_swaps(model):
    permitted={(p['source'],p['target']) for p in model.pairs if p['roles']}
    assert not {('sugar','salt'),('salt','sugar'),('pepper','salt'),('cayenne_pepper','salt'),('cayenne_pepper','nutmeg')}&permitted

def test_blocked_pairs_never_permitted(model):
    blocked={(r['source'],r['target']) for r in csv.DictReader((ROOT/'data/blocked_pairs.csv').open())}
    assert not any(p['roles'] for p in model.pairs if (p['source'],p['target']) in blocked)

def test_dried_to_fresh_mass_ratio(model):
    pair=next(p for p in model.pairs if (p['source'],p['target'])==('garlic_powder','garlic'))
    assert pair['mass_ratio']==3.0

def test_weight_fitting_never_reads_test_split():
    source=(ROOT/'scripts/fit_weights.py').read_text()
    assert 'test.json' not in source and 'test_subs' not in source
