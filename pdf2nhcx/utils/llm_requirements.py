import json
import uuid
import operator
from typing import TypedDict, List, Dict, Annotated, Any
from langgraph.graph import StateGraph, END
# from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
import os
from datetime import datetime, timezone


# ---------------- STATE ----------------
class AgentState(TypedDict, total=False):
    text: str
    id_registry: Dict[str, Any]
    final_resources: Annotated[List[dict], operator.add]
    rulebook_paths: Dict[str, str]
    model: str          # frontend model selector value, propagated through the graph

# ---------------- LLM ----------------
# llm = ChatOllama(model="qwen2.5:latest", temperature=0)
# llm = ChatOllama(model="deepseek-coder-v2", temperature=0)

# Dependency graph - what each resource needs
RESOURCE_DEPENDENCIES = {
    "Organization": [],
    "Binary": [],
    "DocumentReference": ["Binary"],
    "InsurancePlan": ["Organization"],
    "HealthcareService": ["InsurancePlan"],
    "InsurancePlanBundle": ["InsurancePlan", "Organization"] 
    # Notice: No Patient, No Coverage, No Claim needed here!
}

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


from dotenv import load_dotenv
import os

# Load .env for local development (Docker injects vars via env_file)
_here = os.path.dirname(__file__)
for _candidate in [
    os.path.join(_here, "../../.env"),
    os.path.join(_here, "../.env"),
    "/.env",
    "/app/.env",
]:
    if os.path.isfile(_candidate):
        load_dotenv(dotenv_path=_candidate)
        break
else:
    load_dotenv()

_PROJECT_ID = os.getenv("PROJECT_ID", "tanuh-bcd-questionnaire")
_REGION     = os.getenv("REGION", "global")
_ENDPOINT   = os.getenv("ENDPOINT", "aiplatform.googleapis.com")

# ── Authentication ───────────────────────────────────────────────────────────
# Priority 1: Google Application Default Credentials (ADC)
#   - Works automatically on GCP VMs via metadata server
#   - Run 'gcloud auth application-default login' for local dev
# Priority 2: API_KEY from .env (for local/testing)

_cached_credentials = None

def _get_vertex_token() -> str:
    """Return a fresh OAuth2 access token via ADC, or fall back to API_KEY."""
    global _cached_credentials
    try:
        import google.auth
        import google.auth.transport.requests
        
        if _cached_credentials is None:
            _cached_credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
        _cached_credentials.refresh(google.auth.transport.requests.Request())
        print("✅ Fresh token obtained via Google ADC")
        return _cached_credentials.token
    except Exception as e:
        fallback = os.getenv("API_KEY", "")
        # If the fallback key starts with 'AQ.' it's likely a short-lived token, 
        # but we use it as-is if ADC fails.
        print(f"⚠️  ADC unavailable ({e}), falling back to API_KEY env var")
        return fallback

# ── Model ──────────────────────────────────────────────────────────────────
MODEL_MAP = {
    "gemma4": "publishers/google/models/gemma-4-26b-a4b-it-maas",
}
_DEFAULT_MODEL = "gemma4"

def get_llm(model: str = _DEFAULT_MODEL):
    """Return a ChatGoogleGenerativeAI instance for Gemma 4."""
    vertex_model = MODEL_MAP.get(model, MODEL_MAP[_DEFAULT_MODEL])
    print(f"🤖 Using model: {vertex_model}")

    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=vertex_model,
        project=_PROJECT_ID,
        location="global",   # Gemma 4 MaaS is only available via the global endpoint
        temperature=0.7,
        max_output_tokens=8192,
        credentials=_cached_credentials,
    )

def check_llm_health():
    """Verify that we can at least get a token or the API_KEY is set."""
    token = _get_vertex_token()
    if token and len(token) > 10:
        return True, "ok"
    return False, "auth_failed"

def get_must_resources(artifact):
    if artifact == "InsurancePlanBundle":
        return [
            "InsurancePlanBundle", "InsurancePlan", "Organization", "Condition", "DocumentReference"
        ]

    return []
# ---------------- JSON EXTRACTION ----------------
def extract_json(text: str):
    if not text or not text.strip():
        return None
    
    # Remove markdown code blocks
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    decoder = json.JSONDecoder()
    idx = 0
    
    while idx < len(text):
        try:
            obj, end = decoder.raw_decode(text[idx:])
            if isinstance(obj, str):
                try:
                    obj = json.loads(obj)
                except:
                    pass
            return obj
        except json.JSONDecodeError:
            idx += 1
    return None

