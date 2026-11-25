import copy
import pytest
from api.app import app, model


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def body():
    return {'recipe': copy.deepcopy(model().recipes[0]), 'source': 'beef', 'alpha': .5, 'max_fraction': 1, 'exclude': []}


def test_catalogue_does_not_expose_training_contexts(client):
    data = client.get('/api/catalogue').get_json()
    assert len(data['ingredients']) == len(model().ingredients)
    assert 'compounds' not in next(iter(data['ingredients'].values()))
    assert client.get('/api/health').status_code == 200


def test_all_scenarios_match_engine_and_downloaded_recipe(client):
    for recipe in model().recipes:
        response = client.post('/api/options', json={**body(), 'recipe': recipe, 'source': recipe['target']})
        assert response.status_code == 200
        data = response.get_json()
        expected = model().options(recipe, recipe['target'])
        assert len(data['options']) == len(expected)
        for actual, direct in zip(data['options'], expected):
            assert actual['target'] == direct['target']
            assert actual['fraction'] == direct['fraction']
            assert actual['after'] == pytest.approx(direct['after'])
            assert model().footprint(actual['recipe'])['total_kg_co2e'] == pytest.approx(actual['after'])
            # Built-in presets are fully matched: no partial labels or coverage metadata.
            assert 'carbon_coverage' not in actual['recipe'] and 'coverage_label' not in actual
            assert actual['footprint']['coverage'] == 1.0
        assert data['coverage']['partial'] is False
        assert data['coverage']['matched_count'] == data['coverage']['original_count'] == len(recipe['ingredients'])
        assert 'coverage' not in data['original'] or data['original']['coverage'] == 1.0


@pytest.mark.parametrize('patch', [{'source': 'mystery'}, {'alpha': 1.1}, {'alpha': True}, {'max_fraction': -.1}, {'exclude': 'milk'}, {'recipe': None}])
def test_invalid_requests_are_json_errors(client, patch):
    response = client.post('/api/options', json={**body(), **patch})
    assert response.status_code == 422
    assert response.get_json()['error']


def test_malformed_and_oversized_requests(client):
    response = client.post('/api/options', data='{bad', content_type='application/json')
    assert response.status_code == 400 and response.is_json
    response = client.post('/api/options', data='x' * (257 * 1024), content_type='application/json')
    assert response.status_code == 413 and response.is_json


def test_custom_recipe_and_exclusions(client):
    recipe = {'name': 'Spinach', 'servings': 2, 'ingredients': [{'id': 'butter', 'grams': 50, 'role': 'saute'}, {'id': 'spinach', 'grams': 400, 'role': 'background'}]}
    result = client.post('/api/options', json={**body(), 'recipe': recipe, 'source': 'butter', 'exclude': list(model().ingredients)}).get_json()
    assert len(result['options']) == 1
    assert result['options'][0]['fraction'] == 0
    assert result['options'][0]['recipe'] == result['recipe']


def test_requests_do_not_mutate_shared_recipes(client):
    original = copy.deepcopy(model().recipes)
    payload = body(); payload['recipe']['ingredients'][0]['grams'] = 123
    assert client.post('/api/options', json=payload).status_code == 200
    assert model().recipes == original


def test_research_downloads_and_path_allowlist(client):
    research = client.get('/api/research')
    assert research.status_code == 200 and research.get_json()['mapping']
    for file in ['benchmark_metrics.csv', 'scenario_comparison.csv', 'pareto_options.csv', 'weight_sensitivity.csv', 'taste_pilot_protocol.md', 'taste_ratings_template.csv', 'REPORT.md']:
        assert client.get('/api/download/' + file).status_code == 200
    assert client.get('/api/download/app.py').status_code == 404


