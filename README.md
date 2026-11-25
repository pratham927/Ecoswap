# EcoSwap

## React website

The redesigned website is in `frontend/`, with a photographic homepage, separate Swap Studio, How It Works and Research pages, and a Python API in `api/`. See [DEPLOY_REACT.md](DEPLOY_REACT.md) for local development and free Render + Cloudflare Pages deployment. The original Streamlit app below remains available.

A working computational gastronomy mini-project for **lower-carbon ingredient replacement with substitution evidence and flavour-compound support**.

## Start here

Open **EcoSwap_demo.html** in a browser. It works offline, with no installation, and exposes the precomputed 24-scenario option sets from the Python engine. Change the recipe, carbon priority, replacement cap, or chosen alternative. Download the adapted ingredient list.

For the full application, including custom recipe JSON, ingredient selection, source quantities and exclusions:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, use your Python launcher:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Run commands inside the extracted `ecoswap` folder. No GPU, paid API, API key, model download, or account is required. Source snapshots and processed data are included. Python 3.10+ is recommended; tested with Python 3.12, Streamlit 1.64.0, pandas 2.2.3, matplotlib 3.10.8 and pytest 9.1.1.

## Four deliverables

| Deliverable | Implemented output | Status |
|---|---|---|
| Recipe carbon estimator | Grams × mapped emission factors, ingredient contributions, totals and per-serving estimates; invalid/unknown inputs rejected | Implemented |
| Substitute ranking | Directed GISMo training support, manually specified role restrictions, context association, chemical overlap with missing/sparse flags; evidence weights fitted on the validation split | Implemented |
| Partial-replacement optimization | Discrete no-change/25/50/75/100% search, carbon preference slider, fraction limits, Pareto frontier, before/after lists | Implemented |
| Comparative evaluation and taste pilot | Held-out ranking, baseline comparison, 24-scenario emissions analysis, factor/weight sensitivity, taste protocol and rating analysis | Computational evaluation complete; physical taste pilot pending |

The system **does not claim that taste is preserved**. The evidence score is not a taste probability. It uses climate impact as one sustainability indicator; it does not model nutrition, water use or land use.

## Reproduce

```bash
python scripts/build_data.py
python scripts/build_recipes.py
python scripts/fit_weights.py
python scripts/evaluate.py
python scripts/export_demo.py
python scripts/build_report.py
python -m pytest -q
```

`build_data.py` needs only the Python standard library. It converts class-free public GISMo pickle records using a restricted unpickler that rejects executable globals. No arbitrary pickle classes are imported. `evaluate.py` optionally uses matplotlib to generate figures. The application uses pandas and Streamlit. `scripts/download_data.py` can fetch missing raw snapshots and checks shipped SHA-256 hashes; upstream changes are saved separately for review.

## Actual results

On **3,663 mapped held-out examples** from the 10,747-record GISMo test split, combined top-1 recovery is **19.3%**, compared with carbon-only **10.6%**, compound-overlap-only **13.4%**, and frequency-only **22.1%**. The simple frequency baseline is better. Only 1,340 of the 3,663 targets are present in the constrained candidate sets, mostly because about half of the recorded substitutes have a higher carbon factor and are never suggested by design. All-mapped metrics count the others as misses; the report also shows the easier feasible-target metrics. No recipe ID overlaps the training split in these examples.

Fitted evidence weights (**support 0.95, context 0.05, chemistry 0**) beat the hand-picked 0.6 / 0.2 / 0.2 on the combined ranking the app uses: test MRR 0.2557 vs 0.2516, a difference of +0.0040 (95% paired bootstrap interval +0.0020 to +0.0062). Ranking on evidence alone they are level. Flavour-compound overlap adds nothing measurable to predicting which substitute people choose.

On **24 author-defined scenarios**, mean estimated recipe-level reductions are combined **38.4%**, carbon-only **53.2%**, compound-overlap-only **39.5%**, and frequency-only **43.3%**. These are illustrative computations on selected scenarios, not unbiased population results or measured real-world savings. Combined optimization chooses the replacement fraction; the other policies use the chosen candidate's maximum permitted fraction. See `results/REPORT.md` for the complete interpretation.

## Model

