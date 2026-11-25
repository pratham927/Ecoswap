import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeUpload, recipeCoverage, makeDraft, changeIngredient, ingredientComparison, validateUpload, routeFromPath } from './helpers.mjs';
const recipe = { name: 'Test dish', servings: 2, target: 'butter', ingredients: [{ id: 'butter', grams: 100, role: 'saute' }] };
const catalogue = { butter: { name: 'Butter', food_state: 'Butter' }, olive_oil: { name: 'Olive oil', food_state: 'Oil' } };
test('Editing a draft never mutates the shared recipe catalogue', () => {
  const draft = makeDraft(recipe); const changed = changeIngredient(draft, 'grams', 50);
  assert.equal(changed.recipe.ingredients[0].grams, 50);
  assert.equal(draft.recipe.ingredients[0].grams, 100);
  assert.equal(recipe.ingredients[0].grams, 100);
});
test('Invalid uploaded target falls back to a recipe ingredient', () => {
  assert.equal(makeDraft({ ...recipe, target: 'not-present' }).source, 'butter');
});
test('Comparison includes both removed and newly added ingredients', () => {
  const adapted = { ingredients: [{ id: 'olive_oil', grams: 82 }] };
  assert.deepEqual(ingredientComparison(recipe, adapted, catalogue).map(r => [r.id, r.before, r.after]), [['butter', 100, 0], ['olive_oil', 0, 82]]);
});
test('Upload validation rejects malformed, duplicate and nonfinite amounts', () => {
  assert.equal(validateUpload(recipe, catalogue), recipe);
  for (const row of [{ id: '', grams: 100, role: 'saute' }, { id: 'butter', grams: null, role: 'saute' }, { id: 'butter', grams: 0, role: 'saute' }, { id: 'butter', grams: Infinity, role: 'saute' }]) {
    assert.throws(() => validateUpload({ ...recipe, ingredients: [row] }, catalogue));
  }
  assert.throws(() => validateUpload({ ...recipe, ingredients: [recipe.ingredients[0], recipe.ingredients[0]] }, catalogue), /duplicate/);
});
test('Direct URLs with a trailing slash resolve to the correct page', () => {
  assert.equal(routeFromPath('/studio/'), '/studio'); assert.equal(routeFromPath('/'), '/');
});

test('Mixed upload accepts unsupported rows, selects a matched source and retains comparison quantities', () => {
  const unknown = { id: 'saffron', grams: 2.5, role: 'seasoning', note: 'keep' };
  const mixed = { ...recipe, target: 'saffron', ingredients: [unknown, ...recipe.ingredients] };
  const validated = normalizeUpload(mixed, catalogue);
  const draft = makeDraft(validated, catalogue);
  assert.equal(draft.source, 'butter');
  assert.deepEqual(draft.recipe.ingredients[0], unknown);
  assert.equal(recipeCoverage(validated, catalogue).label, 'Matched ingredients only (1 of 2 original ingredients covered).');
  const adapted = { ...validated, ingredients: [unknown, {id:'olive_oil', grams:82, role:'saute'}] };
  const comparison = ingredientComparison(validated, adapted, catalogue);
  assert.equal(comparison.find(r => r.id === 'saffron').after, 2.5);
});
test('Zero-match upload has an empty source and no matched choices', () => {
  const zero = { ...recipe, ingredients: [{id:'unknown', grams:1, role:'seasoning'}] };
  assert.equal(makeDraft(validateUpload(zero, catalogue), catalogue).source, '');
  assert.equal(recipeCoverage(zero, catalogue).matched.length, 0);
});
test('Alias matching agrees with the API and rejects duplicate canonical ingredients', () => {
  const aliases = { unsalted_butter: 'butter' };
  const upload = { ...recipe, ingredients: [{ id:'Unsalted Butter', grams:25, role:'saute' }] };
  assert.equal(makeDraft(normalizeUpload(upload, catalogue, aliases), catalogue).source, 'butter');
  assert.throws(() => normalizeUpload({...upload, ingredients:[...upload.ingredients,...recipe.ingredients]}, catalogue, aliases), /duplicate/);
});
test('An aliased target preselects its matched ingredient', () => {
  const aliases = { unsalted_butter: 'butter' };
  const upload = { ...recipe, target: 'Unsalted Butter', ingredients: [{ id: 'saffron', grams: 1, role: 'x' }, { id: 'olive_oil', grams: 5, role: 'saute' }, { id: 'unsalted butter', grams: 25, role: 'saute' }] };
  assert.equal(makeDraft(normalizeUpload(upload, catalogue, aliases), catalogue).source, 'butter');
});
test('Unknown ingredients cannot bypass quantity validation', () => {
  for (const grams of [null, true, 0, -1, Infinity, NaN, '50']) {
    assert.throws(() => normalizeUpload({...recipe, ingredients:[{id:'unknown', grams, role:'x'}]}, catalogue));
  }
});
