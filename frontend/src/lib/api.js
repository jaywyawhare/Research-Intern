// Same-origin only; Next rewrites /v1 to FastAPI. Do not set NEXT_PUBLIC_* to 127.0.0.1:8000.
function normalizePath(path) {
  let s = typeof path === 'string' ? path.trim() : String(path);
  s = s.replace(/^https?:\/\/127\.0\.0\.1:8000/i, '');
  s = s.replace(/^\/\/127\.0\.0\.1:8000/i, '');
  s = s.replace(/^https?:\/\/localhost:8000/i, '');
  s = s.replace(/^\/\/localhost:8000/i, '');
  if (!s.startsWith('/')) s = `/${s}`;
  return s;
}

function apiUrl(path) {
  const p = normalizePath(path);
  if (typeof window === 'undefined') {
    return p;
  }
  // Avoid `new URL('//127.0.0.1:8000/...', origin)` — that becomes https://127.0.0.1:8000/... in the browser.
  return `${window.location.origin}${p}`;
}

function headers(init, { withJsonContentType = true } = {}) {
  const h = new Headers(init);
  if (withJsonContentType) {
    h.set('Content-Type', 'application/json');
  }
  const key = process.env.NEXT_PUBLIC_RESEARCH_API_KEY;
  if (key) {
    h.set('X-API-Key', key);
  }
  return h;
}

function apiErrorMessage(status, body) {
  const t = (body || '').trim();
  const proxyOrDown =
    status >= 502 ||
    (status === 500 &&
      (!t ||
        t.startsWith('<!DOCTYPE') ||
        t.startsWith('<html') ||
        /failed to proxy/i.test(t) ||
        /ECONNREFUSED/i.test(t)));
  if (proxyOrDown) {
    return 'Cannot reach the API. Start the FastAPI server (default http://127.0.0.1:8000) or set RESEARCH_API_URL in frontend/.env.local.';
  }
  return t || `HTTP ${status}`;
}

function formatHttpError(status, bodyText) {
  const t = (bodyText || '').trim();
  if (t.startsWith('{') && t.includes('"detail"')) {
    try {
      const j = JSON.parse(t);
      const d = j?.detail;
      if (typeof d === 'string') return d;
      if (Array.isArray(d) && d.length && typeof d[0]?.msg === 'string') {
        return d.map((x) => x.msg).join('; ');
      }
    } catch {
    }
  }
  return apiErrorMessage(status, t);
}

async function throwIfNotOk(r) {
  if (r.ok) return;
  const t = await r.text();
  throw new Error(formatHttpError(r.status, t));
}

export async function apiGet(path) {
  const r = await fetch(apiUrl(path), {
    headers: headers(undefined, { withJsonContentType: false }),
    cache: 'no-store',
  });
  await throwIfNotOk(r);
  return r.json();
}

export async function apiPost(path, body) {
  const r = await fetch(apiUrl(path), {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  });
  await throwIfNotOk(r);
  return r.json();
}

export async function apiDelete(path) {
  const r = await fetch(apiUrl(path), {
    method: 'DELETE',
    headers: headers(undefined, { withJsonContentType: false }),
  });
  await throwIfNotOk(r);
}
