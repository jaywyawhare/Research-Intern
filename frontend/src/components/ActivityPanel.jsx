'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const PHASES = [
  {
    label: 'Initialize',
    verbs: ['Initializing', 'Parsing topic', 'Scoping query'],
    context:
      'Breaking down your research topic into structured search terms and identifying key concepts for literature retrieval.',
  },
  {
    label: 'Fetch papers',
    verbs: ['Querying arXiv', 'Fetching preprints', 'Scanning abstracts'],
    context:
      'Pulling the most recent papers from arXiv — up to 30 results sorted by relevance and recency. Abstracts collected for analysis.',
  },
  {
    label: 'Enrich sources',
    verbs: ['Enriching sources', 'Consulting Crossref', 'Checking Wikipedia'],
    context:
      'Cross-referencing with Crossref citations, Semantic Scholar, and Wikipedia to fill in background context and verify key claims.',
  },
  {
    label: 'Index memory',
    verbs: ['Storing to memory', 'Indexing knowledge', 'Linking context'],
    context:
      'Uploading abstracts and summaries to your workspace memory so future turns can recall overlapping work automatically.',
  },
  {
    label: 'Analyse',
    verbs: ['Comparing abstracts', 'Detecting conflicts', 'Mapping gaps'],
    context:
      'Running structured conflict analysis — surfacing contradictions, robust agreements, open questions, and under-explored angles.',
  },
  {
    label: 'Synthesise',
    verbs: ['Synthesizing', 'Drafting analysis', 'Finalizing report'],
    context:
      'Composing a structured synthesis with hypotheses, next-step ideas, and source citations grounded in the collected evidence.',
  },
];

function VerbCycler({ verbs }) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIdx((i) => (i + 1) % verbs.length), 900);
    return () => clearInterval(id);
  }, [verbs]);

  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={verbs[idx]}
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -5 }}
        transition={{ duration: 0.18 }}
        className="inline-block font-mono text-[11px] font-medium"
        style={{ color: 'var(--primary)' }}
      >
        {verbs[idx]}…
      </motion.span>
    </AnimatePresence>
  );
}

export function ActivityPanel({ active }) {
  const [visiblePhases, setVisiblePhases] = useState([]);
  const [currentPhase, setCurrentPhase] = useState(0);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!active) {
      setVisiblePhases([]);
      setCurrentPhase(0);
      return;
    }

    let phase = 0;
    const show = () => {
      if (phase >= PHASES.length) return;
      setVisiblePhases((prev) => [...prev, phase]);
      setCurrentPhase(phase);
      phase += 1;
      if (phase < PHASES.length) {
        setTimeout(show, 2800 + Math.random() * 800);
      }
    };
    const id = setTimeout(show, 300);
    return () => clearTimeout(id);
  }, [active]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [visiblePhases]);

  const progressPct =
    PHASES.length > 0 ? ((currentPhase + 1) / PHASES.length) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: active ? 1 : 0, x: active ? 0 : 40 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26 }}
      className="flex h-full flex-col overflow-hidden rounded-xl border"
      style={{
        background: 'var(--card)',
        borderColor: 'var(--border)',
        boxShadow: 'var(--shadow-md)',
      }}
      aria-live="polite"
    >
      {/* ── Header ── */}
      <div
        className="shrink-0 border-b px-5 pt-4 pb-4"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface-1)',
        }}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {/* Pulsing status dot */}
            <span className="relative flex h-2 w-2 shrink-0">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
                style={{ background: 'var(--primary)' }}
              />
              <span
                className="relative inline-flex h-2 w-2 rounded-full"
                style={{ background: 'var(--primary)' }}
              />
            </span>
            <p
              className="font-mono text-[10.5px] font-medium uppercase tracking-[0.10em]"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Research in progress
            </p>
          </div>
          {/* Phase count */}
          <span
            className="font-mono text-[10.5px] tabular-nums"
            style={{ color: 'var(--muted-foreground)' }}
          >
            {currentPhase + 1}&thinsp;/&thinsp;{PHASES.length}
          </span>
        </div>

        {/* Progress bar */}
        <div
          className="mt-3 h-[3px] w-full overflow-hidden rounded-full"
          style={{ background: 'var(--surface-3)' }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'var(--primary)' }}
            initial={{ width: '0%' }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.65, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* ── Phase log ── */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <AnimatePresence>
          {visiblePhases.map((phaseIdx, listIdx) => {
            const phase = PHASES[phaseIdx];
            const isActive = phaseIdx === currentPhase;
            const phaseNum = String(phaseIdx + 1).padStart(2, '0');

            return (
              <motion.div
                key={phaseIdx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28 }}
                className="relative flex gap-3.5"
                style={{
                  paddingBottom: listIdx < visiblePhases.length - 1 ? '1.25rem' : '0.5rem',
                }}
              >
                {/* Left track — number bubble + connector line */}
                <div className="flex flex-col items-center shrink-0" style={{ width: 20 }}>
                  {/* Phase badge */}
                  <div
                    className="flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-mono font-bold shrink-0 transition-colors duration-300"
                    style={
                      isActive
                        ? {
                            background: 'var(--primary)',
                            color: 'var(--primary-foreground)',
                          }
                        : {
                            background: 'var(--success)',
                            color: 'var(--success-foreground)',
                          }
                    }
                  >
                    {isActive ? phaseNum : '✓'}
                  </div>
                  {/* Connector line below (except last visible) */}
                  {listIdx < visiblePhases.length - 1 && (
                    <div
                      className="mt-1.5 flex-1 w-px"
                      style={{ background: 'var(--border)', minHeight: '20px' }}
                    />
                  )}
                </div>

                {/* Right content */}
                <div className="min-w-0 flex-1 pt-px">
                  <div className="flex items-center gap-2 mb-1.5 min-h-[18px]">
                    {isActive ? (
                      <VerbCycler verbs={phase.verbs} />
                    ) : (
                      <span
                        className="font-mono text-[11px] font-medium"
                        style={{ color: 'var(--muted-foreground)', opacity: 0.60 }}
                      >
                        {phase.label}
                      </span>
                    )}
                  </div>
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: isActive ? 1 : 0.45 }}
                    transition={{ delay: 0.4, duration: 0.35 }}
                    className="text-[11px] leading-relaxed"
                    style={{ color: 'var(--muted-foreground)' }}
                  >
                    {phase.context}
                  </motion.p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </motion.div>
  );
}
