'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';

export function LandingNav() {
  return (
    <header className="fixed top-0 z-50 w-full">
      {/* Layered warm glass backdrop */}
      <div
        className="absolute inset-0 border-b"
        style={{
          background: 'rgba(250, 248, 243, 0.82)',
          backdropFilter: 'blur(20px) saturate(160%)',
          WebkitBackdropFilter: 'blur(20px) saturate(160%)',
          borderColor: 'var(--border)',
          boxShadow: '0 1px 0 rgba(255,255,255,0.65), 0 1px 10px rgba(28,16,8,0.04)',
        }}
      />

      <nav className="relative mx-auto max-w-[1400px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">

          {/* Wordmark */}
          <Link
            href="/"
            className="group flex items-center gap-2.5 transition-all duration-200 hover:opacity-80"
          >
            {/* Book-spine logo mark */}
            <div
              className="flex h-7 w-7 items-center justify-center rounded-md overflow-hidden shrink-0"
              style={{
                background: 'linear-gradient(145deg, var(--primary) 0%, color-mix(in srgb, var(--primary) 75%, #b45309) 100%)',
                boxShadow: '0 1px 4px rgba(124,45,18,0.30), inset 0 1px 0 rgba(255,255,255,0.14)',
              }}
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none" style={{ color: 'var(--primary-foreground)' }}>
                <path d="M7.5 2C5.8 2 4.2 2.6 3 3.7v8.2c1.2-1.1 2.8-1.7 4.5-1.7s3.3.6 4.5 1.7V3.7C10.8 2.6 9.2 2 7.5 2Z"
                  stroke="currentColor" strokeWidth="1.15" strokeLinejoin="round" />
                <line x1="7.5" y1="2" x2="7.5" y2="11.9" stroke="currentColor" strokeWidth="1.15" />
              </svg>
            </div>

            {/* Logo text — "AI" normal, "Researcher" italic */}
            <div className="flex items-baseline">
              <span
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '15px',
                  color: 'var(--foreground)',
                  letterSpacing: '-0.02em',
                }}
              >
                AI
              </span>
              <em
                style={{
                  fontFamily: 'var(--font-display)',
                  fontStyle: 'italic',
                  fontSize: '15px',
                  color: 'var(--primary)',
                  letterSpacing: '-0.02em',
                }}
              >
                Researcher
              </em>
            </div>
          </Link>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              className="h-8 rounded-md px-3.5 text-[13px] font-semibold transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
              style={{
                boxShadow: '0 1px 4px rgba(124,45,18,0.24), inset 0 1px 0 rgba(255,255,255,0.12)',
              }}
              asChild
            >
              <Link href="/research">Workspace</Link>
            </Button>
          </div>
        </div>
      </nav>
    </header>
  );
}