# ---------------- NORMALIZE FUNCTIONS ----------------
def ensure_id(resource):
    if not isinstance(resource, dict):
        return resource
    if "id" not in resource or not resource["id"]:
        resource["id"] = str(uuid.uuid4())
    return resource

def normalize_resource_output(res, resource_type):
    """Convert any input to single dict or list of dicts."""
    if isinstance(res, str):
        parsed = extract_json(res)
        if parsed:
            res = parsed
    
    if isinstance(res, dict):
        return [res]
    elif isinstance(res, list):
        return res
    else:
        # Create minimal resource
        return [{
            "resourceType": resource_type,
            "id": str(uuid.uuid4()),
            "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{resource_type}"]}
        }]

def get_single_resource(resources_list, resource_type):
    """Get first valid resource from list."""
    for res in resources_list:
        if isinstance(res, dict) and res.get("resourceType") == resource_type:
            return res
    # Return first item or create new
    if resources_list:
        res = resources_list
        if isinstance(res, dict):
            res["resourceType"] = resource_type
            return res
    return {
        "resourceType": resource_type,
        "id": str(uuid.uuid4()),
        "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{resource_type}"]}
    }

# ---------------- CORE AGENT FUNCTION ----------------
def run_extraction_agent(state: AgentState, resource_type: str, model: str = _DEFAULT_MODEL):
    rulebook_path = state['rulebook_paths'].get(resource_type)
     # Load rulebook content
    rulebook_content = ""
    if rulebook_path and os.path.exists(rulebook_path):
        with open(rulebook_path, 'r', encoding='utf-8') as f:
            rulebook_content = f.read()
    
    prompt = f'''
    ACT AS an expert NHCX FHIR Data Architect. 

EXTRACT ONLY a valid HL7 FHIR R4 {resource_type} resource (or a Bundle containing multiple resources) from the provided technical insurance text.

RULEBOOK (STRUCTURE GUIDANCE):
{rulebook_content}

INSURANCE POLICY TEXT (DISTILLED):
{state["text"]}

STRICT REQUIREMENTS (NON-NEGOTIABLE):
• Output MUST be valid JSON only.
• Output MUST start with "{{" or "[".
• DO NOT output markdown code fences (e.g., no ```json), no preamble, no comments, and no explanations.
• DO NOT hallucinate or infer missing data. If a field (like TPA name or specific Co-pay) is not in the text, OMIT IT.
• Extract ONLY information explicitly present in the provided text.
• Omit any field whose value is not clearly present.

NHCX + ABDM CONSTRAINTS:
• Conform to NHCX (National Health Claims Exchange) and ABDM profiling expectations.
• Resource Type: If extracting multiple linked resources, wrap them in a Bundle of type "collection".
• Identifiers: Every resource MUST contain an "id" as a UUID string (RFC-4122 format).
• Use the Product UIN (e.g., ADIHLGP22023V032122) as the business 'identifier' for the InsurancePlan resource.
• DO NOT include empty objects, empty arrays, or null values.

TERMINOLOGY & CODING RULES:
• Use IRDAI Standard Exclusion Codes (e.g., Excl03, Excl04) for exclusions.
• Use SNOMED CT for clinical conditions (e.g., Cancer, Myocardial Infarction) if coding is required.
• System URLs:
  - IRDAI Exclusions -> [https://irdai.gov.in/exclusions](https://irdai.gov.in/exclusions)
  - SNOMED CT -> [http://snomed.info/sct](http://snomed.info/sct)
• If no explicit code exists in the text, use only the "text" attribute within the CodeableConcept.
• NEVER fabricate codes.

REFERENCE & LINKING RULES:
• Use URN UUID references for internal Bundle linking: "reference": "urn:uuid:<uuid-here>".
• The InsurancePlan resource MUST reference the 'Organization' (Payer) via the .ownedBy element.
• The InsurancePlan resource SHOULD reference 'Location' resources for network/excluded hospitals if data is present.
• Only create references explicitly justified by the text.

DATA ACCURACY RULES:
• Preserve numeric precision exactly (e.g., 7.5 dioptres, 150% pay-out).
• Preserve all currency values (INR) and time-based limits (Waiting Periods) exactly.
• Ensure "Exclusions" are mapped correctly to either the general plan level or specific benefit level.

OUTPUT FORMAT:
Return ONLY the JSON resource(s) for {resource_type}.
'''

    try:
        fresh_llm = get_llm(state.get('model', _DEFAULT_MODEL))
        response = fresh_llm.invoke([HumanMessage(content=prompt)])
        raw_output = response.content.strip()
        print(f"\n🔍 Raw output for {resource_type}:\n{raw_output[:500]}...")
        
        parsed = extract_json(raw_output)
        if parsed:
            return parsed
        
        print(f"⚠️ Could not parse JSON for {resource_type}")
        
    except Exception as e:
        print(f"❌ Error for {resource_type}: {e}")
    
    # Fallback minimal resource
    return [{
        "resourceType": resource_type,
        "id": str(uuid.uuid4()),
        "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{resource_type}"]}
    }]



