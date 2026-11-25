const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export const apiUrl = path => `${base}/api/${path}`;
export async function api(path, { signal, body } = {}) {
  const response = await fetch(apiUrl(path), {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(100000)]) : AbortSignal.timeout(100000),
  });
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('The recipe service is unavailable. Please try again in a minute.');
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'We could not calculate this recipe.');
  return data;
}
