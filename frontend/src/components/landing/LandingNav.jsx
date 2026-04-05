'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { BookOpen } from 'lucide-react';

export function LandingNav() {
  return (
    <header className="fixed top-0 z-50 w-full border-b border-border/40 bg-background/70 backdrop-blur-xl">
      <nav className="mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/15 text-primary">
              <BookOpen className="h-4 w-4" strokeWidth={2} />
            </div>
            <div className="flex items-baseline gap-1">
              <span className="font-display text-[15px] text-foreground">AI</span>
              <span className="font-display text-[15px] text-primary">Researcher</span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <Button size="sm" className="h-8 rounded-md px-3.5 text-[13px] font-semibold" asChild>
              <Link href="/research">Workspace</Link>
            </Button>
          </div>
        </div>
      </nav>
    </header>
  );
}
