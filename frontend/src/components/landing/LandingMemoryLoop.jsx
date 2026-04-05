'use client';

import { motion } from 'framer-motion';

const steps = [
  {
    num: '01',
    title: 'Gather',
    body: 'Papers, preprints, and citations are pulled from arXiv, Crossref, Wikipedia, and Semantic Scholar for your topic.',
    accent: 'var(--primary)',
  },
  {
    num: '02',
    title: 'Remember',
    body: 'Every source is ingested into your HydraDB knowledge base — entities extracted, relationships mapped, context indexed.',
    accent: 'var(--primary)',
  },
  {
    num: '03',
    title: 'Compound',
    body: 'Future sessions recall from everything before. The more you research, the richer the context — the agent gets smarter.',
    accent: 'var(--primary)',
  },
];

function Arrow() {
  return (
    <div
      className="hidden lg:flex items-center justify-center shrink-0"
      style={{ width: 60 }}
      aria-hidden
    >
      <svg width="40" height="12" viewBox="0 0 40 12" fill="none">
        {/* Dashed line */}
        <line
          x1="0" y1="6" x2="32" y2="6"
          stroke="var(--border)"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
        {/* Arrowhead */}
        <path
          d="M30 2L38 6L30 10"
          stroke="var(--primary)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
          opacity="0.6"
        />
      </svg>
    </div>
  );
}

export function LandingMemoryLoop() {
  return (
    <section
      className="relative overflow-hidden border-t border-b"
      style={{ borderColor: 'var(--border)' }}
    >
      {/* Background */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(180deg, var(--surface-1) 0%, var(--background) 100%)' }}
        aria-hidden
      />

      <div className="relative mx-auto max-w-[1320px] px-6 py-20 lg:px-10 lg:py-24">

        {/* Section header */}
        <div className="mb-14 text-center">
          <div
            className="mb-5 inline-flex items-center gap-2 rounded-full px-4 py-1.5"
            style={{
              background: 'var(--card)',
              border: '1px solid var(--border)',
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.65)',
            }}
          >
            {/* HydraDB icon — simplified wave mark */}
            <svg width="14" height="10" viewBox="0 0 14 10" fill="none" style={{ color: 'var(--primary)' }}>
              <path d="M1 8.5C2.5 5 4 3 7 3C10 3 11.5 5 13 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              <path d="M3 8.5C4 6.5 5 5.5 7 5.5C9 5.5 10 6.5 11 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.6"/>
              <circle cx="7" cy="1.5" r="1" fill="currentColor" opacity="0.8"/>
            </svg>
            <span
              className="font-mono text-[10.5px] font-medium uppercase tracking-[0.10em]"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Powered by HydraDB
            </span>
          </div>

          <h2
            className="font-display leading-tight tracking-tight"
            style={{ fontSize: 'clamp(1.75rem, 3.5vw, 2.5rem)', color: 'var(--foreground)' }}
          >
            Memory that{' '}
            <em style={{ fontStyle: 'italic', color: 'var(--primary)' }}>compounds</em>
          </h2>
          <p
            className="mt-4 mx-auto max-w-lg text-[15px] leading-relaxed"
            style={{ color: 'var(--muted-foreground)' }}
          >
            Unlike one-shot summarizers, each research session enriches a persistent knowledge base.
            The agent recalls everything it has ever read — across every session.
          </p>
        </div>

        {/* 3-step diagram */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-start gap-4 lg:gap-0">
          {steps.map((step, i) => (
            <div key={step.num} className="flex flex-col lg:flex-row items-stretch flex-1 min-w-0">
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.5, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
                className="flex-1 rounded-xl border p-6"
                style={{
                  background: 'var(--card)',
                  borderColor: 'var(--border)',
                  boxShadow: 'var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.75)',
                }}
              >
                {/* Step number */}
                <div className="mb-4 flex items-center gap-3">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-lg font-mono text-[11px] font-bold shrink-0"
                    style={{
                      background: 'var(--primary)',
                      color: 'var(--primary-foreground)',
                      boxShadow: '0 1px 4px rgba(124,45,18,0.28)',
                    }}
                  >
                    {step.num}
                  </div>
                  <h3
                    className="font-display text-lg tracking-tight"
                    style={{ color: 'var(--foreground)' }}
                  >
                    {step.title}
                  </h3>
                </div>
                <p
                  className="text-[13.5px] leading-relaxed"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {step.body}
                </p>
              </motion.div>

              {/* Arrow between steps */}
              {i < steps.length - 1 && (
                <div className="flex items-center justify-center py-2 lg:py-0 lg:px-2">
                  {/* Mobile: vertical arrow */}
                  <div className="lg:hidden flex flex-col items-center gap-1" style={{ color: 'var(--border)' }}>
                    <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
                    <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                      <path d="M1 1L5 6L9 1" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.5"/>
                    </svg>
                  </div>
                  {/* Desktop: horizontal arrow */}
                  <Arrow />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Bottom callout */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-40px' }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="mt-10 rounded-xl border p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4"
          style={{
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--surface-1) 100%)',
            borderColor: 'var(--primary)',
            borderWidth: '1px',
            borderLeftWidth: '3px',
          }}
        >
          <div className="flex-1 min-w-0">
            <p
              className="font-mono text-[10.5px] font-medium uppercase tracking-[0.10em] mb-1"
              style={{ color: 'var(--primary)', opacity: 0.8 }}
            >
              Stateful AI agent
            </p>
            <p
              className="text-[13.5px] leading-relaxed"
              style={{ color: 'var(--foreground)', opacity: 0.85 }}
            >
              HydraDB stores ingested papers as <strong>knowledge records</strong> tagged with session metadata.
              When a new session starts, <strong>graph-aware recall</strong> surfaces the most relevant prior context —
              entities, paths, and relationships — automatically.
            </p>
          </div>
          <a
            href="https://docs.hydradb.com"
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 font-mono text-[11px] font-medium transition-opacity hover:opacity-70"
            style={{ color: 'var(--primary)' }}
          >
            docs.hydradb.com ↗
          </a>
        </motion.div>
      </div>
    </section>
  );
}