1. Normalize only aliases explicitly listed in `data/catalogue.csv`. No fuzzy mapping or unknown-ingredient zero-fill.
2. Calculate `E = sum(grams_i / 1000 * factor_i)` using each mapped food state.
3. Retrieve directed pairs seen in GISMo training. Filter by same food family, shared role, the explicit list in `data/blocked_pairs.csv`, exclusions, and `replacement_mass_ratio * target_factor < source_factor`.
4. Build an evidence score from pair count `log(1+count)/log(1+largest permitted count overall)`, context association (when context exists) and Jaccard overlap (downweighted by `min(profile_sizes)/(min(profile_sizes)+20)`). Normalize available weights. A missing chemical profile stays missing; it is not assigned zero overlap. The weights come from `data/evidence_weights.json`, written by `scripts/fit_weights.py`: it tries every combination on a 0.05 grid and keeps the best validation MRR averaged over carbon priorities 0, 0.25, 0.5 and 0.75. The test split is not read. The original hand-picked weights stay available as `HAND_PICKED_WEIGHTS`.
5. Ranking score for combined candidates is `alpha * ingredient_reduction_fraction + (1-alpha) * evidence`. Carbon-only ranks by carbon reduction; flavour-only ranks by available Jaccard overlap, with missing profiles last and training frequency as a tie-break; frequency ranks by observed training count.
6. Optimize recipe-level options using `alpha * whole_recipe_reduction - (1-alpha) * fraction**2 * (1-evidence)`. The convex penalty is a declared modelling choice, not a trained sensory prediction. Keep-original has zero benefit and zero penalty.

The generic role rules are conservative but not externally validated. For example, butter→oil is allowed for sautéing and blocked for baking. The oil mass ratio is 0.82 as an approximate fat-mass conversion. Protein→legume replacements are capped at 50%. Sugar and salt have their own families, so noisy GISMo pairs such as sugar↔salt and pepper→salt are blocked. Herbs are split from spices, and warm baking spices from hot ones. Dried herbs and garlic or onion powder swap with fresh at 1 g dried : 3 g fresh. Tomato paste has its own role because no catalogue item replaces it gram for gram. Ratios of 1 for other pairs are modelling assumptions, not universal culinary instructions. The engine adapts ingredient lists; it does not rewrite cooking instructions or guarantee equivalent nutrition.

## Data and provenance

