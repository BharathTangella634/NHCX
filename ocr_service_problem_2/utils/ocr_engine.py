# from docling.datamodel.base_models import InputFormat
# from docling.document_converter import DocumentConverter
# import os
# from .logger import get_logger

# logger = get_logger(__name__)

# def classify_document(text: str) -> str:
#     """Classifies the document as either 'discharge_summary' or 'diagnostic_report' based on keywords."""
#     logger.info("Classifying document...")
#     text_lower = text.lower()
#     discharge_keywords = ["discharge", "admission", "course in hospital", "condition at discharge", "hospital course", "chief complaint"]
    
#     discharge_score = sum(1 for kw in discharge_keywords if kw in text_lower)
#     logger.debug(f"Document discharge score: {discharge_score}")
    
#     if discharge_score >= 1:
#         logger.info("Classified as discharge_summary")
#         return "discharge_summary"
#     logger.info("Classified as diagnostic_report")
#     return "diagnostic_report"

# def extract_text_from_pdf(pdf_path):
#     """Extracts text from PDF using Docling and inserts page break markers."""
#     logger.info(f"Extracting text from {pdf_path} using Docling...")
#     converter = DocumentConverter()
#     result = converter.convert(pdf_path)
#     doc = result.document

#     markdown_parts = []
#     current_page = 1
#     for item, _level in doc.iterate_items():
#         page_no = None
#         if hasattr(item, 'prov') and item.prov:
#             page_no = item.prov[0].page_no

#         if page_no and page_no > current_page:
#             # Insert page break marker
#             markdown_parts.append("\n\n<!-- PAGE_BREAK -->\n\n")
#             current_page = page_no

#         # Use the document's method to export individual items if possible.
#         if hasattr(item, 'export_to_markdown'):
#             try:
#                 # Some items might require the doc context
#                 markdown_parts.append(item.export_to_markdown(doc) + "\n")
#             except TypeError:
#                 markdown_parts.append(item.export_to_markdown() + "\n")
#         elif hasattr(item, 'text'):
#             markdown_parts.append(item.text + "\n")

#     logger.info(f"Finished extracting text from {pdf_path}. Total pages detected: {current_page}")
#     return "".join(markdown_parts)


import json

from docling.document_converter import DocumentConverter
import re
from collections import defaultdict
import base64

def extract_metadata(page_text):
    """
    Extract key metadata used for grouping.
    We use Age/Sex + Collection Date (DATE ONLY) as primary fingerprint.
    """

    # Extract Age/Sex
    age_sex_match = re.search(r'Age/Sex\s*:\s*(.*)', page_text)
    age_sex = age_sex_match.group(1).strip() if age_sex_match else "UNKNOWN"

    # Extract ONLY date part (ignore time)
    collection_match = re.search(
        r'Collection Date\s*:\s*([0-9]{2}-[A-Za-z]{3}-[0-9]{4})',
        page_text
    )
    collection_date = collection_match.group(1) if collection_match else "UNKNOWN"

    # Extract Lab No (optional for debugging)
    lab_no_match = re.search(r'Lab No\.\s*:\s*(.*)', page_text)
    lab_no = lab_no_match.group(1).strip() if lab_no_match else "UNKNOWN"

    print(f"Extracted Metadata - Age/Sex: {age_sex}, Collection Date: {collection_date}, Lab No: {lab_no}")

    return age_sex, collection_date

def group_pages_by_patient(pages_text):
    """
    Group pages belonging to same patient using strong fingerprint.
    """

    grouped = defaultdict(list)

    for page_number, page_text in enumerate(pages_text, start=1):
        age_sex, collection_date = extract_metadata(page_text)

        fingerprint = f"{age_sex}_{collection_date}"

        grouped[fingerprint].append((page_number, page_text))

    final_patient_texts = []

    print("\n📌 GROUPING SUMMARY")
    print("=" * 50)

    for patient_index, (key, page_data) in enumerate(grouped.items(), start=1):

        page_numbers = [str(page_num) for page_num, _ in page_data]
        merged_text = "\n\n".join([text for _, text in page_data])

        final_patient_texts.append(merged_text)

        age_sex, collection_date = key.split("_", 1)

        if len(page_numbers) > 1:
            print(f"🟢 Patient {patient_index} ({age_sex}, {collection_date})")
            print(f"   → Merged Pages: {', '.join(page_numbers)}")
        else:
            print(f"🔵 Patient {patient_index} ({age_sex}, {collection_date})")
            print(f"   → Single Page: {page_numbers[0]}")

        print("-" * 50)

    # print(f"\n🎯 Total Unique Patients Identified: {len(final_patient_texts)}\n")

    return final_patient_texts

