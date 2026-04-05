#!/usr/bin/env bash
# FastAPI on 127.0.0.1:8000; Next standalone on $PORT (Render injects PORT).
set -euo pipefail

export RESEARCH_API_URL="${RESEARCH_API_URL:-http://127.0.0.1:8000}"
export BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export PORT="${PORT:-3000}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"

NODE_PID=""
_CLEANED=0

cd /app
uvicorn backend.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
UV_PID=$!

shutdown() {
  [[ "${_CLEANED}" -eq 1 ]] && return
  _CLEANED=1
  if [[ -n "${NODE_PID}" ]] && kill -0 "${NODE_PID}" 2>/dev/null; then
    kill -TERM "${NODE_PID}" 2>/dev/null || true
    wait "${NODE_PID}" 2>/dev/null || true
  fi
  if kill -0 "${UV_PID}" 2>/dev/null; then
    kill -TERM "${UV_PID}" 2>/dev/null || true
    wait "${UV_PID}" 2>/dev/null || true
  fi
}
trap shutdown EXIT
trap 'shutdown; exit 130' INT
trap 'shutdown; exit 143' TERM

HEALTH_OK=""
for _ in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null; then
    HEALTH_OK=1
    break
  fi
  sleep 1
done
if [[ -z "${HEALTH_OK}" ]]; then
  echo "entrypoint: backend did not become healthy on 127.0.0.1:${BACKEND_PORT}" >&2
  exit 1
fi

cd /app/frontend
node server.js &
NODE_PID=$!
wait "${NODE_PID}"
