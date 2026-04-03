#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# test_gemini.sh  —  Quick test for Gemini 2.5 Flash Lite via Google AI API
# Usage: ./test_gemini.sh
# ─────────────────────────────────────────────────────────────────────────────

# Load API_KEY from .env in the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌  .env file not found at: $ENV_FILE"
    exit 1
fi

# Source only the API_KEY line (safe, avoids eval-ing everything)
API_KEY=$(grep -E '^API_KEY=' "$ENV_FILE" | head -1 | cut -d'"' -f2)

if [[ -z "$API_KEY" ]]; then
    echo "❌  API_KEY not found in .env"
    exit 1
fi

echo "✅  API_KEY loaded from .env"
echo "🚀  Sending request to Gemini 2.5 Flash Lite..."
echo "────────────────────────────────────────────────"

curl -s \
    "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:streamGenerateContent?key=${API_KEY}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
      "contents": [
        {
          "role": "user",
          "parts": [
            {
              "text": "Explain how AI works in a few words"
            }
          ]
        }
      ]
    }' | python3 -c "
import sys, json

raw = sys.stdin.read().strip()

# The streaming response is a JSON array of chunks
try:
    chunks = json.loads(raw)
    print()
    for chunk in chunks:
        parts = chunk.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        for part in parts:
            print(part.get('text', ''), end='', flush=True)
    print()
except json.JSONDecodeError:
    # Fallback: just print raw if parsing fails
    print(raw)
"

echo ""
echo "────────────────────────────────────────────────"
echo "✅  Done."
