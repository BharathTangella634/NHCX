# ABDM FHIR Document Bundle Generator

LLM-orchestrated pipeline that converts ABDM-compatible clinical PDFs
into **HL7 FHIR R4 Document Bundles** compliant with **ABDM / NDHM
profiles**.

------------------------------------------------------------------------

# 1. Brief Functional Scope

This system:

-   Accepts a clinical PDF (Lab Report / Discharge Summary)
-   Extracts structured text using OCR (Docling)
-   Automatically identifies document type using an LLM
-   Dynamically determines required FHIR resources
-   Extracts structured HL7 FHIR R4 resources using rulebook-constrained
    prompts
-   Assembles a compliant **FHIR Document Bundle**
-   Embeds the original PDF (base64) into `DocumentReference`
-   Outputs a fully structured ABDM-compliant JSON bundle

## Supported Clinical Artifacts

-   DiagnosticReportRecord
-   DischargeSummaryRecord

------------------------------------------------------------------------

# 2. High-Level Architecture

PDF Input\
→ Docling OCR + Page Extraction\
→ Patient Page Grouping\
→ LLM Document Classification\
→ Dynamic Workflow Builder (LangGraph)\
→ Per-Resource LLM Extraction\
→ FHIR Resource Normalization\
→ Bundle Assembly (Document Type: document)\
→ Post Processing\
→ FHIR Document Bundle JSON Output

------------------------------------------------------------------------

# 3. Tools and Libraries Used

## Open Source

### Core Frameworks

-   Python 3.10+
-   LangGraph
-   LangChain
-   langchain-ollama
-   Ollama

### Document Processing

-   Docling
-   base64 (Python stdlib)
-   re
-   json
-   uuid

### Utilities

-   argparse
-   datetime
-   typing
-   collections
-   os
-   sys

## Closed Source

### LLM Model Weights

-   qwen2.5:32b (served via Ollama)

Note: Model weights are not included in this repository.

------------------------------------------------------------------------

# 4. Setup Instructions

## Step 1 --- Clone Repository

``` bash
git clone <your-repo-url>
cd <repo-folder>
```

## Step 2 --- Create Virtual Environment

``` bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate   # Windows
```

## Step 3 --- Install Dependencies

``` bash
pip install -r requirements.txt
```

## Step 4 --- Install Ollama

Download from: https://ollama.com

Verify installation:

``` bash
ollama --version
```

## Step 5 --- Pull Required Model

``` bash
ollama pull qwen2.5:32b
```

## Step 6 --- Start Ollama Server

``` bash
ollama serve
```

## Step 7 --- Run Pipeline

``` bash
python main.py input.pdf --output_dir fhir_results
```

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

## Execution Flow

main()\
→ get_abdm_json()\
→ process_pdf_and_group_patients()\
→ classify_document()\
→ build_dynamic_workflow()\
→ run_extraction_agent()\
→ assembly_node()\
→ clean_and_reorder_bundle()\
→ document_reference_node()

## Core Design Principles

-   Deterministic dependency ordering
-   Rulebook-driven FHIR extraction
-   Strict UUID enforcement
-   No hallucinated data
-   Composition-first document bundling
-   PDF embedded via DocumentReference

------------------------------------------------------------------------

# 7. Known Limitations

-   Only first patient returned due to early return inside loop
-   Latency scales with number of resources
-   No automatic FHIR validation layer
-   No retry mechanism for malformed JSON
-   Large memory footprint for 32B model

------------------------------------------------------------------------

# 8. Output Example

FHIR_BUNDLE_DiagnosticReportRecord_Patient_0.json

Conforms to:

-   HL7 FHIR R4
-   ABDM / NDHM profiles
-   Document Bundle structure
-   Embedded PDF attachment

------------------------------------------------------------------------

# License

Specify your license here.
