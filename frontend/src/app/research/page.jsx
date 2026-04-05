'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { apiGet, apiPost } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ActivityPanel } from '@/components/ActivityPanel';
import { useToast } from '@/components/Toast';
import { Loader2, RefreshCw, Plus, X, GitCommitVertical, Brain, BookOpen, Network } from 'lucide-react';

function statusDotClass(status) {
  if (status === 'ready') return 'bg-success border-success/40';
  if (status === 'error') return 'bg-destructive border-destructive/40';
  if (status === 'running' || status === 'pending') return 'bg-primary border-primary/40 animate-pulse';
  return 'bg-muted-foreground/40 border-border';
}

function statusBadgeClass(status) {
  if (status === 'ready') return 'bg-success/15 text-success';
  if (status === 'error') return 'bg-destructive/15 text-destructive';
  return 'bg-secondary text-secondary-foreground';
}

function statusAccentColor(status) {
  if (status === 'ready') return 'var(--success)';
  if (status === 'error') return 'var(--destructive)';
  if (status === 'running' || status === 'pending') return 'var(--primary)';
  return 'var(--surface-3)';
}

function GitTree({ sessions }) {
  if (sessions.length === 0) {
    return (
      <div
        className="rounded-xl border border-dashed border-border py-16 text-center"
        style={{ background: 'linear-gradient(145deg, var(--card), var(--surface-1))' }}
      >
        <p
          className="font-display text-base"
          style={{ color: 'var(--foreground)', opacity: 0.55 }}
        >
          No sessions yet
        </p>
        <p className="mt-1.5 text-xs text-muted-foreground">
          Create your first workspace above to begin.
        </p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Trunk line */}
      <div className="absolute left-[11px] top-3 bottom-3 w-px bg-border" aria-hidden />

      <ul className="space-y-0">
        {sessions.map((s, i) => {
          const isLast = i === sessions.length - 1;
          return (
            <li key={s.session_id} className="relative flex gap-0">
              {/* Node column */}
              <div className="relative z-10 flex w-6 shrink-0 flex-col items-center">
                <div
                  className={`mt-4 h-3.5 w-3.5 shrink-0 rounded-full border-2 ${statusDotClass(s.status)}`}
                />
                {/* connector below dot (except last) */}
                {!isLast && (
                  <div className="flex-1 w-px bg-border mt-1" style={{ minHeight: 20 }} />
                )}
              </div>

              {/* Card */}
              <div className="mb-3 ml-3 flex-1 min-w-0">
                <Link
                  href={`/research/${encodeURIComponent(s.session_id)}`}
                  className="block rounded-lg border border-border bg-card transition-all duration-200 hover:bg-surface-1 hover:-translate-y-0.5 hover:shadow-sm"
                  style={{
                    padding: '0.875rem 0.875rem 0.875rem 0.75rem',
                    borderLeftWidth: '3px',
                    borderLeftStyle: 'solid',
                    borderLeftColor: statusAccentColor(s.status),
                    boxShadow: 'var(--shadow-xs)',
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground text-sm">{s.topic}</p>
                      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{s.session_id}</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">
                        {s.use_hydra
                          ? s.hydra_connected
                            ? 'Cloud memory · on'
                            : 'Cloud memory · unavailable'
                          : 'Cloud memory · off'}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2.5 py-0.5 font-mono text-[10px] font-semibold ${statusBadgeClass(s.status)}`}
                    >
                      {s.status}
                    </span>
                  </div>
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ─── Memory flywheel stats panel ─────────────────────────────────────────────

function MemoryStats({ sessions }) {
  const memorySessions = sessions.filter((s) => s.use_hydra);
  const connected = sessions.filter((s) => s.hydra_connected);
  const completed = sessions.filter((s) => s.status === 'ready');

  if (memorySessions.length === 0) return null;

  const stats = [
    { icon: Brain, value: connected.length, label: 'Memory sessions', sub: 'HydraDB connected' },
    { icon: BookOpen, value: completed.length, label: 'Completed runs', sub: 'Knowledge ingested' },
    { icon: Network, value: connected.length > 0 ? '↑' : '—', label: 'Compounding', sub: 'Across all sessions' },
  ];

  return (
    <div
      className="mb-8 rounded-xl border p-5"
      style={{
        background: 'linear-gradient(135deg, var(--card) 0%, var(--surface-1) 100%)',
        borderColor: 'var(--border)',
        boxShadow: 'var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.70)',
        borderLeftWidth: '3px',
        borderLeftColor: 'var(--primary)',
      }}
    >
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          {/* HydraDB wave mark */}
          <svg width="16" height="11" viewBox="0 0 16 11" fill="none" style={{ color: 'var(--primary)' }}>
            <path d="M1 9.5C3 5.5 5 3 8 3C11 3 13 5.5 15 9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <path d="M3.5 9.5C5 7 6.2 6 8 6C9.8 6 11 7 12.5 9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.55"/>
            <circle cx="8" cy="1.5" r="1.1" fill="currentColor" opacity="0.75"/>
          </svg>
          <p
            className="font-mono text-[10.5px] font-medium uppercase tracking-[0.10em]"
            style={{ color: 'var(--primary)' }}
          >
            HydraDB Knowledge Base
          </p>
        </div>
        <span
          className="flex items-center gap-1.5 font-mono text-[10px]"
          style={{ color: 'var(--muted-foreground)' }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'var(--success)' }} />
          Active · Global
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {stats.map(({ icon: Icon, value, label, sub }) => (
          <div key={label}>
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className="h-3.5 w-3.5" style={{ color: 'var(--primary)', opacity: 0.7 }} />
              <span
                className="font-display text-2xl leading-none"
                style={{ color: 'var(--foreground)' }}
              >
                {value}
              </span>
            </div>
            <p className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{label}</p>
            <p className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{sub}</p>
          </div>
        ))}
      </div>

      <p
        className="mt-4 pt-4 text-[11.5px] leading-relaxed border-t"
        style={{ color: 'var(--muted-foreground)', borderColor: 'var(--border)' }}
      >
        Each session with memory ON ingests papers into a shared knowledge base.
        Recall improves with every run — the agent draws from everything it has ever read.
      </p>
    </div>
  );
}

// ─── New workspace form (collapsible) ────────────────────────────────────────

function NewWorkspaceForm({ onCreated, onCancel }) {
  const [topic, setTopic] = useState('');
  const [useHydra, setUseHydra] = useState(true);
  const [runLlmSynthesis, setRunLlmSynthesis] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  async function onCreate(e) {
    e.preventDefault();
    if (!topic.trim()) {
      setErr('Enter a topic before creating a session.');
      return;
    }
    setLoading(true);
    setErr('');
    try {
      await apiPost('/v1/sessions/', {
        topic: topic.trim(),
        use_hydra: useHydra,
        prompt_only: !runLlmSynthesis,
        ingest_to_knowledge: useHydra,
        restrict_recall_to_session: true,
        max_papers: 20,
        restrict_arxiv_cs_stat_ml: false,
        wikipedia_max: 2,
        crossref_max: 4,
      });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={onCreate}
      className="rounded-xl border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between mb-4">
        <label className="text-sm font-medium text-foreground" htmlFor="topic">
          New topic
        </label>
        <button
          type="button"
          onClick={onCancel}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <textarea
        ref={textareaRef}
        id="topic"
        name="topic"
        autoComplete="off"
        value={topic}
        onChange={(e) => { setTopic(e.target.value); if (err) setErr(''); }}
        rows={2}
        placeholder="e.g. diffusion models for protein structure"
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-shadow focus:shadow-sm"
      />

      <fieldset className="mt-4 space-y-3 border-t border-border pt-4">
        <legend className="text-sm font-medium text-foreground">Options</legend>

        <label className="flex cursor-pointer gap-3 rounded-md border border-border bg-muted/20 p-3 text-sm leading-snug transition-colors hover:bg-muted/40">
          <input
            type="checkbox"
            checked={useHydra}
            onChange={(e) => setUseHydra(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
          />
          <span className="min-w-0 flex-1 space-y-0.5">
            <span className="block font-semibold text-foreground">Cloud memory</span>
            <p className="text-muted-foreground leading-relaxed text-xs">
              Tie recall and saved notes to this session via HydraDB.
            </p>
          </span>
        </label>

        <label className="flex cursor-pointer gap-3 rounded-md border border-border bg-muted/20 p-3 text-sm leading-snug transition-colors hover:bg-muted/40">
          <input
            type="checkbox"
            checked={runLlmSynthesis}
            onChange={(e) => setRunLlmSynthesis(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
          />
          <span className="min-w-0 flex-1 space-y-0.5">
            <span className="block font-semibold text-foreground">Initial synthesis</span>
            <p className="text-muted-foreground leading-relaxed text-xs">
              Run the literature analysis once after sources are gathered.
            </p>
          </span>
        </label>
      </fieldset>

      {err && (
        <p className="mt-3 text-sm text-destructive">{err}</p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={loading}
          aria-busy={loading}
          className="transition-transform duration-200 hover:-translate-y-0.5 hover:skew-x-[-1deg] active:translate-y-0"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create session'}
        </Button>
        <button
          type="button"
          onClick={onCancel}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ResearchSessionsPage() {
  const [sessions, setSessions] = useState([]);
  const [loadError, setLoadError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [activityActive, setActivityActive] = useState(false);
  const addToast = useToast();

  const refresh = useCallback(async () => {
    setLoadError('');
    try {
      const data = await apiGet('/v1/sessions/');
      setSessions(Array.isArray(data) ? data : []);
    } catch (e) {
      setSessions([]);
      setLoadError(
        e instanceof Error ? e.message : 'Failed to load sessions. Is the API running?'
      );
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Poll running sessions and fire toasts
  useEffect(() => {
    const running = sessions.filter((s) => s.status === 'pending' || s.status === 'running');
    if (!running.length) return;
    const id = setInterval(async () => {
      try {
        const data = await apiGet('/v1/sessions/');
        const updated = Array.isArray(data) ? data : [];
        setSessions(updated);
        running.forEach((prev) => {
          const curr = updated.find((s) => s.session_id === prev.session_id);
          if (curr?.status === 'ready') {
            addToast({ message: `Research ready: "${curr.topic}"`, type: 'success' });
            setActivityActive(false);
          } else if (curr?.status === 'error') {
            addToast({ message: `Session failed: "${curr.topic}"`, type: 'error' });
            setActivityActive(false);
          }
        });
      } catch {}
    }, 1800);
    return () => clearInterval(id);
  }, [sessions, addToast]);

  function handleCreated() {
    setShowForm(false);
    setActivityActive(true);
    refresh();
  }

  return (
    <div className="min-h-screen px-4 py-10 lg:px-6">
      <div className="mx-auto max-w-[1320px]">

        {/* Page header */}
        <div className="mb-8 flex items-center justify-between">
          <h1 className="font-display text-3xl text-foreground">Workspaces</h1>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refresh()}
            className="transition-transform duration-200 hover:-translate-y-0.5"
          >
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>

        {/* Memory flywheel stats */}
        <MemoryStats sessions={sessions} />

        {/* Two-column when activity is active */}
        <div className="flex gap-6">
          {/* Left column */}
          <motion.div
            layout
            animate={{ flex: activityActive ? '0 0 55%' : '1 1 100%' }}
            transition={{ type: 'spring', stiffness: 220, damping: 28 }}
            className="min-w-0"
          >
            {/* ── New workspace button / form ── */}
            <AnimatePresence mode="wait">
              {!showForm ? (
                <motion.div
                  key="cta"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.18 }}
                  className="mb-8"
                >
                  <button
                    onClick={() => setShowForm(true)}
                    className="group flex w-full items-center gap-3.5 rounded-xl border border-dashed border-border px-5 py-4 text-left transition-all duration-200 hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-sm"
                    style={{
                      background: 'linear-gradient(145deg, var(--card) 0%, var(--surface-1) 100%)',
                      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.70)',
                    }}
                  >
                    <div
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-110"
                      style={{
                        background: 'var(--primary)',
                        color: 'var(--primary-foreground)',
                        boxShadow: '0 1px 5px rgba(124,45,18,0.32)',
                      }}
                    >
                      <Plus className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">New workspace</p>
                      <p className="text-xs text-muted-foreground">Enter a topic, pick options, and start a session</p>
                    </div>
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="form"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  className="mb-8 overflow-hidden"
                >
                  <NewWorkspaceForm
                    onCreated={handleCreated}
                    onCancel={() => setShowForm(false)}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Git-tree session history ── */}
            <div>
              <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">
                <GitCommitVertical className="h-3.5 w-3.5" />
                Session history
              </div>
              {loadError ? (
                <div
                  role="alert"
                  className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                  {loadError}
                </div>
              ) : null}
              <GitTree sessions={sessions} />
            </div>
          </motion.div>

          {/* Right column — activity panel */}
          <AnimatePresence>
            {activityActive && (
              <motion.div
                key="activity-panel"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: '42%' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ type: 'spring', stiffness: 220, damping: 28 }}
                className="shrink-0 overflow-hidden"
                style={{ minHeight: 480 }}
              >
                <ActivityPanel active={activityActive} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </div>
  );
}
