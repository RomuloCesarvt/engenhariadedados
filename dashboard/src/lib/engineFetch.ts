/** fetch para a engine Python, com a chave compartilhada (ENGINE_API_KEY) quando configurada. */
export function engineFetch(url: string, init: RequestInit = {}) {
  const chave = process.env.ENGINE_API_KEY;
  if (!chave) return fetch(url, init);
  const headers = new Headers(init.headers);
  headers.set('x-engine-key', chave);
  return fetch(url, { ...init, headers });
}
