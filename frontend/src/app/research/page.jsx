'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCw } from 'lucide-react';

export default function ResearchSessionsPage() {
  const [sessions, setSessions] = useState([]);
  const [topic, setTopic] = useState('');
  const [useHydra, setUseHydra] = useState(true);
  const [runLlmSynthesis, setRunLlmSynthesis] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const refresh = useCallback(async () => {
    setErr('');
    try {
      const data = await apiGet('/v1/sessions/');
      setSessions(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function onCreate(e) {
    e.preventDefault();
    if (!topic.trim()) {
      setErr('Enter a topic above before creating a session.');
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
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 lg:px-6">
      <div className="mb-8">
        <h1 className="font-display text-3xl text-foreground">Research sessions</h1>
      </div>

      <form onSubmit={onCreate} className="mb-10 rounded-lg border border-border bg-card p-5 shadow-sm">
        <label className="text-sm font-medium text-foreground" htmlFor="topic">
          New topic
        </label>
        <textarea
          id="topic"
          name="topic"
          autoComplete="off"
          value={topic}
          onChange={(e) => {
            setTopic(e.target.value);
            if (err) setErr('');
          }}
          rows={2}
          placeholder="e.g. diffusion models for protein structure"
          className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <fieldset className="mt-4 space-y-4 border-t border-border pt-4">
          <legend className="text-sm font-medium text-foreground">Session build options</legend>
          <label className="flex cursor-pointer gap-3 rounded-md border border-border bg-muted/20 p-3 text-sm leading-snug">
            <input
              type="checkbox"
              checked={useHydra}
              onChange={(e) => setUseHydra(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
            />
            <span className="min-w-0 flex-1 space-y-1">
              <span className="block font-semibold text-foreground">Hydra DB</span>
              <p className="text-muted-foreground leading-relaxed">
                Session-scoped recall and corpus ingest. Configure Hydra on the API server; if it is
                unavailable, the session still builds a local corpus.
              </p>
            </span>
          </label>
          <label className="flex cursor-pointer gap-3 rounded-md border border-border bg-muted/20 p-3 text-sm leading-snug">
            <input
              type="checkbox"
              checked={runLlmSynthesis}
              onChange={(e) => setRunLlmSynthesis(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-primary focus-visible:ring-2 focus-visible:ring-ring"
            />
            <span className="min-w-0 flex-1 space-y-1">
              <span className="block font-semibold text-foreground">Initial LLM synthesis</span>
              <p className="text-muted-foreground leading-relaxed">
                Run the literature-analysis model once after ingest. Configure your LLM provider on the API
                server. Agent turns also use the LLM when that is set up.
              </p>
            </span>
          </label>
        </fieldset>
        <div className="relative z-10 mt-4 flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={loading} aria-busy={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create session'}
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => refresh()}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </form>

      {err ? (
        <div className="mb-6 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {err}
        </div>
      ) : null}

      <ul className="space-y-3">
        {sessions.length === 0 ? (
          <li className="rounded-lg border border-dashed border-border bg-surface-1/50 py-12 text-center text-sm text-muted-foreground">
            No sessions yet. Create one above (defaults: Hydra + LLM when configured on the server).
          </li>
        ) : (
          sessions.map((s) => (
            <li key={s.session_id}>
              <Link
                href={`/research/${encodeURIComponent(s.session_id)}`}
                className="block rounded-lg border border-border bg-card p-4 transition-colors hover:bg-surface-1"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{s.topic}</p>
                    <p className="mt-1 font-mono text-xs text-muted-foreground">{s.session_id}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {s.use_hydra
                        ? s.hydra_connected
                          ? 'Hydra · connected'
                          : 'Hydra · not connected'
                        : 'Hydra · off'}
                    </p>
                  </div>
                  <span
                    className={
                      s.status === 'ready'
                        ? 'rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-semibold text-success'
                        : s.status === 'error'
                          ? 'rounded-full bg-destructive/15 px-2.5 py-0.5 text-xs font-semibold text-destructive'
                          : 'rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground'
                    }
                  >
                    {s.status}
                  </span>
                </div>
              </Link>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
