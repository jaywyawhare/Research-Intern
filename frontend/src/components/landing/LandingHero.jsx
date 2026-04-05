'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';
import { AnimatedResearchCard } from './AnimatedResearchCard';
import { FeatureCardStack } from './FeatureCardStack';

export function LandingHero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-24 lg:pt-44 lg:pb-32">

      {/* ── Atmospheric background layers ── */}

      {/* Primary warm amber glow — top-right */}
      <div
        className="pointer-events-none absolute -top-40 -right-40 h-[960px] w-[960px]"
        style={{
          background: 'radial-gradient(ellipse at 42% 40%, oklch(0.76 0.20 65), oklch(0.88 0.10 70) 38%, transparent 62%)',
          filter: 'blur(72px)',
          opacity: 0.30,
        }}
        aria-hidden
      />

      {/* Deep sepia glow — bottom-left */}
      <div
        className="pointer-events-none absolute -bottom-28 -left-28 h-[680px] w-[760px]"
        style={{
          background: 'radial-gradient(ellipse at 48% 58%, oklch(0.70 0.16 58), transparent 55%)',
          filter: 'blur(88px)',
          opacity: 0.16,
        }}
        aria-hidden
      />

      {/* Fine grid — fades toward edges */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(oklch(0.50 0.14 55 / 0.38) 1px, transparent 1px), linear-gradient(90deg, oklch(0.50 0.14 55 / 0.38) 1px, transparent 1px)',
          backgroundSize: '42px 42px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 65% 38%, black 10%, transparent 76%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 65% 38%, black 10%, transparent 76%)',
          opacity: 0.10,
        }}
        aria-hidden
      />

      <div className="relative mx-auto max-w-[1320px] px-6 lg:px-10">
        <div className="grid items-center gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,min(100%,480px))] lg:gap-12 xl:gap-20">

          {/* ── Copy column ── */}
          <div className="max-w-2xl animate-fade-up">

            {/* Status badge */}
            <div
              className="mb-9 inline-flex items-center gap-2.5 rounded-full px-4 py-1.5"
              style={{
                background: 'var(--surface-1)',
                border: '1px solid var(--border)',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.65)',
              }}
            >
              <span
                className="flex h-1.5 w-1.5 rounded-full"
                style={{ background: 'var(--success)' }}
              />
              <span
                className="font-mono text-[10.5px] font-medium uppercase tracking-[0.10em]"
                style={{ color: 'var(--muted-foreground)' }}
              >
                Literature · Memory · Teamwork
              </span>
            </div>

            {/* Headline — "evidence" in italic display serif */}
            <h1
              className="font-display leading-[1.05] tracking-tight"
              style={{
                fontSize: 'clamp(2.6rem, 5.8vw, 4.5rem)',
                color: 'var(--foreground)',
              }}
            >
              Research driven{' '}
              <br className="hidden sm:block" />
              by{' '}
              <span className="relative inline-block">
                <em
                  style={{
                    fontStyle: 'italic',
                    color: 'var(--primary)',
                  }}
                >
                  evidence
                </em>
                {/* Warm gradient underline */}
                <span
                  className="absolute -bottom-1 left-0 right-0 rounded-full"
                  style={{
                    height: '3px',
                    background: 'linear-gradient(90deg, var(--primary) 0%, oklch(0.72 0.18 62) 100%)',
                    opacity: 0.40,
                  }}
                  aria-hidden
                />
              </span>
            </h1>

            {/* Ornamental rule */}
            <div className="mt-8 flex items-center gap-3">
              <div
                className="h-px w-16 rounded-full"
                style={{ background: 'var(--border)' }}
              />
              <div className="flex items-center gap-1.5">
                <span className="inline-block h-[5px] w-[5px] rounded-full" style={{ background: 'var(--primary)', opacity: 0.50 }} />
                <span className="inline-block h-[5px] w-[5px] rounded-full" style={{ background: 'var(--primary)', opacity: 0.28 }} />
                <span className="inline-block h-[5px] w-[5px] rounded-full" style={{ background: 'var(--primary)', opacity: 0.12 }} />
              </div>
            </div>

            {/* Body */}
            <p
              className="mt-7 max-w-[520px] text-[17px] leading-relaxed"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Gather papers and references from the open web, keep everything tied
              to your workspace, get a first-pass synthesis, then keep chatting with
              a team of assistants over the same material.
            </p>

            {/* CTA */}
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Button
                size="lg"
                className="gap-2 font-semibold transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
                style={{
                  boxShadow: '0 2px 8px rgba(124,45,18,0.26), inset 0 1px 0 rgba(255,255,255,0.12)',
                }}
                asChild
              >
                <Link href="/research">
                  Start a session
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>

          {/* ── Card column ── */}
          <div
            className="relative mx-auto w-full lg:mx-0 animate-fade-up"
            style={{ animationDelay: '0.18s' }}
          >
            <AnimatedResearchCard />
          </div>
        </div>

        {/* ── Feature strip ── */}
        <div className="mt-24 stagger-fade-in">
          <div className="mb-10 flex items-center gap-5">
            <div
              className="h-px flex-1"
              style={{ background: 'var(--border)' }}
            />
            <p
              className="shrink-0 font-mono text-[10.5px] font-medium uppercase tracking-[0.12em]"
              style={{ color: 'var(--muted-foreground)' }}
            >
              Everything in one workflow
            </p>
            <div
              className="h-px flex-1"
              style={{ background: 'var(--border)' }}
            />
          </div>
          <FeatureCardStack />
        </div>
      </div>
    </section>
  );
}