def process_pdf_and_group_patients(pdf_path):
    """
    MAIN FUNCTION

    Input:
        pdf_path (str)

    Output:
        list of unique patient text blocks
    """

    # Step 1: Convert using Docling
    converter = DocumentConverter()
    result = converter.convert(pdf_path)

    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # Step 2: Extract page-wise text
    pages_text = []

    for i, page_num in enumerate(result.document.pages.keys(), start=1):
        page_content = result.document.export_to_markdown(page_no=page_num)
        pages_text.append(page_content)
        print(f"Processed page {i}")

    print(f"\n✅ Extracted {len(pages_text)} pages successfully!")

    # Step 3: Group pages by patient
    unique_patient_texts = group_pages_by_patient(pages_text)

    print(f"\n🎯 Total Unique Patients Identified: {len(unique_patient_texts)}")

    return unique_patient_texts, pdf_base64




from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
import os
from .logger import get_logger

def get_must_resources(artifact):
    if artifact == "DiagnosticReportRecord":
        return [
            "DocumentBundle", "DiagnosticReportRecord", "Patient", "Practitioner", 
            "Organization", "DiagnosticReportLab", "Observation", "DocumentReference"
        ]
    elif artifact == "DischargeSummaryRecord":
        return [
            "DocumentBundle", "DischargeSummaryRecord", "Patient", "Encounter", "Practitioner", 
            "Organization", "Condition", "Procedure", "Specimen", "Appointment", 
            "Observation", "DocumentReference"
        ]
    return []

logger = get_logger(__name__)

