"""Read-only HTTP interface to the existing EcoSwap engine."""
import copy
import csv
import json
import os
from functools import lru_cache
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from ecoswap import EcoSwap
from ecoswap.engine import number

ROOT = Path(__file__).resolve().parents[1]
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024
ALLOWED_ORIGINS = {s.strip().rstrip('/') for s in os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173').split(',') if s.strip()}
DOWNLOADS = {
    'benchmark_metrics.csv', 'scenario_comparison.csv', 'pareto_options.csv',
    'weight_sensitivity.csv', 'taste_pilot_protocol.md', 'taste_ratings_template.csv', 'REPORT.md',
}


@lru_cache(maxsize=1)
def model():
    return EcoSwap()


@app.after_request
def headers(response):
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store' if request.method == 'POST' else 'public, max-age=60'
    return response


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code


@app.get('/api/health')
def health():
    return jsonify(status='ok', ingredients=len(model().ingredients))


@app.get('/api/catalogue')
def catalogue():
    m = model()
    return jsonify(recipes=m.recipes, aliases=m.aliases, ingredients={key: {
        'name': value['name'], 'roles': value['roles'], 'food_state': value['agb_name'],
        'factor': value['factor'],
    } for key, value in m.ingredients.items()})


def match_recipe(raw, m):
    """Validate every row, but pass only recognized rows to the strict engine."""
    if not isinstance(raw, dict):
        raise ValueError('Recipe must be a JSON object')
    recipe = copy.deepcopy(raw)
    rows = recipe.get('ingredients')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('Use between 1 and 100 ingredients per recipe.')
    recipe.setdefault('name', 'Custom recipe')
    recipe.setdefault('id', 'custom')
    if not isinstance(recipe['name'], str) or not recipe['name'].strip() or len(recipe['name']) > 160:
        raise ValueError('Recipe name must be text of at most 160 characters.')
    recipe['servings'] = number(recipe.get('servings', 1), 'servings', 1, 10000)
    matched, unsupported, seen = [], [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
            raise ValueError('Each ingredient needs a non-empty text ID.')
        grams = number(row.get('grams'), 'grams', 0, 100000)
        if grams == 0:
            raise ValueError('Ingredient grams must be positive')
        if not isinstance(row.get('role'), str) or not row['role'].strip():
            raise ValueError('Each ingredient needs an explicit role')
        key = row['id'].strip().lower().replace(' ', '_')
        canonical = m.aliases.get(key)
        identity = canonical or key
        if identity in seen:
            raise ValueError('Combine duplicate ingredient rows before importing.')
        seen.add(identity)
        if canonical:
            row['id'] = canonical
            row['grams'] = grams
            matched.append(row)
        else:
            unsupported.append(row)  # Preserve the entire unsupported row verbatim.
    count, total = len(matched), len(rows)
    coverage = {
        'matched_count': count, 'original_count': total,
        'matched_ids': [r['id'] for r in matched],
        'unsupported': unsupported, 'partial': count < total,
        'label': (f'Matched ingredients only ({count} of {total} original ingredients covered).'
                  if count < total else 'All original ingredients covered.'),
    }
    return recipe, {**recipe, 'ingredients': matched}, coverage


def restore_unsupported(full, adapted, m, coverage):
    # Keep original row order; append any newly introduced supported ingredient.
    remaining = {r['id']: r for r in adapted['ingredients']}
    restored = []
    for row in full['ingredients']:
        if row['id'] not in m.ingredients:
            restored.append(copy.deepcopy(row))
        elif row['id'] in remaining:
            restored.append(remaining.pop(row['id']))
    restored.extend(remaining.values())
    result = {**adapted, 'ingredients': restored}
    if coverage['partial']:
        result['carbon_coverage'] = coverage
    return result


@app.post('/api/options')
def options():
    payload = request.get_json()
    try:
        if not isinstance(payload, dict):
            raise ValueError('Send a JSON object containing a recipe and source ingredient.')
        m = model()
        full, recipe, coverage = match_recipe(payload.get('recipe'), m)
        if not recipe['ingredients']:
            return jsonify(recipe=full, original=None, options=[], coverage=coverage,
                           message='No ingredients matched. Swap analysis is unavailable.')
        source = m.canonical(payload.get('source', ''))
        exclusions = payload.get('exclude', [])
        if not isinstance(exclusions, list) or len(exclusions) > len(m.ingredients):
            raise ValueError('Exclusions must be an ingredient list.')
        ranked = m.options(recipe, source, payload.get('alpha', .5), payload.get('max_fraction', 1), exclusions)
        original = m.footprint(recipe)
        output = []
        fields = ['target', 'target_name', 'fraction', 'before', 'after', 'saved_kg_co2e',
                  'recipe_reduction_pct', 'evidence_score', 'chemical_similarity',
                  'chemical_coverage', 'train_count', 'note', 'mass_ratio', 'objective', 'pareto', 'change_penalty']
        for option in ranked:
            adapted = recipe if option['fraction'] == 0 else m.apply(recipe, source, option['target'], option['fraction'])
            output.append({**{key: option[key] for key in fields}, 'recipe': restore_unsupported(full, adapted, m, coverage),
                           'footprint': m.footprint(adapted), 'sensitivity': m.sensitivity(recipe, source, option)})
        # Keep coverage tied to the original upload even when a swap adds/removes rows.
        if coverage['partial']:
            original['coverage'] = coverage['matched_count'] / coverage['original_count']
            original['coverage_label'] = coverage['label']
            for option in output:
                option['coverage_label'] = coverage['label']
                option['footprint']['coverage'] = original['coverage']
                option['footprint']['coverage_label'] = coverage['label']
        return jsonify(recipe=full, original=original, options=output, coverage=coverage,
                       message=('No suitable alternative found for this ingredient and settings.'
                                if not any(o['fraction'] > 0 for o in output) else None))
    except (ValueError, TypeError, KeyError) as error:
        return jsonify(error=str(error)), 422


@app.get('/api/research')
def research():
    return jsonify(summary=json.loads((ROOT / 'results/summary.json').read_text()),
                   manifest=json.loads((ROOT / 'data/manifest.json').read_text()),
                   weights=model().evidence_weights,
                   mapping=list(csv.DictReader((ROOT / 'data/ingredient_mapping.csv').open())))


@app.get('/api/download/<name>')
def download(name):
    if name not in DOWNLOADS:
        return jsonify(error='File not found.'), 404
    return send_from_directory(ROOT / 'results', name, as_attachment=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '8000')))
