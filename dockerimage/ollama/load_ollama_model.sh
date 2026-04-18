#!/usr/bin/env bash
set -euo pipefail

# If file was mounted with CRLF line endings, remove them in-place (requires sed available in image)
if grep -q $'\r' "/load_ollama_model.sh" 2>/dev/null || true; then
  sed -i 's/\r$//' "/load_ollama_model.sh" || true
fi

# Start ollama in background, pull the configured model, then signal readiness
/bin/ollama serve &
pid=$!
sleep 5
echo "Starting pulling model $OLLAMA_MODEL..."
ollama pull "$OLLAMA_MODEL"
echo "DONE! Pulling model $OLLAMA_MODEL successful!"
echo "Starting pulling model $OLLAMA_EMBED..."
ollama pull "$OLLAMA_EMBED"
touch /tmp/ollama_is_ready
echo "DONE! Pulling model $OLLAMA_EMBED successful!"
wait "$pid"

