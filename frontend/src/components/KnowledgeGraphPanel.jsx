'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, GitBranch, X } from 'lucide-react';

const KnowledgeGraphFlow = dynamic(
  () => import('./KnowledgeGraphFlow').then((m) => m.KnowledgeGraphFlow),
  { ssr: false, loading: () => <p className="mt-5 text-xs text-muted-foreground">Loading graph…</p> },
);

const NODE_FIELD_KEYS = new Set(['id', 'label', 'kind']);

function pathsMentioningNode(node, paths) {
  if (!node?.id) return [];
  const label = (node.label || '').trim();
  return paths.filter((p) => {
    const s = typeof p.summary === 'string' ? p.summary : '';
    if (label.length >= 3 && s.includes(label)) return true;
    return s.includes(node.id);
  });
}

function edgesForNode(nodeId, edges) {
  return edges.filter((e) => e.source === nodeId || e.target === nodeId);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    /* ignore */
  }
}

function EntityInspectSidebar({ node, edges, paths, onClose }) {
  const related = useMemo(() => (node ? edgesForNode(node.id, edges) : []), [node, edges]);
  const pathHits = useMemo(() => (node ? pathsMentioningNode(node, paths) : []), [node, paths]);
  const extraFields = useMemo(() => {
    if (!node || typeof node !== 'object') return [];
    return Object.entries(node).filter(([k, v]) => !NODE_FIELD_KEYS.has(k) && v != null && v !== '');
  }, [node]);

  if (!node) return null;

  return (
    <aside
      className="flex max-h-[min(620px,calc(100vh-14rem))] min-h-[200px] w-full shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-lg xl:w-[380px]"
      aria-label="Entity details"
    >
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Entity</p>
          <h3 className="mt-1 break-words text-sm font-semibold leading-snug text-foreground">{node.label || node.id}</h3>
          {node.kind ? (
            <span className="mt-2 inline-block rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              {node.kind}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-3">
        <section>
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Identifiers</h4>
          <div className="mt-2 flex items-start gap-2 rounded-md border border-border/80 bg-muted/20 p-2">
            <code className="min-w-0 flex-1 break-all font-mono text-[11px] text-foreground/90">{node.id}</code>
            <button
              type="button"
              className="shrink-0 rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground"
              title="Copy id"
              onClick={() => copyText(String(node.id))}
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        </section>

        {extraFields.length > 0 ? (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Extra fields</h4>
            <dl className="mt-2 space-y-2 text-[11px]">
              {extraFields.map(([k, v]) => (
                <div key={k} className="rounded-md border border-border/60 bg-background/80 px-2 py-1.5">
                  <dt className="font-mono text-[10px] text-muted-foreground">{k}</dt>
                  <dd className="mt-0.5 break-words text-foreground/90">
                    {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}

        <section>
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Connections ({related.length})
          </h4>
          {related.length === 0 ? (
            <p className="mt-2 text-[11px] text-muted-foreground">No edges in this snapshot.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {related.map((e) => {
                const out = e.source === node.id;
                const otherLabel = out ? e.target_label : e.source_label;
                const otherId = out ? e.target : e.source;
                return (
                  <li
                    key={e.id}
                    className="rounded-md border border-border/70 bg-background/90 px-2.5 py-2 text-[11px] leading-snug"
                  >
                    <span className="font-mono text-[10px] text-primary">{e.predicate}</span>
                    <p className="mt-1 text-foreground/95">
                      {out ? '→' : '←'} {otherLabel || otherId}
                    </p>
                    {e.context ? (
                      <p className="mt-1.5 border-t border-border/50 pt-1.5 text-[10px] text-muted-foreground">{e.context}</p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {pathHits.length > 0 ? (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Paths ({pathHits.length})
            </h4>
            <ul className="mt-2 space-y-2">
              {pathHits.map((p) => (
                <li
                  key={p.id}
                  className="rounded-md border border-border/60 bg-muted/15 px-2.5 py-2 font-mono text-[10px] leading-relaxed text-foreground/85"
                >
                  {p.summary}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </aside>
  );
}

function LinkInspectSidebar({ edge, onClose }) {
  if (!edge) return null;
  return (
    <aside
      className="flex max-h-[min(620px,calc(100vh-14rem))] min-h-[200px] w-full shrink-0 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-lg xl:w-[380px]"
      aria-label="Relation details"
    >
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Relation</p>
          <h3 className="mt-1 font-mono text-sm font-semibold text-primary">{edge.predicate}</h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3 text-[11px]">
        <div>
          <p className="text-[10px] font-medium uppercase text-muted-foreground">Source</p>
          <p className="mt-1 text-foreground">{edge.source_label || edge.source}</p>
          <code className="mt-1 block break-all font-mono text-[10px] text-muted-foreground">{edge.source}</code>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase text-muted-foreground">Target</p>
          <p className="mt-1 text-foreground">{edge.target_label || edge.target}</p>
          <code className="mt-1 block break-all font-mono text-[10px] text-muted-foreground">{edge.target}</code>
        </div>
        {edge.context ? (
          <div>
            <p className="text-[10px] font-medium uppercase text-muted-foreground">Context</p>
            <p className="mt-1 leading-relaxed text-muted-foreground">{edge.context}</p>
          </div>
        ) : null}
        <div>
          <p className="text-[10px] font-medium uppercase text-muted-foreground">Edge id</p>
          <div className="mt-1 flex items-start gap-2">
            <code className="min-w-0 flex-1 break-all font-mono text-[10px]">{edge.id}</code>
            <button
              type="button"
              className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
              onClick={() => copyText(String(edge.id))}
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

/**
 * Renders Hydra-derived graph data from session outcome (`knowledge_graph`: nodes, edges, paths, stats).
 * @param {boolean} [embedded] - When true, tighter spacing for the notebook shell (pinned above bottom nav).
 */
export function KnowledgeGraphPanel({ knowledgeGraph, embedded = false }) {
  const [selection, setSelection] = useState(null);

  const clearSelection = useCallback(() => setSelection(null), []);

  const kg = knowledgeGraph && typeof knowledgeGraph === 'object' ? knowledgeGraph : null;

  const nodes = useMemo(
    () => (kg && Array.isArray(kg.nodes) ? kg.nodes : []),
    [kg]
  );
  const edges = useMemo(
    () => (kg && Array.isArray(kg.edges) ? kg.edges : []),
    [kg]
  );
  const paths = useMemo(
    () => (kg && Array.isArray(kg.paths) ? kg.paths : []),
    [kg]
  );
  const stats = useMemo(
    () => (kg && kg.stats && typeof kg.stats === 'object' ? kg.stats : {}),
    [kg]
  );

  const empty = useMemo(
    () =>
      (stats.node_count ?? nodes.length) === 0 &&
      (stats.edge_count ?? edges.length) === 0 &&
      (stats.path_count ?? paths.length) === 0,
    [stats, nodes.length, edges.length, paths.length]
  );

  const emptyStateDetail = useMemo(() => {
    if (!kg || !empty) return '';
    const meta = kg.meta && typeof kg.meta === 'object' ? kg.meta : {};
    const fullMeta = meta.full_recall && typeof meta.full_recall === 'object' ? meta.full_recall : {};
    const prefMeta = meta.preferences && typeof meta.preferences === 'object' ? meta.preferences : {};
    const hadGraphContext = Boolean(fullMeta.graph_context || prefMeta.graph_context);
    const gcKeys = [
      ...new Set([
        ...(Array.isArray(fullMeta.graph_context_keys) ? fullMeta.graph_context_keys : []),
        ...(Array.isArray(prefMeta.graph_context_keys) ? prefMeta.graph_context_keys : []),
      ]),
    ];
    const fullHasGc = fullMeta.graph_context === true;
    const prefHasGc = prefMeta.graph_context === true;
    const fullListsEmpty = !fullHasGc || fullMeta.graph_lists_empty === true;
    const prefListsEmpty = !prefHasGc || prefMeta.graph_lists_empty === true;
    const hydraReturnedEmptyGraphSlots =
      (fullHasGc || prefHasGc) && fullListsEmpty && prefListsEmpty;

    if (hadGraphContext) {
      return hydraReturnedEmptyGraphSlots
        ? `Hydra sent graph_context (${gcKeys.length ? gcKeys.slice(0, 12).join(', ') : '…'}) but the lists that hold paths and relations are empty. Workspaces use session-scoped recall: the graph only sees chunks tagged for this session. If ingest is still running, the topic is very narrow, or nothing matched yet, you get an empty shell. Wait for ingest to finish, try a slightly broader topic, confirm entity/graph features for your tenant, then open a new session—or check Hydra with the same topic and session id.`
        : `The API returned a graph_context block with data we could not map to nodes and edges (keys seen: ${gcKeys.length ? gcKeys.slice(0, 12).join(', ') : '…'}). Your Hydra tenant may use another schema, or graph extraction may be off for this corpus.`;
    }
    return 'Recall ran, but the response had no graph_context section with entity paths or relations. Ingest more sources into Hydra, enable graph extraction for your tenant if available, or try a broader topic and a new session.';
  }, [kg, empty]);

  useEffect(() => {
    if (selection?.type === 'node' && !nodes.some((n) => n.id === selection.id)) {
      setSelection(null);
    }
    if (selection?.type === 'link' && !edges.some((e) => e.id === selection.id)) {
      setSelection(null);
    }
  }, [nodes, edges, selection]);

  const selectedNode = useMemo(() => {
    if (selection?.type !== 'node') return null;
    return nodes.find((n) => n.id === selection.id) ?? null;
  }, [selection, nodes]);

  const selectedEdge = useMemo(() => {
    if (selection?.type !== 'link') return null;
    return edges.find((e) => e.id === selection.id) ?? null;
  }, [selection, edges]);

  const shell = embedded ? 'mb-0 rounded-none border-x-0 border-b-0 border-t-0 bg-transparent p-0 sm:p-0' : 'mb-10 rounded-lg border border-border bg-card p-5';

  if (!kg) {
    return (
      <section className={shell}>
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          <GitBranch className="h-4 w-4 shrink-0" aria-hidden />
          Knowledge graph
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          No graph snapshot for this session. Create a new session with cloud memory enabled so recall can
          return graph relations from your provider.
        </p>
      </section>
    );
  }

  if (empty) {
    return (
      <section className={shell}>
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          <GitBranch className="h-4 w-4 shrink-0" aria-hidden />
          Knowledge graph
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">{emptyStateDetail}</p>
      </section>
    );
  }

  const showSidebar = Boolean(selectedNode || selectedEdge);

  return (
    <section className={shell}>
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        <GitBranch className="h-4 w-4 shrink-0" aria-hidden />
        Knowledge graph
      </h2>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        Entities and relations from cloud memory recall. Click a node or edge to open details.
      </p>

      <div
        className={`mt-5 flex flex-col gap-4 ${showSidebar ? 'xl:flex-row xl:items-start' : ''}`}
      >
        <div className="min-w-0 flex-1">
          <KnowledgeGraphFlow
            nodes={nodes}
            edges={edges}
            selectedNodeId={selection?.type === 'node' ? selection.id : null}
            selectedLinkId={selection?.type === 'link' ? selection.id : null}
            onSelectNode={(id) => setSelection({ type: 'node', id })}
            onSelectLink={(id) => setSelection({ type: 'link', id })}
            onClearSelection={clearSelection}
          />
        </div>
        {selectedNode ? (
          <EntityInspectSidebar node={selectedNode} edges={edges} paths={paths} onClose={clearSelection} />
        ) : selectedEdge ? (
          <LinkInspectSidebar edge={selectedEdge} onClose={clearSelection} />
        ) : null}
      </div>

      <dl className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <div>
          <dt className="font-medium text-foreground">Nodes</dt>
          <dd>{stats.node_count ?? nodes.length}</dd>
        </div>
        <div>
          <dt className="font-medium text-foreground">Edges</dt>
          <dd>{stats.edge_count ?? edges.length}</dd>
        </div>
        <div>
          <dt className="font-medium text-foreground">Paths</dt>
          <dd>{stats.path_count ?? paths.length}</dd>
        </div>
      </dl>

      {nodes.length > 0 ? (
        <div className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-foreground">Nodes</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {nodes.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  className={`max-w-full rounded-full border px-3 py-1 text-left text-xs transition-colors ${
                    selection?.type === 'node' && selection.id === n.id
                      ? 'border-primary bg-primary/10 text-foreground'
                      : 'border-border bg-muted/30 text-foreground hover:bg-muted/50'
                  }`}
                  title={n.kind ? `${n.kind}: ${n.id}` : n.id}
                  onClick={() => setSelection({ type: 'node', id: n.id })}
                >
                  <span className="font-mono text-[10px] text-muted-foreground">{n.id.slice(0, 8)}…</span>{' '}
                  <span className="break-words">{n.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {paths.length > 0 ? (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-foreground">Entity paths</h3>
          <ul className="mt-2 space-y-2">
            {paths.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-border/80 bg-background/80 px-3 py-2 font-mono text-[11px] leading-relaxed text-foreground/90"
              >
                {p.summary}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
