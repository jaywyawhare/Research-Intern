'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const MAX_NODES = 220;
const MAX_EDGES = 650;

const NODE_COLORS = {
  entity: { fill: '#4dabf7', stroke: '#1971c2' },
  concept: { fill: '#da77f2', stroke: '#9c36b5' },
  source: { fill: '#51cf66', stroke: '#2f9e44' },
  default: { fill: '#868e96', stroke: '#495057' },
};

const EDGE_COLORS = {
  RELATED_TO: '#7d8fa3',
  USES: '#4dabf7',
  PART_OF: '#b197fc',
  CAUSES: '#ff8787',
  USES_TOOL: '#63e6be',
  PUBLISHED_BY: '#74c0fc',
  MEMBER_OF: '#c0eb75',
  default: '#5c6f82',
};

const NODE_RADIUS = 8;

function nodeIdFromLinkEnd(end) {
  if (end && typeof end === 'object') return end.id;
  return end;
}

function linkTouchesNodeId(link, id) {
  if (id == null) return false;
  return nodeIdFromLinkEnd(link.source) === id || nodeIdFromLinkEnd(link.target) === id;
}

function buildGraph(nodes, edges) {
  const graphNodes = nodes.map((n) => {
    const kind = n.kind || 'default';
    const colors = NODE_COLORS[kind] || NODE_COLORS.default;
    return {
      id: n.id,
      label: String(n.label ?? n.id ?? '').slice(0, 96),
      kind,
      color: colors.fill,
      stroke: colors.stroke,
      __r: NODE_RADIUS,
    };
  });
  const graphLinks = edges.map((e) => {
    const predicate = String(e.predicate || 'related_to');
    const edgeColor = EDGE_COLORS[predicate] || EDGE_COLORS.default;
    const short =
      predicate.length > 22 ? `${predicate.slice(0, 20)}…` : predicate;
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      predicate: short,
      color: edgeColor,
    };
  });
  return { nodes: graphNodes, links: graphLinks };
}

