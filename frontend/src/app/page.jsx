import { LandingNav } from '@/components/landing/LandingNav';
import { LandingHero } from '@/components/landing/LandingHero';
import { LandingMemoryLoop } from '@/components/landing/LandingMemoryLoop';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <LandingNav />
      <main>
        <LandingHero />
        <LandingMemoryLoop />
      </main>
    </div>
  );
}
