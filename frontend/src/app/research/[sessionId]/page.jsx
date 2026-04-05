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

          {/* ── Knowledge stats row ── */}
          {detail.status === 'ready' && (
            <div className="mt-6 grid grid-cols-3 gap-3">
              {[
                {
                  value: detail.outcome?.corpus_stats?.total ?? 0,
                  label: 'Sources ingested',
                  sub: 'Papers, preprints, entries',
                },
                {
                  value: detail.outcome?.knowledge_graph?.nodes?.length ?? 0,
                  label: 'Entities mapped',
                  sub: 'In knowledge graph',
                },
                {
                  value: detail.outcome?.knowledge_graph?.edges?.length ?? 0,
                  label: 'Relationships',
                  sub: 'Graph connections',
                },
              ].map(({ value, label, sub }) => (
                <div
                  key={label}
                  className="rounded-xl border p-4 text-center"
                  style={{
                    background: 'linear-gradient(145deg, var(--card), var(--surface-1))',
                    borderColor: 'var(--border)',
                    boxShadow: 'var(--shadow-xs), inset 0 1px 0 rgba(255,255,255,0.70)',
                  }}
                >
                  <p
                    className="font-display text-3xl leading-none"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {value}
                  </p>
                  <p className="mt-1.5 text-xs font-medium" style={{ color: 'var(--foreground)' }}>{label}</p>
                  <p className="mt-0.5 text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{sub}</p>
                </div>
              ))}
            </div>
          )}

          {/* ── Status + Memory ── */}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface-1/60 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</p>
              <p className="mt-2">
                <span
                  className={
                    detail.status === 'ready'
                      ? 'rounded-full bg-success/15 px-2.5 py-1 text-xs font-mono font-semibold text-success'
                      : detail.status === 'error'
                        ? 'rounded-full bg-destructive/15 px-2.5 py-1 text-xs font-mono font-semibold text-destructive'
                        : 'rounded-full bg-secondary px-2.5 py-1 text-xs font-mono font-medium'
                  }
                >
                  {detail.status}
                </span>
              </p>
              {detail.error && <p className="mt-2 text-sm text-destructive">{detail.error}</p>}
            </div>

            {/* Memory card — prominent when connected */}
            <div
              className="rounded-lg border p-4"
              style={
                detail.use_hydra && detail.hydra_connected
                  ? {
                      background: 'linear-gradient(135deg, var(--accent) 0%, var(--surface-1) 100%)',
                      borderColor: 'var(--primary)',
                      borderWidth: '1px',
                      borderLeftWidth: '3px',
                    }
                  : { background: 'var(--surface-1)', borderColor: 'var(--border)' }
              }
            >
              <div className="flex items-center gap-2 mb-2">
                {/* HydraDB wave mark */}
                <svg width="14" height="10" viewBox="0 0 14 10" fill="none" style={{ color: detail.hydra_connected ? 'var(--primary)' : 'var(--muted-foreground)' }}>
                  <path d="M1 8.5C2.5 5 4 3 7 3C10 3 11.5 5 13 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                  <path d="M3 8.5C4 6.5 5 5.5 7 5.5C9 5.5 10 6.5 11 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.55"/>
                  <circle cx="7" cy="1.5" r="1" fill="currentColor" opacity="0.75"/>
                </svg>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  HydraDB Memory
                </p>
              </div>
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {detail.use_hydra
                  ? detail.hydra_connected
                    ? 'Active — papers ingested, graph built, recall enabled.'
                    : 'Requested but could not reach the server.'
                  : 'Off for this workspace.'}
              </p>
              {detail.use_hydra && detail.hydra_connected && (
                <p
                  className="mt-2 font-mono text-[10px] uppercase tracking-[0.08em]"
                  style={{ color: 'var(--primary)', opacity: 0.75 }}
                >
                  Knowledge carries forward →
                </p>
              )}
            </div>
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
      const sourceCount = detail.outcome?.corpus_stats?.total ?? 0;
      return (
        <div className="px-8 py-7">
          <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
            <div>
              <h2 className="font-display text-xl text-foreground">Synthesis</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Latest analysis on top. Open <strong className="text-foreground/90">Knowledge graph</strong> for the
                interactive graph.
              </p>
            </div>
            {/* HydraDB metadata badges */}
            <div className="flex flex-wrap items-center gap-2">
              {sourceCount > 0 && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[10px] font-medium uppercase tracking-wider"
                  style={{
                    background: 'var(--surface-1)',
                    border: '1px solid var(--border)',
                    color: 'var(--muted-foreground)',
                  }}
                >
                  {sourceCount} sources
                </span>
              )}
              {detail.hydra_connected && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[10px] font-medium uppercase tracking-wider"
                  style={{
                    background: 'var(--accent)',
                    border: '1px solid var(--primary)',
                    borderWidth: '1px',
                    color: 'var(--primary)',
                  }}
                >
                  {/* HydraDB wave mark */}
                  <svg width="12" height="9" viewBox="0 0 12 9" fill="none">
                    <path d="M1 7.5C2 4.5 3.5 2.5 6 2.5C8.5 2.5 10 4.5 11 7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    <path d="M2.5 7.5C3.3 5.8 4.4 5 6 5C7.6 5 8.7 5.8 9.5 7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" opacity="0.55"/>
                    <circle cx="6" cy="1.2" r="0.9" fill="currentColor" opacity="0.75"/>
                  </svg>
                  HydraDB recall
                </span>
              )}
            </div>
          </div>
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
            <article
              className="rounded-xl border p-6"
              style={{
                background: 'var(--card)',
                borderColor: 'var(--border)',
                boxShadow: 'var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.75)',
              }}
            >
              <div className="flex items-center gap-2 mb-4 pb-4 border-b" style={{ borderColor: 'var(--border)' }}>
                <span
                  className="rounded-full px-2.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider"
                  style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                >
                  Current
                </span>
                <span className="font-mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                  Latest synthesis run
                </span>
              </div>
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
          {/* Sources ingested to HydraDB */}
          {(() => {
            const papers = Array.isArray(o?.papers) ? o.papers : [];
            if (papers.length === 0) return null;
            return (
              <details className="mt-6 group rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                <summary
                  className="flex cursor-pointer list-none items-center justify-between px-5 py-4 marker:content-none [&::-webkit-details-marker]:hidden transition-colors"
                  style={{ background: 'var(--surface-1)' }}
                >
                  <div className="flex items-center gap-3">
                    {/* HydraDB wave mark */}
                    <svg width="14" height="10" viewBox="0 0 14 10" fill="none" style={{ color: 'var(--primary)' }}>
                      <path d="M1 8.5C2.5 5 4 3 7 3C10 3 11.5 5 13 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                      <path d="M3 8.5C4 6.5 5 5.5 7 5.5C9 5.5 10 6.5 11 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.55"/>
                      <circle cx="7" cy="1.5" r="1" fill="currentColor" opacity="0.75"/>
                    </svg>
                    <span className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                      Sources ingested to HydraDB
                    </span>
                    <span
                      className="rounded-full px-2 py-0.5 font-mono text-[10px]"
                      style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                    >
                      {papers.length}
                    </span>
                  </div>
                  <ChevronDown
                    className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180"
                    style={{ color: 'var(--muted-foreground)' }}
                  />
                </summary>

                <div
                  className="border-t divide-y"
                  style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
                >
                  {papers.slice(0, 30).map((p, idx) => (
                    <div key={p.arxiv_id || idx} className="px-5 py-3.5 flex items-start gap-3">
                      {/* Source badge */}
                      <span
                        className="shrink-0 mt-0.5 rounded px-1.5 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider"
                        style={{
                          background: p.source === 'arxiv' ? 'var(--primary)' : 'var(--surface-2)',
                          color: p.source === 'arxiv' ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                        }}
                      >
                        {p.source || 'src'}
                      </span>
                      <div className="min-w-0 flex-1">
                        {p.abs_url ? (
                          <a
                            href={p.abs_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[13px] font-medium leading-snug hover:underline"
                            style={{ color: 'var(--foreground)' }}
                          >
                            {p.title}
                          </a>
                        ) : (
                          <p className="text-[13px] font-medium leading-snug" style={{ color: 'var(--foreground)' }}>
                            {p.title}
                          </p>
                        )}
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                          {p.authors?.length > 0 && (
                            <span className="font-mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                              {p.authors.slice(0, 3).join(', ')}{p.authors.length > 3 ? ` +${p.authors.length - 3}` : ''}
                            </span>
                          )}
                          {p.published && (
                            <span className="font-mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                              {p.published.slice(0, 4)}
                            </span>
                          )}
                          {p.citation_count > 0 && (
                            <span className="font-mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                              {p.citation_count} citations
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  {papers.length > 30 && (
                    <p className="px-5 py-3 text-xs text-center" style={{ color: 'var(--muted-foreground)' }}>
                      + {papers.length - 30} more sources in HydraDB
                    </p>
                  )}
                </div>
              </details>
            );
          })()}

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
          <div className="flex items-center gap-3 mb-6">
            <h2 className="font-display text-xl text-foreground">{page.label}</h2>
            <span
              className="rounded-full px-2.5 py-0.5 font-mono text-[10px]"
              style={{ background: 'var(--surface-1)', color: 'var(--muted-foreground)', border: '1px solid var(--border)' }}
            >
              {page.turns.length} turn{page.turns.length !== 1 ? 's' : ''}
            </span>
          </div>
          <ul className="space-y-3">
            {page.turns.map((t, i) => (
              <li
                key={`${t.ts}-${i}`}
                className="rounded-xl border overflow-hidden"
                style={
                  t.role === 'user'
                    ? {
                        borderColor: 'var(--primary)',
                        borderWidth: '1px',
                        borderLeftWidth: '3px',
                        background: 'linear-gradient(135deg, var(--accent), var(--surface-1))',
                        boxShadow: 'var(--shadow-xs)',
                      }
                    : {
                        borderColor: 'var(--border)',
                        background: 'var(--card)',
                        boxShadow: 'var(--shadow-xs)',
                      }
                }
              >
                {/* Turn header */}
                <div
                  className="flex items-center gap-2 px-4 py-2.5 border-b"
                  style={{ borderColor: t.role === 'user' ? 'rgba(124,45,18,0.15)' : 'var(--border)' }}
                >
                  <span
                    className="rounded-full px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider"
                    style={
                      t.role === 'user'
                        ? { background: 'var(--primary)', color: 'var(--primary-foreground)' }
                        : { background: 'var(--surface-2)', color: 'var(--muted-foreground)' }
                    }
                  >
                    {t.role === 'user' ? 'You' : (t.agent || 'Agent')}
                  </span>
                  {t.ts && (
                    <span className="font-mono text-[9px]" style={{ color: 'var(--muted-foreground)' }}>
                      {new Date(t.ts * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                {/* Turn content */}
                <div className="px-4 py-3 max-w-none text-sm leading-relaxed text-foreground/90">
                  <MarkdownContent>{t.content}</MarkdownContent>
                </div>
              </li>
            ))}
          </ul>
        </div>
      );

    case 'followup': {
      const specialists = ['Analyst', 'Critic', 'Synthesizer'];
      return (
        <div className="px-8 py-7">

          {/* Header row */}
          <div className="flex flex-wrap items-start justify-between gap-4 mb-7">
            <div>
              <h2 className="font-display text-xl text-foreground">Follow-up</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Routed to the right specialist automatically
              </p>
            </div>
            {/* Specialist pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {specialists.map((s) => (
                <span
                  key={s}
                  className="rounded-full border px-2.5 py-0.5 font-mono text-[9px] font-medium uppercase tracking-wider"
                  style={{
                    borderColor: 'var(--border)',
                    background: 'var(--surface-1)',
                    color: 'var(--muted-foreground)',
                  }}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>

          {/* Last reply — shown above the input */}
          {page.lastTurn?.final_answer ? (
            <div
              className="mb-6 rounded-xl border p-5 relative overflow-hidden"
              style={{
                background: 'linear-gradient(145deg, var(--card), var(--surface-1))',
                borderColor: 'var(--border)',
                borderLeftWidth: '3px',
                borderLeftColor: 'var(--primary)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <span
                  className="rounded-full px-2.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider"
                  style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
                >
                  {page.lastTurn.agent || 'Agent'}
                </span>
                <span className="font-mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>replied</span>
              </div>
              <div className="max-w-none text-sm leading-relaxed">
                <MarkdownContent>{page.lastTurn.final_answer}</MarkdownContent>
              </div>
            </div>
          ) : null}

          {/* Input area */}
          <form onSubmit={sendAgentTurn} className="relative">
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  if (!agentBusy && msg.trim()) sendAgentTurn(e);
                }
              }}
              rows={4}
              placeholder="Ask a follow-up question, request a deeper dive, or probe a conflict in the literature…"
              className="w-full rounded-xl border border-input bg-background px-4 py-3 pb-12 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-shadow focus:shadow-sm resize-none"
              style={{ boxShadow: 'var(--shadow-xs)' }}
            />
            {/* Floating send button */}
            <div className="absolute bottom-3 right-3 flex items-center gap-2">
              <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: 'var(--muted-foreground)' }}>
                ⌘↵
              </span>
              <Button
                type="submit"
                size="sm"
                className="h-8 gap-1.5 rounded-lg px-3 text-xs font-semibold transition-all hover:-translate-y-0.5"
                disabled={agentBusy || !msg.trim()}
              >
                {agentBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Send
              </Button>
            </div>
          </form>

          {agentErr ? <p className="mt-2 text-sm text-destructive">{agentErr}</p> : null}
        </div>
      );
    }

    default:
      return null;
  }
}
