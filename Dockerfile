# Single Web Service on Render: Next.js (standalone) + FastAPI (uvicorn).
# Build: docker build -t ai-researcher .
# Run:  docker run --rm -p 8080:8080 -e PORT=8080 ai-researcher
# Set secrets (e.g. OPENAI_API_KEY, MONGODB_URI) via Render Environment or -e.

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
# Rewrites embed this URL at build time; runtime uses the same loopback backend.
ARG RESEARCH_API_URL=http://127.0.0.1:8000
ENV RESEARCH_API_URL=${RESEARCH_API_URL}
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

# Next standalone runs `node server.js`; the Python image does not include Node.
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY core ./core

COPY --from=frontend-build /app/frontend/.next/standalone/frontend ./frontend
COPY --from=frontend-build /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-build /app/frontend/public ./frontend/public

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV BACKEND_HOST=127.0.0.1
ENV BACKEND_PORT=8000
ENV RESEARCH_API_URL=http://127.0.0.1:8000

EXPOSE 3000
ENTRYPOINT ["/entrypoint.sh"]
