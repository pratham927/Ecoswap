"""Run: python -m streamlit run app.py"""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from ecoswap import EcoSwap

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='EcoSwap · The swap studio',page_icon='🍅',layout='wide')
st.markdown('<style>'+ (ROOT/'styles/app.css').read_text() +'</style>',unsafe_allow_html=True)

@st.cache_resource
def load():return EcoSwap()
model=load()
st.markdown('''<div class="eco-masthead"><div class="eco-wordmark">Eco<span>Swap</span></div><p>Food, thoughtfully adapted.</p></div>
<div class="eco-intro"><div class="eco-eyebrow">A little thought for every ingredient</div><h1>Good food.<br>A <em>lighter</em> footprint.</h1><p>Rethink an ingredient in a dish you love. Explore a replacement, adjust the amount, and see its estimated carbon impact.</p></div>''',unsafe_allow_html=True)
st.caption('Research prototype · French AGRIBALYSE 3.2 carbon factors · Adaptations await taste testing.')
studio,bench,data,pilot=st.tabs(['Swap studio','Evaluation','Data & method','Taste pilot'])

with studio:
    left,right=st.columns([1,2],gap='large')
    with left:
        st.subheader('What’s on the menu?')
        index=st.selectbox('Choose a recipe',range(len(model.recipes)),format_func=lambda i:model.recipes[i]['name'])
        base=model.recipes[index]
        upload=st.file_uploader('Or import a recipe JSON',type=['json'])
        if upload:
            try:base=model.validate_recipe(json.load(upload))
            except (ValueError,TypeError,json.JSONDecodeError) as exc:st.error(str(exc));st.stop()
        recipe=model.validate_recipe(base)
        st.caption('Quantities are grams in the food state listed under Data & method. Grain and legume quantities are cooked weights.')
        source_ids=[x['id'] for x in recipe['ingredients']]
        default=source_ids.index(recipe.get('target',source_ids[0])) if recipe.get('target') in source_ids else 0
        source=st.selectbox('Ingredient to replace',source_ids,index=default,format_func=lambda x:model.ingredients[x]['name'])
        row=next(x for x in recipe['ingredients'] if x['id']==source)
        roles=model.ingredients[source]['roles']
        role=st.selectbox('Its role in this recipe',roles,index=roles.index(row['role']) if row['role'] in roles else 0)
        row['role']=role
        row['grams']=st.number_input('Source amount (g)',min_value=1.0,max_value=100000.0,value=float(row['grams']),step=10.0)
        alpha=st.slider('Carbon priority',0.0,1.0,.5,.05,help='0 prioritizes avoiding change. 1 prioritizes modelled carbon reduction. This is a preference weight, not a fitted parameter.')
        cap=st.select_slider('Maximum replacement',options=[0,.25,.5,.75,1.0],value=1.0,format_func=lambda x:f'{x:.0%}')
        excluded=st.multiselect('Exclude replacement ingredients',list(model.ingredients),format_func=lambda x:model.ingredients[x]['name'])
        st.caption('Exclusions apply to replacement suggestions only; they do not remove existing recipe ingredients or certify allergen safety.')
        options=model.options(recipe,source,alpha,cap,excluded)
    with right:
        st.subheader(recipe['name'])
        st.caption(f"{recipe['servings']:g} servings · {len(recipe['ingredients'])} ingredients")
        choice=st.selectbox('Recommended option first — explore alternatives',range(len(options)),
            format_func=lambda i:f"{options[i]['target_name']} · {options[i]['fraction']:.0%} replacement · {options[i]['recipe_reduction_pct']:.1f}% estimated recipe reduction")
        best=options[choice]
        original=model.footprint(recipe)
        modified=recipe if best['fraction']==0 else model.apply(recipe,source,best['target'],best['fraction'])
        after=model.footprint(modified)
        a,b,c=st.columns(3)
        a.metric('Original · kg CO₂e',f"{original['total_kg_co2e']:.3f}")
        b.metric('Adapted · kg CO₂e',f"{after['total_kg_co2e']:.3f}")
        c.metric('Estimated reduction',f"{best['recipe_reduction_pct']:.1f}%",f"{best['saved_kg_co2e']:.3f} kg CO₂e saved")
        st.caption(f"Per serving: {original['per_serving_kg_co2e']:.3f} → {after['per_serving_kg_co2e']:.3f} kg CO₂e; {recipe['servings']:g} servings.")
        if best['fraction']:
            st.info(best['note'])
            similarity='Not available' if best['chemical_similarity'] is None else f"{best['chemical_similarity']:.3f} Jaccard"
            st.write(f"**Evidence:** {best['train_count']} observed training substitutions · compound overlap: {similarity} · coverage: {best['chemical_coverage']}.")
            st.caption(f"Evidence score: {best['evidence_score']:.3f}. Combines training frequency, recipe-context associations and available chemical profiles; it is not a sensory measurement.")
            sensitivity=model.sensitivity(recipe,source,best)
            st.caption(f"Illustrative ±20% factor stress test: savings {sensitivity['low']:.3f} to {sensitivity['high']:.3f} kg CO₂e. This is not a confidence interval.")
        else:st.info('No change selected. This is an explicit option; the system can abstain when rules or preferences rule out substitutions.')
        st.subheader('Your adapted ingredients')
        before_g={x['id']:x['grams'] for x in recipe['ingredients']};after_g={x['id']:x['grams'] for x in modified['ingredients']}
        table=pd.DataFrame([{'Ingredient':model.ingredients[k]['name'],'Original (g)':before_g.get(k,0),'Adapted (g)':after_g.get(k,0),
                            'Mapped food state':model.ingredients[k]['agb_name']} for k in sorted(before_g.keys()|after_g.keys())])
        st.dataframe(table,hide_index=True,width='stretch')
        st.download_button('Download adapted recipe',json.dumps(modified,indent=2),file_name='adapted_recipe.json',mime='application/json')
    st.divider()
    a,b=st.columns(2)
    with a:
        st.subheader('Where the original emissions come from')
        frame=pd.DataFrame(original['contributions']).set_index('name')
        st.bar_chart(frame[['kg_co2e']],color='#ab3527')
    with b:
        st.subheader('Replacement amount vs carbon reduction')
        points=pd.DataFrame([{'Fraction (%)':o['fraction']*100,'Candidate':o['target_name'],'Recipe reduction (%)':o['recipe_reduction_pct']} for o in options if o['fraction']])
        if not points.empty:
            st.line_chart(points,x='Fraction (%)',y='Recipe reduction (%)',color='Candidate')
        else:st.caption('No permitted replacements for this selection.')
    with st.expander('All options, Pareto frontier and objective scores'):
        cols=['target_name','fraction','recipe_reduction_pct','evidence_score','change_penalty','objective','pareto','chemical_coverage']
        st.dataframe(pd.DataFrame(options)[cols],hide_index=True,width='stretch')

