'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { apiGet, apiPost } from '@/lib/api';
import { MarkdownContent } from '@/components/MarkdownContent';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Loader2, Send } from 'lucide-react';

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

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = sessionIdFromParams(params);
  const [detail, setDetail] = useState(null);
  const [pollErr, setPollErr] = useState('');
  const [msg, setMsg] = useState('');
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentErr, setAgentErr] = useState('');
  const [lastTurn, setLastTurn] = useState(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const d = await apiGet(`/v1/sessions/${encodeURIComponent(sessionId)}`);
      setDetail(d);
      setPollErr('');
    } catch (e) {
      setPollErr(e instanceof Error ? e.message : String(e));
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    load();
  }, [sessionId, load]);

  useEffect(() => {
    if (!detail || detail.status === 'ready' || detail.status === 'error') return undefined;
    const t = setInterval(load, 1200);
    return () => clearInterval(t);
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
        <Link href="/research" className="mb-6 inline-flex items-center text-sm text-primary hover:underline">
          <ArrowLeft className="mr-1 h-4 w-4" />
          All sessions
        </Link>
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

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 lg:px-6">
      <Link href="/research" className="mb-6 inline-flex items-center text-sm text-primary hover:underline">
        <ArrowLeft className="mr-1 h-4 w-4" />
        All sessions
      </Link>

      <header className="mb-8 border-b border-border pb-6">
        <h1 className="font-display text-2xl text-foreground">{detail.topic}</h1>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{detail.session_id}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {detail.use_hydra ? (
            detail.hydra_connected ? (
              <>Cloud memory is on for this workspace. Recall and saved context are active.</>
            ) : (
              <>Cloud memory was requested but the server could not reach it. Check setup with whoever runs
              the API.</>
            )
          ) : (
            <>Cloud memory is off for this workspace.</>
          )}
        </p>
        <p className="mt-3">
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
          {detail.error ? (
            <span className="ml-3 text-sm text-destructive">Error: {detail.error}</span>
          ) : null}
        </p>
      </header>

      {detail.status === 'pending' || detail.status === 'running' ? (
        <p className="mb-8 text-sm text-muted-foreground">
          Gathering sources… this page refreshes automatically.
        </p>
      ) : null}

      {detail.status === 'ready' &&
      detail.outcome &&
      (detail.outcome.corpus_stats?.total ?? 0) === 0 ? (
        <div className="mb-8 rounded-lg border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-medium">No sources were found for this workspace.</p>
          <p className="mt-1 text-amber-900/90 dark:text-amber-100/85">
            Try starting a new session with a clearer topic, or ask whoever runs this deployment to widen
            sources or turn on cloud memory. Some older sessions used a narrower paper filter and fewer web
            sources.
          </p>
        </div>
      ) : null}

      {detail.outcome?.final_analysis ? (
        <section className="mb-10 rounded-lg border border-border bg-card p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Synthesis</h2>
          <div className="mt-3 max-w-none">
            <MarkdownContent>{detail.outcome.final_analysis}</MarkdownContent>
          </div>
        </section>
      ) : null}

      {detail.transcript?.length > 0 ? (
        <section className="mb-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Transcript</h2>
          <ul className="space-y-3">
            {detail.transcript.map((t, i) => (
              <li
                key={`${t.ts}-${i}`}
                className={`rounded-md border px-3 py-2 text-sm ${
                  t.role === 'user'
                    ? 'border-primary/25 bg-primary/5'
                    : 'border-border bg-surface-1'
                }`}
              >
                {t.agent ? (
                  <span className="font-mono text-xs font-semibold text-primary">{t.agent}</span>
                ) : null}
                <div className="mt-1 max-w-none text-foreground/90">
                  <MarkdownContent>{t.content}</MarkdownContent>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {detail.status === 'ready' ? (
        <section className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Follow-up</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            The right specialists are picked for each question you ask. Advanced setups can pin specific
            experts through the API.
          </p>
          <form onSubmit={sendAgentTurn} className="mt-4">
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              rows={3}
              placeholder="Ask a question or request a short literature summary…"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            {agentErr ? <p className="mt-2 text-sm text-destructive">{agentErr}</p> : null}
            <Button type="submit" className="mt-3 gap-2" disabled={agentBusy || !msg.trim()}>
              {agentBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </Button>
          </form>
          {lastTurn?.final_answer ? (
            <div className="mt-6 rounded-md border border-border bg-surface-1 p-4">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Last reply</p>
              <div className="mt-2 max-w-none text-sm">
                <MarkdownContent>{lastTurn.final_answer}</MarkdownContent>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
