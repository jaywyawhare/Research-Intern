// Public origin for browser fetches to /v1/* (same host as the Next app). Optional: NEXT_PUBLIC_RESEARCH_API_BASE.
// RESEARCH_API_URL (server-only) is where Next proxies to FastAPI — never 127.0.0.1:8000 in NEXT_PUBLIC_*.

function normalizePath(path) {
  let s = typeof path === 'string' ? path.trim() : String(path);
  s = s.replace(/^https?:\/\/127\.0\.0\.1:8000/i, '');
  s = s.replace(/^\/\/127\.0\.0\.1:8000/i, '');
  s = s.replace(/^https?:\/\/localhost:8000/i, '');
  s = s.replace(/^\/\/localhost:8000/i, '');
  if (!s.startsWith('/')) s = `/${s}`;
  return s;
}

/** Inlined at build time. Must be the site origin (https://your-app.onrender.com), not the internal API. */
function configuredPublicOrigin() {
  const raw = (process.env.NEXT_PUBLIC_RESEARCH_API_BASE || '').trim();
  if (!raw) return '';
  const base = raw.replace(/\/$/, '');
  // Never use direct FastAPI URL in the browser (common mistake).
  if (/^https?:\/\/(127\.0\.0\.1|localhost):8000\/?$/i.test(base)) {
    return '';
  }
  return base;
}

function apiUrl(path) {
  const p = normalizePath(path);
  const fromEnv = configuredPublicOrigin();
  if (fromEnv) {
    return `${fromEnv}${p}`;
  }
  if (typeof window === 'undefined') {
    return p;
  }
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
