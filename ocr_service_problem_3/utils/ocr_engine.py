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
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
import os
from .logger import get_logger

logger = get_logger(__name__)



# Deterministic mapping of mandatory resources based on the selected artifact
def get_must_resources(artifact):
    if artifact == "InsurancePlanBundle":
        return [
            "InsurancePlanBundle", "InsurancePlan", "Organization", "Condition", "DocumentReference"
        ]

    return []

import re
def select_nhcx_resources(distilled_text):
    nhcx_extraction_dictionary = {
        "NHCXArtifact": {
            "InsurancePlanBundle": "This profile is based on a Bundle of type collection, providing a description of a health insurance package that consists of a comprehensive list of covered benefits (referred to as the product), associated costs (known as the plan), and supplementary details regarding the offering, such as ownership and administration."
        },
        "OtherResources": {
            "InsurancePlan": "Represents the health insurance product/plan provided by an organization. It describes the contractual arrangement, covered benefits (product), and cost-sharing structures (plan) offered to consumers.",
            "Claim": "A provider-issued list of professional services and products provided, or to be provided, to a patient. It is sent to an insurer for reimbursement, preauthorization, or predetermination.",
            "ClaimResponse": "This resource provides the adjudication results from a payer (insurer) in response to a Claim resource, detailing payments, rejections, and amounts for each line item.",
            "Coverage": "This profile sets the minimum expectations for the Coverage resource to record and search for insurance plan details for a patient, linking the beneficiary to a specific insurance policy.",
            "CoverageEligibilityRequest": "Used by healthcare providers to check with a payer whether a patient has insurance coverage for specific services and to discover the terms of that coverage.",
            "CoverageEligibilityResponse": "The response from a payer providing eligibility and plan details (like remaining deductibles or authorization requirements) following a CoverageEligibilityRequest.",
            "Task": "In the NHCX context, this resource is used to convey information related to payments, status checks during claim adjudication, and facilitating the request or transmission of supporting documentation.",
            "Communication": "A record of an exchange of information between a sender and a receiver (e.g., provider and payer), used to document any communication that occurred during the claims process.",
            "CommunicationRequest": "A record of a request for a communication to take place, such as a payer requesting additional documents from a provider to process a claim.",
            "PaymentNotice": "A notification that a payment has been made or a payment status has changed, confirming to the payee that funds have been transferred.",
            "PaymentReconciliation": "Used to reconcile a bulk payment (e.g., a single bank transfer) against multiple individual claims, providing a detailed breakdown of the total amount settled.",
            "Organization": "Sets minimum expectations for the Organization resource to record, search, and fetch information about healthcare organizations, insurers, or TPAs.",
            "Patient": "Sets minimum expectations for the Patient resource to record, search, and fetch basic demographics and administrative information about an individual beneficiary.",
            "Practitioner": "Sets minimum expectations for the Practitioner resource to record, search, and fetch demographics and administrative info about a healthcare professional.",
            "PractitionerRole": "Describes the specific roles, specialties, and locations of a practitioner within an organization (e.g., a surgeon at a specific hospital).",
            "Condition": "Used to record a list of conditions, problems, or diagnoses associated with a patient, often used in claims to justify medical necessity.",
            "Procedure": "Records details of clinical actions or procedures performed on a patient, which are mapped to line items in a claim for reimbursement.",
            "DocumentReference": "Provides a reference to a document (like a clinical note or lab report) to support the claim, acting as a pointer to the actual data artifact.",
            "Binary": "Allows for the storage and retrieval of raw digital content (like a scanned PDF of a diagnostic report or an insurance brochure) in its native format.",
        }
        }
    
    prompt = f"""
    ACT AS an expert NHCX FHIR Data Architect.

    **TASK:**
    Identify and select relevant FHIR resources from the `OtherResources` section of the provided `nhcx_extraction_dictionary` based **ONLY** on the clinical and administrative information present in the `[Extracted Text]`.

    **RULES:**
    1. **Source Strictly from Text**: Only select a resource if the `[Extracted Text]` contains specific data points (e.g., policy numbers, diagnosis names, procedure names, insurer names, patient names) that belong in that resource profile.
    2. **Exclude Mandatory Base**: DO NOT select resources that are already part of the Mandatory Base for the primary artifact (e.g., if the primary is `InsurancePlanBundle`, do not list `InsurancePlan` or `Organization` as "Other" as they are already core components).
    3. **Accuracy**: If the text mentions a "Diagnosis," select `Condition`. If it mentions "Surgery," select `Procedure`. If it mentions "Co-pay/Policy details," select `Coverage`. If no relevant information is found for a category, return an empty list.

    **INPUT:**
    [Extracted Text]: 
    {distilled_text}

    [Dictionary]:
    {json.dumps(nhcx_extraction_dictionary, indent=2)}

    **OUTPUT FORMAT:**
    Return ONLY a valid JSON object. No pre-amble, markdown blocks, or explanation.
    {{
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
        clinical_artifact = "InsurancePlanBundle"  # This is fixed based on the problem statement
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

import math
from langchain_core.messages import HumanMessage

import math
from langchain_core.messages import HumanMessage

def distill_insurance_text(full_text):
    # 1. Divide text with OVERLAP to prevent data loss at boundaries
    num_chunks = 8 # Increased chunks slightly for better focus
    overlap_size = 2000 # ~500 words overlap
    
    total_len = len(full_text)
    chunk_size = math.ceil(total_len / num_chunks)
    
    chunks = []
    for i in range(num_chunks):
        start = max(0, i * chunk_size - overlap_size)
        end = min(total_len, (i + 1) * chunk_size)
        chunks.append(full_text[start:end])
    
    distilled_outputs = []
    
    # 2. The "Lossless" Distillation Prompt
    # This prompt focuses on capturing facts rather than filling a form
    distill_prompt_template = """
    ACT AS an Insurance Policy Underwriter. Your goal is to simplify this policy text into a high-density "Fact Sheet" for a FHIR Architect.

    TASK:
    Scan the text below and extract EVERY technical detail related to insurance policy parameters. 

    STRICT EXTRACTION RULES:
    1. CAPTURE ALL NUMERICS: Every INR value, Percentage (%), Day limit, or Age limit must be preserved.
    2. PRESERVE TABLES: If you find a benefit table or a list of limits (e.g., Room Rent, ICU), recreate it as a Markdown Table.
    3. NO NARRATIVE: Do not use filler words like "This section discusses...". Just state the facts.
    4. NO "NOT SPECIFIED": If a specific category (like TPA) isn't there, simply MOVE ON. Do not write "Not specified".
    5. TERMINOLOGY: Keep specific medical/insurance terms (e.g., "Pre-existing Disease", "OPD", "Co-payment", "Waiting Period").
    6. INSURANCE PLAN DETAILS: Don't miss on extracting details about the insurance plan, covered benefits, costs, and any specific limits or conditions mentioned.

    TEXT CONTENT:
    {chunk_text}

    OUTPUT:
    Provide a condensed version of the relevant data found above. If the text is purely legal preamble with no specific limits or benefits, return: [NO_INSURANCE_DATA]
    """

    print(f"🚀 Distilling {total_len} characters with overlap...")

    for i, chunk in enumerate(chunks):
        print(f"📝 Processing Section {i+1}/{num_chunks}...")
        
        try:
            from .llm_requirements import get_llm
            fresh_llm = get_llm()
            response = fresh_llm.invoke([HumanMessage(content=distill_prompt_template.format(chunk_text=chunk))])
            content = response.content.strip()
            
            if "[NO_INSURANCE_DATA]" not in content:
                distilled_outputs.append(f"### SECTION {i+1} SUMMARY ###\n{content}")
        
        except Exception as e:
            print(f"❌ Error in Section {i+1}: {e}")

    # 3. Join the distilled facts
    final_distilled_text = "\n\n".join(distilled_outputs)
    
    print(f"✅ Distillation complete.")
    print(f"Original: {total_len} chars | Distilled: {len(final_distilled_text)} chars")
    return final_distilled_text


def extract_distilled_text_from_nhcx_pdf(pdf_path):
    """Extracts text from PDF using Docling and inserts page break markers."""
    logger.info(f"Extracting text from {pdf_path} using Docling...")

    source = pdf_path

    # 1. Initialize the converter
    converter = DocumentConverter()

    # 2. Convert the entire document in one go (Preserves internal structure)
    result = converter.convert(source)

    # 3. Access individual pages from the result object
    # Docling's 'result.document' contains the structured data
    pages_text = []

    # If you want to iterate through the document's pages as Markdown:
    # Note: Docling usually exports the whole doc, but we can filter by page index
    for page_num, page in result.document.pages.items():
        # This gets the content specifically associated with this page
        page_content = result.document.export_to_markdown(page_no=page_num)
        pages_text.append(page_content)
        print(f"Processed page {page_num}")

    
    extracted_text = "\n".join(pages_text)

    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    
    distilled_text = distill_insurance_text(extracted_text)


    return distilled_text, pdf_base64