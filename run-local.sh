#!/usr/bin/env bash
# Build the container and start the website on http://localhost:8000
# Usage:  ./run-local.sh        (stop it with Ctrl+C)
set -euo pipefail
cd "$(dirname "$0")"

if command -v podman >/dev/null 2>&1; then ENGINE=podman
elif command -v docker >/dev/null 2>&1; then ENGINE=docker
else echo "Neither podman nor docker found. Install one:  sudo dnf install -y podman"; exit 1; fi

echo ">>> Building with $ENGINE (first time: about 3-5 minutes; afterwards usually seconds)"
$ENGINE build -t kaushal-setu .

echo ">>> Starting. Open http://localhost:8000 in your browser. Press Ctrl+C to stop."
$ENGINE run --rm -it -p 8000:10000 --name kaushal-setu kaushal-setu
