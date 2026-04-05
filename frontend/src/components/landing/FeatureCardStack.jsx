'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LibraryBig, Database, Bot, GitBranch, Lightbulb } from 'lucide-react';

const features = [
  {
    id: 1,
    icon: LibraryBig,
    title: 'Rich sources',
    description:
      'Preprints, encyclopedia entries, and citation data pulled together for your topic from arXiv, Wikipedia, Crossref, and Semantic Scholar.',
  },
  {
    id: 2,
    icon: Database,
    title: 'Saved workspaces',
    description:
      'Your topic and sources stay put; the UI updates as the run progresses. Resume any session and pick up exactly where you left off.',
  },
  {
    id: 3,
    icon: Bot,
    title: 'Specialist assistants',
    description:
      'Different experts weigh in on each turn, with an optional quality pass when enabled. The right agent is routed automatically.',
  },
  {
    id: 4,
    icon: GitBranch,
    title: 'Conflict detection',
    description:
      "Surfaces contradictions and robust agreements across your paper corpus — so you know exactly where the field agrees and where it doesn't.",
  },
  {
    id: 5,
    icon: Lightbulb,
    title: 'Hypothesis engine',
    description:
      'Generates testable hypotheses and next-step ideas grounded in your collected sources, not hallucinated from thin air.',
  },
];

function signedOffset(i, active, len) {
  const raw = i - active;
  const alt = raw > 0 ? raw - len : raw + len;
  return Math.abs(alt) < Math.abs(raw) ? alt : raw;
}

export function FeatureCardStack() {
  const [active, setActive] = useState(0);
  const len = features.length;

  const next = useCallback(() => setActive((a) => (a + 1) % len), [len]);
  const prev = useCallback(() => setActive((a) => (a - 1 + len) % len), [len]);

  useEffect(() => {
    const id = setInterval(next, 3200);
    return () => clearInterval(id);
  }, [next]);

  const maxOffset = 2;
  const cardWidth = 340;
  const cardSpacing = Math.round(cardWidth * 0.52);
  const spreadDeg = 40;
  const stepDeg = spreadDeg / maxOffset;

  return (
    <div className="w-full">
      <div
        className="relative w-full"
        style={{ height: 260 }}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') prev();
          if (e.key === 'ArrowRight') next();
        }}
      >
        <div
          className="pointer-events-none absolute inset-x-0 top-4 mx-auto h-40 w-[60%] rounded-full opacity-50 blur-3xl"
          style={{
            background: 'radial-gradient(ellipse, oklch(0.75 0.18 65 / 0.3), transparent 70%)',
          }}
          aria-hidden
        />

        <div
          className="absolute inset-0 flex items-end justify-center"
          style={{ perspective: '1100px' }}
        >
          <AnimatePresence initial={false}>
            {features.map((feat, i) => {
              const off = signedOffset(i, active, len);
              const abs = Math.abs(off);
              if (abs > maxOffset) return null;

              const isActive = off === 0;
              const rotateZ = off * stepDeg;
              const x = off * cardSpacing;
              const y = abs * 8;
              const z = -abs * 120;
              const scale = isActive ? 1.02 : 0.93;
              const lift = isActive ? -18 : 0;
              const rotateX = isActive ? 0 : 10;
              const zIndex = 100 - abs;

              const Icon = feat.icon;

              return (
                <motion.div
                  key={feat.id}
                  className="absolute bottom-0 rounded-2xl border border-border/60 bg-card/60 backdrop-blur-sm shadow-lg overflow-hidden cursor-pointer select-none"
                  style={{
                    width: cardWidth,
                    height: 180,
                    zIndex,
                    transformStyle: 'preserve-3d',
                  }}
                  animate={{
                    opacity: isActive ? 1 : 0.55,
                    x,
                    y: y + lift,
                    rotateZ,
                    rotateX,
                    scale,
                    translateZ: z,
                  }}
                  transition={{ type: 'spring', stiffness: 280, damping: 28 }}
                  onClick={() => setActive(i)}
                >
                  <div className="flex h-full flex-col justify-between p-5">
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Icon className="h-5 w-5" strokeWidth={2} />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">{feat.title}</p>
                        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground line-clamp-3">
                          {feat.description}
                        </p>
                      </div>
                    </div>
                    {isActive && (
                      <motion.div
                        initial={{ opacity: 0, scaleX: 0 }}
                        animate={{ opacity: 1, scaleX: 1 }}
                        className="mt-3 h-0.5 w-full origin-left rounded-full bg-primary/20"
                      />
                    )}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-center gap-2">
        {features.map((_, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => setActive(idx)}
            className={`h-1.5 rounded-full transition-all duration-300 ${
              idx === active ? 'w-5 bg-foreground' : 'w-1.5 bg-foreground/25 hover:bg-foreground/45'
            }`}
            aria-label={`Feature ${idx + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
