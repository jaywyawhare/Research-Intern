import './globals.css';

export const metadata = {
  title: 'AI Researcher',
  description: 'Literature-backed research workspaces, synthesis, and collaborative AI assistance',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
