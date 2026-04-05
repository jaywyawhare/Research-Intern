import { LandingNav } from '@/components/landing/LandingNav';

export default function ResearchLayout({ children }) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <LandingNav />
      <div className="pt-14 flex-1">{children}</div>
      {/* HydraDB attribution footer */}
      <footer
        className="border-t px-6 py-4 flex items-center justify-center gap-3"
        style={{ borderColor: 'var(--border)' }}
      >
        {/* HydraDB wave mark */}
        <svg width="14" height="10" viewBox="0 0 14 10" fill="none" style={{ color: 'var(--primary)', opacity: 0.6 }}>
          <path d="M1 8.5C2.5 5 4 3 7 3C10 3 11.5 5 13 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          <path d="M3 8.5C4 6.5 5 5.5 7 5.5C9 5.5 10 6.5 11 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.55"/>
          <circle cx="7" cy="1.5" r="1" fill="currentColor" opacity="0.75"/>
        </svg>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.10em]"
          style={{ color: 'var(--muted-foreground)' }}
        >
          Stateful memory powered by{' '}
          <a
            href="https://docs.hydradb.com"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-opacity hover:opacity-100"
            style={{ color: 'var(--primary)', opacity: 0.85 }}
          >
            HydraDB
          </a>
        </span>
      </footer>
    </div>
  );
}
