'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const PHASES = [
  {
    verbs: ['Initializing', 'Parsing topic', 'Scoping query'],
    context:
      'Breaking down your research topic into structured search terms and identifying key concepts for literature retrieval.',
  },
  {
    verbs: ['Querying arXiv', 'Fetching preprints', 'Scanning abstracts'],
    context:
      'Pulling the most recent papers from arXiv — up to 30 results sorted by relevance and recency. Abstracts collected for analysis.',
  },
  {
    verbs: ['Enriching sources', 'Consulting Crossref', 'Checking Wikipedia'],
    context:
      'Cross-referencing with Crossref citations, Semantic Scholar, and Wikipedia to fill in background context and verify key claims.',
  },
  {
    verbs: ['Storing to memory', 'Indexing knowledge', 'Linking context'],
    context:
      'Uploading abstracts and summaries to your workspace memory so future turns can recall overlapping work automatically.',
  },
  {
    verbs: ['Comparing abstracts', 'Detecting conflicts', 'Mapping gaps'],
    context:
      'Running structured conflict analysis — surfacing contradictions, robust agreements, open questions, and under-explored angles.',
  },
  {
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
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.2 }}
        className="inline-block font-mono text-xs font-medium text-primary"
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

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: active ? 1 : 0, x: active ? 0 : 40 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26 }}
      className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card/80 backdrop-blur-sm"
      aria-live="polite"
    >
      <div className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
          </span>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Research in progress
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-0">
        <AnimatePresence>
          {visiblePhases.map((phaseIdx, i) => {
            const phase = PHASES[phaseIdx];
            const isLast = phaseIdx === currentPhase;
            return (
              <motion.div
                key={phaseIdx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
              >
                <div className="flex items-center gap-2 py-2">
                  {isLast ? (
                    <VerbCycler verbs={phase.verbs} />
                  ) : (
                    <span className="font-mono text-xs font-medium text-muted-foreground line-through opacity-50">
                      {phase.verbs[phase.verbs.length - 1]}
                    </span>
                  )}
                </div>
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5, duration: 0.4 }}
                  className="text-xs leading-relaxed text-muted-foreground pb-3"
                >
                  {phase.context}
                </motion.p>
                {i < visiblePhases.length - 1 && <div className="mb-3 h-px w-full bg-border/60" />}
              </motion.div>
            );
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </motion.div>
  );
}
