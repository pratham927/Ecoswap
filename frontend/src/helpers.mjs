export const routes = { '/': 'Home', '/studio': 'Swap Studio', '/how-it-works': 'How It Works', '/research': 'Research' };
export function routeFromPath(path) { return path.length > 1 ? path.replace(/\/+$/, '') : '/'; }
export function makeDraft(recipe, catalogue = null) {
  const copy = structuredClone(recipe);
  const matched = copy.ingredients.filter(row => !catalogue || Object.hasOwn(catalogue, row.id));
  return { recipe: copy, source: matched.some(row => row.id === copy.target) ? copy.target : matched[0]?.id || '', alpha: .5, max_fraction: 1, exclude: [] };
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
    if (!row || typeof row.id !== 'string' || !row.id.trim()) throw new Error('Each ingredient needs a non-empty text ID.');
    if (seen.has(row.id.trim().toLowerCase().replaceAll(' ', '_'))) throw new Error('Combine duplicate ingredient rows before importing.');
    seen.add(row.id.trim().toLowerCase().replaceAll(' ', '_'));
    if (!Number.isFinite(row.grams) || row.grams <= 0 || row.grams > 100000) throw new Error('Ingredient amounts must be positive numbers, up to 100,000 g.');
    if (typeof row.role !== 'string' || !row.role.trim()) throw new Error('Each ingredient needs a role.');
  }
  return recipe;
}

export function normalizeUpload(recipe, catalogue, aliases = {}) {
  // Normalize recognized aliases only; unsupported rows remain unchanged.
  const copy = structuredClone(recipe);
  const canonical = value => {
    if (typeof value !== 'string') return null;
    const key = value.trim().toLowerCase().replaceAll(' ', '_');
    const id = Object.hasOwn(aliases, key) ? aliases[key] : key;
    return Object.hasOwn(catalogue, id) ? id : null;
  };
  if (Array.isArray(copy?.ingredients)) copy.ingredients = copy.ingredients.map(row => {
    const id = canonical(row?.id);
    return id ? { ...row, id } : row;
  });
  // An aliased `target` should still preselect the matching ingredient.
  if (copy && typeof copy === 'object' && canonical(copy.target)) copy.target = canonical(copy.target);
  return validateUpload(copy, catalogue);
}
export function recipeCoverage(recipe, catalogue) {
  const matched = recipe.ingredients.filter(row => Object.hasOwn(catalogue, row.id));
  const unsupported = recipe.ingredients.filter(row => !Object.hasOwn(catalogue, row.id));
  return { matched, unsupported, label: unsupported.length ? `Matched ingredients only (${matched.length} of ${recipe.ingredients.length} original ingredients covered).` : '' };
}