_node_cache = {}

def create_insurance_node(resource_type: str):
    """
    Factory function for NHCX Insurance resources.
    Handles Bundle creation for InsurancePlanBundle and individual financial resources.
    """
    if resource_type in _node_cache:
        return _node_cache[resource_type]
    
    def node(state: AgentState):
        # ✅ SPECIAL CASE: InsurancePlanBundle is a Bundle resource
        model = state.get('model', _DEFAULT_MODEL)
        if resource_type == "InsurancePlanBundle":
            actual_resource_type = "Bundle"
            is_insurance_bundle = True
        else:
            actual_resource_type = resource_type
            is_insurance_bundle = False
        
        # Run the extraction agent (using the prompt we defined previously)
        resources = run_extraction_agent(state, actual_resource_type, model)
        resources = normalize_resource_output(resources, actual_resource_type)
        
        if isinstance(resources, list):
            safe_resources = []
            # Bundle should typically be singular, but constituent resources can be multiple
            max_items = 1 if is_insurance_bundle else 15 
            for res in resources[:max_items]:
                if isinstance(res, dict):
                    if res.get("resourceType") != actual_resource_type:
                        res["resourceType"] = actual_resource_type
                    
                    # ✅ NHCX Profile forcing
                    if is_insurance_bundle:
                        res.setdefault('meta', {})['profile'] = [
                            "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle"
                        ]
                        res['type'] = 'collection' # Mandatory for NHCX InsurancePlanBundle
                    
                    res = ensure_id(res)
                    
                    # Add Payer/Organization reference logic
                    # If we have a payer_id in registry, link the InsurancePlan to it
                    payer_id = state['id_registry'].get('organization_id')
                    if payer_id and resource_type == "InsurancePlan":
                        res['ownedBy'] = {'reference': f'urn:uuid:{payer_id}'}
                    
                    safe_resources.append(res)
            result = safe_resources
        else:
            result = get_single_resource([resources], actual_resource_type)
            result = ensure_id(result)
            
            # Profile forcing for single object return
            if is_insurance_bundle:
                result.setdefault('meta', {})['profile'] = [
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle"
                ]
                result['type'] = 'collection'
            
            # Linkage logic for single resource
            payer_id = state['id_registry'].get('organization_id')
            if payer_id and resource_type == "InsurancePlan":
                result['ownedBy'] = {'reference': f'urn:uuid:{payer_id}'}
        
        # ✅ ID REGISTRATION LOGIC
        # Store refs differently for the bundle vs individual resources
        if isinstance(result, list):
            state['id_registry'][f'{resource_type.lower()}_refs'] = [
                {'reference': f'urn:uuid:{r["id"]}'} for r in result
            ]
            # If it's the primary organization, save its ID specifically for linking
            if resource_type == "Organization" and len(result) > 0:
                state['id_registry']['organization_id'] = result[0]['id']
        else:
            state['id_registry'][f'{resource_type.lower()}_id'] = result['id']
            if resource_type == "Organization":
                state['id_registry']['organization_id'] = result['id']
        
        count = len(result) if isinstance(result, list) else 1
        resource_display = "Bundle" if is_insurance_bundle else resource_type
        print(f"✅ {resource_type}: {count} {resource_display}")
        
        return {"final_resources": [result] if isinstance(result, list) else [result]}
    
    node.__name__ = f"{resource_type.lower()}_node"
    _node_cache[resource_type] = node
    return node

