'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { apiDelete, apiGet, apiPost } from '@/lib/api';
import { KnowledgeGraphPanel } from '@/components/KnowledgeGraphPanel';
import { MarkdownContent } from '@/components/MarkdownContent';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/Toast';
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Trash2,
} from 'lucide-react';

function sessionIdFromParams(params) {
  const raw = params?.sessionId;
  const one = Array.isArray(raw) ? raw[0] : raw;
  if (typeof one !== 'string' || !one.trim()) return '';
  try {
    return decodeURIComponent(one.trim());
  } catch {
    return one.trim();
  }
}

function friendlyLoadError(message) {
  const s = (message || '').toLowerCase();
  if (s.includes('session not found') || s.includes('not found')) {
    return "We couldn't load this session. It may no longer exist. Open one from the workspace.";
  }
  return message || 'Something went wrong loading this session.';
}

// Split session content into pages
function buildPages(detail, lastTurn) {
  const pages = [];

  // Page 1: Session info + status
  pages.push({
    id: 'info',
    label: 'Overview',
    type: 'info',
    detail,
  });

  // Page 2: Synthesis — show whenever we have a stored outcome (even if LLM was skipped or failed)
  if (detail.outcome) {
    pages.push({
      id: 'synthesis',
      label: 'Synthesis',
      type: 'synthesis',
      outcome: detail.outcome,
    });
  }

  if (detail.status === 'ready' && detail.outcome) {
    pages.push({
      id: 'knowledge-graph',
      label: 'Knowledge graph',
      type: 'knowledge_graph',
      outcome: detail.outcome,
    });
  }

  // Transcript pages — group into sets of 4 turns per page
  if (detail.transcript?.length > 0) {
    const chunkSize = 4;
    for (let i = 0; i < detail.transcript.length; i += chunkSize) {
      const chunk = detail.transcript.slice(i, i + chunkSize);
      pages.push({
        id: `transcript-${i}`,
        label: `Notes ${Math.floor(i / chunkSize) + 1}`,
        type: 'transcript',
        turns: chunk,
        startIdx: i,
      });
    }
  }

  // Follow-up page (always last when ready)
  if (detail.status === 'ready') {
    pages.push({
      id: 'followup',
      label: 'Follow-up',
      type: 'followup',
      lastTurn,
    });
  }

  return pages;
}

// Page flip animation variants
const pageVariants = {
  enter: (direction) => ({
    rotateY: direction > 0 ? 90 : -90,
    opacity: 0,
    transformOrigin: direction > 0 ? 'left center' : 'right center',
  }),
  center: {
    rotateY: 0,
    opacity: 1,
    transformOrigin: 'center center',
  },
  exit: (direction) => ({
    rotateY: direction > 0 ? -90 : 90,
    opacity: 0,
    transformOrigin: direction > 0 ? 'right center' : 'left center',
  }),
};

