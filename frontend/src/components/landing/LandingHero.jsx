'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';
import { AnimatedResearchCard } from './AnimatedResearchCard';
import { FeatureCardStack } from './FeatureCardStack';

export function LandingHero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 lg:pt-40 lg:pb-28">
      <div
        className="pointer-events-none absolute -top-20 -right-20 h-[800px] w-[900px] opacity-25"
        style={{
          background: 'radial-gradient(ellipse at center, oklch(0.75 0.18 65), transparent 45%)',
          filter: 'blur(56px)',
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.1]"
        style={{
          backgroundImage:
            'linear-gradient(oklch(0.6 0.16 55 / 0.45) 1px, transparent 1px), linear-gradient(90deg, oklch(0.6 0.16 55 / 0.45) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />

      <div className="relative mx-auto max-w-[1320px] px-6 lg:px-10">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,min(100%,480px))] lg:gap-10 xl:gap-16">
          <div className="max-w-2xl animate-fade-up">
            <div className="mb-8 inline-flex items-center gap-2.5 rounded-full border border-border bg-surface-1 px-3.5 py-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-success" />
              <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Literature · memory · teamwork
              </span>
            </div>

            <h1 className="font-display text-[clamp(2.5rem,5.5vw,4.25rem)] leading-[1.06] tracking-tight text-foreground">
              Research driven by{' '}
              <span className="relative">
                <span className="relative z-10">evidence</span>
                <span
                  className="absolute bottom-1 left-0 right-0 z-0 h-3 rounded-sm bg-amber-200/70"
                  aria-hidden
                />
              </span>
            </h1>

            <p className="mt-7 max-w-xl text-[17px] leading-relaxed text-muted-foreground">
              Gather papers and references from the open web, keep everything tied to your workspace, get a
              first-pass synthesis, then keep chatting with a team of assistants over the same material.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Button
                size="lg"
                className="gap-2 font-semibold transition-transform duration-200 hover:-translate-y-0.5 hover:skew-x-[-1deg] active:translate-y-0"
                asChild
              >
                <Link href="/research">
                  Start a session
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>

          <div className="relative mx-auto w-full lg:mx-0 animate-fade-up" style={{ animationDelay: '0.15s' }}>
            <AnimatedResearchCard />
          </div>
        </div>

        <div className="mt-20 stagger-fade-in">
          <p className="mb-8 text-center font-mono text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Everything in one workflow
          </p>
          <FeatureCardStack />
        </div>
      </div>
    </section>
  );
}
