import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, apiUrl } from './api.js';
import { routes, routeFromPath, normalizeUpload, recipeCoverage, makeDraft, changeSource, changeIngredient, ingredientComparison } from './helpers.mjs';
import photos from './photos.json';
import './styles.css';

function Leaf({ className = '' }) {
  return <svg className={className} viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M8 26C7 11 21 6 33 8c1 16-7 25-20 22M10 31l17-17" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>;
}
function Link({ to, navigate, children, className = '', ...props }) {
  return <a href={to} className={className} onClick={event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); navigate(to);
  }} {...props}>{children}</a>;
}
function Header({ page, navigate }) {
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [page]);
  return <header className={`site-header ${page === '/' ? 'on-dark' : ''}`}>
    <Link to="/" navigate={navigate} className="wordmark" aria-label="EcoSwap home"><Leaf />Eco<span>Swap</span><span className="wordmark-dot">.</span></Link>
    <button className="menu-button" aria-expanded={open} aria-controls="main-navigation" onClick={() => setOpen(!open)}>{open ? 'Close' : 'Menu'}</button>
    <nav id="main-navigation" className={open ? 'navigation open' : 'navigation'} aria-label="Main navigation">
      {Object.entries(routes).map(([path, label]) => <Link key={path} to={path} navigate={navigate} aria-current={page === path ? 'page' : undefined}>{label}</Link>)}
    </nav>
  </header>;
}
const photoUrl = (photo, width) => import.meta.env.DEV ? `${photo.image}?auto=format&fit=crop&fm=webp&w=${width}&q=80` : `/photos/${photo.id}-${width}.webp`;
function Home({ navigate }) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [hidden, setHidden] = useState(document.hidden);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(media.matches);
    const visibility = () => setHidden(document.hidden);
    media.addEventListener('change', change); document.addEventListener('visibilitychange', visibility);
    return () => { media.removeEventListener('change', change); document.removeEventListener('visibilitychange', visibility); };
  }, []);
  useEffect(() => {
    if (paused || reduced || hidden) return;
    const timer = setInterval(() => setActive(index => (index + 1) % photos.length), 6000);
    return () => clearInterval(timer);
  }, [paused, reduced, hidden, active]);
  return <main id="main" className={`home ${paused || reduced ? 'paused' : ''}`}>
    <div className="hero-photographs" aria-hidden="true">{photos.map((photo, index) => <picture key={photo.id} className={`hero-photo ${index === active ? 'active' : ''}`}><source media="(max-width: 700px)" srcSet={photoUrl(photo, 900)} /><img src={photoUrl(photo, 1920)} alt="" style={{ objectPosition: photo.position }} fetchPriority={index === 0 ? 'high' : 'low'} /></picture>)}</div>
    <div className="hero-shade" />
    <div className="hero-content">
      <p className="eyebrow"><span className="short-rule" /> A little thought for every ingredient</p>
      <h1>Good food.<br />A <em>lighter</em><br className="desktop-break" /> footprint.</h1>
      <p className="hero-description">The dishes you love. A fresh way to make them.<br className="wide-break" /> Explore ingredient swaps with a smaller carbon footprint.</p>
      <div className="hero-actions"><Link to="/studio" navigate={navigate} className="button cream">Get Started</Link><Link to="/how-it-works" navigate={navigate} className="button glass">Know More</Link></div>
    </div>
    <div className="hero-bottom">
      <p className="hero-footnote"><Leaf /> Thoughtful swaps. Transparent estimates.</p>
      <div className="slideshow"><div className="photo-caption"><span>On the table</span><p>{photos[active].title}</p></div><div className="slide-controls" role="group" aria-label="Dish photographs">
        {photos.map((photo, index) => <button key={photo.id} className={`slide-dot ${index === active ? 'selected' : ''}`} aria-label={`Show ${photo.title}`} aria-pressed={index === active} onClick={() => { setActive(index); setPaused(true); }} />)}
        {!reduced && <button className="pause-button" aria-label={paused ? 'Play slideshow' : 'Pause slideshow'} onClick={() => setPaused(!paused)}>{paused ? 'Play' : 'Pause'}</button>}
      </div></div>
    </div>
  </main>;
}
function Footer({ navigate }) {
  return <footer className="footer"><Link to="/" navigate={navigate} className="wordmark"><Leaf />Eco<span>Swap</span>.</Link><p>A computational gastronomy research project.<br />Carbon estimates, not a guarantee of taste or nutrition.</p><Link to="/how-it-works" navigate={navigate}>Sources & photo credits</Link></footer>;
}
function PageIntro({ eyebrow, title, children }) {
  return <div className="page-intro"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{children}</p></div>;
}
function Loading({ label = 'Loading the recipe studio' }) {
  return <div className="loading-state" role="status"><span className="spinner" /><h2>{label}</h2><p>The free recipe service may need about a minute to wake up.</p></div>;
}
function ErrorBox({ message, retry }) {
  return <div className="error-box" role="alert"><strong>We couldn’t complete that.</strong><p>{message}</p>{retry && <button className="button green" onClick={retry}>Try again</button>}</div>;
}
function saveJson(value, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const format = (value, digits = 3) => Number(value).toLocaleString('en', { maximumFractionDigits: digits, minimumFractionDigits: digits });

function Studio({ catalogue, saved, onSave }) {
  const [draft, setDraft] = useState(() => saved?.draft || makeDraft(catalogue.recipes[0]));
  const [result, setResult] = useState(saved?.result || null);
  const [choice, setChoice] = useState(saved?.choice || 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const abort = useRef(null);
  const resultsHeading = useRef(null);
  useEffect(() => { onSave({ draft, result, choice }); }, [draft, result, choice, onSave]);
  useEffect(() => () => abort.current?.abort(), []);
  const source = draft.recipe.ingredients.find(row => row.id === draft.source);
  const sourceInfo = catalogue.ingredients[draft.source];
  const coverage = recipeCoverage(draft.recipe, catalogue.ingredients);
  const roles = sourceInfo ? [...new Set([source.role, ...sourceInfo.roles])] : [];
  const change = updated => { abort.current?.abort(); setBusy(false); setDraft(updated); setResult(null); setChoice(0); setError(''); };
  async function calculate(event) {
    event.preventDefault(); if (!coverage.matched.length) return; abort.current?.abort();
    const controller = new AbortController(); abort.current = controller;
    setBusy(true); setError('');
    try {
      const data = await api('options', { body: draft, signal: controller.signal });
      if (controller.signal.aborted) return;
      setResult(data); setChoice(0); requestAnimationFrame(() => resultsHeading.current?.focus({ preventScroll: true }));
    } catch (caught) { if (!controller.signal.aborted && caught.name !== 'AbortError') setError(caught.name === 'TimeoutError' ? 'The recipe service took too long to respond. Please try again.' : caught.message); }
    finally { if (abort.current === controller) setBusy(false); }
  }
  async function upload(event) {
    const file = event.target.files[0]; event.target.value = '';
    if (!file) return;
    try {
      if (file.size > 256 * 1024) throw new Error('Choose a JSON file smaller than 256 KB.');
      change(makeDraft({ ...normalizeUpload(JSON.parse(await file.text()), catalogue.ingredients, catalogue.aliases), id: 'custom-upload' }, catalogue.ingredients));
    } catch (caught) { setError(caught instanceof SyntaxError ? 'This file is not valid JSON.' : caught.message); }
  }
  const best = result?.options[choice];
  return <>
    <PageIntro eyebrow="The swap studio" title={<>A small swap.<br /><em>A considered choice.</em></>}>Choose a dish, explore an alternative, and see what changes.</PageIntro>
    <div className="studio-layout">
      <form onSubmit={calculate} className="recipe-form">
        <fieldset disabled={busy}><legend>What’s on the menu?</legend>
          <label htmlFor="recipe">Your recipe</label><select id="recipe" value={catalogue.recipes.some(r => r.id === draft.recipe.id) ? draft.recipe.id : 'custom'} onChange={e => change(makeDraft(catalogue.recipes.find(r => r.id === e.target.value)))}>
            {!catalogue.recipes.some(r => r.id === draft.recipe.id) && <option value="custom">{draft.recipe.name} (imported)</option>}
            {catalogue.recipes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <label className="upload-label" htmlFor="upload">Or upload your own recipe <span>JSON</span><input id="upload" type="file" accept=".json,application/json" onChange={upload} /></label>
          <div className="form-divider" />
          {draft.recipe.id === 'custom-upload' && <div className="match-report" role="status">
            <strong>{coverage.matched.length} of {draft.recipe.ingredients.length} ingredients matched</strong>
            <p>Matched: {coverage.matched.map(row => catalogue.ingredients[row.id].name).join(', ') || 'None'}</p>
            <p>Unsupported: {coverage.unsupported.map(row => `${row.id} (${row.grams} g)`).join(', ') || 'None'}</p>
            {coverage.unsupported.length > 0 && coverage.matched.length > 0 && <p>{coverage.label} Unsupported ingredients stay unchanged and are excluded from emissions estimates; their emissions are unknown, not zero.</p>}
          </div>}
          {!coverage.matched.length && <p role="status">No ingredients matched. Swap analysis is unavailable. Upload a recipe with at least one supported ingredient.</p>}
          {sourceInfo && <>
          <label htmlFor="ingredient">Ingredient to replace</label><select id="ingredient" value={draft.source} onChange={e => change(changeSource(draft, e.target.value))}>{coverage.matched.map(row => <option key={row.id} value={row.id}>{catalogue.ingredients[row.id].name}</option>)}</select>
          <div className="form-pair"><div><label htmlFor="grams">Amount (g)</label><input id="grams" type="number" min="0.001" max="100000" step="any" required value={source.grams} onChange={e => change(changeIngredient(draft, 'grams', e.target.value === '' ? '' : Number(e.target.value)))} /></div><div><label htmlFor="role">Cooking role</label><select id="role" value={source.role} onChange={e => change(changeIngredient(draft, 'role', e.target.value))}>{roles.map(role => <option key={role} value={role}>{role}</option>)}</select></div></div>
          <p className="field-hint">Food state: {sourceInfo.food_state}. Match your amount to this state.</p></>}
          <label htmlFor="priority" className="range-label">Carbon priority <output>{Math.round(draft.alpha * 100)}%</output></label><input id="priority" type="range" min="0" max="1" step=".05" value={draft.alpha} onChange={e => change({ ...draft, alpha: Number(e.target.value) })} /><div className="range-ends"><span>Less change</span><span>Lower carbon</span></div>
          <label htmlFor="cap">Maximum replacement</label><select id="cap" value={draft.max_fraction} onChange={e => change({ ...draft, max_fraction: Number(e.target.value) })}>{[0, .25, .5, .75, 1].map(value => <option key={value} value={value}>{value * 100}%</option>)}</select>
          <details className="exclusions"><summary>Exclude ingredients <span>{draft.exclude.length ? `(${draft.exclude.length})` : '(optional)'}</span></summary><div className="exclusion-list">{Object.entries(catalogue.ingredients).map(([id, ingredient]) => <label key={id}><input type="checkbox" checked={draft.exclude.includes(id)} onChange={e => change({ ...draft, exclude: e.target.checked ? [...draft.exclude, id] : draft.exclude.filter(x => x !== id) })} />{ingredient.name}</label>)}</div><p className="field-hint">Only suggestions are excluded. Existing ingredients remain; this is not an allergen safety check.</p></details>
          <button className="button green full" type="submit" disabled={!coverage.matched.length}>{busy ? 'Finding your swaps…' : 'Explore replacements'}</button>
        </fieldset>
        <details className="import-help"><summary>Custom recipe format</summary><p>Use canonical IDs or recognized aliases for matching. Unsupported ingredients are retained unchanged. Grains and legumes use cooked weights.</p><button type="button" className="text-button" onClick={() => saveJson(catalogue.recipes[0], 'ecoswap-recipe-template.json')}>Download example JSON</button><button type="button" className="text-button" onClick={() => saveJson(catalogue.ingredients, 'ecoswap-ingredient-ids.json')}>Download ingredient IDs</button></details>
      </form>
      <section className="studio-results" aria-label="Replacement results" aria-busy={busy}>
        {error && <ErrorBox message={error} />}
        {busy ? <Loading label="Considering your ingredients" /> : !best ? <div className="empty-result"><div className="empty-art"><img src={photoUrl(photos[0], 900)} alt="Pasta with pesto and sun-dried tomatoes" /><span className="round-seal"><Leaf /><span>Every ingredient<br />has a story.</span></span></div><p className="eyebrow">Start with something you love</p><h2>Your next favourite<br /><em>could start with a swap.</em></h2><p>Select a recipe and choose “Explore replacements” to compare real estimates from the EcoSwap engine.</p><p className="small-note">Research prototype · adaptations await taste testing</p></div> : <>
          <div className="result-heading"><p className="eyebrow">Your recipe, reconsidered</p><h2 tabIndex="-1" ref={resultsHeading}>{result.recipe.name}</h2><p>{result.recipe.servings} servings · {result.recipe.ingredients.length} ingredients</p></div>
          {result.message && <p className="coverage-notice no-alternative" role="status"><strong>{result.message}</strong></p>}
          {result.coverage?.partial && <p className="coverage-notice" role="status"><strong>{result.coverage.label}</strong></p>}
          <label htmlFor="alternative">Recommended option first — explore alternatives</label><select id="alternative" value={choice} onChange={e => setChoice(Number(e.target.value))}>{result.options.map((option, index) => <option key={`${option.target}-${option.fraction}`} value={index}>{option.target_name} · {option.fraction * 100}% replacement · {option.recipe_reduction_pct.toFixed(1)}% reduction{result.coverage?.partial ? ` — ${result.coverage.label}` : ''}</option>)}</select>
          <div className="impact-panel" aria-label={result.coverage?.label || 'Recipe carbon comparison'}><div className="impact-total"><span>Estimated {result.coverage?.partial ? 'matched-ingredient' : 'recipe'} reduction</span><strong>{best.recipe_reduction_pct.toFixed(1)}<small>%</small></strong><p>{format(best.saved_kg_co2e)} kg CO₂e saved</p></div><div className="impact-comparison"><div><span>Original</span><strong>{format(best.before)} <small>kg CO₂e</small></strong><div className="impact-track"><i style={{ width: '100%' }} /></div></div><div><span>Adapted</span><strong>{format(best.after)} <small>kg CO₂e</small></strong><div className="impact-track adapted"><i style={{ width: `${best.before ? best.after / best.before * 100 : 0}%` }} /></div></div><p>Per serving: {format(result.original.per_serving_kg_co2e)} → {format(best.footprint.per_serving_kg_co2e)} kg CO₂e</p>{result.coverage?.partial && <p className="impact-coverage">{result.coverage.label} Unsupported ingredients are excluded; their emissions are unknown, not zero.</p>}</div></div>
          <div className="swap-note"><Leaf /><p>{best.fraction ? best.note : 'Keeping the original is a valid choice. Your preferences or the available evidence may rule out a suitable swap.'}</p></div>
          <div className="section-heading"><h3>Your selected adaptation</h3><button className="text-button" onClick={() => saveJson(best.recipe, 'adapted-recipe.json')}>Download recipe</button></div>
          <div className="table-scroll"><table><caption className="sr-only">Original and adapted ingredient quantities in grams</caption><thead><tr><th>Ingredient</th><th>Original</th><th>Adapted</th></tr></thead><tbody>{ingredientComparison(result.recipe, best.recipe, catalogue.ingredients).map(row => <tr key={row.id} className={row.before !== row.after ? 'changed' : ''}><th scope="row">{row.name}<small>{row.state || 'Unsupported — preserved, excluded from carbon estimates'}</small></th><td>{format(row.before, 1)} g</td><td>{format(row.after, 1)} g</td></tr>)}</tbody></table></div>
          <details className="evidence"><summary>Why this suggestion?</summary><p>{best.train_count} observed training substitutions. Evidence score: {best.evidence_score.toFixed(3)}.</p><p>Compound overlap: {best.chemical_similarity === null ? 'Not available' : `${best.chemical_similarity.toFixed(3)} Jaccard`}. Coverage: {best.chemical_coverage}.</p><p>The evidence score is not a taste probability. Savings under an illustrative ±20% factor stress test: {format(best.sensitivity.low)}–{format(best.sensitivity.high)} kg CO₂e. This is not a confidence interval.</p></details>
          <details className="evidence"><summary>Original carbon contributions</summary>{result.coverage?.partial && <p>{result.coverage.label}</p>}<div className="contributions">{[...result.original.contributions].sort((a, b) => b.kg_co2e - a.kg_co2e).map(row => <div key={row.id}><span>{row.name}</span><div className="contribution-track"><i style={{ width: `${row.kg_co2e / result.original.total_kg_co2e * 100}%` }} /></div><span>{format(row.kg_co2e)} kg</span></div>)}</div></details>
          <details className="evidence"><summary>All options & Pareto frontier</summary>{result.coverage?.partial && <p>{result.coverage.label}</p>}<div className="table-scroll"><table><thead><tr><th>Alternative</th><th>Replace</th><th>Reduction</th><th>Objective</th><th>Pareto</th></tr></thead><tbody>{result.options.map(option => <tr key={`${option.target}-${option.fraction}`}><th>{option.target_name}</th><td>{option.fraction * 100}%</td><td>{option.recipe_reduction_pct.toFixed(1)}%</td><td>{option.objective.toFixed(3)}</td><td>{option.pareto ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div></details>
          <p className="small-note">Ingredient-level screening estimates using French-average factors. Cooking, texture, nutrition and taste need separate assessment.</p>
        </>}
      </section>
    </div>
  </>;
}

function About({ navigate }) {
  return <>
    <PageIntro eyebrow="Food, thoughtfully adapted" title={<>Keep the curiosity.<br /><em>Rethink an ingredient.</em></>}>EcoSwap explores a simple question: could changing part of a recipe reduce its estimated carbon footprint?</PageIntro>
    <div className="about-feature"><img src={photoUrl(photos[1], 900)} alt={photos[1].alt} /><div><p className="eyebrow">A little context</p><h2>It starts with<br />what’s on your plate.</h2><p>Ingredients have different production footprints. EcoSwap combines mapped emissions data with evidence of substitutions people have used, then compares possible replacement amounts.</p><p>You choose the dish and how much change you’re comfortable with. The tool shows its estimates and the evidence behind each suggestion.</p><Link to="/studio" navigate={navigate} className="button green">Try the Swap Studio</Link></div></div>
    <section className="method-section"><div><p className="eyebrow">From recipe to possibility</p><h2>How a swap<br /><em>takes shape.</em></h2></div><div className="method-list"><article><h3>Choose your starting point</h3><p>Pick an example recipe or import your own ingredient list. Match quantities to the mapped food state: raw meat, cooked grains, and so on.</p></article><article><h3>Explore supported alternatives</h3><p>We look for substitutions observed in the GISMo training data, then filter by food family, cooking role, exclusions, and lower estimated emissions.</p></article><article><h3>Decide how much to change</h3><p>Compare 25%, 50%, 75%, or full replacement where the rules permit. A “keep original” option lets the system suggest no change.</p></article><article><h3>See the difference</h3><p>Compare carbon estimates, inspect the evidence, and download the adapted ingredient list. Cooking instructions and sensory equivalence still need kitchen testing.</p></article></div></section>
    <section className="sources-section"><p className="eyebrow">Open about our ingredients</p><h2>The data behind the dish.</h2><div className="source-grid"><article><h3>AGRIBALYSE</h3><p>French-average carbon factors mapped to specific food products and states.</p><a href="https://data.ademe.fr/datasets/agribalyse-31-synthese" target="_blank" rel="noreferrer">Explore the source</a></article><article><h3>GISMo</h3><p>Observed ingredient substitutions, used for training support and recipe context.</p><a href="https://github.com/facebookresearch/gismo" target="_blank" rel="noreferrer">Explore the source</a></article><article><h3>FlavorGraph</h3><p>Available flavour-compound profiles, with missing or sparse coverage made explicit.</p><a href="https://github.com/lamypark/FlavorGraph" target="_blank" rel="noreferrer">Explore the source</a></article></div></section>
    <aside className="honesty-note"><Leaf /><div><h3>A research tool, with room to learn.</h3><p>Lower carbon does not automatically mean identical taste, better nutrition, or suitability for an allergy. The mappings and cooking rules need expert review; the physical taste pilot has not yet been conducted. This project is for academic, noncommercial use.</p></div></aside>
    <details className="photo-credits"><summary>Photography credits</summary><p>Real photographs from Unsplash, used under the <a href="https://unsplash.com/license">Unsplash licence</a>. Images illustrate dishes; they are not photographs of tested EcoSwap adaptations.</p><ul>{photos.map(photo => <li key={photo.id}><a href={photo.source} target="_blank" rel="noreferrer">{photo.title}</a> — {photo.photographer}</li>)}</ul></details>
  </>;
}
function DataTable({ rows }) {
  if (!rows?.length) return <p>No results available.</p>;
  const keys = Object.keys(rows[0]);
  return <div className="table-scroll"><table><thead><tr>{keys.map(key => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{keys.map(key => <td key={key}>{typeof row[key] === 'number' ? Number.isInteger(row[key]) ? row[key].toLocaleString() : row[key].toFixed(4) : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table></div>;
}
function Research({ data }) {
  const { summary, weights, manifest, mapping } = data;
  return <>
    <PageIntro eyebrow="Evidence, in the open" title={<>Behind every swap,<br /><em>a question worth testing.</em></>}>Explore what the model measures, where it falls short, and what still needs to be tested in the kitchen.</PageIntro>
    <section className="research-section"><h2>Recovering observed substitutions</h2><p>{summary.audit.evaluated_test_records.toLocaleString()} mapped test examples from {summary.audit.original_gismo_test_records.toLocaleString()} original GISMo test records. Targets outside the permitted candidate set count as misses.</p><DataTable rows={summary.benchmark} /><p className="small-note">Feasible-target metrics only include cases whose answer is in the candidate set. Recovery of an observed substitute is not a sensory evaluation. The simple frequency baseline performs better on top-1 recovery.</p></section>
    <section className="research-section"><h2>Carbon estimates across the scenarios</h2><p>These authored examples illustrate the model’s behaviour. They are not a representative sample of recipes or measured real-world savings.</p><DataTable rows={summary.scenarios} /></section>
    <section className="research-section"><h2>How the model weighs evidence</h2><div className="weight-row">{Object.entries(weights).map(([key, value]) => <div key={key}><strong>{Math.round(value * 100)}%</strong><span>{key === 'support' ? 'Training support' : key === 'context' ? 'Recipe context' : 'Compound overlap'}</span></div>)}</div><p>These base weights are manually chosen so flavour-compound evidence influences recommendations when profiles are available. Compound weight is reduced for sparse profiles; missing terms are omitted and available weights are normalized. The optimizer trades estimated whole-recipe carbon reduction against a declared change penalty; it is not a prediction of flavour preservation.</p><details className="evidence"><summary>Ingredient mappings</summary><DataTable rows={mapping} /></details><details className="evidence"><summary>Source manifest & coverage</summary><pre>{JSON.stringify(manifest, null, 2)}</pre></details></section>
    <section className="pilot-section"><div><p className="eyebrow">The next step is in the kitchen</p><h2>A taste pilot.<br /><em>Not a taste promise.</em></h2><p>The protocol is ready; the physical pilot is pending. Blind flavour-similarity and liking ratings should be collected separately.</p></div><div className="download-list"><a href={apiUrl('download/taste_pilot_protocol.md')}>Taste pilot protocol <span>MD</span></a><a href={apiUrl('download/taste_ratings_template.csv')}>Rating sheet <span>CSV</span></a><a href={apiUrl('download/REPORT.md')}>Full research report <span>MD</span></a></div></section>
    <details className="photo-credits"><summary>Download the computational results</summary><div className="download-list">{['benchmark_metrics.csv', 'scenario_comparison.csv', 'pareto_options.csv', 'weight_sensitivity.csv'].map(name => <a key={name} href={apiUrl(`download/${name}`)}>{name.replaceAll('_', ' ')} <span>CSV</span></a>)}</div></details>
  </>;
}

function App() {
  const [page, setPage] = useState(() => routeFromPath(location.pathname));
  const [catalogue, setCatalogue] = useState(null);
  const [research, setResearch] = useState(null);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const pageRef = useRef(null);
  function navigate(path) { if (path !== page) { history.pushState({}, '', path); setPage(path); window.scrollTo(0, 0); } }
  useEffect(() => { const back = () => { setPage(routeFromPath(location.pathname)); window.scrollTo(0, 0); }; window.addEventListener('popstate', back); return () => window.removeEventListener('popstate', back); }, []);
  useEffect(() => { document.title = `${routes[page] || 'Page not found'} · EcoSwap`; setError(''); pageRef.current?.focus({ preventScroll: true }); }, [page]);
  useEffect(() => {
    if (!((page === '/studio' && !catalogue) || (page === '/research' && !research))) return;
    const controller = new AbortController(); setError('');
    api(page === '/studio' ? 'catalogue' : 'research', { signal: controller.signal }).then(data => { if (page === '/studio') setCatalogue(data); else setResearch(data); }).catch(caught => { if (caught.name !== 'AbortError') setError(caught.name === 'TimeoutError' ? 'The recipe service took too long to respond. Please retry.' : caught.message); });
    return () => controller.abort();
  }, [page, retry, catalogue, research]);
  return <><a className="skip-link" href="#main">Skip to content</a><Header page={page} navigate={navigate} />{page === '/' ? <Home navigate={navigate} /> : <><main id="main" className="page-shell" ref={pageRef} tabIndex="-1">
    {page === '/studio' ? catalogue ? <Studio catalogue={catalogue} saved={saved} onSave={setSaved} /> : error ? <ErrorBox message={error} retry={() => setRetry(retry + 1)} /> : <Loading /> : page === '/how-it-works' ? <About navigate={navigate} /> : page === '/research' ? research ? <Research data={research} /> : error ? <ErrorBox message={error} retry={() => setRetry(retry + 1)} /> : <Loading label="Opening the research" /> : <PageIntro eyebrow="Page not found" title="Let’s get back to the table."><Link to="/" navigate={navigate}>Go home</Link></PageIntro>}
    </main><Footer navigate={navigate} /></>}</>;
}

createRoot(document.getElementById('root')).render(<App />);