export default function SessionDetailPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = sessionIdFromParams(params);
  const [detail, setDetail] = useState(null);
  const [pollErr, setPollErr] = useState('');
  const [msg, setMsg] = useState('');
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentErr, setAgentErr] = useState('');
  const [lastTurn, setLastTurn] = useState(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [retryBusy, setRetryBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const addToast = useToast();
  /** Avoid calling addToast inside setDetail — that runs during render/commit and updates ToastProvider illegally. */
  const prevSessionStatusRef = useRef({ sessionId: '', status: '' });
  /** True after we have loaded session JSON once (failed refresh should toast + keep last good detail). */
  const hadDetailRef = useRef(false);
  useEffect(() => {
    hadDetailRef.current = detail != null;
  }, [detail]);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const d = await apiGet(`/v1/sessions/${encodeURIComponent(sessionId)}`);
      const prev = prevSessionStatusRef.current;
      const sameSession = prev.sessionId === sessionId;
      if (sameSession && prev.status && prev.status !== 'ready' && d.status === 'ready') {
        queueMicrotask(() => {
          addToast({ message: `Research ready: "${d.topic}"`, type: 'success' });
        });
      }
      prevSessionStatusRef.current = { sessionId, status: d.status };
      setDetail(d);
      setPollErr('');
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setPollErr(msg);
      if (hadDetailRef.current) {
        queueMicrotask(() => {
          addToast({ message: `Could not refresh: ${msg}`, type: 'error' });
        });
      }
    }
  }, [sessionId, addToast]);

  const refreshSession = useCallback(async () => {
    setPollErr('');
    setAgentErr('');
    setRefreshBusy(true);
    try {
      await load();
    } finally {
      setRefreshBusy(false);
    }
  }, [load]);

  const retryFailedSession = useCallback(async () => {
    if (!sessionId) return;
    setRetryBusy(true);
    try {
      await apiPost(`/v1/sessions/${encodeURIComponent(sessionId)}/retry`, {});
      await load();
      addToast({ message: 'Research run restarted from the beginning.', type: 'success' });
    } catch (e) {
      addToast({
        message: e instanceof Error ? e.message : String(e),
        type: 'error',
      });
    } finally {
      setRetryBusy(false);
    }
  }, [sessionId, load, addToast]);

  const deleteWorkspace = useCallback(async () => {
    if (!sessionId) return;
    if (!window.confirm('Delete this workspace? This cannot be undone.')) return;
    setDeleteBusy(true);
    try {
      await apiDelete(`/v1/sessions/${encodeURIComponent(sessionId)}`);
      router.push('/research');
    } catch (e) {
      addToast({
        message: e instanceof Error ? e.message : String(e),
        type: 'error',
      });
    } finally {
      setDeleteBusy(false);
    }
  }, [sessionId, router, addToast]);

  useEffect(() => {
    prevSessionStatusRef.current = { sessionId: '', status: '' };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    load();
  }, [sessionId, load]);

  useEffect(() => {
    if (!detail || detail.status === 'ready') return undefined;
    if (detail.status === 'pending' || detail.status === 'running') {
      const t = setInterval(load, 1200);
      return () => clearInterval(t);
    }
    if (detail.status === 'error') {
      const t = setInterval(load, 3000);
      return () => clearInterval(t);
    }
    return undefined;
  }, [detail, load]);

  async function sendAgentTurn(e) {
    e.preventDefault();
    if (!msg.trim() || detail?.status !== 'ready') return;
    setAgentBusy(true);
    setAgentErr('');
    try {
      const res = await apiPost(`/v1/sessions/${encodeURIComponent(sessionId)}/agents/turn`, {
        message: msg.trim(),
        run_auditor: false,
      });
      setLastTurn(res);
      setMsg('');
      await load();
    } catch (e) {
      setAgentErr(e instanceof Error ? e.message : String(e));
    } finally {
      setAgentBusy(false);
    }
  }

  function goTo(idx) {
    if (!pages.length) return;
    setDirection(idx > pageIndex ? 1 : -1);
    setPageIndex(Math.max(0, Math.min(idx, pages.length - 1)));
  }

  if (!sessionId) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <Link href="/research" className="mb-6 inline-flex items-center text-sm text-primary hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          All sessions
        </Link>
        <p className="text-muted-foreground">Invalid or missing session in the URL.</p>
      </div>
    );
  }

  if (pollErr && !detail) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link href="/research" className="inline-flex items-center text-sm text-primary hover:underline">
            <ArrowLeft className="mr-1 h-4 w-4" />
            All sessions
          </Link>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={refreshBusy}
            onClick={() => refreshSession()}
            className="gap-1.5"
          >
            {refreshBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{friendlyLoadError(pollErr)}</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const pages = buildPages(detail, lastTurn);
  const clampedIdx = Math.min(pageIndex, pages.length - 1);
  const currentPage = pages[clampedIdx];

  return (
    <div className="mx-auto max-w-[1320px] px-4 py-8 lg:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/research"
          className="inline-flex items-center text-sm text-primary hover:underline transition-transform hover:-translate-x-0.5"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          All sessions
        </Link>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={refreshBusy}
          onClick={() => refreshSession()}
          className="gap-1.5"
          aria-label="Refresh session from server"
        >
          {refreshBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </Button>
      </div>

      {pollErr && detail ? (
        <div
          role="alert"
          className="mb-6 flex flex-wrap items-start justify-between gap-2 rounded-lg border border-destructive/35 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          <p className="min-w-0 flex-1">
            <span className="font-medium">Last refresh failed.</span>{' '}
            <span className="text-destructive/95">{friendlyLoadError(pollErr)}</span>
          </p>
          <button
            type="button"
            onClick={() => setPollErr('')}
            className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      {/* Notebook container */}
      <div
        className="relative rounded-2xl border border-border bg-card shadow-xl overflow-hidden"
        style={{ minHeight: 560, perspective: '1200px' }}
      >
        {/* Notebook top bar — tab strip */}
        <div className="flex items-end gap-1 overflow-x-auto overflow-y-hidden border-b border-border bg-surface-1 px-4 pt-3 pb-0">
          {pages.map((p, i) => (
            <button
              key={p.id}
              onClick={() => goTo(i)}
              className={`shrink-0 rounded-t-lg border border-b-0 px-4 py-2 text-xs font-medium transition-all duration-150 ${
                i === clampedIdx
                  ? 'border-border bg-card text-foreground -mb-px'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-surface-2'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Page content with flip animation */}
        <div className="relative" style={{ minHeight: 480 }}>
          <AnimatePresence custom={direction} mode="wait">
            <motion.div
              key={currentPage?.id}
              custom={direction}
              variants={pageVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              className="w-full"
              style={{ transformStyle: 'preserve-3d' }}
            >
              <PageContent
                page={currentPage}
                detail={detail}
                msg={msg}
                setMsg={setMsg}
                agentBusy={agentBusy}
                agentErr={agentErr}
                sendAgentTurn={sendAgentTurn}
                lastTurn={lastTurn}
                onSessionRefresh={load}
                retryBusy={retryBusy}
                deleteBusy={deleteBusy}
                onRetryFailedSession={retryFailedSession}
                onDeleteWorkspace={deleteWorkspace}
              />
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Bottom navigation */}
        <div className="flex items-center justify-between border-t border-border bg-surface-1 px-6 py-3">
          <button
            onClick={() => goTo(clampedIdx - 1)}
            disabled={clampedIdx === 0}
            className="flex items-center gap-1.5 text-sm text-muted-foreground disabled:opacity-30 hover:text-foreground transition-all duration-150 hover:-translate-x-0.5"
          >
            <ChevronLeft className="h-4 w-4" />
            Prev
          </button>

          <span className="font-mono text-xs text-muted-foreground">
            {clampedIdx + 1} / {pages.length}
          </span>

          <button
            onClick={() => goTo(clampedIdx + 1)}
            disabled={clampedIdx >= pages.length - 1}
            className="flex items-center gap-1.5 text-sm text-muted-foreground disabled:opacity-30 hover:text-foreground transition-all duration-150 hover:translate-x-0.5"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function formatSynthTs(ts) {
  if (typeof ts !== 'number' || Number.isNaN(ts)) return 'Earlier run';
  try {
    return new Date(ts * 1000).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return 'Earlier run';
  }
}

function SessionCorpusTools({ sessionId, onDone }) {
  const [mode, setMode] = useState('manual');
  const [title, setTitle] = useState('');
  const [bodyMd, setBodyMd] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [beamWidth, setBeamWidth] = useState(5);
  const [beamDepth, setBeamDepth] = useState(2);
  const [maxNewPapers, setMaxNewPapers] = useState(20);
  const [restrictCsMl, setRestrictCsMl] = useState(true);
  const [rawArxivQuery, setRawArxivQuery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [beamBusy, setBeamBusy] = useState(false);
  const [err, setErr] = useState('');
  const [regBusy, setRegBusy] = useState(false);

  async function submitSource(e) {
    e.preventDefault();
    if (!title.trim() || !bodyMd.trim()) {
      setErr('Title and body are required.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await apiPost(`/v1/sessions/${encodeURIComponent(sessionId)}/add-sources`, {
        title: title.trim(),
        body_md: bodyMd.trim(),
        source_url: sourceUrl.trim() || undefined,
      });
      setTitle('');
      setBodyMd('');
      setSourceUrl('');
      onDone?.();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  async function submitBeam(e) {
    e.preventDefault();
    setBeamBusy(true);
    setErr('');
    try {
      await apiPost(`/v1/sessions/${encodeURIComponent(sessionId)}/extend-arxiv-beam`, {
        beam_width: Math.min(25, Math.max(1, Number(beamWidth) || 5)),
        depth: Math.min(5, Math.max(1, Number(beamDepth) || 2)),
        max_new_papers: Math.min(100, Math.max(1, Number(maxNewPapers) || 20)),
        restrict_arxiv_cs_stat_ml: restrictCsMl,
        raw_arxiv_query: rawArxivQuery,
      });
      onDone?.();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBeamBusy(false);
    }
  }

  async function regenerate() {
    setRegBusy(true);
    setErr('');
    try {
      await apiPost(`/v1/sessions/${encodeURIComponent(sessionId)}/regenerate-graph`, {});
      onDone?.();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setRegBusy(false);
    }
  }

  return (
    <div className="mt-8 rounded-xl border border-border bg-surface-1/40 p-5">
      <h3 className="text-sm font-semibold text-foreground">Extend corpus &amp; refresh</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Add material in one of two ways, then we re-ingest into cloud memory and rebuild the graph and synthesis. You
        can also re-run on the current corpus only.
      </p>

      <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Corpus extension mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'manual'}
          onClick={() => setMode('manual')}
          className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
            mode === 'manual'
              ? 'border-primary bg-primary/10 text-foreground'
              : 'border-border bg-background/80 text-muted-foreground hover:text-foreground'
          }`}
        >
          <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Manual source
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'beam'}
          onClick={() => setMode('beam')}
          className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
            mode === 'beam'
              ? 'border-primary bg-primary/10 text-foreground'
              : 'border-border bg-background/80 text-muted-foreground hover:text-foreground'
          }`}
        >
          <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
          arXiv beam search
        </button>
      </div>

      {err ? <p className="mt-3 text-sm text-destructive">{err}</p> : null}

      {mode === 'manual' ? (
        <form onSubmit={submitSource} className="mt-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            Provide a <strong className="text-foreground/90">title</strong>,{' '}
            <strong className="text-foreground/90">markdown</strong> body, and optionally a canonical{' '}
            <strong className="text-foreground/90">URL</strong>.
          </p>
          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="src-title">
              Source title
            </label>
            <input
              id="src-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="e.g. Meeting notes — model biases"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="src-body">
              Markdown body
            </label>
            <textarea
              id="src-body"
              value={bodyMd}
              onChange={(e) => setBodyMd(e.target.value)}
              rows={5}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              placeholder="Write or paste markdown…"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="src-url">
              Source URL (optional)
            </label>
            <input
              id="src-url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="https://…"
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={busy} size="sm">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Add source &amp; regenerate
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={regBusy} onClick={regenerate}>
              {regBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Re-run graph &amp; synthesis
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={submitBeam} className="mt-4 space-y-3">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Runs several arXiv queries: first using this session&apos;s <strong className="text-foreground/90">topic</strong>,
            then short phrases from titles of papers found in the previous wave (beam expansion). New papers are
            ingested into Hydra, merged into the session corpus, then the graph and synthesis refresh.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="beam-w">
                Beam width
              </label>
              <input
                id="beam-w"
                type="number"
                min={1}
                max={25}
                value={beamWidth}
                onChange={(e) => setBeamWidth(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="beam-d">
                Depth (waves)
              </label>
              <input
                id="beam-d"
                type="number"
                min={1}
                max={5}
                value={beamDepth}
                onChange={(e) => setBeamDepth(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground" htmlFor="beam-max">
                Max new papers
              </label>
              <input
                id="beam-max"
                type="number"
                min={1}
                max={100}
                value={maxNewPapers}
                onChange={(e) => setMaxNewPapers(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={restrictCsMl}
              onChange={(e) => setRestrictCsMl(e.target.checked)}
              className="rounded border-input"
            />
            Limit to cs.CL / cs.AI / cs.LG / stat.ML
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={rawArxivQuery}
              onChange={(e) => setRawArxivQuery(e.target.checked)}
              className="rounded border-input"
            />
            Treat session topic as a raw arXiv query (advanced)
          </label>
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={beamBusy} size="sm">
              {beamBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Run beam search &amp; regenerate
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={regBusy} onClick={regenerate}>
              {regBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Re-run graph &amp; synthesis
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function PageContent({
  page,
  detail,
  msg,
  setMsg,
  agentBusy,
  agentErr,
  sendAgentTurn,
  lastTurn,
  onSessionRefresh,
  retryBusy,
  deleteBusy,
  onRetryFailedSession,
  onDeleteWorkspace,
}) {
  if (!page) return null;

  switch (page.type) {
    case 'info':
      return (
        <div className="px-8 py-7">
          <h1 className="font-display text-2xl text-foreground">{detail.topic}</h1>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{detail.session_id}</p>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface-1/60 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</p>
              <p className="mt-2">
                <span
                  className={
                    detail.status === 'ready'
                      ? 'rounded-full bg-success/15 px-2.5 py-1 text-xs font-semibold text-success'
                      : detail.status === 'error'
                        ? 'rounded-full bg-destructive/15 px-2.5 py-1 text-xs font-semibold text-destructive'
                        : 'rounded-full bg-secondary px-2.5 py-1 text-xs font-medium'
                  }
                >
                  {detail.status}
                </span>
              </p>
              {detail.error && <p className="mt-2 text-sm text-destructive">{detail.error}</p>}
            </div>

            <div className="rounded-lg border border-border bg-surface-1/60 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Memory</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {detail.use_hydra
                  ? detail.hydra_connected
                    ? 'Cloud memory is on — recall and saved context are active.'
                    : 'Cloud memory was requested but the server could not reach it.'
                  : 'Cloud memory is off for this workspace.'}
              </p>
            </div>

            {detail.outcome?.corpus_stats && (
              <div className="rounded-lg border border-border bg-surface-1/60 p-4 sm:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Corpus</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {detail.outcome.corpus_stats.total ?? 0} sources collected
                </p>
              </div>
            )}
          </div>

          {detail.status === 'error' ? (
            <div className="mt-6 rounded-lg border border-amber-200/80 bg-amber-50/90 px-4 py-4 text-sm text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
              <p className="font-medium">Fix or remove this workspace</p>
              <p className="mt-1 text-xs opacity-90">
                <strong>Retry run</strong> starts the research job again (same topic and cloud-memory setting). Use the
                header <strong>Refresh</strong> button to reload status without restarting. <strong>Delete</strong> removes
                this session from the list.
              </p>
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-3">
            {detail.status === 'error' ? (
              <Button type="button" size="sm" disabled={retryBusy} onClick={onRetryFailedSession}>
                {retryBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                Retry run
              </Button>
            ) : null}
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={deleteBusy}
              onClick={onDeleteWorkspace}
            >
              {deleteBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Delete workspace
            </Button>
          </div>

          {detail.status === 'pending' || detail.status === 'running' ? (
            <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Gathering sources… this page refreshes automatically.
            </div>
          ) : null}

          {detail.status === 'ready' && (detail.outcome?.corpus_stats?.total ?? 0) === 0 ? (
            <div className="mt-6 rounded-lg border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
              <p className="font-medium">No sources were found for this workspace.</p>
              <p className="mt-1 text-amber-900/90">
                Try starting a new session with a clearer topic.
              </p>
            </div>
          ) : null}

          {detail.status === 'ready' && detail.use_hydra ? (
            <SessionCorpusTools sessionId={detail.session_id} onDone={onSessionRefresh} />
          ) : null}
        </div>
      );

    case 'synthesis': {
      const o = page.outcome;
      const history = Array.isArray(o?.synthesis_history) ? o.synthesis_history : [];
      const synthErr = typeof o?.synthesis_error === 'string' ? o.synthesis_error.trim() : '';
      return (
        <div className="px-8 py-7">
          <h2 className="mb-1 font-display text-xl text-foreground">Synthesis</h2>
          <p className="mb-5 text-xs text-muted-foreground">
            Latest analysis on top. Open the <strong className="text-foreground/90">Knowledge graph</strong> tab for the
            interactive graph. Older runs are folded below.
          </p>
          {synthErr ? (
            <div className="mb-5 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <p className="font-semibold text-destructive">Synthesis did not complete</p>
              <p className="mt-2 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-destructive/95">
                {synthErr}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                Fix keys or provider errors, then use <strong className="text-foreground">Overview → Re-run graph &amp; synthesis</strong>.
              </p>
            </div>
          ) : null}
          {o?.final_analysis ? (
            <article className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-primary">Current</p>
              <div className="prose-sm max-w-none leading-relaxed">
                <MarkdownContent>{o.final_analysis}</MarkdownContent>
              </div>
            </article>
          ) : o?.analysis_prompt ? (
            <article className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {synthErr ? 'Prompt sent to the model (synthesis failed)' : 'Analysis prompt (no LLM reply yet)'}
              </p>
              <p className="mb-3 text-xs text-muted-foreground">
                Instructions and corpus below are the model input, not the answer. After a successful run you will see
                sections such as <strong className="text-foreground/90">Conflicts</strong>,{' '}
                <strong className="text-foreground/90">Hypotheses</strong>, etc.
              </p>
              <details className="group rounded-md border border-border/80 bg-muted/20">
                <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
                  <span className="inline-flex items-center gap-2">
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                    View full prompt (tasks &amp; rubric)
                  </span>
                </summary>
                <div className="max-h-[min(480px,50vh)] overflow-y-auto border-t border-border/60 px-4 pb-4 pt-2">
                  <div className="prose-sm max-w-none leading-relaxed text-foreground/85">
                    <MarkdownContent>{o.analysis_prompt}</MarkdownContent>
                  </div>
                </div>
              </details>
            </article>
          ) : (
            <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">No synthesis for this run yet.</p>
              <p className="mt-2 leading-relaxed">
                This can happen if the workspace was created with <strong>prompt only</strong>, the LLM step failed
                (check API keys), or analysis is still running. Use <strong>Overview → Re-run graph &amp; synthesis</strong>{' '}
                (with Hydra) to generate one.
              </p>
            </div>
          )}
          {history.length > 0 ? (
            <div className="mt-6 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                History ({history.length})
              </p>
              {history.map((h, i) => (
                <details
                  key={`${h.ts}-${i}`}
                  className="group rounded-lg border border-border/80 bg-muted/15 open:bg-muted/25"
                >
                  <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                    <span className="font-mono text-xs text-muted-foreground">{formatSynthTs(h.ts)}</span>
                    <span className="text-muted-foreground">— previous version</span>
                  </summary>
                  <div className="border-t border-border/60 px-4 pb-4 pt-1">
                    <div className="prose-sm max-w-none leading-relaxed text-foreground/90">
                      <MarkdownContent>{h.text}</MarkdownContent>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          ) : null}
        </div>
      );
    }

    case 'knowledge_graph':
      return (
        <div className="px-4 py-4 sm:px-8 sm:py-6">
          <KnowledgeGraphPanel knowledgeGraph={page.outcome?.knowledge_graph} />
        </div>
      );

    case 'transcript':
      return (
        <div className="px-8 py-7">
          <h2 className="mb-5 font-display text-xl text-foreground">{page.label}</h2>
          <ul className="space-y-3">
            {page.turns.map((t, i) => (
              <li
                key={`${t.ts}-${i}`}
                className={`rounded-md border px-3 py-2 text-sm transition-colors hover:bg-surface-1 ${
                  t.role === 'user'
                    ? 'border-primary/25 bg-primary/5'
                    : 'border-border bg-surface-1/50'
                }`}
              >
                {t.agent && (
                  <span className="font-mono text-xs font-semibold text-primary">{t.agent}</span>
                )}
                <div className="mt-1 max-w-none text-foreground/90">
                  <MarkdownContent>{t.content}</MarkdownContent>
                </div>
              </li>
            ))}
          </ul>
        </div>
      );

    case 'followup':
      return (
        <div className="px-8 py-7">
          <h2 className="mb-1 font-display text-xl text-foreground">Follow-up</h2>
          <p className="mb-5 text-xs text-muted-foreground">
            The right specialists are picked for each question you ask.
          </p>
          <form onSubmit={sendAgentTurn}>
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              rows={3}
              placeholder="Ask a question or request a short literature summary…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-shadow focus:shadow-sm"
            />
            {agentErr ? <p className="mt-2 text-sm text-destructive">{agentErr}</p> : null}
            <Button
              type="submit"
              className="mt-3 gap-2 transition-transform duration-200 hover:-translate-y-0.5 hover:skew-x-[-1deg]"
              disabled={agentBusy || !msg.trim()}
            >
              {agentBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </Button>
          </form>
          {page.lastTurn?.final_answer ? (
            <div className="mt-6 rounded-md border border-border bg-surface-1 p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Last reply</p>
              <div className="mt-2 max-w-none text-sm">
                <MarkdownContent>{page.lastTurn.final_answer}</MarkdownContent>
              </div>
            </div>
          ) : null}
        </div>
      );

    default:
      return null;
  }
}