def classify_document(text: str) -> list:
    print("\n🔍 Classifying document type and required resources using LLM...")
    abdm_extraction_dictionary = {
        "ClinicalArtifacts": {
            "DischargeSummaryRecord": "A Clinical document used to represent the discharge summary record for ABDM HDE data set. It provides a single coherent clinical statement with clinical attestation of a patient's stay.",
            "DiagnosticReportRecord": "A Clinical Artifact representing diagnostic reports, including Radiology and Laboratory reports, that can be shared across the health ecosystem. It provides a single coherent statement of meaning with clinical attestation.",
        },
        "OtherResources": {
            "Patient": "This profile sets minimum expectations for the Patient resource to record, search, and fetch basic demographics and other administrative information about an individual patient.",
            "Practitioner": "This profile sets minimum expectations for the Practitioner resource to record, search, and fetch basic demographics and other administrative information about an individual practitioner.",
            "PractitionerRole": "This profile sets minimum expectations for the PractitionerRole resource to record, search, and fetch the practitioner role for a practitioner within an organization.",
            "Organization": "This profile sets minimum expectations for the Organization resource to record, search, and fetch information about a healthcare organization.",
            "Encounter": "This profile sets minimum expectations for the Encounter resource to record, search, and fetch basic encounter information for an individual patient, such as inpatient or outpatient status.",
            "Condition": "This profile sets minimum expectations for the Condition resource to record, search, and fetch a list of conditions, problems, or diagnoses associated with a patient.",
            "Procedure": "This profile sets minimum expectations for the Procedure resource to record, search, and fetch details of clinical actions or procedures performed on or with a patient.",
            "Observation": "Represents an individual laboratory test and result value, or a finding. It sets minimum expectations for the Observation resource to record, search, and fetch clinical observations associated with a patient.",
            "DiagnosticReportLab": "This profile represents the set of information related to the Laboratory diagnosis report generated by laboratory services like CBC, Lipid Panel, Urinalysis, etc.",
            "DiagnosticReportImaging": "This profile represents the set of information related to the Imaging diagnosis report generated by imaging services like Radiology, Cardiology, or Endoscopy.",
            "ObservationVitalSigns": "This profile sets minimum expectations for the Observation resource to record, search, and fetch vital signs like Blood Pressure, Heart Rate, and Temperature.",
            "ObservationBodyMeasurement": "This profile sets minimum expectations for the Observation resource to record, search, and fetch physical metrics such as Body Weight, Height, and BMI.",
            "ObservationGeneralAssessment": "This profile sets minimum expectations for the ObservationGeneralAssessment to record, search, and fetch the details of the general health assessment or qualitative scores of a patient.",
            "ObservationLifestyle": "This profile sets minimum expectations for the ObservationLifestyle to record, search, and fetch details of the lifestyle of the patient (e.g., smoking or alcohol status).",
            "ObservationPhysicalActivity": "This profile sets minimum expectations for the ObservationPhysicalActivity to record, search, and fetch details of the physical movement and exercise levels of the patient.",
            "ObservationWomenHealth": "This profile sets minimum expectations for the Observation resource to record specific metrics related to obstetric and gynecological history, such as LMP and pregnancy status.",
            "MedicationRequest": "This resource is used to record a patient's medication prescription or order. It sets minimum expectations to record, search, and fetch medications associated with a patient.",
            "MedicationStatement": "Used to record a patient's medication information, specifically medications consumed by the patient in the past, present, or future.",
            "Medication": "This profile sets the minimum expectations for the medication resource in order to store various details about a given medicine (ingredients, form, etc.).",
            "AllergyIntolerance": "Records the risk of harmful or undesirable physiological response unique to an individual associated with exposure to a substance (food, drug, or material).",
            "FamilyMemberHistory": "This profile sets minimum expectations to record, search, and fetch significant health conditions of the patient's relatives for risk assessment.",
            "Immunization": "This profile sets minimum expectations for the Immunization resource to record, fetch, and search immunization history and vaccine administration associated with a patient.",
            "CarePlan": "This profile sets minimum expectations for the CarePlan resource to record, search, and fetch assessment and plan of treatment data associated with a patient.",
            "ServiceRequest": "A record of a request for service such as diagnostic investigations, treatments, or referrals to be performed.",
            "Specimen": "This profile sets minimum expectations for the Specimen resource to record details about a biological sample (blood, urine, etc.) used in diagnostic testing.",
            "ImagingStudy": "Representation of the content produced in a DICOM imaging study, comprising a set of series and instances (images) acquired in a common context.",
            "DocumentReference": "This profile sets minimum expectations for searching and fetching patient documents, including clinical notes, using a reference to a document.",
            "Binary": "This profile sets minimum expectations for the Binary resource to search and fetch the data of a single raw artifact (e.g., PDF or scanned image) in its native format.",
            "Media": "This profile sets minimum expectations for the Media resource to search and fetch media like a photo, video, or audio recording acquired or used in healthcare."
        }
    }
    
    # The Optimized Prompt
    prompt = f"""
    ACT AS an expert ABDM FHIR Data Architect.

    TASK:
    1. Analyze the [Extracted Text] and select the most appropriate key from [ClinicalArtifacts].
    2. Select any relevant keys from [RemainingResources] that are explicitly mentioned in the text. 
    - DO NOT select resources that are already part of the Mandatory Base for your chosen artifact.
    - The number of selected resources can be zero or more depending on the text content.

    INPUT:
    [Extracted Text]: 
    {text}

    [Dictionary]:
    {json.dumps(abdm_extraction_dictionary, indent=2)}

    OUTPUT FORMAT:
    Return ONLY a valid JSON object. No pre-amble or markdown blocks.
    {{
        "clinical_artifact": "SelectedKeyFromClinicalArtifacts",
        "selected_other_resources": ["Key1", "Key2", ...]
    }}
    """

    # Invoke the LLM with a fresh client (token baked in at construction)
    from .llm_requirements import get_llm
    fresh_llm = get_llm()
    response = fresh_llm.invoke(prompt)
    raw_output = response.content.strip()

    # Parsing Logic
    try:
        # Clean up potential markdown formatting
        clean_json = re.sub(r'^```json\s*|```$', '', raw_output, flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
        
        # Final Variables
        clinical_artifact = data.get("clinical_artifact", "")
        must_resources = get_must_resources(clinical_artifact)
        selected_other_resources = data.get("selected_other_resources", [])
        selected_other_resources = [res for res in selected_other_resources 
                            if res not in must_resources]
        
        # Logging the results
        print(f"--- Extraction Complete ---")
        print(f"Artifact: {clinical_artifact}")
        print(f"Must Resources (Fixed): {must_resources}")
        print(f"Other Selected Resources: {selected_other_resources}")

    except Exception as e:
        print(f"Error parsing LLM output: {e}")
        print(f"Raw response was: {raw_output}")

    
    return clinical_artifact, must_resources, selected_other_resources


def extract_text_from_abdm_pdf(pdf_path):
    """Extracts text from PDF using Docling and inserts page break markers."""
    logger.info(f"Extracting text from {pdf_path} using Docling...")

    unique_patient_lists, pdf_base64 = process_pdf_and_group_patients(pdf_path)

    return unique_patient_lists, pdf_base64

