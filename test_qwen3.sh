#!/bin/bash

# Load environment variables from .env
if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found. Please create one with your API_KEY."
  exit 1
fi

# Validate API key
if [ -z "${API_KEY}" ] || [ "${API_KEY}" = "your_api_key_here" ]; then
  echo "Error: API_KEY is not set. Please update your .env file."
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
