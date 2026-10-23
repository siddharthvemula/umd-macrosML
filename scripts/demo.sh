#!/usr/bin/env bash
# One-command demo: rebuilds the Docker image, starts the app on :8080 with
# docker-data/ mounted, opens a temporary Cloudflare tunnel, and prints only the
# public https link. Keeps the Mac awake until Control+C, which stops everything.
# Usage: scripts/demo.sh   (menus must already be scraped into docker-data/)

set -euo pipefail

CONTAINER=macros
IMAGE=macros
APP_URL=http://127.0.0.1:8080
HEALTH_TIMEOUT_S=90
TUNNEL_TIMEOUT_S=45

# Run from the repo root so "docker build ." and docker-data/ resolve, wherever it's called from.
cd "$(dirname "$0")/.."

# Build and tunnel output go to log files so the terminal shows only the link.
LOG_DIR=$(mktemp -d)
tunnel_pid=""
caffeinate_pid=""

fail() {
  echo "demo.sh: $1" >&2
  exit 1
}

cleanup() {
  # Clear the trap first so Control+C during cleanup can't run it twice.
  trap - INT TERM EXIT
  [ -n "$tunnel_pid" ] && kill "$tunnel_pid" 2>/dev/null || true
  [ -n "$caffeinate_pid" ] && kill "$caffeinate_pid" 2>/dev/null || true
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

# 1. Stop any old container (rm -f stops it first; no error if there isn't one).
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

# 2. Rebuild the image so the demo runs the latest code.
docker build -t "$IMAGE" . >"$LOG_DIR/build.log" 2>&1 \
  || fail "docker build failed, see $LOG_DIR/build.log"

# 3. Start the app in the background.
docker run -d --name "$CONTAINER" -p 8080:8080 -v "$PWD/docker-data:/data" "$IMAGE" >/dev/null \
  || fail "docker run failed"

# 4. Wait until /api/health answers OK (FastAPI needs a few seconds to start).
for _ in $(seq "$HEALTH_TIMEOUT_S"); do
  curl -fsS "$APP_URL/api/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "$APP_URL/api/health" >/dev/null 2>&1 \
  || fail "app not healthy after ${HEALTH_TIMEOUT_S}s, see: docker logs $CONTAINER"

# 5. Start the quick tunnel. http2 = TCP instead of QUIC/UDP, which some networks block.
cloudflared tunnel --url "$APP_URL" --protocol http2 >"$LOG_DIR/tunnel.log" 2>&1 &
tunnel_pid=$!

# cloudflared prints the random trycloudflare.com URL first and "Registered tunnel
# connection" once traffic can flow; wait for both so the printed link works.
public_url=""
for _ in $(seq "$TUNNEL_TIMEOUT_S"); do
  public_url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/tunnel.log" | head -1 || true)
  [ -n "$public_url" ] && grep -q "Registered tunnel connection" "$LOG_DIR/tunnel.log" && break
  kill -0 "$tunnel_pid" 2>/dev/null || fail "cloudflared exited, see $LOG_DIR/tunnel.log"
  sleep 1
done
[ -n "$public_url" ] && grep -q "Registered tunnel connection" "$LOG_DIR/tunnel.log" \
  || fail "tunnel not ready after ${TUNNEL_TIMEOUT_S}s, see $LOG_DIR/tunnel.log"

# 6. Keep the Mac from idle/system sleep while the demo runs (the display may still sleep).
caffeinate -is &
caffeinate_pid=$!

echo "$public_url"

# Block here until the tunnel exits or Control+C fires the cleanup trap.
wait "$tunnel_pid"