def test_cors_allows_only_configured_frontend(client):
    allowed = client.options('/api/options', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    assert allowed.headers['Access-Control-Allow-Origin'] == 'http://localhost:5173'
    assert 'Access-Control-Allow-Origin' not in client.get('/api/catalogue', headers={'Origin': 'https://unrelated.example'}).headers


def mixed_body():
    matched = [
        {'id': 'butter', 'grams': 50, 'role': 'saute'},
        {'id': 'spinach', 'grams': 100, 'role': 'background'},
        {'id': 'garlic', 'grams': 10, 'role': 'background'},
        {'id': 'salt', 'grams': 2, 'role': 'background'},
        {'id': 'onion', 'grams': 50, 'role': 'background'},
    ]
    unknown = [{'id': f'unknown spice {i}', 'grams': i + .5, 'role': 'seasoning',
                'note': {'original': True}} for i in range(5)]
    return {**body(), 'source': 'butter',
            'recipe': {'name': 'Mixed', 'servings': 2, 'ingredients': unknown[:2] + matched + unknown[2:]}}


def test_partial_upload_swap_and_download(client):
    payload = mixed_body()
    before = copy.deepcopy(payload)
    response = client.post('/api/options', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    label = 'Matched ingredients only (5 of 10 original ingredients covered).'
    assert data['coverage']['label'] == label
    assert data['coverage']['matched_count'] == 5
    assert len(data['coverage']['unsupported']) == 5
    # Compare every candidate, including full replacement and keep-original.
    assert any(o['fraction'] > 0 for o in data['options'])
    expected_original = model().footprint({**payload['recipe'], 'ingredients':
        [r for r in payload['recipe']['ingredients'] if r['id'] in model().ingredients]})
    for option in data['options']:
        assert option['before'] == pytest.approx(expected_original['total_kg_co2e'])
        assert option['coverage_label'] == label
        assert option['footprint']['coverage_label'] == label
        assert option['recipe']['carbon_coverage']['label'] == label
        exported = option['recipe']['ingredients']
        unknown = [r for r in exported if r['id'] not in model().ingredients]
        assert unknown == data['coverage']['unsupported']
        for row in payload['recipe']['ingredients']:
            if row['id'] != 'butter' and row['id'] != option['target']:
                assert row in exported
        supported = [r for r in exported if r['id'] in model().ingredients]
        assert option['after'] == pytest.approx(model().footprint(
            {**payload['recipe'], 'ingredients': supported})['total_kg_co2e'])
        assert option['recipe_reduction_pct'] == pytest.approx(
            100 * (option['before'] - option['after']) / option['before'])
    assert payload == before


def test_fully_matched_upload_is_unchanged_by_partial_support(client):
    payload = mixed_body()
    payload['recipe']['ingredients'] = [r for r in payload['recipe']['ingredients'] if r['id'] in model().ingredients]
    data = client.post('/api/options', json=payload).get_json()
    assert data['coverage']['partial'] is False and data['coverage']['matched_count'] == 5
    assert data['message'] is None
    direct = model().options(payload['recipe'], 'butter')
    assert [(o['target'], o['fraction']) for o in data['options']] == [(o['target'], o['fraction']) for o in direct]
    for option in data['options']:
        assert 'carbon_coverage' not in option['recipe']
        assert model().footprint(option['recipe'])['total_kg_co2e'] == pytest.approx(option['after'])


def test_zero_matches_has_no_estimate_or_analysis(client):
    payload = mixed_body()
    payload['recipe']['ingredients'] = [{'id': 'unknown', 'grams': 50, 'role': 'background'}]
    data = client.post('/api/options', json=payload).get_json()
    assert data['original'] is None and data['options'] == []
    assert data['coverage']['matched_count'] == 0
    assert data['recipe']['ingredients'] == payload['recipe']['ingredients']
    assert 'No ingredients matched' in data['message']


@pytest.mark.parametrize('grams', [None, True, -1, 0, float('inf'), float('nan'), 100001])
def test_unsupported_quantities_still_validated(client, grams):
    payload = mixed_body()
    payload['recipe']['ingredients'][0]['grams'] = grams
    assert client.post('/api/options', json=payload).status_code == 422


@pytest.mark.parametrize('row', [None, [], {}, {'id': '', 'grams': 3, 'role': 'x'},
                                {'id': {}, 'grams': 3, 'role': 'x'},
                                {'id': 'mystery', 'grams': 3, 'role': None}])
def test_unsupported_malformed_rows_rejected(client, row):
    payload = mixed_body()
    payload['recipe']['ingredients'][0] = row
    assert client.post('/api/options', json=payload).status_code == 422


def test_alias_matches_and_duplicate_aliases_rejected(client):
    payload = mixed_body()
    payload['recipe']['ingredients'][2]['id'] = 'unsalted butter'
    data = client.post('/api/options', json=payload).get_json()
    assert data['coverage']['matched_count'] == 5
    payload['recipe']['ingredients'].append({'id': 'butter', 'grams': 1, 'role': 'saute'})
    assert client.post('/api/options', json=payload).status_code == 422


def test_supported_without_alternatives_and_unsupported_source(client):
    payload = mixed_body()
    payload['exclude'] = list(model().ingredients)
    data = client.post('/api/options', json=payload).get_json()
    assert 'No suitable alternative' in data['message']
    assert len(data['options']) == 1 and data['options'][0]['fraction'] == 0
    payload['source'] = 'unknown spice 0'
    assert client.post('/api/options', json=payload).status_code == 422
