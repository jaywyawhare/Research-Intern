'use client';

import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';

import styles from './MarkdownContent.module.css';

function normalizeLlmHtml(s) {
  return s.replace(/<br\s*\/?>/gi, '\n');
}

export function MarkdownContent({ children, className = '' }) {
  const raw = typeof children === 'string' ? children.trim() : '';
  if (!raw) return null;
  const s = normalizeLlmHtml(raw);
  return (
    <div className={`${styles.md} ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
      >
        {s}
      </ReactMarkdown>
    </div>
  );
}
