from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.documentreference import DocumentReference
from fhir.resources.attachment import Attachment
from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.composition import Composition, CompositionSection
from fhir.resources.identifier import Identifier
from fhir.resources.quantity import Quantity
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.reference import Reference
from fhir.resources.extension import Extension
import base64
import uuid
import re
import pandas as pd
import os
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

class Vocab(Enum):
    """
    https://build.fhir.org/terminologies-systems.html
    """
    SNOMEDCT_US = "http://snomed.info/sct"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    LOINC = "http://loinc.org"
    LNC = "http://loinc.org"
    CPT = "http://www.ama-assn.org/go/cpt"
    MEDRT = "http://va.gov/terminology/medrt"
    NDFRT = "http://hl7.org/fhir/ndfrt"
    NDC = "http://hl7.org/fhir/sid/ndc"
    CVX = "http://hl7.org/fhir/sid/cvx"
    ICD9 = "http://terminology.hl7.org/CodeSystem/icd9"
    ICD10 = "http://hl7.org/fhir/sid/icd-10"
    UMLS = "http://terminology.hl7.org/CodeSystem/umls"
    UCUM = "http://unitsofmeasure.org"

def create_coding(system: str, code: str, display: str = None) -> Coding:
    kwargs = {"code": code}
    if display:
        kwargs["display"] = display
    if system and system not in ["http://loinc.org", "http://unitsofmeasure.org"]:
        kwargs["system"] = system
    return Coding(**kwargs)

def create_codeable_concept(system: str, code: str, display: str = None, text: str = None) -> CodeableConcept:
    coding = create_coding(system, code, display)
    return CodeableConcept(coding=[coding], text=text or display)

def create_reference(resource_type: str, resource_id: str) -> Reference:
    return Reference(reference=f"urn:uuid:{resource_id}")

def create_bundle_entry(resource: Any) -> BundleEntry:
    """Creates a BundleEntry with urn:uuid fullUrl."""
    return BundleEntry(
        resource=resource,
        fullUrl=f"urn:uuid:{resource.id}"
    )

FHIR_DERIVATION_REF_URL = "http://hl7.org/fhir/StructureDefinition/derivation-reference"

def create_derivation_extension(doc_ref_id: str) -> Extension:
    """
    Creates a simple derivation extension linking back to the DocumentReference.
    """
    return Extension(
        url=FHIR_DERIVATION_REF_URL,
        extension=[
            Extension(url="reference", valueReference=create_reference("DocumentReference", doc_ref_id))
        ]
    )

# Load LOINC mappings from reference table
LOINC_MAP = {}
REFERENCE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'reference', 'LOINC-codes.xlsx')

