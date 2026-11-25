# EcoSwap: implementation and measured results

A transparent prototype for lower-carbon ingredient replacement. The software and computational experiments are complete. **The physical taste pilot has not been conducted.**

## What you can use now

- Open `EcoSwap_demo.html` directly for the offline explorer. It exposes the same precomputed recipe options as the Python engine.
- Run `python -m streamlit run app.py` for the full app, including custom recipe JSON, source selection, quantities, exclusions, and data downloads.
- Inspect the source code, raw datasets, explicit mappings, individual predictions and tests in the accompanying project.

## The four deliverables

| Deliverable | Concrete result |
|---|---|
| Carbon estimator | Ingredient contributions, total and per-serving emissions using quantities in grams and named AGRIBALYSE records. Unknown quantities/factors cannot silently become zero. |
| Substitute ranking | Training-supported directed pairs filtered by manually assigned food families and cooking roles; ranks with frequency, context and chemical evidence. |
| Partial optimization | No change and 25/50/75/100% replacements, mass ratios, pair-specific fraction limits, exclusion filters and a computed Pareto frontier. |
| Evaluation and taste pilot | Held-out ranking, baseline comparisons, scenario carbon calculations and sensitivity completed. Protocol, blank ratings CSV and analysis script supplied; cooking/tasting remains to be done. |

## Data actually processed

- AGRIBALYSE API snapshot: **2,451 rows**, with **135** explicitly mapped ingredients. Metadata identifies version 3.2 despite `31` in the API URL.
- FlavorGraph: **400** ingredient source nodes have direct flavour-compound edges in the downloaded CSV; **76 of 135** mapped ingredients have chemical profiles.
- GISMo: **49,044 training**, **10,729 validation**, and **10,747 test** examples downloaded. **2080** directed training pairs map to this catalogue; **579** pass the basic food-family/role rules, before carbon and query-specific filtering.
- RecipeEmissions: 5,595 records inspected. Its quantities were not used: recipe 79222 records a 14-ounce can as 28.35 g and a dash of cayenne as 142 g. Twenty-four gram-based scenarios were authored and labelled explicitly instead.

## Experiment 1: observed-substitute recovery

The test set is not used to fit pair counts, context associations or weights. Exact curated alias matching maps 3,663 of the 10,747 test examples to distinct catalogue ingredients (34.08%), after excluding 0 whose recipe ID also appears in training. These represent 2,688 recipe IDs. Results therefore describe a subset, not the complete GISMo benchmark.

All methods use the same permitted lower-carbon candidate sets. Of 3,663 mapped targets, 1,340 (36.6%) can be retrieved from those sets; the other 2,323 count as misses below. Most of those are substitutes with a higher carbon factor, which the system never suggests by design. There are 927 abstentions. This benchmark does not have ground-truth cooking-role labels, so it accepts any shared manually allowed role; the app uses a user-specified role.

| Method | Top-1, all 3,663 | Top-5, all 3,663 | MRR, all 3,663 | Top-1, feasible 1,340 only |
|---|---:|---:|---:|---:|
| Carbon only | 10.6% | 30.6% | 0.178 | 29.1% |
| Compound overlap only | 13.4% | 34.4% | 0.209 | 36.7% |
| Frequency baseline | 22.1% | 35.3% | 0.277 | 60.5% |
| Combined | 18.8% | 33.7% | 0.252 | 51.4% |

**Finding:** combined ranking improves observed-substitute recovery over carbon-only and chemical-overlap-only ranking, but the simpler frequency baseline is slightly better. We do not claim a state-of-the-art model or superiority to every baseline. Conditional scores on the feasible targets are easier and should not replace the all-mapped scores.

Top-1 asks whether the first suggestion equals the recorded substitute; top-5 asks whether it occurs among the first five. MRR averages the reciprocal rank, with zero for an unreachable target. A different suggested substitute can still be reasonable; exact-match recovery is not a taste or plausibility measurement. Multiple records can share a recipe, so these rows are not independent sensory observations.

The active app uses manually chosen base weights: **support 0.6, context 0.2, chemistry 0.2**. These include compound evidence when available; sparse profiles reduce its effective weight.

## Experiment 1b: fitted evidence weights (comparison)

`scripts/fit_weights.py` searches every weight combination on a 0.05 grid using only the 3,590 mapped validation records. It keeps the one with the highest validation MRR averaged over carbon priorities 0, 0.25, 0.5 and 0.75, because the evidence score is always mixed with carbon in the app. Fitted comparison weights: **support 0.95, context 0.05, chemistry 0** (hand-picked: support 0.6, context 0.2, chemistry 0.2). Ranking on evidence alone would favour more context (support 0.65, context 0.35, chemistry 0), but those weights shrink the score so the carbon term dominates at the default setting.

| Weights | Ranking | Top-1 | MRR |
|---|---|---:|---:|
| Hand picked | Evidence only (α = 0) | 22.3% | 0.2778 |
| Hand picked | Combined (α = 0.5) | 18.8% | 0.2516 |
| Fitted | Evidence only (α = 0) | 22.3% | 0.2781 |
| Fitted | Combined (α = 0.5) | 19.3% | 0.2557 |

- Evidence only: fitted minus hand-picked MRR +0.0003 (95% paired bootstrap interval over recipes -0.0016 to +0.0021).
- Combined: fitted minus hand-picked MRR +0.0040 (95% paired bootstrap interval over recipes +0.0020 to +0.0062).

