export const routes = { '/': 'Home', '/studio': 'Swap Studio', '/how-it-works': 'How It Works', '/research': 'Research' };
export function routeFromPath(path) { return path.length > 1 ? path.replace(/\/+$/, '') : '/'; }
export function makeDraft(recipe) {
  const copy = structuredClone(recipe);
  return { recipe: copy, source: copy.ingredients.some(row => row.id === copy.target) ? copy.target : copy.ingredients[0].id, alpha: .5, max_fraction: 1, exclude: [] };
}
export function changeSource(draft, source) { return { ...draft, source }; }
export function changeIngredient(draft, key, value) {
  return { ...draft, recipe: { ...draft.recipe, ingredients: draft.recipe.ingredients.map(row => row.id === draft.source ? { ...row, [key]: value } : row) } };
}
export function ingredientComparison(original, adapted, catalogue) {
  const before = Object.fromEntries(original.ingredients.map(row => [row.id, row.grams]));
  const after = Object.fromEntries(adapted.ingredients.map(row => [row.id, row.grams]));
  return [...new Set([...Object.keys(before), ...Object.keys(after)])].map(id => ({
    id, name: catalogue[id]?.name || id, before: before[id] || 0, after: after[id] || 0,
    state: catalogue[id]?.food_state || '',
  }));
}
export function validateUpload(recipe, catalogue) {
  if (!recipe || typeof recipe !== 'object' || !Array.isArray(recipe.ingredients) || !recipe.ingredients.length || recipe.ingredients.length > 100) throw new Error('Use a recipe JSON with between 1 and 100 ingredient rows.');
  if (typeof recipe.name !== 'string' || !recipe.name.trim() || recipe.name.length > 160) throw new Error('Include a recipe name of at most 160 characters.');
  if (!Number.isFinite(recipe.servings) || recipe.servings < 1 || recipe.servings > 10000) throw new Error('Servings must be a number between 1 and 10,000.');
  const seen = new Set();
  for (const row of recipe.ingredients) {
    if (!row || !catalogue[row.id]) throw new Error(`Unknown ingredient ID: ${row?.id || '(missing)'}. Use an ID from the ingredient list.`);
    if (seen.has(row.id)) throw new Error('Combine duplicate ingredient rows before importing.');
    seen.add(row.id);
    if (!Number.isFinite(row.grams) || row.grams <= 0 || row.grams > 100000) throw new Error('Ingredient amounts must be positive numbers, up to 100,000 g.');
    if (typeof row.role !== 'string' || !row.role) throw new Error('Each ingredient needs a role.');
  }
  return recipe;
}