# ✅ CLEAR CACHE BETWEEN WORKFLOWS (if needed)
def clear_node_cache():
    global _node_cache
    _node_cache = {}



def insurance_assembly_node(state):
    """
    Assembles the final NHCX InsurancePlanBundle.
    Structure: InsurancePlan FIRST, supporting resources MIDDLE, DocumentReference/Binary LAST.
    """
    import uuid
    from datetime import datetime, timezone

    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle"]
        },
        "type": "collection", # NHCX InsurancePlanBundle must be a collection
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": []
    }
    
    # ✅ STEP 1: Find and Add the InsurancePlan FIRST
    # This serves as the 'anchor' of the bundle
    plan_found = False
    seen_ids = set()

    for resources_list in state["final_resources"]:
        if isinstance(resources_list, list):
            for res in resources_list:
                if isinstance(res, dict) and res.get('resourceType') == 'InsurancePlan':
                    bundle["entry"].insert(0, {
                        "fullUrl": f"urn:uuid:{res['id']}",
                        "resource": res
                    })
                    seen_ids.add(res['id'])
                    plan_found = True
                    print(f"✅ InsurancePlan ({res['id']}) added FIRST")
                    break
        if plan_found:
            break

    # ✅ STEP 2: Categorize remaining resources
    # We want to keep DocumentReference and Binary for the end
    supporting_entries = []
    attachment_entries = []
    
    for resources_list in state["final_resources"]:
        if not isinstance(resources_list, list):
            resources_list = [resources_list]
            
        for r in resources_list:
            if not isinstance(r, dict) or r.get('id') in seen_ids:
                continue
            
            resource_type = r.get('resourceType')
            entry = {
                "fullUrl": f"urn:uuid:{r['id']}",
                "resource": r
            }
            
            # Group Binary and DocumentReference to be added last
            if resource_type in ['DocumentReference', 'Binary']:
                attachment_entries.append(entry)
            else:
                supporting_entries.append(entry)
            
            seen_ids.add(r['id'])

    # ✅ STEP 3: Assemble the entries in order
    # 1. (Already added InsurancePlan at index 0)
    # 2. Add Supporting Resources (Organization, Location, HealthcareService)
    bundle["entry"].extend(supporting_entries)
    
    # 3. Add Attachments (The original PDF data) LAST
    bundle["entry"].extend(attachment_entries)

    print(f"✅ NHCX Bundle Assembled: {len(bundle['entry'])} total resources.")
    print(f"📊 Breakdown: 1 InsurancePlan, {len(supporting_entries)} Supporting, {len(attachment_entries)} Attachments.")
    
    return {"final_resources": [bundle]}
def build_insurance_workflow(clinical_artifact: str, selected_other_resources: List[str], rulebook_paths: Dict[str, str]):
    # 1. Get mandatory resources for InsurancePlanBundle (Organization, InsurancePlan, etc.)
    must_resources = get_must_resources(clinical_artifact)
    
    # 2. Filter out duplicates
    selected_other_resources = [res for res in selected_other_resources if res not in must_resources]
    all_resources = list(set(must_resources + selected_other_resources))
    
    # Ensure the main artifact (InsurancePlanBundle) is included if not already
    if clinical_artifact not in all_resources:
        all_resources.append(clinical_artifact)
    
    print(f"📋 NHCX Workflow for {clinical_artifact}: {all_resources}")
    
    workflow = StateGraph(AgentState)
    
    # ✅ CREATE NODES
    created_nodes = set()
    for resource in all_resources:
        node_name = resource.lower()
        if node_name not in created_nodes:
            # Using the insurance factory function we created earlier
            node_func = create_insurance_node(resource) 
            workflow.add_node(node_name, node_func)
            created_nodes.add(node_name)
            print(f"✅ Added node: {node_name}")
    
    # 3. Topological sort (Uses your RESOURCE_DEPENDENCIES)
    def topological_sort(resources):
        visited = set()
        order = []
        def visit(resource):
            if resource in visited: return
            visited.add(resource)
            for dep in RESOURCE_DEPENDENCIES.get(resource, []):
                if dep in resources:
                    visit(dep)
            order.append(resource)
        for resource in resources:
            visit(resource)
        return order
    
    resource_order = topological_sort(all_resources)
    print(f"📊 Execution order: {[r.lower() for r in resource_order]}")
    
    # 4. Create Edges
    for i in range(len(resource_order) - 1):
        current = resource_order[i].lower()
        next_node = resource_order[i + 1].lower()
        workflow.add_edge(current, next_node)
        print(f"➡️  Edge: {current} → {next_node}")
    
    # 5. Assembly Node (Using the insurance_assembly_node created earlier)
    workflow.add_node("assembly", insurance_assembly_node)
    last_node = resource_order[-1].lower()
    workflow.add_edge(last_node, "assembly")
    workflow.add_edge("assembly", END)
    
    # ✅ FIX: Dynamic Entry Point
    # In NHCX, 'organization' (the Payer) is usually the best starting point
    if "organization" in created_nodes:
        workflow.set_entry_point("organization")
    else:
        # Fallback to the first resource in the sorted order
        workflow.set_entry_point(resource_order[0].lower())
    
    return workflow.compile(), all_resources

