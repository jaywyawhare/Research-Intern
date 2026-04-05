import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function backendUrl() {
  const u = process.env.RESEARCH_API_URL || 'http://127.0.0.1:8000';
  return u.replace(/\/$/, '');
}

function devAllowedOriginHosts() {
  const extra = process.env.NEXT_DEV_EXTRA_ORIGIN_HOSTS;
  const more = extra
    ? extra.split(',').map((s) => s.trim()).filter(Boolean)
    : [];
  return ['127.0.0.1', ...more];
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '..'),
  serverExternalPackages: ['tailwind-merge'],
  allowedDevOrigins: devAllowedOriginHosts(),
  async rewrites() {
    const b = backendUrl();
    return [
      { source: '/health', destination: `${b}/health` },
      { source: '/v1/:path*', destination: `${b}/v1/:path*` },
      { source: '/docs', destination: `${b}/docs` },
      { source: '/openapi.json', destination: `${b}/openapi.json` },
      { source: '/redoc', destination: `${b}/redoc` },
    ];
  },
};

export default nextConfig;
