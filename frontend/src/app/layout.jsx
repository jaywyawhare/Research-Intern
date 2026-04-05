import './globals.css';
import { ToastProvider } from '@/components/Toast';

export const metadata = {
  title: 'AI Researcher',
  description: 'Literature-backed research workspaces, synthesis, and collaborative AI assistance',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