**Finding:** this validation search selected zero compound weight for recorded-substitute recovery. The app deliberately uses the manually chosen 60/20/20 weights to include chemical evidence. The fitted comparison improves MRR slightly; these results do not measure sensory preservation.

## Experiment 2: carbon estimates on 24 scenarios

| Policy | Mean recipe reduction | Median recipe reduction | Positive savings under illustrative ±20% factor stress |
|---|---:|---:|---:|
| Carbon only | 53.2% | 50.1% | 19 / 24 |
| Compound overlap only | 39.5% | 37.2% | 13 / 24 |
| Frequency baseline | 43.3% | 38.1% | 17 / 24 |
| Combined | 35.5% | 36.0% | 19 / 24 |

Carbon-only selects the option with the largest estimated whole-recipe saving. Frequency-only and compound-overlap-only select a candidate and use its maximum permitted fraction. Combined optimization jointly selects candidate and fraction at carbon priority 0.5, with no change available. These are policy comparisons; the fraction choice is a deliberate difference. All operate on the same rule-permitted options.

**These scenarios were selected for demonstration.** Their mean reduction is not an estimate for typical recipes, and carbon-only achieving greater reduction does not establish equivalent flavour, nutrition or culinary quality. No cooking outcomes are inferred from these calculations.

### Concrete combined-policy examples

| Scenario | Replacement | Original kg CO₂e | Adapted kg CO₂e | Estimated reduction |
|---|---|---:|---:|---:|
| Beef and tomato pasta | 100% beef → turkey | 15.285 | 2.829 | 81.5% |
| Butter biscuit batter | 100% butter → margarine | 1.328 | 0.770 | 42.0% |
| Creamy spinach pasta | 50% cream → milk | 1.532 | 1.303 | 14.9% |
| Milk rice pudding | 75% milk → almond milk | 1.276 | 0.791 | 38.0% |
| Cheddar potato topping | Keep original | 1.867 | 1.867 | 0.0% |

For the first example, the recipe contains 400 g of beef. The mapped factors are 35.7 kg CO₂e/kg for raw 15%-fat minced beef and 4.56 for raw turkey meat, yielding 12.456 kg CO₂e of modelled savings at equal mass. Turkey meat is a proxy for minced turkey; this is visible in the mapping notes. The other ingredients are unchanged.

## Architecture and equations

The runtime is a small deterministic Python engine with a Streamlit UI. There is no neural network, GPU, paid model or generated substitution text. Training consists of counting observed directed substitutions and their ingredient contexts. The code separates data preparation, accounting, ranking, optimization and evaluation.

`E(recipe) = Σ grams_i / 1000 × factor_i`

`saving(a→b, f) = grams_a / 1000 × f × (factor_a − mass_ratio × factor_b)`

The support term is `log(1 + pair_count) / log(1 + largest_allowed_pair_count_overall)`, so a rarely observed swap scores low even when it is the only option for its source. Context association averages how often the current recipe context ingredients appear in training examples for that pair. Chemical similarity is the Jaccard overlap between compound sets. Chemical weight is reduced by `min(profile_sizes)/(min(profile_sizes)+20)`. Missing chemical terms are omitted and remaining weights normalized; this is a heuristic availability treatment, not statistical imputation.

The evidence score combines support, context (if context exists) and chemistry with manually chosen base weights (support 0.6, context 0.2, chemistry 0.2). It is not calibrated to taste, probability of acceptability, or amount of flavour preserved.

`objective = α × whole_recipe_reduction − (1−α) × f² × (1−evidence)`

The square on replacement fraction is a chosen increasing change penalty. It allows partial options to trade off with emissions. It is not a mechanistic model of sensory mixtures. The script records sensitivity to α = 0, 0.25, 0.5, 0.75 and 1; no test-set tuning was done.

## Boundaries that matter

- Only lower-carbon pairs observed in training are offered. Unseen replacements can be missed, and unsupported queries can abstain.
- Same-family and cooking-role rules are manual design choices, not an independent culinary validation. No rule-violation metric is presented as proof of quality.
- Recipe quantities must match named food states. Cooked grains and legumes use cooked weight; meat examples use raw weight. These are ingredient-sum screening estimates, not a validated finished-dish LCA.
- Chemical coverage is uneven. Compound identity alone does not model concentration, aroma thresholds, texture or cooking transformations. Some species-level profiles and carbon records are proxies.
- AGRIBALYSE factors describe French-average conditions; they are not India-specific production or purchasing measurements.
- The ±20% factor perturbation is a stress test, not a confidence interval. DQR is retained as supplied, not interpreted as a variance.
- Taste pilot, independent expert plausibility review, nutritional equivalence and preparation-instruction adaptation remain unperformed.

## Reproducibility and outputs

Run the commands in README.md. The source files are hashed in `data/manifest.json`; individual mappings are in `data/ingredient_mapping.csv`. Ranking predictions, all optimization options and scenario comparisons are saved as CSV, not just aggregate numbers. The taste sheet is empty, and the analysis script explicitly reports “not conducted” on it.

Sources: [AGRIBALYSE public API](https://data.ademe.fr/datasets/agribalyse-31-synthese), [AGRIBALYSE documentation](https://doc.agribalyse.fr/documentation/utiliser-agribalyse/acces-donnees), [FlavorGraph](https://github.com/lamypark/FlavorGraph), [GISMo / Recipe1MSubs](https://github.com/facebookresearch/gismo), [RecipeEmissions](https://github.com/RaoulKalisvaart/green-recommender-systems). Dataset snapshot retrieved 1 October 2026. Third-party licenses and attribution are retained in the project.