export function KnowledgeGraphFlow({
  nodes: rawNodes,
  edges: rawEdges,
  selectedNodeId = null,
  selectedLinkId = null,
  onSelectNode,
  onSelectLink,
  onClearSelection,
}) {
  const fgRef = useRef();
  const surfaceRef = useRef(null);
  const [[graphW, graphH], setGraphDims] = useState([800, 560]);
  const graphDataRef = useRef({ nodes: [], links: [] });

  useLayoutEffect(() => {
    const el = surfaceRef.current;
    if (!el) return;
    /** Layout size (not getBoundingClientRect): parent uses 3D flip transforms; screen-space AABB stays narrow mid-animation and under-measures width. */
    const measure = () => {
      const w = Math.max(1, Math.floor(el.clientWidth));
      const h = Math.max(1, Math.floor(el.clientHeight));
      setGraphDims([w, h]);
    };
    measure();
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(measure);
    });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
      ro.disconnect();
    };
  }, []);

  const { graphData, cappedNodes, cappedEdges, totalNodes, totalEdges } = useMemo(() => {
    const nodes = Array.isArray(rawNodes) ? rawNodes : [];
    const edges = Array.isArray(rawEdges) ? rawEdges : [];
    console.log('[KnowledgeGraphFlow] rawNodes:', nodes.length, 'rawEdges:', edges.length);
    const overNodes = nodes.length > MAX_NODES;
    const sliced = overNodes ? nodes.slice(0, MAX_NODES) : nodes;
    const idSet = new Set(sliced.map((n) => n.id));
    let de = edges.filter((e) => idSet.has(e.source) && idSet.has(e.target));
    const overEdges = de.length > MAX_EDGES;
    if (overEdges) de = de.slice(0, MAX_EDGES);
    console.log('[KnowledgeGraphFlow] graphData nodes:', sliced.length, 'edges:', de.length);
    return {
      graphData: buildGraph(sliced, de),
      cappedNodes: overNodes,
      cappedEdges: overEdges,
      totalNodes: nodes.length,
      totalEdges: edges.length,
    };
  }, [rawNodes, rawEdges]);

  graphDataRef.current = graphData;

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && onClearSelection) onClearSelection();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClearSelection]);

  const fit = useCallback(() => {
    const fg = fgRef.current;
    if (fg && typeof fg.zoomToFit === 'function') {
      fg.zoomToFit(400, 72);
    }
  }, []);

  const handleEngineStop = useCallback(() => {
    graphDataRef.current.nodes.forEach((n) => {
      if (n.x != null && n.y != null) {
        n.fx = n.x;
        n.fy = n.y;
      }
    });
    fit();
  }, [fit]);

  useEffect(() => {
    if (graphData.nodes.length === 0) return undefined;
    const t = requestAnimationFrame(() => fit());
    return () => cancelAnimationFrame(t);
  }, [graphData, graphW, graphH, fit]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg || graphData.nodes.length === 0) return;
    const n = graphData.nodes.length;
    const charge = fg.d3Force?.('charge');
    if (charge && typeof charge.strength === 'function') {
      const s = -90 - Math.min(220, Math.sqrt(n) * 12);
      charge.strength(s);
    }
    const linkF = fg.d3Force?.('link');
    if (linkF && typeof linkF.distance === 'function') {
      linkF.distance(n > 120 ? 48 : 56);
    }
  }, [graphData]);

  const focusNode = useCallback((node) => {
    const fg = fgRef.current;
    if (!fg || node.x == null || node.y == null) return;
    const cur = typeof fg.zoom === 'function' ? fg.zoom() : 1;
    const k = Math.min(3.8, Math.max(1.2, (cur || 1) * 1.35));
    fg.centerAt(node.x, node.y, 380);
    fg.zoom(k, 380);
  }, []);

  const nodeCanvasObject = useCallback(
    (node, ctx, globalScale) => {
      const r = node.__r ?? NODE_RADIUS;
      const { x, y } = node;
      if (x == null || y == null) return;

      const selected = selectedNodeId === node.id;

      if (selected) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(x, y, r + 5 / Math.max(0.5, globalScale), 0, 2 * Math.PI, false);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.95)';
        ctx.lineWidth = Math.max(2, 2.4 / globalScale);
        ctx.stroke();
        ctx.restore();
      }

      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = node.stroke || 'rgba(15, 23, 42, 0.65)';
      ctx.lineWidth = Math.max(1, 1.15 / globalScale);
      ctx.stroke();
      ctx.restore();
    },
    [selectedNodeId]
  );

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const r = (node.__r ?? NODE_RADIUS) + 5;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
    ctx.fill();
  }, []);

  const linkColorFn = useCallback(
    (l) => {
      if (selectedLinkId && l.id === selectedLinkId) return '#e2e8f0';
      if (selectedNodeId && linkTouchesNodeId(l, selectedNodeId)) return '#bae6fd';
      return l.color;
    },
    [selectedLinkId, selectedNodeId]
  );

  const linkWidthFn = useCallback(
    (l) => {
      if (selectedLinkId && l.id === selectedLinkId) return 2.8;
      if (selectedNodeId && linkTouchesNodeId(l, selectedNodeId)) return 2;
      return 1.1;
    },
    [selectedLinkId, selectedNodeId]
  );

  if (graphData.nodes.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      {(cappedNodes || cappedEdges) && (
        <p className="text-[11px] text-muted-foreground">
          {cappedNodes ? `First ${MAX_NODES} of ${totalNodes} nodes. ` : ''}
          {cappedEdges ? `First ${MAX_EDGES} of ${totalEdges} edges.` : ''}
        </p>
      )}
      <div
        ref={surfaceRef}
        className="relative h-[min(620px,calc(100vh-14rem))] min-h-[420px] w-full min-w-0 overflow-hidden rounded-xl border border-slate-700/50 bg-[#0c0f14]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, rgba(71, 85, 105, 0.22) 1px, transparent 0)',
          backgroundSize: '24px 24px',
        }}
      >
        <div className="absolute inset-0 min-h-0 min-w-0 cursor-grab active:cursor-grabbing">
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            backgroundColor="rgba(0,0,0,0)"
            width={graphW}
            height={graphH}
            showNavInfo={false}
            nodeRelSize={4}
            nodeVal={1}
            nodeLabel={(n) => n.label || n.id}
            linkLabel={(l) => l.predicate || ''}
            nodeCanvasObjectMode={() => 'replace'}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={nodePointerAreaPaint}
            linkColor={linkColorFn}
            linkWidth={linkWidthFn}
            linkCurvature={0}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkDirectionalArrowColor={linkColorFn}
            d3AlphaDecay={0.045}
            d3VelocityDecay={0.55}
            d3AlphaMin={0.001}
            warmupTicks={Math.min(120, 64 + Math.floor(graphData.nodes.length / 8))}
            cooldownTicks={280}
            cooldownTime={8000}
            onEngineStop={handleEngineStop}
            onNodeClick={(node) => {
              onSelectNode?.(node.id);
              focusNode(node);
            }}
            onLinkClick={(link) => {
              onSelectLink?.(link.id);
            }}
            onBackgroundClick={() => onClearSelection?.()}
            onNodeHover={(node) => {
              const el = surfaceRef.current;
              if (el) el.style.cursor = node ? 'pointer' : 'grab';
            }}
            onLinkHover={(link) => {
              const el = surfaceRef.current;
              if (el) el.style.cursor = link ? 'pointer' : 'grab';
            }}
            onNodeDragEnd={(node) => {
              if (node.x != null && node.y != null) {
                node.fx = node.x;
                node.fy = node.y;
              }
            }}
          />
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground/70">
        Click node or edge · Esc to clear · hover for names
      </p>
    </div>
  );
}
