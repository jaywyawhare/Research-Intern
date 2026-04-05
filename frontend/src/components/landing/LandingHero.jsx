'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Bot, Database, LibraryBig } from 'lucide-react';

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
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,min(100%,520px))] lg:gap-10 xl:gap-14">
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
              <Button size="lg" className="gap-2 font-semibold" asChild>
                <Link href="/research">
                  Start a session
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md lg:mx-0 lg:max-w-none">
            <div
              className="pointer-events-none absolute -inset-6 -z-10 rounded-[3rem] opacity-80 blur-3xl sm:-inset-8"
              style={{
                background:
                  'radial-gradient(ellipse 72% 65% at 58% 42%, oklch(0.82 0.1 62 / 0.45), transparent 68%)',
              }}
              aria-hidden
            />
            <div
              className="relative aspect-[4/3] overflow-hidden rounded-[1.75rem] sm:rounded-[2rem]
                [mask-image:radial-gradient(ellipse_90%_88%_at_56%_48%,#000_52%,transparent_100%)]
                [-webkit-mask-image:radial-gradient(ellipse_90%_88%_at_56%_48%,#000_52%,transparent_100%)]"
            >
              <Image
                src="/hero.webp"
                alt="AI Researcher hero"
                fill
                className="scale-[1.04] object-cover object-center"
                sizes="(max-width: 1024px) 100vw, 520px"
                priority
              />
              <div
                className="pointer-events-none absolute inset-0 bg-gradient-to-l from-transparent via-transparent to-background/55"
                aria-hidden
              />
              <div
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/35 via-transparent to-background/40"
                aria-hidden
              />
            </div>
          </div>
        </div>

        <ul className="mt-14 grid gap-4 sm:grid-cols-3 stagger-fade-in">
          <li className="flex gap-4 rounded-lg border border-border bg-card/80 p-4">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
              aria-hidden
            >
              <LibraryBig className="h-5 w-5" strokeWidth={2} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">Rich sources</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                Preprints, encyclopedia entries, and citation data, pulled together for your topic
              </p>
            </div>
          </li>
          <li className="flex gap-4 rounded-lg border border-border bg-card/80 p-4">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
              aria-hidden
            >
              <Database className="h-5 w-5" strokeWidth={2} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">Saved workspaces</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                Your topic and sources stay put; the UI updates as the run progresses
              </p>
            </div>
          </li>
          <li className="flex gap-4 rounded-lg border border-border bg-card/80 p-4">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
              aria-hidden
            >
              <Bot className="h-5 w-5" strokeWidth={2} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">Specialist assistants</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                Different experts weigh in on each turn, with an optional quality pass when enabled
              </p>
            </div>
          </li>
        </ul>
      </div>
    </section>
  );
}
