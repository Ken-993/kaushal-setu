#!/usr/bin/env bash
# Kaushal Setu - run the website on your own computer.
#
#   ./run-local.sh          build (if needed) and start the site in the background, then show its logs
#   ./run-local.sh stop     stop the site
#   ./run-local.sh logs     show the logs of the running site again
#   ./run-local.sh status   is it running?
#
# The site keeps running even if you close VS Code or the terminal; use "stop" to end it.
# Pressing Ctrl+C only stops SHOWING the logs, not the site.
set -euo pipefail
cd "$(dirname "$0")"

NAME=kaushal-setu
URL=http://127.0.0.1:8000

if command -v podman >/dev/null 2>&1; then ENGINE=podman
elif command -v docker >/dev/null 2>&1; then ENGINE=docker
else echo "Neither podman nor docker found. Install one:  sudo dnf install -y podman"; exit 1; fi

case "${1:-start}" in
  stop)
    if $ENGINE ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
      $ENGINE rm -f "$NAME" >/dev/null && echo "Stopped."
    else
      echo "It was not running."
    fi
    exit 0 ;;
  logs)
    exec $ENGINE logs -f "$NAME" ;;
  status)
    if $ENGINE ps --format '{{.Names}}' | grep -qx "$NAME"; then echo "Running at $URL"; else echo "Not running."; fi
    exit 0 ;;
  start) ;;
  *) echo "Usage: ./run-local.sh [start|stop|logs|status]"; exit 1 ;;
esac

echo ">>> Building with $ENGINE (first time: about 3-5 minutes; afterwards usually seconds)"
$ENGINE build -t "$NAME" .

echo ">>> Removing any old copy that is still running"
$ENGINE rm -f "$NAME" >/dev/null 2>&1 || true

echo ">>> Starting in the background"
$ENGINE run -d --name "$NAME" -p 8000:10000 "$NAME" >/dev/null

echo ">>> Waiting for the site to be ready..."
for _ in $(seq 1 60); do
  if curl -sf "$URL/api/health" >/dev/null 2>&1; then break; fi
  sleep 1
done

if curl -sf "$URL/api/health" >/dev/null 2>&1; then
  echo ""
  echo "  Kaushal Setu is running:  $URL"
  echo "  Stop it with:             ./run-local.sh stop"
  echo ""
  echo ">>> Live logs below. Ctrl+C hides them; the site keeps running."
  exec $ENGINE logs -f "$NAME"
else
  echo "The site did not start. Last log lines:"
  $ENGINE logs --tail 30 "$NAME" || true
  exit 1
fi
