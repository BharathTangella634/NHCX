# NHCX InsurancePlanBundle FHIR Generator

LLM-orchestrated pipeline that converts insurance policy PDFs into HL7
FHIR R4 InsurancePlanBundle (NHCX-compliant) JSON bundles aligned with
ABDM / NDHM standards.

------------------------------------------------------------------------

# 1. Brief Functional Scope

This system:

-   Accepts an Insurance Policy PDF
-   Extracts structured text using Docling
-   Performs lossless LLM-based distillation of insurance facts
-   Automatically selects relevant NHCX FHIR resources
-   Dynamically builds a dependency-aware workflow
-   Extracts structured HL7 FHIR R4 resources using rulebook-constrained
    prompts
-   Assembles an NHCX-compliant InsurancePlanBundle (Bundle type:
    collection)
-   Embeds the original PDF as base64 into DocumentReference
-   Outputs a fully structured FHIR JSON bundle

Primary Artifact: - InsurancePlanBundle (NHCX Profile)

------------------------------------------------------------------------

# 2. High-Level Architecture

PDF Input\
→ Docling Text Extraction\
→ LLM Text Distillation (Chunked + Overlap)\
→ LLM Resource Selection\
→ Dynamic Workflow Builder (LangGraph)\
→ Per-Resource LLM Extraction\
→ UUID Linking & Normalization\
→ InsurancePlanBundle Assembly\
→ PDF Embedding\
→ Final FHIR JSON Output

------------------------------------------------------------------------

# 3. Tools and Libraries Used

## Open Source

Core Frameworks: - Python 3.10+ - LangGraph - LangChain -
langchain-ollama - Ollama

Document Processing: - Docling - base64 (stdlib) - re - json - uuid -
datetime - argparse - typing - collections

Orchestration: - LangGraph StateGraph - HumanMessage (LangChain Core)

## Closed Source / Model Weights

LLM Model: - qwen2.5:32b (served via Ollama)

Note: Model weights are not included in this repository.

------------------------------------------------------------------------

# 4. Setup Instructions

Step 1 --- Clone Repository

git clone `<your-repo-url>`{=html} cd `<repo-folder>`{=html}

Step 2 --- Create Virtual Environment

python -m venv venv source venv/bin/activate \# macOS/Linux
venv`\Scripts`{=tex}`\activate    `{=tex}\# Windows

Step 3 --- Install Dependencies

pip install -r requirements.txt

Step 4 --- Install Ollama

Download from: https://ollama.com

Verify: ollama --version

Step 5 --- Pull Required Model

ollama pull qwen2.5:32b

Step 6 --- Start Ollama Server

ollama serve

Step 7 --- Run Pipeline

python main.py input.pdf --output_dir fhir_results

Output: FHIR_BUNDLE_InsurancePlanBundle_Patient_0.json

------------------------------------------------------------------------

# 5. Dependencies

Example requirements.txt:

-   langchain
-   langgraph
-   langchain-ollama
-   docling
-   pydantic

System Requirements:

-   Python 3.10+
-   16--32 GB RAM recommended
-   GPU recommended (optional)
-   Ollama installed locally

------------------------------------------------------------------------

# 6. Implementation Details

Execution Flow:

main() → get_nhcx_json() → extract_distilled_text_from_nhcx_pdf() →
distill_insurance_text() → select_nhcx_resources() →
build_insurance_workflow() → run_extraction_agent() →
insurance_assembly_node() → clean_and_reorder_bundle() →
document_reference_node()

Text Distillation Strategy:

-   Split document into overlapping chunks
-   Preserve INR values, %, waiting periods, age limits
-   Preserve benefit tables
-   No hallucination
-   No inferred fields

Dynamic Workflow Construction:

-   Merge mandatory + selected resources
-   Resolve dependencies via topological sort
-   Create LangGraph nodes per resource
-   Deterministic execution order

Resource Extraction Rules:

-   Conform to HL7 FHIR R4
-   UUID id mandatory (RFC-4122)
-   No null values
-   No empty arrays
-   No hallucinated data
-   IRDAI exclusions when applicable
-   SNOMED CT if required
-   URN UUID internal references

InsurancePlanBundle Assembly Order:

1.  InsurancePlan (Anchor)
2.  Supporting Resources
3.  Attachments (DocumentReference / Binary) last

Bundle type: collection

State Management:

AgentState contains: - text - clinical_artifact - id_registry -
final_resources - rulebook_paths

------------------------------------------------------------------------

# 7. Known Limitations

-   Artifact fixed to InsurancePlanBundle
-   Multiple LLM calls increase latency
-   No FHIR validation layer
-   No retry strategy for malformed JSON
-   Large memory footprint for 32B model

------------------------------------------------------------------------

# 8. Output Characteristics

FHIR_BUNDLE_InsurancePlanBundle_Patient_0.json

Conforms to:

-   HL7 FHIR R4
-   NHCX InsurancePlanBundle profile
-   ABDM constraints
-   Bundle type: collection
-   Embedded original PDF

------------------------------------------------------------------------

# License

Specify project license here.
