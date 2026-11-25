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
