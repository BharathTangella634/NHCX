#!/bin/bash

# Load environment variables from .env
if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found. Please create one with your API_KEY."
  exit 1
fi

# Validate Credentials and get token
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS}" ] && [ -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
  echo "Using service account: ${GOOGLE_APPLICATION_CREDENTIALS}"
  # First try using gcloud if available
  if command -v gcloud &> /dev/null; then
    # Activate the service account if needed, OR just use it to print token
    API_KEY=$(gcloud auth application-default print-access-token 2>/dev/null)
    
    # If gcloud ADC failed, try explicitly activating the account
    if [ -z "$API_KEY" ]; then
      gcloud auth activate-service-account --key-file="${GOOGLE_APPLICATION_CREDENTIALS}" &>/dev/null
      API_KEY=$(gcloud auth print-access-token 2>/dev/null)
    fi
  fi

  # Fallback: if gcloud failed or isn't installed, use Python (which is surely installed)
  if [ -z "${API_KEY}" ]; then
    echo "gcloud unavailable or failed, attempting to get token via Python..."
    API_KEY=$(python3 - <<EOF
import os
import google.auth
import google.auth.transport.requests
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '${GOOGLE_APPLICATION_CREDENTIALS}'
credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
credentials.refresh(google.auth.transport.requests.Request())
print(credentials.token)
EOF
)
  fi
fi

# Final validation
if [ -z "${API_KEY}" ] || [ "${API_KEY}" = "your_api_key_here" ]; then
  echo "Error: Could not generate a valid token from ${GOOGLE_APPLICATION_CREDENTIALS} or API_KEY is not set."
  exit 1
fi

# Create the request payload
cat << EOF > request.json
{
    "model": "qwen/qwen3-next-80b-a3b-instruct-maas"
    ,"stream": true
    ,"max_tokens": 8192
    ,"temperature": 0.7
    ,"top_p": 0.8
    ,"messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Hi, how are you?"
                }
            ]
        }
    ]
}
EOF

# Invoke the model
echo "Invoking Qwen3 model..."
curl \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  "https://${ENDPOINT}/v1beta1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/openapi/chat/completions" \
  -d '@request.json'

# Cleanup
rm -f request.json