with bench:
    st.subheader('Held-out substitute recovery')
    path=ROOT/'results/summary.json'
    if not path.exists():st.info('Run python scripts/evaluate.py to generate the evaluation.')
    else:
        result=json.loads(path.read_text())
        audit=result['audit']
        st.write(f"{audit['evaluated_test_records']:,} mapped test examples from {audit['original_gismo_test_records']:,} original GISMo test records. Targets outside the permitted candidate set count as misses in the all-mapped metrics.")
        st.dataframe(pd.DataFrame(result['benchmark']),hide_index=True,width='stretch')
        st.caption('The feasible-target metrics condition on the answer being in the candidate set and are easier. These are observed-substitute recovery scores, not taste or culinary-plausibility scores. GISMo provides ingredient context, not validated role labels for this experiment.')
        st.subheader('Carbon comparison on 24 authored scenarios')
        st.dataframe(pd.DataFrame(result['scenarios']),hide_index=True,width='stretch')
        st.caption('Carbon-only and flavour-only policies use their chosen candidate at its maximum permitted fraction. Combined optimization also chooses the fraction. Scenario results are illustrative, not estimates for the population of recipes.')
        st.image(str(ROOT/'results/method_comparison.png'))
        for filename in ['benchmark_metrics.csv','scenario_comparison.csv','pareto_options.csv','weight_sensitivity.csv']:
            st.download_button(f'Download {filename}',(ROOT/'results'/filename).read_bytes(),file_name=filename,mime='text/csv')

with data:
    st.subheader('Every ingredient has an auditable mapping')
    st.dataframe(pd.read_csv(ROOT/'data/ingredient_mapping.csv'),hide_index=True,width='stretch')
    st.json(json.loads((ROOT/'data/manifest.json').read_text()),expanded=False)
    w=model.evidence_weights
    st.markdown(f'''**Carbon accounting:** sum of grams / 1000 × kg CO₂e per kg in the mapped food state. No missing factor is silently treated as zero. These are ingredient-sum screening estimates, not a validated LCA of a cooked dish; do not add kitchen energy on top without reviewing lifecycle boundaries.

**Candidates:** directed substitution pairs observed in the GISMo training split, within the same manually assigned food family and a shared permitted cooking role, and not on the explicit blocked-pair list. Candidates must reduce estimated emissions after the mass-ratio adjustment.

**Evidence:** weights fitted on the GISMo validation split: {w['support']:g} for training frequency (log-scaled against the most observed swap overall); {w['context']:g} for mean context association when context is present; up to {w['chemistry']:g} for chemical Jaccard similarity, downweighted when either profile is sparse. Available weights are normalized. Missing chemical profiles remain missing.

**Optimization:** `alpha × whole-recipe carbon reduction − (1 − alpha) × fraction² × (1 − evidence score)`. The penalty is a heuristic preference model, not a prediction of taste change. Search includes no change, 25%, 50%, 75%, and 100%, subject to role and fraction limits.

**Sources:** [AGRIBALYSE / ADEME](https://data.ademe.fr/datasets/agribalyse-31-synthese) · [FlavorGraph](https://github.com/lamypark/FlavorGraph) · [GISMo / Recipe1MSubs](https://github.com/facebookresearch/gismo).

**Scope:** climate impact only; no water, land, nutrition or unchanged-taste guarantee. French-average factors may differ substantially from your actual supply chain. Curated mappings and role rules need culinary review.''')

with pilot:
    st.subheader('Taste pilot — ready to collect, not yet conducted')
    st.write('Use the protocol to compare an original dish with a selected adaptation. Record blind flavour-similarity ratings separately from liking. No participant responses are included or simulated.')
    for filename in ['taste_pilot_protocol.md','taste_ratings_template.csv']:
        p=ROOT/'results'/filename
        if p.exists():st.download_button('Download '+filename,p.read_bytes(),file_name=filename)
