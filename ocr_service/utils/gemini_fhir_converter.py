import os
import json
import requests
from dotenv import load_dotenv
from .logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GCP_API_KEY")

def call_gemini_for_fhir_segregation(extracted_text: str) -> str:
    if not API_KEY:
        raise ValueError("GCP_API_KEY not found in environment variables.")

    url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    prompt = f"""
You are an expert in healthcare data and HL7 FHIR R4 standard. 
Your task is to analyze the following clinical text (OCR output) and segregate the extracted information into a structured FHIR R4 Bundle.
Please refer to the profiles available at https://nrces.in/ndhm/fhir/r4/profiles.html and map the data strictly to the following resources if applicable:
- Patient
- DiagnosticReportRecord
- DischargeSummaryRecord
- HealthDocumentRecord
- ImmunizationRecord
- OPConsultRecord
- PrescriptionRecord
- WellnessRecord
- Specimen
- Observation
- Procedure

Requirements:
1. Output valid JSON representing a FHIR R4 Bundle of type 'collection' or 'document'.
2. The Bundle should contain entries for all the resources you could identify and segregate from the text.
3. Use realistic dummy UUIDs for references.
4. Output ONLY the raw JSON without any markdown formatting like ```json ... ```.

Clinical Text:
{extracted_text}
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Gemini API Error {response.status_code}: {response.text}")

    result_json = response.json()
    try:
        content_text = result_json['candidates'][0]['content']['parts'][0]['text']
        # Clean up possible markdown wrappers
        if content_text.startswith("```json"):
            content_text = content_text[7:]
        if content_text.startswith("```"):
            content_text = content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
        return content_text.strip()
    except (KeyError, IndexError) as e:
        raise Exception(f"Unexpected response format from Gemini: {result_json}")

def convert_to_fhir_with_gemini(extracted_text: str, filename: str) -> str:
    logger.info(f"Calling Gemini API for {filename} to segregate FHIR resources page by page...")
    
    pages = [page.strip() for page in extracted_text.split("<!-- PAGE_BREAK -->") if page.strip()]
    
    combined_entries = []
    for i, page_text in enumerate(pages):
        logger.info(f"Processing page {i+1} of {len(pages)}...")
        fhir_json_str = call_gemini_for_fhir_segregation(page_text)
        
        # Validate JSON and extract entries
        try:
            page_bundle = json.loads(fhir_json_str)
            if "entry" in page_bundle:
                combined_entries.extend(page_bundle["entry"])
        except json.JSONDecodeError as e:
            logger.warning(f"Warning: Gemini did not return valid JSON for {filename} page {i+1}. Error: {e}")
            
    # Create combined bundle
    combined_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": combined_entries
    }
    
    return json.dumps(combined_bundle, indent=2)
