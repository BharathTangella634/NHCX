from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.documentreference import DocumentReference
from fhir.resources.attachment import Attachment
from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.identifier import Identifier
from fhir.resources.quantity import Quantity
import base64
import uuid
import re
import csv
import os
from datetime import datetime

# Load LOINC mappings from reference table
LOINC_MAP = {}
REFERENCE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'reference', 'loinc_mapping.csv')

def load_loinc_map():
    global LOINC_MAP
    if not os.path.exists(REFERENCE_FILE):
        return
    with open(REFERENCE_FILE, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            LOINC_MAP[row['Test Name']] = {
                'code': row['LOINC Code'],
                'display': row['Display Name'],
                'unit': row['Unit']
            }

load_loinc_map()

def parse_extracted_text(text):
    """
    Simple parser to extract some key fields from the OCR text.
    In a real-world scenario, this would be much more sophisticated or use an LLM.
    """
    data = {
        "patient_name": "anonymous",
        "age": None,
        "gender": None,
        "observations": []
    }

    # Extract Patient Name
    name_match = re.search(r"Patient Name\s+:\s+(.*)", text, re.IGNORECASE)
    if name_match:
        data["patient_name"] = name_match.group(1).strip()

    # Extract Age/Sex
    age_sex_match = re.search(r"Age/Sex\s+:\s+(\d+)\s+Yr/([MF])", text, re.IGNORECASE)
    if age_sex_match:
        data["age"] = age_sex_match.group(1)
        data["gender"] = "male" if age_sex_match.group(2).upper() == 'M' else "female"

    # Extract Timestamp (using Reporting Date if available, otherwise Collection Date)
    timestamp_match = re.search(r"Reporting Date\s*:\s*(\d{2}-[a-zA-Z]{3}-\d{4}\s+\d{2}:\d{2})", text, re.IGNORECASE)
    if not timestamp_match:
        timestamp_match = re.search(r"Collection Date\s*:\s*(\d{2}-[a-zA-Z]{3}-\d{4}\s+\d{2}:\d{2})", text, re.IGNORECASE)
    
    if timestamp_match:
        try:
            dt = datetime.strptime(timestamp_match.group(1), "%d-%b-%Y %H:%M")
            data["timestamp"] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            data["timestamp"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        data["timestamp"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    # Extract Lab Results (simplified regex for the table-like structure)
    # Using the reference table for lookups
    lines = text.split('\n')
    for test_name, mapping in LOINC_MAP.items():
        # Only look for specific tests defined in the reference table
        if test_name == "Consult Note" or test_name == "Laboratory report":
            continue

        for line in lines:
            if test_name in line and any(char.isdigit() for char in line):
                val_match = re.search(r"(\d+\.\d+|\d+)", line)
                if val_match:
                    data["observations"].append({
                        "code": mapping['code'],
                        "display": mapping['display'],
                        "value": float(val_match.group(1)),
                        "unit": mapping['unit'] if mapping['unit'] else "g/dL"
                    })
                    break # Found the result for this test

    return data

def text_to_abdm_fhir(text, original_filename="document.pdf"):
    """
    Wraps extracted text into an ABDM-compliant FHIR Bundle with structured resources.
    """
    parsed_data = parse_extracted_text(text)
    entries = []

    # 1. Patient Resource
    patient = Patient(
        id=str(uuid.uuid4()),
        name=[{"text": parsed_data["patient_name"]}],
        gender=parsed_data["gender"] if parsed_data["gender"] else "unknown"
    )
    if parsed_data["age"]:
        # Simplified: just adding age as a comment or extension since birthDate is preferred
        pass
    
    entries.append(BundleEntry(resource=patient, fullUrl=f"Patient/{patient.id}"))

    # 2. Observation Resources
    observation_refs = []
    for obs_data in parsed_data["observations"]:
        obs = Observation(
            id=str(uuid.uuid4()),
            status="final",
            code={"coding": [{"system": "http://loinc.org", "code": obs_data["code"], "display": obs_data["display"]}]},
            subject={"reference": f"Patient/{patient.id}"},
            effectiveDateTime=parsed_data.get("timestamp"),
            valueQuantity=Quantity(value=obs_data["value"], unit=obs_data["unit"], system="http://unitsofmeasure.org")
        )
        entries.append(BundleEntry(resource=obs, fullUrl=f"Observation/{obs.id}"))
        observation_refs.append({"reference": f"Observation/{obs.id}"})

    # 3. DocumentReference (Raw OCR text)
    attachment = Attachment(
        contentType="text/plain",
        data=base64.b64encode(text.encode('utf-8')).decode('utf-8'),
        title=f"Extracted text from {original_filename}"
    )

    doc_ref_type = LOINC_MAP.get("Consult Note", {"code": "11488-4", "display": "Consult Note"})
    doc_ref = DocumentReference(
        id=str(uuid.uuid4()),
        status="current",
        docStatus="final",
        type={"coding": [{"system": "http://loinc.org", "code": doc_ref_type["code"], "display": doc_ref_type["display"]}]},
        subject={"reference": f"Patient/{patient.id}"},
        date=parsed_data.get("timestamp", datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')),
        content=[{"attachment": attachment}]
    )
    entries.append(BundleEntry(resource=doc_ref, fullUrl=f"DocumentReference/{doc_ref.id}"))

    # 4. DiagnosticReport (Linking them all)
    report_type = LOINC_MAP.get("Laboratory report", {"code": "11502-2", "display": "Laboratory report"})
    report = DiagnosticReport(
        id=str(uuid.uuid4()),
        status="final",
        code={"coding": [{"system": "http://loinc.org", "code": report_type["code"], "display": report_type["display"]}]},
        subject={"reference": f"Patient/{patient.id}"},
        issued=parsed_data.get("timestamp", datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')),
        result=observation_refs
    )
    entries.append(BundleEntry(resource=report, fullUrl=f"DiagnosticReport/{report.id}"))

    # Create Bundle
    bundle = Bundle(
        type="document",
        identifier=Identifier(system="https://www.abdm.gov.in/bundle", value=str(uuid.uuid4())),
        entry=entries
    )

    return bundle.json()
