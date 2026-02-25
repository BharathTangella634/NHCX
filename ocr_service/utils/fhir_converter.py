import os
import json
import re
import pandas as pd
from dotenv import load_dotenv
from typing import Dict, List, Union
from google.cloud import aiplatform

load_dotenv()
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from .logger import get_logger

logger = get_logger(__name__)

LOINC_MAPPING = {}

def load_loinc_mapping():
    global LOINC_MAPPING
    if LOINC_MAPPING:
        return
    
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        loinc_file = os.path.join(base_dir, 'reference', 'LOINC-codes.xlsx')
        if not os.path.exists(loinc_file):
            logger.warning(f"LOINC reference file not found at {loinc_file}")
            return
            
        df = pd.read_excel(loinc_file, header=12)
        mapping = {}
        
        if 'Result Test Name' in df.columns and 'Result LOINC Code' in df.columns:
            for _, row in df.dropna(subset=['Result Test Name', 'Result LOINC Code']).iterrows():
                test_name = str(row['Result Test Name']).strip().lower()
                loinc_code = str(row['Result LOINC Code']).strip()
                if len(test_name) > 3 and loinc_code:
                    mapping[test_name] = loinc_code
                    
        if 'Order Test Name' in df.columns and 'Result LOINC Code' in df.columns:
            for _, row in df.dropna(subset=['Order Test Name', 'Result LOINC Code']).iterrows():
                test_name = str(row['Order Test Name']).strip().lower()
                loinc_code = str(row['Result LOINC Code']).strip()
                if len(test_name) > 3 and loinc_code:
                    mapping[test_name] = loinc_code
                    
        LOINC_MAPPING.update(mapping)
        logger.info(f"Loaded {len(LOINC_MAPPING)} LOINC codes from reference.")
    except Exception as e:
        logger.error(f"Failed to load LOINC mapping: {e}")

def regex_nlp_extract(text: str, doc_type: str = None) -> dict:
    """
    Leverages Regex and basic NLP to identify right items from the OCR text
    that match common FHIR Map entities.
    """
    extracted = {}
    
    # Dates: YYYY-MM-DD or DD/MM/YYYY or DD-MM-YYYY
    dates = re.findall(r'\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b', text)
    if dates:
        extracted["Potential Dates"] = list(set(dates))
        
    # Phone Numbers (Indian format as example)
    phones = re.findall(r'\b(?:\+91[-\s]?)?[6789]\d{9}\b', text)
    if phones:
        extracted["Potential Phone Numbers"] = list(set(phones))
        
    # Gender
    gender_match = re.search(r'\b(?:Gender|Sex)[\s\.:#-]+(Male|Female|Other|M|F|O)\b', text, re.IGNORECASE)
    if gender_match:
        extracted["Potential Gender"] = gender_match.group(1)
        
    # Age
    age_match = re.search(r'\b(\d{1,3})\s*(?:years?|yrs?|Y/O)\b', text, re.IGNORECASE)
    if age_match:
        extracted["Potential Age"] = age_match.group(1)
        
    # Identifiers (like UUIDs or standard alphanum IDs)
    uuids = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', text, re.IGNORECASE)
    if uuids:
        extracted["Potential UUIDs"] = list(set(uuids))
        
    # Registration / Patient ID / Ref
    id_match = re.findall(r'\b(?:ID|No|Number|Reg|MRN|Ref)[\s\.:#-]+([A-Z0-9]{3,})\b', text, re.IGNORECASE)
    if id_match:
        extracted["Potential Identifiers"] = list(set(id_match))
        
    # Blood Group / Rh
    blood_group = re.search(r'\b(A|B|AB|O)[\s\-]*(Pos|Neg|\+|\-)\b', text, re.IGNORECASE)
    if blood_group:
        extracted["Potential Blood Group"] = f"{blood_group.group(1)} {blood_group.group(2)}"
        
    # Emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    if emails:
        extracted["Potential Emails"] = list(set(emails))
        
    # PIN Codes (India - 6 digits)
    pincodes = re.findall(r'\b[1-9][0-9]{5}\b', text)
    if pincodes:
        extracted["Potential PIN Codes"] = list(set(pincodes))
        
    # Doctor Names
    doctors = re.findall(r'\b(?:Dr\.|Dr|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', text)
    if doctors:
        extracted["Potential Doctor Names"] = list(set(["Dr. " + d.strip() for d in doctors]))

    # Vitals
    vitals = {}
    
    # Blood Pressure (e.g., 120/80)
    bp_match = re.search(r'\b(?:BP|Blood Pressure)[\s\.:#-]*(\d{2,3}\s*/\s*\d{2,3})\s*(?:mmHg)?\b', text, re.IGNORECASE)
    if not bp_match:
        bp_match = re.search(r'\b(\d{2,3}\s*/\s*\d{2,3})\s*mmHg\b', text, re.IGNORECASE)
    if bp_match:
        vitals["Blood Pressure"] = bp_match.group(1).replace(" ", "")

    # Heart Rate / Pulse
    hr_match = re.search(r'\b(?:HR|Pulse|PR)[\s\.:#-]*(\d{2,3})\s*(?:bpm|beats/min)?\b', text, re.IGNORECASE)
    if hr_match:
        vitals["Heart Rate"] = hr_match.group(1)

    # Temperature
    temp_match = re.search(r'\b(?:Temp|Temperature)[\s\.:#-]*(\d{2,3}(?:\.\d+)?)\s*(F|C|°F|°C)\b', text, re.IGNORECASE)
    if temp_match:
        vitals["Temperature"] = f"{temp_match.group(1)} {temp_match.group(2)}"

    # SpO2
    spo2_match = re.search(r'\b(?:SpO2|Oxygen|O2)[\s\.:#-]*(\d{2,3})\s*%\b', text, re.IGNORECASE)
    if spo2_match:
        vitals["SpO2"] = spo2_match.group(1) + "%"
        
    # Weight
    weight_match = re.search(r'\b(?:Weight|Wt)[\s\.:#-]*(\d{1,3}(?:\.\d+)?)\s*(kg|lbs)\b', text, re.IGNORECASE)
    if weight_match:
        vitals["Weight"] = f"{weight_match.group(1)} {weight_match.group(2)}"
        
    # Height
    height_match = re.search(r'\b(?:Height|Ht)[\s\.:#-]*(\d{1,3}(?:\.\d+)?)\s*(cm|inch|ft|in)\b', text, re.IGNORECASE)
    if height_match:
        vitals["Height"] = f"{height_match.group(1)} {height_match.group(2)}"

    if vitals:
        extracted["Potential Vitals"] = vitals
        
    if doc_type == "diagnostic_report":
        load_loinc_mapping()
        if LOINC_MAPPING:
            text_lower = text.lower()
            matched_loincs = {}
            # Quick substring search, then regex boundary to confirm
            for test_name, loinc_code in LOINC_MAPPING.items():
                if test_name in text_lower:
                    try:
                        if re.search(rf'\b{re.escape(test_name)}\b', text_lower):
                            matched_loincs[test_name.title()] = loinc_code
                    except Exception:
                        pass
            if matched_loincs:
                extracted["Potential LOINC Tests"] = matched_loincs
                
    return extracted