def load_loinc_map():
    global LOINC_MAP
    if not os.path.exists(REFERENCE_FILE):
        return
    try:
        df = pd.read_excel(REFERENCE_FILE, header=12)
        for _, row in df.dropna(subset=['Result Test Name', 'Result LOINC Code']).iterrows():
            test_name = str(row['Result Test Name']).strip()
            LOINC_MAP[test_name] = {
                'code': str(row['Result LOINC Code']).strip(),
                'display': test_name,
                'unit': str(row['Units of Measure']).strip() if pd.notna(row['Units of Measure']) else ""
            }
    except Exception as e:
        print(f"Error loading LOINC mapping: {e}")

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
        "observations": [],
        "timestamp": None
    }

    # Extract Patient Name
    name_match = re.search(r"Patient Name\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    if name_match:
        data["patient_name"] = name_match.group(1).strip()

    # Extract Age/Sex
    age_sex_match = re.search(r"Age/Sex\s*[:\-]?\s*(\d+)\s*(Yr|Mth|Day)?/([MF])", text, re.IGNORECASE)
    if age_sex_match:
        data["age"] = f"{age_sex_match.group(1)} {age_sex_match.group(2) if age_sex_match.group(2) else 'Yr'}"
        data["gender"] = "male" if age_sex_match.group(3).upper() == 'M' else "female"
    else:
        # Fallback for just age
        age_match = re.search(r"Age\s*[:\-]?\s*(\d+)\s*(Yr|Mth|Day)?", text, re.IGNORECASE)
        if age_match:
            data["age"] = f"{age_match.group(1)} {age_match.group(2) if age_match.group(2) else 'Yr'}"
        # Fallback for just sex
        sex_match = re.search(r"Sex\s*[:\-]?\s*([MF])", text, re.IGNORECASE)
        if sex_match:
            data["gender"] = "male" if sex_match.group(1).upper() == 'M' else "female"

    # Extract Timestamp (using Reporting Date if available, otherwise Collection Date)
    timestamp_match = re.search(r"Reporting Date\s*[:\-]?\s*(\d{2}-[a-zA-Z]{3}-\d{4}\s+\d{2}:\d{2})", text, re.IGNORECASE)
    if not timestamp_match:
        timestamp_match = re.search(r"Collection Date\s*[:\-]?\s*(\d{2}-[a-zA-Z]{3}-\d{4}\s+\d{2}:\d{2})", text, re.IGNORECASE)
    
    if timestamp_match:
        try:
            dt = datetime.strptime(timestamp_match.group(1), "%d-%b-%Y %H:%M")
            data["timestamp"] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            pass
    
    # If still no timestamp, look for any date-time like pattern as a fallback
    if not data["timestamp"]:
        date_pattern = re.search(r"(\d{2}-[a-zA-Z]{3}-\d{4}\s+\d{2}:\d{2})", text)
        if date_pattern:
            try:
                dt = datetime.strptime(date_pattern.group(1), "%d-%b-%Y %H:%M")
                data["timestamp"] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass

    # Extract Lab Results (simplified regex for the table-like structure)
    # Using the reference table for lookups
    lines = text.split('\n')
    
    # Track which tests we've already found to avoid duplicates from different pages if not needed
    # But for multiple pages, we might want all of them.
    
    for test_name, mapping in LOINC_MAP.items():
        # Only look for specific tests defined in the reference table
        if test_name in ["Consult Note", "Laboratory report", "Patient Name", "Age", "Gender", "ABHA ID", "Date"]:
            continue

        for idx, line in enumerate(lines):
            # Look for the test name in the line. Use regex for word boundaries to avoid partial matches.
            if re.search(r'\b' + re.escape(test_name) + r'\b', line, re.IGNORECASE):
                # Try to find a numeric value in the SAME line or within the next few lines (handles section-style layouts)
                search_window = [line]
                # Look ahead up to 5 lines to catch patterns like:
                #   Test Name\nResult\n<value>\nRef Range ...
                for k in range(1, 6):
                    if idx + k < len(lines):
                        search_window.append(lines[idx + k])
                joined = "\n".join(search_window)

                value = None
                # Special handling for APTT-like tests to avoid picking '3.2 %' from SPECIMEN line
                aptt_like = test_name.lower() in [
                    "aptt", "activated partial thromboplastin time", "activated partial thromboplastin time (aptt)"
                ]
                if aptt_like:
                    # Prefer a number that follows the word 'Result'
                    m = re.search(r"Result[\s:\-]*.*?(\d+\.\d+|\d+)", joined, re.IGNORECASE | re.DOTALL)
                    if m:
                        value = m.group(1)
                    else:
                        # Otherwise, pick the first number not immediately followed by % and not on a SPECIMEN line
                        for l in search_window:
                            if re.search(r"SPECIMEN", l, re.IGNORECASE):
                                continue
                            m2 = re.search(r"\b(\d+(?:\.\d+)?)\b(?!\s*%)", l)
                            if m2:
                                value = m2.group(1)
                                break
                else:
                    m = re.search(r"(\d+\.\d+|\d+)", joined)
                    if m:
                        value = m.group(1)

                if value is not None:
                    # Use UCUM unit from mapping when available; else try to glean 'sec'/'s' from the nearby text
                    unit = mapping['unit'] if mapping.get('unit') else None
                    if not unit:
                        unit_match = re.search(r"\b(sec|s|seconds)\b", joined, re.IGNORECASE)
                        if unit_match:
                            unit = 's'
                    data["observations"].append({
                        "code": mapping['code'],
                        "display": mapping['display'],
                        "value": float(value),
                        "unit": unit or "g/dL"
                    })
                    break # Found the result for this test in/near this line
                
    # Extract Comments on PBS
    pbs_match = re.search(r"Comments on PBS\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    if pbs_match:
        data["pbs_comments"] = pbs_match.group(1).strip()
    
    # Extract Impression
    impression_match = re.search(r"Impression\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    if impression_match:
        data["impression"] = impression_match.group(1).strip()

    return data

def text_to_abdm_fhir(text, original_filename="document.pdf"):
    """
    Wraps extracted text into an ABDM-compliant FHIR Bundle with structured resources.
    Creates a separate DocumentReference for each page identified by <!-- PAGE_BREAK -->.
    Ensures multiple occurrences of the same test (e.g. Hemoglobin on every page) are captured.
    """
    # Split text by page break marker
    pages = [p.strip() for p in text.split("<!-- PAGE_BREAK -->") if p.strip()]
    
    # Use the full text for patient and overall data extraction
    # (Patient details usually appear on the first page or are consistent throughout)
    full_parsed_data = parse_extracted_text(text)
    
    # Ensure we have a valid timestamp for the Bundle
    if not full_parsed_data.get("timestamp"):
        full_parsed_data["timestamp"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
    entries = []
    
    # Generate UUIDs for all resources beforehand for linking
    composition_id = str(uuid.uuid4())
    patient_id = str(uuid.uuid4())
    diagnostic_report_id = str(uuid.uuid4())

    # 0. Organization Resource
    organization_id = str(uuid.uuid4())
    organization = {
        "resourceType": "Organization",
        "id": organization_id,
        "identifier": [{"system": "https://www.abdm.gov.in/organization", "value": "NHCX-HACKATHON"}],
        "name": "NHCX-HACKATHON"
    }
    
    # 1. Patient Resource
    patient_args = {
        "id": patient_id,
        "name": [{"text": full_parsed_data["patient_name"]}],
        "gender": full_parsed_data["gender"] if full_parsed_data["gender"] else "unknown"
    }
    
    if full_parsed_data.get("age"):
        patient_args["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/patient-age",
                "valueString": full_parsed_data["age"]
            }
        ]

    patient = Patient(**patient_args)
    patient_entry = create_bundle_entry(patient)

    # 2 & 3. Process each page for Observations and DocumentReferences
    observation_resources = []
    observation_refs = []
    doc_ref_resources = []
    doc_ref_mapping = LOINC_MAP.get("Consult Note", {"code": "11488-4", "display": "Consult Note"})
    
    for i, page_content in enumerate(pages):
        page_data = parse_extracted_text(page_content)
        page_timestamp = page_data.get("timestamp") or full_parsed_data["timestamp"]
        
        # Create DocumentReference for this page
        current_doc_id = str(uuid.uuid4())
        # Encode this page's extracted text as base64 per ABDM DocumentReference profile (attachment.data min=1)
        attachment = Attachment(
            contentType="text/plain",
            title=f"Extracted text from {original_filename} - Page {i+1}",
            data=base64.b64encode(page_content.encode("utf-8")).decode("utf-8")
        )
        
        doc_ref = DocumentReference(
            id=current_doc_id,
            meta={"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentReference"]},
            status="current",
            docStatus="final",
            type=create_codeable_concept(Vocab.LOINC.value, doc_ref_mapping["code"], doc_ref_mapping["display"]),
            subject=create_reference("Patient", patient.id),
            date=page_timestamp,
            author=[create_reference("Organization", organization_id)],
            custodian=create_reference("Organization", organization_id),
            content=[{"attachment": attachment}]
        )
        doc_ref_resources.append(doc_ref)
        
        # Create Observations from this page
        for obs_data in page_data["observations"]:
            obs = Observation(
                id=str(uuid.uuid4()),
                status="final",
                code=create_codeable_concept(Vocab.LOINC.value, obs_data["code"], obs_data["display"]),
                subject=create_reference("Patient", patient.id),
                effectiveDateTime=page_timestamp, # Use the page-specific timestamp
                valueQuantity=Quantity(value=obs_data["value"], unit=obs_data["unit"]),
                extension=[create_derivation_extension(current_doc_id)] # Link to THIS page's DocumentReference
            )
            observation_resources.append(obs)
            observation_refs.append(create_reference("Observation", obs.id))
            
        # Add PBS Comments as an Observation if available ON THIS PAGE
        if page_data.get("pbs_comments"):
            pbs_obs = Observation(
                id=str(uuid.uuid4()),
                status="final",
                code=create_codeable_concept(Vocab.LOINC.value, "11524-6", "Microscopic observation [Identifier] in Blood by Peripheral blood smear"),
                subject=create_reference("Patient", patient.id),
                effectiveDateTime=page_timestamp,
                valueString=page_data["pbs_comments"],
                extension=[create_derivation_extension(current_doc_id)]
            )
            observation_resources.append(pbs_obs)
            observation_refs.append(create_reference("Observation", pbs_obs.id))

    # 4. DiagnosticReport
    report_mapping = LOINC_MAP.get("Laboratory report", {"code": "11502-2", "display": "Laboratory report"})
    report_args = {
        "id": diagnostic_report_id,
        "status": "final",
        "code": create_codeable_concept(Vocab.LOINC.value, report_mapping["code"], report_mapping["display"]),
        "subject": create_reference("Patient", patient.id),
        "issued": full_parsed_data["timestamp"],
        "result": observation_refs
    }
    
    if full_parsed_data.get("impression"):
        report_args["conclusion"] = full_parsed_data["impression"]
        
    report = DiagnosticReport(**report_args)

    # 5. Composition (MUST be the first entry)
    bundle_timestamp = full_parsed_data["timestamp"]
    
    composition = Composition.model_construct(
        id=composition_id,
        status="final",
        type=create_codeable_concept(Vocab.LOINC.value, report_mapping["code"], report_mapping["display"]),
        subject=create_reference("Patient", patient.id),
        date=bundle_timestamp,
        author=[create_reference("Organization", organization_id)],
        title=f"Diagnostic Report - {full_parsed_data['patient_name']}",
        section=[
            CompositionSection(
                title="Laboratory Results",
                code=create_codeable_concept(Vocab.LOINC.value, report_mapping["code"], report_mapping["display"]),
                entry=([create_reference("DiagnosticReport", report.id)] + 
                       observation_refs + 
                       [create_reference("DocumentReference", dr.id) for dr in doc_ref_resources])
            )
        ]
    )

    # Assemble the Bundle in order
    entries.append(create_bundle_entry(composition))
    entries.append(BundleEntry(resource=organization, fullUrl=f"urn:uuid:{organization_id}"))
    entries.append(patient_entry)
    for obs in observation_resources:
        entries.append(create_bundle_entry(obs))
    for dr in doc_ref_resources:
        entries.append(create_bundle_entry(dr))
    entries.append(create_bundle_entry(report))

    # Create Bundle
    bundle = Bundle(
        type="document",
        timestamp=bundle_timestamp,
        identifier=Identifier(system="https://www.abdm.gov.in/bundle", value=str(uuid.uuid4())),
        entry=entries
    )

    return bundle.json(indent=2)
