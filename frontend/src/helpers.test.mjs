import test from 'node:test';
import assert from 'node:assert/strict';
import { makeDraft, changeIngredient, ingredientComparison, validateUpload, routeFromPath } from './helpers.mjs';
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
test('Upload validation rejects unknown, duplicate and nonfinite amounts', () => {
  assert.equal(validateUpload(recipe, catalogue), recipe);
  for (const row of [{ id: 'unknown', grams: 100, role: 'saute' }, { id: 'butter', grams: null, role: 'saute' }, { id: 'butter', grams: 0, role: 'saute' }, { id: 'butter', grams: Infinity, role: 'saute' }]) {
    assert.throws(() => validateUpload({ ...recipe, ingredients: [row] }, catalogue));
  }
  assert.throws(() => validateUpload({ ...recipe, ingredients: [recipe.ingredients[0], recipe.ingredients[0]] }, catalogue), /duplicate/);
});
test('Direct URLs with a trailing slash resolve to the correct page', () => {
  assert.equal(routeFromPath('/studio/'), '/studio'); assert.equal(routeFromPath('/'), '/');
});