import json

def sanitize_fhir_resource(resource):
    res_type = resource.get("resourceType")
    if not res_type: return

    # Recurse into nested Bundles
    if res_type == "Bundle":
        for entry in resource.get("entry", []):
            if "resource" in entry:
                sanitize_fhir_resource(entry["resource"])
        return

    # 1. 'entry' is ONLY valid on Bundle
    if res_type != "Bundle" and "entry" in resource:
        del resource["entry"]
        
    # Remove hallucinated fields
    if "entity" in resource: del resource["entity"]
    if "permission" in resource: del resource["permission"]
        
    # 2. 'type' formatting
    if res_type in ["Organization", "InsurancePlan"] and "type" in resource:
        if isinstance(resource["type"], str):
            code = "pay" if res_type == "Organization" else "medical"
            resource["type"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": code, "display": resource["type"]}]}]
        elif isinstance(resource["type"], dict):
            resource["type"] = [resource["type"]]
            
    if res_type == "DocumentReference" and "type" in resource:
        if isinstance(resource["type"], list):
            resource["type"] = resource["type"][0] if len(resource["type"]) > 0 else {}
            
    # 3. 'ownedBy' in InsurancePlan must be a Reference (an object), not an array.
    if res_type == "InsurancePlan" and "ownedBy" in resource:
        if isinstance(resource["ownedBy"], list):
            resource["ownedBy"] = resource["ownedBy"][0] if len(resource["ownedBy"]) > 0 else {}

    # 4. Clean up InsurancePlan hallucinations
    if res_type == "InsurancePlan":
        if "benefit" in resource: del resource["benefit"]
        if "exclusion" in resource: del resource["exclusion"]
        for cov in resource.get("coverage", []):
            if "description" in cov: del cov["description"]
            if "type" not in cov:
                cov["type"] = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/insurance-plan-type", "code": "medical"}]}
            if "benefit" not in cov or not isinstance(cov["benefit"], list) or len(cov["benefit"]) == 0:
                cov["benefit"] = [{"type": {"coding": [{"code": "benefit"}]}}]
        if "identifier" in resource and isinstance(resource["identifier"], list):
            for ident in resource["identifier"]:
                if ident.get("system") == "uin":
                    ident["system"] = "https://irdai.gov.in/uin"

    # 5. Fix missing required fields
    if res_type == "Procedure":
        if "status" not in resource: resource["status"] = "completed"
        if "subject" not in resource: resource["subject"] = {"reference": "Patient/1"}
            
    if res_type == "Coverage":
        if "status" not in resource: resource["status"] = "active"
        if "beneficiary" not in resource: resource["beneficiary"] = {"reference": "Patient/1"}
        if "payor" not in resource: resource["payor"] = [{"reference": "Organization/1"}]
            
    if res_type == "Organization":
        if "name" not in resource and "identifier" not in resource:
            resource["name"] = "Unknown Organization"
            
    # 6. Condition category codes
    if res_type == "Condition" and "category" in resource and isinstance(resource["category"], list):
        for cat in resource["category"]:
            if "coding" in cat and isinstance(cat["coding"], list):
                for coding in cat["coding"]:
                    if coding.get("system") == "http://terminology.hl7.org/CodeSystem/condition-category" and coding.get("code") == "encounter-related":
                        coding["code"] = "encounter-diagnosis"

def clean_and_reorder_bundle(bundle):
    entries = bundle.get("entry", [])
    
    # Identify indices for removal and relocation
    composition_entry = None
    cleaned_entries = []

    for entry in entries:
        resource = entry.get("resource", {})
        res_type = resource.get("resourceType")

        # Map ABDM Profile names back to standard FHIR R4 resource types
        if res_type in ["DiagnosticReportRecord", "DischargeSummaryRecord", "WellnessRecord", "HealthDocumentRecord", "PrescriptionRecord", "InsurancePlanBundle"]:
            resource["resourceType"] = "Composition"
            res_type = "Composition"
        elif res_type in ["DiagnosticReportLab", "DiagnosticReportImaging"]:
            resource["resourceType"] = "DiagnosticReport"
            res_type = "DiagnosticReport"
        elif res_type in ["ObservationVitalSigns", "ObservationLifestyle", "ObservationWomenHealth", "ObservationPhysicalActivity", "ObservationGeneralAssessment", "ObservationBodyMeasurement"]:
            resource["resourceType"] = "Observation"
            res_type = "Observation"
            
        # Clean up common LLM hallucinations
        sanitize_fhir_resource(resource)

        # Task A: Find the Composition to move it later
        if res_type == "Composition":
            composition_entry = entry
        
        # Task B: Identify and skip the fake 'DocumentBundle' resource
        elif res_type == "DocumentBundle":
            print(f"🗑️ Removing invalid 'DocumentBundle' resource (ID: {resource.get('id')})")
            continue
            
        else:
            cleaned_entries.append(entry)

    # Task C: Reassemble with Composition at the very beginning
    if composition_entry:
        final_entries = [composition_entry] + cleaned_entries
        bundle["entry"] = final_entries
    else:
        bundle["entry"] = cleaned_entries

    return bundle

def document_reference_node(bundle, pdf_base64):

    updated = False

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})

        if resource.get("resourceType") == "DocumentReference":

            # If content does NOT exist → create it
            if "content" not in resource or not resource["content"]:

                resource["content"] = [
                    {
                        "attachment": {
                            "contentType": "application/pdf",
                            "data": pdf_base64
                        }
                    }
                ]
                print(resource["content"][0]['attachment']['data'])
                # print("Created new content block")

            else:
                # Content exists → update attachment
                attachment = resource["content"][0].setdefault("attachment", {})

                attachment["contentType"] = "application/pdf"
                attachment["data"] = pdf_base64
                print(attachment['data'])
                # print("Updated existing content block")

    return bundle

