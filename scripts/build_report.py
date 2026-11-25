"""Generate a report directly from saved experiment outputs."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    results=json.loads((ROOT/'results/summary.json').read_text())
    manifest=json.loads((ROOT/'data/manifest.json').read_text())
    examples=list(csv.DictReader((ROOT/'results/scenario_comparison.csv').open()))
    labels={'carbon_only':'Carbon only','flavor_only':'Compound overlap only','frequency':'Frequency baseline','combined':'Combined'}
    audit=results['audit'];bench=results['benchmark'][0];weights=results['evidence_weights']
    n,feasible=bench['mapped_test_records'],bench['feasible_target_records']
    w=weights['in_use'];fmt_w=lambda x:f"support {x['support']:g}, context {x['context']:g}, chemistry {x['chemistry']:g}"
    lines=['# EcoSwap: implementation and measured results','',
    'A transparent prototype for lower-carbon ingredient replacement. The software and computational experiments are complete. **The physical taste pilot has not been conducted.**','',
    '## What you can use now','',
    '- Open `EcoSwap_demo.html` directly for the offline explorer. It exposes the same precomputed recipe options as the Python engine.',
    '- Run `python -m streamlit run app.py` for the full app, including custom recipe JSON, source selection, quantities, exclusions, and data downloads.',
    '- Inspect the source code, raw datasets, explicit mappings, individual predictions and tests in the accompanying project.',
    '', '## The four deliverables','',
    '| Deliverable | Concrete result |','|---|---|',
    '| Carbon estimator | Ingredient contributions, total and per-serving emissions using quantities in grams and named AGRIBALYSE records. Unknown quantities/factors cannot silently become zero. |',
    '| Substitute ranking | Training-supported directed pairs filtered by manually assigned food families and cooking roles; ranks with frequency, context and chemical evidence. |',
    '| Partial optimization | No change and 25/50/75/100% replacements, mass ratios, pair-specific fraction limits, exclusion filters and a computed Pareto frontier. |',
    '| Evaluation and taste pilot | Held-out ranking, baseline comparisons, scenario carbon calculations and sensitivity completed. Protocol, blank ratings CSV and analysis script supplied; cooking/tasting remains to be done. |',
    '', '## Data actually processed','',
    f"- AGRIBALYSE API snapshot: **{manifest['environment_rows']:,} rows**, with **{manifest['catalogue_ingredients']}** explicitly mapped ingredients. Metadata identifies version 3.2 despite `31` in the API URL.",
    f"- FlavorGraph: **{manifest['flavor_ingredients_with_profiles']}** ingredient source nodes have direct flavour-compound edges in the downloaded CSV; **{manifest['catalogue_with_profiles']} of {manifest['catalogue_ingredients']}** mapped ingredients have chemical profiles.",
    f"- GISMo: **{manifest['gismo_train_records']:,} training**, **{manifest['gismo_val_records']:,} validation**, and **{manifest['gismo_test_records']:,} test** examples downloaded. **{manifest['mapped_train_pairs']}** directed training pairs map to this catalogue; **{manifest['role_permitted_pairs']}** pass the basic food-family/role rules, before carbon and query-specific filtering.",
    '- RecipeEmissions: 5,595 records inspected. Its quantities were not used: recipe 79222 records a 14-ounce can as 28.35 g and a dash of cayenne as 142 g. Twenty-four gram-based scenarios were authored and labelled explicitly instead.',
    '', '## Experiment 1: observed-substitute recovery','',
    f"The test set is not used to fit pair counts, context associations or weights. Exact curated alias matching maps {n:,} of the {audit['original_gismo_test_records']:,} test examples to distinct catalogue ingredients ({n/audit['original_gismo_test_records']:.2%}), after excluding {audit['excluded_train_recipe_id_overlap']} whose recipe ID also appears in training. These represent {audit['unique_test_recipes']:,} recipe IDs. Results therefore describe a subset, not the complete GISMo benchmark.",
    '', f"All methods use the same permitted lower-carbon candidate sets. Of {n:,} mapped targets, {feasible:,} ({feasible/n:.1%}) can be retrieved from those sets; the other {n-feasible:,} count as misses below. Most of those are substitutes with a higher carbon factor, which the system never suggests by design. There are {bench['abstentions']} abstentions. This benchmark does not have ground-truth cooking-role labels, so it accepts any shared manually allowed role; the app uses a user-specified role.",
    '', f'| Method | Top-1, all {n:,} | Top-5, all {n:,} | MRR, all {n:,} | Top-1, feasible {feasible:,} only |',
    '|---|---:|---:|---:|---:|']
    for r in results['benchmark']:
        lines.append(f"| {labels[r['method']]} | {r['hit1_all_mapped']:.1%} | {r['hit5_all_mapped']:.1%} | {r['mrr_all_mapped']:.3f} | {r['hit1_feasible']:.1%} |")
    lines += ['',
    '**Finding:** combined ranking improves observed-substitute recovery over carbon-only and chemical-overlap-only ranking, but the simpler frequency baseline is slightly better. We do not claim a state-of-the-art model or superiority to every baseline. Conditional scores on the feasible targets are easier and should not replace the all-mapped scores.',
    '', 'Top-1 asks whether the first suggestion equals the recorded substitute; top-5 asks whether it occurs among the first five. MRR averages the reciprocal rank, with zero for an unreachable target. A different suggested substitute can still be reasonable; exact-match recovery is not a taste or plausibility measurement. Multiple records can share a recipe, so these rows are not independent sensory observations.',
    '', f"The active app uses manually chosen base weights: **{fmt_w(w)}**. These include compound evidence when available; sparse profiles reduce its effective weight.",'', '## Experiment 1b: fitted evidence weights (comparison)','',
    f"`scripts/fit_weights.py` searches every weight combination on a 0.05 grid using only the {weights['validation']['records']:,} mapped validation records. It keeps the one with the highest validation MRR averaged over carbon priorities 0, 0.25, 0.5 and 0.75, because the evidence score is always mixed with carbon in the app. Fitted comparison weights: **{fmt_w(json.loads((ROOT/'data/evidence_weights.json').read_text())['weights'])}** (hand-picked: {fmt_w(weights['hand_picked'])}). Ranking on evidence alone would favour more context ({fmt_w(json.loads((ROOT/'data/evidence_weights.json').read_text())['evidence_only_optimum']['weights'])}), but those weights shrink the score so the carbon term dominates at the default setting.",
    '', '| Weights | Ranking | Top-1 | MRR |','|---|---|---:|---:|']
    for r in weights['test']:
        lines.append(f"| {r['weights'].replace('_',' ').capitalize()} | {'Evidence only (α = 0)' if r['ranking']=='evidence_only' else 'Combined (α = 0.5)'} | {r['hit1_all_mapped']:.1%} | {r['mrr_all_mapped']:.4f} |")
    lines += ['']+[f"- {'Evidence only' if k=='evidence_only' else 'Combined'}: fitted minus hand-picked MRR {v['mrr_difference']:+.4f} (95% paired bootstrap interval over recipes {v['ci95_low']:+.4f} to {v['ci95_high']:+.4f})." for k,v in weights['test_mrr_difference'].items()]
    lines += ['', '**Finding:** this validation search selected zero compound weight for recorded-substitute recovery. The app deliberately uses the manually chosen 60/20/20 weights to include chemical evidence. The fitted comparison improves MRR slightly; these results do not measure sensory preservation.',
    '', '## Experiment 2: carbon estimates on 24 scenarios','',
    '| Policy | Mean recipe reduction | Median recipe reduction | Positive savings under illustrative ±20% factor stress |',
    '|---|---:|---:|---:|']
    for r in results['scenarios']:
        lines.append(f"| {labels[r['method']]} | {r['mean_recipe_reduction_pct']:.1f}% | {r['median_recipe_reduction_pct']:.1f}% | {r['positive_savings_under_20pct_stress']} / 24 |")
    lines += ['',
    'Carbon-only selects the option with the largest estimated whole-recipe saving. Frequency-only and compound-overlap-only select a candidate and use its maximum permitted fraction. Combined optimization jointly selects candidate and fraction at carbon priority 0.5, with no change available. These are policy comparisons; the fraction choice is a deliberate difference. All operate on the same rule-permitted options.',
    '', '**These scenarios were selected for demonstration.** Their mean reduction is not an estimate for typical recipes, and carbon-only achieving greater reduction does not establish equivalent flavour, nutrition or culinary quality. No cooking outcomes are inferred from these calculations.',
    '', '### Concrete combined-policy examples','',
    '| Scenario | Replacement | Original kg CO₂e | Adapted kg CO₂e | Estimated reduction |',
    '|---|---|---:|---:|---:|']
    for r in examples:
        if r['method']=='combined' and r['recipe_id'] in ['demo_01','demo_13','demo_15','demo_19','demo_22']:
            swap='Keep original' if float(r['fraction'])==0 else f"{float(r['fraction']):.0%} {r['source']} → {r['target'].replace('_',' ')}"
            lines.append(f"| {r['recipe']} | {swap} | {float(r['before']):.3f} | {float(r['after']):.3f} | {float(r['recipe_reduction_pct']):.1f}% |")
    lines += ['',
    'For the first example, the recipe contains 400 g of beef. The mapped factors are 35.7 kg CO₂e/kg for raw 15%-fat minced beef and 4.56 for raw turkey meat, yielding 12.456 kg CO₂e of modelled savings at equal mass. Turkey meat is a proxy for minced turkey; this is visible in the mapping notes. The other ingredients are unchanged.',
    '', '## Architecture and equations','',
    'The runtime is a small deterministic Python engine with a Streamlit UI. There is no neural network, GPU, paid model or generated substitution text. Training consists of counting observed directed substitutions and their ingredient contexts. The code separates data preparation, accounting, ranking, optimization and evaluation.',
    '', '`E(recipe) = Σ grams_i / 1000 × factor_i`',
    '', '`saving(a→b, f) = grams_a / 1000 × f × (factor_a − mass_ratio × factor_b)`',
    '', 'The support term is `log(1 + pair_count) / log(1 + largest_allowed_pair_count_overall)`, so a rarely observed swap scores low even when it is the only option for its source. Context association averages how often the current recipe context ingredients appear in training examples for that pair. Chemical similarity is the Jaccard overlap between compound sets. Chemical weight is reduced by `min(profile_sizes)/(min(profile_sizes)+20)`. Missing chemical terms are omitted and remaining weights normalized; this is a heuristic availability treatment, not statistical imputation.',
    '', f"The evidence score combines support, context (if context exists) and chemistry with manually chosen base weights ({fmt_w(w)}). It is not calibrated to taste, probability of acceptability, or amount of flavour preserved.",
    '', '`objective = α × whole_recipe_reduction − (1−α) × f² × (1−evidence)`',
    '', 'The square on replacement fraction is a chosen increasing change penalty. It allows partial options to trade off with emissions. It is not a mechanistic model of sensory mixtures. The script records sensitivity to α = 0, 0.25, 0.5, 0.75 and 1; no test-set tuning was done.',
    '', '## Boundaries that matter','',
    '- Only lower-carbon pairs observed in training are offered. Unseen replacements can be missed, and unsupported queries can abstain.',
    '- Same-family and cooking-role rules are manual design choices, not an independent culinary validation. No rule-violation metric is presented as proof of quality.',
    '- Recipe quantities must match named food states. Cooked grains and legumes use cooked weight; meat examples use raw weight. These are ingredient-sum screening estimates, not a validated finished-dish LCA.',
    '- Chemical coverage is uneven. Compound identity alone does not model concentration, aroma thresholds, texture or cooking transformations. Some species-level profiles and carbon records are proxies.',
    '- AGRIBALYSE factors describe French-average conditions; they are not India-specific production or purchasing measurements.',
    '- The ±20% factor perturbation is a stress test, not a confidence interval. DQR is retained as supplied, not interpreted as a variance.',
    '- Taste pilot, independent expert plausibility review, nutritional equivalence and preparation-instruction adaptation remain unperformed.',
    '', '## Reproducibility and outputs','',
    'Run the commands in README.md. The source files are hashed in `data/manifest.json`; individual mappings are in `data/ingredient_mapping.csv`. Ranking predictions, all optimization options and scenario comparisons are saved as CSV, not just aggregate numbers. The taste sheet is empty, and the analysis script explicitly reports “not conducted” on it.',
    '', 'Sources: [AGRIBALYSE public API](https://data.ademe.fr/datasets/agribalyse-31-synthese), [AGRIBALYSE documentation](https://doc.agribalyse.fr/documentation/utiliser-agribalyse/acces-donnees), [FlavorGraph](https://github.com/lamypark/FlavorGraph), [GISMo / Recipe1MSubs](https://github.com/facebookresearch/gismo), [RecipeEmissions](https://github.com/RaoulKalisvaart/green-recommender-systems). Dataset snapshot retrieved 1 October 2026. Third-party licenses and attribution are retained in the project.',
    '']
    (ROOT/'results/REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Generated results/REPORT.md')

if __name__=='__main__':main()

