'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ArrowRight, Clock, FileText, Zap } from 'lucide-react';
import Link from 'next/link';

const papers = [
  {
    src: '/research-summary.png',
    label: 'Transformer Architectures',
  },
  {
    src: '/hero.webp',
    label: 'Neural Scaling Laws',
  },
  {
    src: '/image.png',
    label: 'Retrieval-Augmented Generation',
  },
];

const stats = [
  { icon: <Clock className="h-4 w-4" />, label: '~40 s' },
  { icon: <FileText className="h-4 w-4" />, label: '30 papers' },
  { icon: <Zap className="h-4 w-4" />, label: 'Live synthesis' },
];

export function AnimatedResearchCard() {
  const [hovered, setHovered] = useState(false);

  return (
    <Link
      href="/research"
      className="group relative block w-full max-w-sm cursor-pointer rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-sm transition-all duration-300 ease-in-out hover:-translate-y-1 hover:shadow-lg lg:max-w-md"
      aria-label="Start a research session"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="mb-6 flex items-center justify-between">
        <h2 className="font-display text-2xl tracking-tight text-foreground">
          Deep research,
          <br />
          on demand
        </h2>
        <ArrowRight className="h-5 w-5 transition-transform duration-300 ease-in-out group-hover:translate-x-1 text-primary" />
      </div>

      <div className="relative mb-6 h-32">
        {papers.map((paper, index) => (
          <div
            key={paper.src}
            className="absolute h-full w-[42%] overflow-hidden rounded-xl border-2 border-background shadow-md"
            style={{
              transform: hovered
                ? `translateX(${index * 80}px) rotate(${index * 5 - 5}deg)`
                : `translateX(${index * 30}px)`,
              transition: 'transform 0.35s cubic-bezier(0.22,1,0.36,1)',
              zIndex: papers.length - index,
            }}
          >
            <Image
              src={paper.src}
              alt={paper.label}
              fill
              className="object-cover"
              sizes="160px"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
            <span className="absolute bottom-1.5 left-2 text-[9px] font-semibold text-white/90 leading-tight">
              {paper.label}
            </span>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-4 text-sm text-muted-foreground">
        {stats.map((stat, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {stat.icon}
            <span>{stat.label}</span>
          </div>
        ))}
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">
        Submit a topic and get structured conflict analysis, testable hypotheses, and source-backed insights
        — in under a minute.
      </p>
    </Link>
  );
}
