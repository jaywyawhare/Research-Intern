import { LandingNav } from '@/components/landing/LandingNav';

export default function ResearchLayout({ children }) {
  return (
    <div className="min-h-screen bg-background">
      <LandingNav />
      <div className="pt-14">{children}</div>
    </div>
  );
}