def run_nhcx_insurance_pipeline(distilled_text: str, clinical_artifact: str, selected_other_resources: List[str], output_dir=None, pdf_base64=None, idx=None, model: str = _DEFAULT_MODEL):
    # Complete rulebook paths (add all your paths)

    rulebook_paths = {
        "Organization": "./rulebooks_updated/StructureDefinition-Organization_updated.json",
        "InsurancePlan": "./rulebooks_updated/StructureDefinition-InsurancePlan_updated.json",
        "InsurancePlanBundle": "./rulebooks_updated/StructureDefinition-InsurancePlanBundle_updated.json",
        **{
            res: f"./rulebooks_updated/StructureDefinition-{res}_updated.json"
            for res in selected_other_resources
        }
    }
    
    initial_state = {
        "text": distilled_text, 
        "clinical_artifact": clinical_artifact,
        "id_registry": {},
        "final_resources": [],
        "rulebook_paths": rulebook_paths,
        "model": model,  # propagate model selection through the LangGraph state
    }
    
    # Build and run dynamic workflow
    app, used_resources = build_insurance_workflow(clinical_artifact, selected_other_resources, rulebook_paths)
    
    print(f"🚀 Starting FHIR Bundle Generation for Patient {idx}...")
    final_output = app.invoke(initial_state)
    bundle = final_output['final_resources'][-1]
    
    # Process the bundle in memory if needed
    bundle = clean_and_reorder_bundle(bundle)
    bundle = document_reference_node(bundle, pdf_base64=pdf_base64)
    
    # Upload to GCS instead of local file save
    from utils.gcs_storage import upload_json_to_gcs
    filename = f"FHIR_BUNDLE_{clinical_artifact}_Patient_{idx}.json"
    gcs_uri = upload_json_to_gcs(bundle, "json_output/nhcx", filename)
    
    print(f"\n SUCCESS! FHIR Bundle generated (GCS: {gcs_uri})")
    print(f" Resources processed: {used_resources}")
    print(f" Bundle entries: {len(bundle.get('entry', []))}")
    
    return bundle