def resolve_endpoint_name(project: str, location: str, endpoint_id_or_name: str) -> str:
    s = endpoint_id_or_name.strip()
    if s.startswith("projects/") and "/endpoints/" in s:
        return s
    return f"projects/{project}/locations/{location}/endpoints/{s}"

def predict_custom_trained_model_sample(
    project: str,
    endpoint_id: str,
    instances: Union[Dict, List[Dict]],
    location: str = os.getenv("VERTEX_LOCATION", "asia-northeast1"),
    parameters: dict = None,
):
    """
    Calls the Vertex AI deployed model endpoint for Qwen prediction.
    """
    aiplatform.init(project=project, location=location)
    
    instances = instances if isinstance(instances, list) else [instances]
    
    endpoint_name = resolve_endpoint_name(project, location, endpoint_id)
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_name)
    
    response = endpoint.predict(instances=instances, parameters=parameters)
    return response.predictions

def generate_fhir_from_llm(text: str, map_files: list, doc_type: str = None) -> tuple:
    """
    Builds the FHIR JSON purely using regex and the provided map templates.
    Returns a tuple of (fhir_json_str, extracted_items_dict)
    """
    # Use regex/NLP to extract basic items
    extracted_items = regex_nlp_extract(text, doc_type)
    
    # Take the primary template (first map file)
    primary_map_file = map_files[0]
    try:
        with open(primary_map_file, "r") as f:
            template = json.load(f)
    except Exception as e:
        logger.error(f"Error reading map file {primary_map_file}: {e}")
        template = {}
        
    def fill_template(obj):
        if isinstance(obj, dict):
            return {k: fill_template(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [fill_template(item) for item in obj]
        elif isinstance(obj, str):
            # Replace basic placeholders if we have extracted data
            if "<UUID>" in obj and "Potential UUIDs" in extracted_items and extracted_items["Potential UUIDs"]:
                return extracted_items["Potential UUIDs"][0]
            if "DATE_FORMAT" in obj and "Potential Dates" in extracted_items and extracted_items["Potential Dates"]:
                return extracted_items["Potential Dates"][0]
            if obj == "str" and "Potential Identifiers" in extracted_items and extracted_items["Potential Identifiers"]:
                return extracted_items["Potential Identifiers"][0]
            return obj
        return obj

    filled_template = fill_template(template)
    
    return json.dumps(filled_template, indent=2), extracted_items

def convert_diagnostic_report_to_fhir(text, original_filename="document.pdf"):
    logger.info(f"Converting Diagnostic Report to FHIR via Regex/Template for {original_filename}")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    map_files = [os.path.join(base_dir, 'reference', 'diagnostic_report_map.json')]
    
    return generate_fhir_from_llm(text, map_files, doc_type="diagnostic_report")

def convert_discharge_summary_to_fhir(text, original_filename="document.pdf"):
    logger.info(f"Converting Discharge Summary to FHIR via Regex/Template for {original_filename}")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    map_files = [
        os.path.join(base_dir, 'reference', 'discharge_summary_map.json')
    ]
    
    return generate_fhir_from_llm(text, map_files, doc_type="discharge_summary")
