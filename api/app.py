"""Read-only HTTP interface to the existing EcoSwap engine."""
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
    return jsonify(recipes=m.recipes, ingredients={key: {
        'name': value['name'], 'roles': value['roles'], 'food_state': value['agb_name'],
        'factor': value['factor'],
    } for key, value in m.ingredients.items()})


@app.post('/api/options')
def options():
    payload = request.get_json()
    try:
        if not isinstance(payload, dict):
            raise ValueError('Send a JSON object containing a recipe and source ingredient.')
        m = model()
        recipe = m.validate_recipe(payload.get('recipe'))
        if len(recipe['ingredients']) > 100:
            raise ValueError('Use at most 100 ingredients per recipe.')
        if not isinstance(recipe['name'], str) or len(recipe['name']) > 160:
            raise ValueError('Recipe name must be text of at most 160 characters.')
        for row in recipe['ingredients']:
            number(row['grams'], 'grams', 0, 100000)
        number(recipe['servings'], 'servings', 1, 10000)
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
            output.append({**{key: option[key] for key in fields}, 'recipe': adapted,
                           'footprint': m.footprint(adapted), 'sensitivity': m.sensitivity(recipe, source, option)})
        return jsonify(recipe=recipe, original=original, options=output)
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
