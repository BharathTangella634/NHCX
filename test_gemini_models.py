import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GCP_API_KEY")

if not API_KEY:
    print("No GCP_API_KEY found in .env")
    exit(1)

models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro"
]

print("Testing available Gemini models on the provided endpoint...\n")

available_models = []

for model in models_to_test:
    url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Hello, say 'yes' if you work."}]}]
    }
    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    
    if res.status_code == 200:
        print(f"✅ {model} is AVAILABLE.")
        available_models.append(model)
    else:
        print(f"❌ {model} is UNAVAILABLE (Error {res.status_code}).")

print("\nSummary of Available Models:")
for m in available_models:
    print(f"- {m}")
