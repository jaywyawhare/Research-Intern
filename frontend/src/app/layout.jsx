import './globals.css';

export const metadata = {
  title: 'Research Intern',
  description: 'Literature sessions, Hydra memory, multi-agent research',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