| Source | Retrieved and used | Caveat |
|---|---|---|
| [AGRIBALYSE 3.2 / ADEME API](https://data.ademe.fr/datasets/agribalyse-31-synthese) | 2,451 rows in the actual public API snapshot; 135 manually mapped ingredient records | French-average factors, food-state and cut/product proxies. API route contains `31` but retrieved metadata explicitly identifies 3.2. Documentation's 2,516 count differs from the API snapshot; no missing records invented. |
| [FlavorGraph](https://github.com/lamypark/FlavorGraph) | nodes and edges; 400 source nodes with direct `ingr-fcomp` edges in these files; 76 of the 135 catalogue ingredients have profiles | Incomplete and uneven chemical coverage; ignores concentrations, cooking transformations and sensory thresholds. Species profiles used for some ground-meat aliases. |
| [GISMo / Recipe1MSubs](https://github.com/facebookresearch/gismo) | 49,044 training, 10,729 validation and 10,747 test records; 2,080 mapped training pairs, 579 permitted by basic family/role rules before carbon filtering | Only a subset overlaps the curated catalogue. No pretrained GISMo model is reproduced. The validation split is used only to fit the three evidence weights. |
| [RecipeEmissions](https://github.com/RaoulKalisvaart/green-recommender-systems) | Inspected 5,595 records | Not used for quantitative recipe calculations: observed suspect unit conversions. Demo scenarios are explicitly authored instead. |

`data/catalogue.csv` is the editable source of every mapping choice. `data/ingredient_mapping.csv` gives exact AGRIBALYSE codes, English product names, factors, DQR, FlavorGraph IDs and mapping notes. `data/manifest.json` records source hashes and coverage. Source licenses are included; GISMo data is CC BY-NC 4.0 and FlavorGraph is Apache 2.0. AGRIBALYSE uses the French Open Licence / Etalab. This bundled project is for academic/noncommercial use; third-party data retains its original terms. The RecipeEmissions snapshot is retained for the documented audit, not claimed as newly authored data.

Relevant papers:

- Park et al. (2021), *FlavorGraph: a large-scale food-chemical graph for generating food representations and recommending food pairings*. [Scientific Reports](https://doi.org/10.1038/s41598-020-79422-8).
- Fatemi et al. (2023), *Learning to Substitute Ingredients in Recipes*. [arXiv](https://arxiv.org/abs/2302.07960).
- *Towards Carbon Footprint-Aware Recommender Systems for Greener Item Recommendation*. [Dataset repository and paper attribution](https://github.com/RaoulKalisvaart/green-recommender-systems).
- [AGRIBALYSE methodology and dataset access](https://doc.agribalyse.fr/documentation/utiliser-agribalyse/acces-donnees).

## Custom recipes

Import JSON shaped like the following. The source quantity must match the mapped food state, and each row needs a role. Zero/negative/non-finite masses, missing IDs or roles, and duplicate canonical ingredients are rejected. Catalogue aliases used in the benchmark do not imply validated quantity conversions.

In the React Studio and API, rows whose IDs are not in the catalogue are accepted as unsupported: they are kept unchanged (ID, quantity and any extra fields) in the adapted recipe and download, but excluded from carbon calculations. Estimates and percentage reductions for such recipes are labelled with their coverage, for example “Matched ingredients only (5 of 10 original ingredients covered).” If no ingredient matches, no estimate is shown and swap analysis is disabled. The Streamlit app still requires every ingredient to be in the catalogue.

```json
{
  "name": "My sauteed spinach",
  "servings": 2,
  "ingredients": [
    {"id": "butter", "grams": 50, "role": "saute"},
    {"id": "spinach", "grams": 400, "role": "background"},
    {"id": "garlic", "grams": 10, "role": "background"}
  ]
}
```

The UI lets you specify a role when selecting a different source ingredient. Exclusions affect suggested replacements only, not existing ingredients. No allergen certification is provided by those controls.

## Adding ingredients

Every mapping lives in `data/catalogue.csv`, one row per ingredient: AGRIBALYSE code, FlavorGraph node, family, roles, aliases and notes. The `status` column controls what gets built:

- `reviewed`: built by default.
- `proposed`: built only with `python scripts/build_data.py --include-proposed`, for previews.
- anything else (for example `rejected`): never built.

A row with only `id` and `aliases` filled adds aliases to an ingredient defined earlier in the file.

To add more ingredients:

1. Run `python scripts/propose_mappings.py --top 200`. It writes `data/review/mapping_proposals.csv`: the most frequent unmapped GISMo substitution names, with up to three AGRIBALYSE candidates, the FlavorGraph match and a family hint. These are suggestions only.
2. Choose the record, group aliases and set roles, then add the row to `data/catalogue.csv` with `status=proposed`.
3. Preview with `--include-proposed`, then switch checked rows to `reviewed` and rebuild.

The catalogue holds 135 reviewed ingredients: the original 40, plus 95 added and reviewed by Claude on 2026-11-19, which is not a human expert check. Four proposals were rejected, with reasons in `review_note`. Rows marked "Proxy record" use the nearest available AGRIBALYSE record.

## Project files

- `ecoswap/engine.py`: accounting, constraints, ranking, optimizer and sensitivity.
- `app.py`: full interactive Streamlit application.
- `EcoSwap_demo.html`: immediately usable offline scenario explorer, generated from engine outputs.
- `scripts/`: data preparation, evaluation, offline-demo export and pilot analysis.
- `data/catalogue.csv`: editable ingredient mappings with review status; `data/review/`: generated mapping suggestions.
- `data/blocked_pairs.csv`: explicitly blocked substitutions, with reasons.
- `data/evidence_weights.json` and `scripts/fit_weights.py`: fitted evidence weights and the validation-only fitting script.
- `data/`: processed catalogue, aliases, scenarios, evaluation subsets, mapping sheet and raw snapshots.
- `results/`: report, detailed predictions, method comparisons, Pareto options, sensitivity tables, figures and empty taste forms.
- `tests/`: accounting, validation, constraints, missingness, deterministic ranking and optimization checks.

## Important boundaries

These totals are ingredient-sum screening estimates, not a validated recipe lifecycle assessment. Raw/cooked food states, composition and generic proxies are visible in the mapping table. Do not add another kitchen-energy estimate without revisiting dataset boundaries. A ±20% sensitivity band is an illustrative factor stress test, not a statistical confidence interval; DQR is not converted to a standard error. Taste, texture and liking require a physical pilot. No pilot responses are included or fabricated.

