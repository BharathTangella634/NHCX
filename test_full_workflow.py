import os
import time
import asyncio
from fastapi.testclient import TestClient

# Override env vars so pdf2abdm talks to the local session_logger process
os.environ["SESSION_LOGGER_URL"] = "http://localhost:8002"

# Mock the heavy ML pipeline so it doesn't run locally and take minutes/GPUs
async def mock_get_abdm_json(pdf_path, **kwargs):
    print(f"    [Mock] Simulating ABDM extraction for {pdf_path}")
    await asyncio.sleep(1) # simulate some processing time
    bundles = [{"resourceType": "Bundle", "type": "document"}]
    doc_types = ["diagnostic_report"]
    return bundles, doc_types

# Inject the mock
import pdf2abdm.app.main as abdm_main
abdm_main.get_abdm_json = mock_get_abdm_json

print("--- Testing PDF2ABDM workflow ---")
client = TestClient(abdm_main.app)

# Hit the URL endpoint which reads a local file
test_pdf = "./test_files/abdm_diagnostic_report.pdf"
response = client.post(
    "/pdf2abdmurl",
    json={"file_path": test_pdf, "model": "gemma4", "ocr_engine": "auto"}
)

print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Response: {data.get('message')} - {data.get('processing_time')}")
else:
    print(f"Error: {response.text}")

print("Giving background task 2 seconds to fire log to session_logger...")
time.sleep(2)

print("\n--- Verifying Session Logger DB ---")
import requests
stats = requests.get("http://localhost:8002/logs/stats").json()
print("Stats from Cloud SQL DB:")
import pprint
pprint.pprint(stats)

print("\nChecking latest log entries in DB:")
logs = requests.get("http://localhost:8002/logs?limit=3").json()
for idx, log in enumerate(logs.get('items', [])):
    print(f" [{idx+1}] {log['created_at']} | IP: {log['ip_address']} | {log['document_type']} | JSON URI: {log['json_location']}")

print("\n✅ Workflow test complete.")
