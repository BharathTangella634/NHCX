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
import csv
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
    return Coding(system=system, code=code, display=display)

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
        "observations": [],
        "timestamp": None
    }

    # Extract Patient Name
    name_match = re.search(r"Patient Name\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    if name_match:
        data["patient_name"] = name_match.group(1).strip()

    # Extract Age/Sex
    age_sex_match = re.search(r"Age/Sex\s*[:\-]?\s*(\d+)\s*Yr/([MF])", text, re.IGNORECASE)
    if age_sex_match:
        data["age"] = age_sex_match.group(1)
        data["gender"] = "male" if age_sex_match.group(2).upper() == 'M' else "female"

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
    Creates a separate DocumentReference for each page identified by <!-- PAGE_BREAK -->.
    """
    # Split text by page break marker
    pages = [p.strip() for p in text.split("<!-- PAGE_BREAK -->") if p.strip()]
    
    # Use the full text for patient and overall data extraction
    # (Patient details usually appear on the first page or are consistent throughout)
    parsed_data = parse_extracted_text(text)
    
    # Ensure we have a valid timestamp for the Bundle
    if not parsed_data.get("timestamp"):
        parsed_data["timestamp"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
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
    # Using a simple dict for Organization to avoid complex pydantic validation if profile is strict
    
    # 1. Patient Resource
    patient = Patient(
        id=patient_id,
        name=[{"text": parsed_data["patient_name"]}],
        gender=parsed_data["gender"] if parsed_data["gender"] else "unknown"
    )
    patient_entry = create_bundle_entry(patient)

    # 2. Observation Resources
    observation_resources = []
    observation_refs = []
    first_doc_ref_id = str(uuid.uuid4())
    
    for obs_data in parsed_data["observations"]:
        obs = Observation(
            id=str(uuid.uuid4()),
            status="final",
            code=create_codeable_concept(Vocab.LOINC.value, obs_data["code"], obs_data["display"]),
            subject=create_reference("Patient", patient.id),
            effectiveDateTime=parsed_data["timestamp"],
            valueQuantity=Quantity(value=obs_data["value"], unit=obs_data["unit"], system=Vocab.UCUM.value),
            extension=[create_derivation_extension(first_doc_ref_id)]
        )
        observation_resources.append(obs)
        observation_refs.append(create_reference("Observation", obs.id))

    # 3. DocumentReference (One per page)
    doc_ref_resources = []
    doc_ref_mapping = LOINC_MAP.get("Consult Note", {"code": "11488-4", "display": "Consult Note"})
    
    for i, page_content in enumerate(pages):
        page_data = parse_extracted_text(page_content)
        page_timestamp = page_data.get("timestamp") or parsed_data["timestamp"]
        
        attachment = Attachment(
            contentType="text/plain",
            title=f"Extracted text from {original_filename} - Page {i+1}"
        )

        current_doc_id = first_doc_ref_id if i == 0 else str(uuid.uuid4())
        
        doc_ref = DocumentReference(
            id=current_doc_id,
            status="current",
            docStatus="final",
            type=create_codeable_concept(Vocab.LOINC.value, doc_ref_mapping["code"], doc_ref_mapping["display"]),
            subject=create_reference("Patient", patient.id),
            date=page_timestamp,
            content=[{"attachment": attachment}]
        )
        doc_ref_resources.append(doc_ref)

    # 4. DiagnosticReport
    report_mapping = LOINC_MAP.get("Laboratory report", {"code": "11502-2", "display": "Laboratory report"})
    report = DiagnosticReport(
        id=diagnostic_report_id,
        status="final",
        code=create_codeable_concept(Vocab.LOINC.value, report_mapping["code"], report_mapping["display"]),
        subject=create_reference("Patient", patient.id),
        issued=parsed_data["timestamp"],
        result=observation_refs
    )

    # 5. Composition (MUST be the first entry)
    bundle_timestamp = parsed_data["timestamp"]
    
    composition = Composition.model_construct(
        id=composition_id,
        status="final",
        type=create_codeable_concept(Vocab.LOINC.value, report_mapping["code"], report_mapping["display"]),
        subject=create_reference("Patient", patient.id),
        date=bundle_timestamp,
        author=[create_reference("Organization", organization_id)],
        title=f"Diagnostic Report - {parsed_data['patient_name']}",
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
    # Composition MUST be first
    entries.append(create_bundle_entry(composition))
    
    # Organization
    entries.append(BundleEntry(
        resource=organization,
        fullUrl=f"urn:uuid:{organization_id}"
    ))

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
