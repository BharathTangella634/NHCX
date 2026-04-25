import requests
import json
import os
import argparse

# Define the base URLs for the APIs. Defaulting to localhost ports used by docker-compose.
PDF2ABDM_URL = "http://localhost:8000/pdf2abdmurl"
PDF2NHCX_URL = "http://localhost:8001/pdf2nhcxurl"

def test_api(endpoint_url, file_path, model="gemma4", ocr_engine="auto"):
    """
    Sends a POST request to the local file processing endpoint.
    """
    print(f"\n[{endpoint_url}] Testing with file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: The file '{file_path}' does not exist locally.")
        return

    payload = {
        "file_path": os.path.abspath(file_path),
        "model": model,
        "ocr_engine": ocr_engine
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        print("Sending request... (this may take a few moments for synchronous processing)")
        response = requests.post(endpoint_url, json=payload, headers=headers)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success!")
            data = response.json()
            
            # Print a summary of the response
            print(f"Message: {data.get('message')}")
            print(f"Processing Time: {data.get('processing_time')}")
            print(f"Document Type: {data.get('document_type')}")
            print(f"Number of Bundles: {len(data.get('bundles', []))}")
            
            # Save the JSON locally to inspect
            output_filename = f"output_{os.path.basename(endpoint_url)}.json"
            with open(output_filename, "w") as f:
                json.dump(data, f, indent=2)
            print(f"💾 Full response saved to {output_filename}")
            
        else:
            print(f"❌ Failed: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {endpoint_url}. Is the docker container running?")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script for local file processing endpoints (/pdf2abdmurl & /pdf2nhcxurl).")
    parser.add_argument("file_path", help="Absolute or relative path to the PDF file to process.")
    parser.add_argument("--api", choices=["abdm", "nhcx", "both"], default="both", help="Which API to test (default: both).")
    parser.add_argument("--model", default="gemma4", help="Model to use (default: gemma4).")
    
    args = parser.parse_args()
    
    if args.api in ["abdm", "both"]:
        test_api(PDF2ABDM_URL, args.file_path, args.model)
        
    if args.api in ["nhcx", "both"]:
        test_api(PDF2NHCX_URL, args.file_path, args.model)
