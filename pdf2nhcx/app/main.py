# import os
# import sys
# import argparse

# # Add the parent directory to sys.path to allow importing from utils
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from utils.ocr_engine import extract_text_from_pdf, classify_document
# from utils.fhir_converter import convert_diagnostic_report_to_fhir, convert_discharge_summary_to_fhir
# from utils.logger import get_logger

# logger = get_logger(__name__)

# def process_pdf(pdf_path, output_dir=None, md_dir=None):
#     try:
#         filename = os.path.basename(pdf_path)
#         logger.info(f"Processing {filename}...")
        
#         # Perform OCR
#         extracted_text = extract_text_from_pdf(pdf_path)

#         # Classify Document
#         doc_type = classify_document(extracted_text)
#         logger.info(f"Document classified as: {doc_type}")
#         print(f"Document classified as: {doc_type}")

#         # Save intermediate Markdown if requested
#         if md_dir:
#             if not os.path.exists(md_dir):
#                 os.makedirs(md_dir)
#             md_path = os.path.join(md_dir, f"{os.path.splitext(filename)[0]}_{doc_type}.md")
#             with open(md_path, "w") as f:
#                 f.write(extracted_text)
#             logger.info(f"Saved intermediate markdown to {md_path}")

#         # Convert to FHIR
#         if doc_type == "discharge_summary":
#             fhir_json, regex_data, llm_json = convert_discharge_summary_to_fhir(extracted_text, filename)
#         else:
#             fhir_json, regex_data, llm_json = convert_diagnostic_report_to_fhir(extracted_text, filename)

#         # Save result
#         if output_dir:
#             if not os.path.exists(output_dir):
#                 os.makedirs(output_dir)
#             output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_{doc_type}_fhir.json")
#             with open(output_path, "w") as f:
#                 f.write(fhir_json)
#             logger.info(f"Successfully processed {filename} and saved to {output_path}")
            
#             # Save LLM output separately if generated
#             if llm_json:
#                 llm_output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_{doc_type}_llm.json")
#                 with open(llm_output_path, "w") as f:
#                     f.write(llm_json)
#                 logger.info(f"Saved LLM generated FHIR JSON for {filename} to {llm_output_path}")

#             # Save Regex output separately
#             regex_output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_{doc_type}_regex.json")
#             import json
#             with open(regex_output_path, "w") as f:
#                 json.dump(regex_data, f, indent=2)
#             logger.info(f"Saved Regex extraction for {filename} to {regex_output_path}")
#         else:
#             logger.info(f"Successfully processed {filename}. Result:")
#             print(fhir_json)
#             print("Regex Extracted Data:")
#             import json
#             print(json.dumps(regex_data, indent=2))

#     except Exception as e:
#         logger.exception(f"Error processing {pdf_path}: {e}")

# def main():
#     parser = argparse.ArgumentParser(description="OCR PDF to ABDM FHIR Converter (Local)")
#     parser.add_argument("input", help="Path to input PDF file or directory")
#     parser.add_argument("--output_dir", help="Directory to save FHIR JSON results", default="fhir_results")
#     parser.add_argument("--md_dir", help="Directory to save intermediate Markdown results", default=None)
    
#     args = parser.parse_args()

#     if os.path.isfile(args.input):
#         process_pdf(args.input, args.output_dir, args.md_dir)
#     elif os.path.isdir(args.input):
#         for file in os.listdir(args.input):
#             if file.lower().endswith(".pdf"):
#                 process_pdf(os.path.join(args.input, file), args.output_dir, args.md_dir)
#     else:
#         logger.error(f"Error: {args.input} is not a valid file or directory")
#         sys.exit(1)

# if __name__ == "__main__":
#     main()


import os
import sys
import argparse
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import time

import subprocess
import json
import re
import uuid
from fastapi import HTTPException
from pydantic import BaseModel

class LocalFileRequest(BaseModel):
    file_path: str
    model: str = "gemma4"
    ocr_engine: str = "auto"

# ── PDF Upload Limits ────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 25
MAX_PAGE_COUNT   = 100

def validate_pdf_upload(file_path: str):
    """Raise HTTPException 413 if the PDF exceeds size or page limits."""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail={
                "title": "File Too Large",
                "message": f"The uploaded PDF is {size_mb:.1f} MB. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            }
        )
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        page_count = len(reader.pages)
        if page_count > MAX_PAGE_COUNT:
            raise HTTPException(
                status_code=413,
                detail={
                    "title": "Too Many Pages",
                    "message": f"The uploaded PDF has {page_count} pages. Maximum allowed is {MAX_PAGE_COUNT} pages."
                }
            )
    except HTTPException:
        raise
    except Exception:
        pass  # If page counting fails, let the pipeline handle it


app = FastAPI(
    title="NHCX Extraction API",
    description="Production-grade OCR and FHIR extraction pipeline for insurance documents.",
    version="2.0.0",
    docs_url="/docs",
    openapi_tags=[
        {"name": "Status", "description": "Health and system status endpoints."},
        {"name": "Processing", "description": "Core document processing endpoints."},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from common.tasks import process_document_task
from celery.result import AsyncResult


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Map UPLOAD_DIR to /app/pdf_uploads if in Docker, else relative to app
UPLOAD_DIR = "/app/pdf_uploads" if os.environ.get("PYTHONUNBUFFERED") else os.path.join(BASE_DIR, "pdf_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/health", tags=["Status"], summary="Check API health")
@app.get("/pdf2nhcx/health", tags=["Status"], include_in_schema=False)
@app.get("/ocr-service-problem-3/health", tags=["Status"], include_in_schema=False)
def health_check():
    from utils.llm_requirements import check_llm_health
    is_healthy, status_code = check_llm_health()
    if is_healthy:
        return {"status": "ok", "service": "pdf2nhcx"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": status_code, "service": "pdf2nhcx"}
        )

@app.get("/model-health", tags=["Status"], summary="Check LLM model availability")
@app.get("/pdf2nhcx/model-health", tags=["Status"], include_in_schema=False)
@app.get("/ocr-service-problem-3/model-health", tags=["Status"], include_in_schema=False)
def model_health(model: str = "gemma4"):
    """Check if a specific LLM model is available (valid name + Vertex auth OK)."""
    from utils.llm_requirements import check_llm_health, MODEL_MAP
    if model not in MODEL_MAP:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "reason": "unknown_model", "model": model}
        )
    is_healthy, reason = check_llm_health()
    if is_healthy:
        return {"status": "ok", "model": model, "vertex_model": MODEL_MAP[model]}
    return JSONResponse(
        status_code=503,
        content={"status": "error", "reason": reason, "model": model}
    )

@app.get("/ocr-health", tags=["Status"], summary="Check OCR engine availability")
@app.get("/pdf2nhcx/ocr-health", tags=["Status"], include_in_schema=False)
@app.get("/ocr-service-problem-3/ocr-health", tags=["Status"], include_in_schema=False)
def ocr_health(engine: str = "lighton"):
    """Check if a specific OCR engine is available."""
    KNOWN_ENGINES = {"lighton", "suriya", "chandra", "docling"}
    if engine not in KNOWN_ENGINES:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "reason": "unknown_engine", "engine": engine}
        )
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
        return {"status": "ok", "engine": engine}
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "docling_unavailable", "engine": engine}
        )


# Add the parent directory to sys.path to allow importing from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ocr_engine import  extract_distilled_text_from_nhcx_pdf, select_nhcx_resources 
# from utils.fhir_converter import convert_diagnostic_report_to_fhir, convert_discharge_summary_to_fhir
from utils.llm_requirements import run_nhcx_insurance_pipeline

from utils.logger import get_logger

logger = get_logger(__name__)


async def get_nhcx_json(pdf_path, model: str = "gemma4"):
    try:
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing {filename}...")
        
        # Perform OCR
        distilled_text, pdf_base64 = await extract_distilled_text_from_nhcx_pdf(pdf_path)

        doc_type, must_resources, selected_other_resources = select_nhcx_resources(distilled_text)

        logger.info(f"Document classified as: {doc_type}")
        print(f"Document classified as: {doc_type}")

        bundle = run_nhcx_insurance_pipeline(
            distilled_text, doc_type, selected_other_resources,
            pdf_base64=pdf_base64, idx=0,
            model=model
        )
        logger.info(f"Successfully processed {filename}")

        return bundle
    except Exception as e:
        logger.exception(f"Error processing {pdf_path}: {e}")

@app.post("/pdf2nhcx", tags=["Processing"], summary="Convert PDF to NHCX Bundle (Sync)")
async def convert_pdf_to_nhcx(
    file: UploadFile = File(...),
    model: str = Form("gemma4"),
    ocr_engine: str = Form("auto"),
):
    file.filename = file.filename.replace(" ", "_")
    logger.info(f"Received PDF upload: {file.filename}")
    logger.info(f"🤖 Model selected: {model} | 👁 OCR engine: {ocr_engine}")
    print(f"🤖 Model: {model}  |  👁 OCR: {ocr_engine}")
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info(f"Saved uploaded PDF to {file_path}")

    # ── Validate file size + page count ─────────────────────────────────
    validate_pdf_upload(file_path)

    # ── Upload PDF to GCS ──────────────────────────────────────────────────
    from utils.gcs_storage import upload_pdf_to_gcs
    gcs_uri = upload_pdf_to_gcs(file_path, "pdf2fhir/PDF2NHCX")
    if gcs_uri:
        logger.info(f"PDF uploaded to GCS: {gcs_uri}")
    # ───────────────────────────────────────────────────────────────────────

    start_time = time.perf_counter()
    logger.info("Starting get_nhcx_json processing...")
    bundle = await get_nhcx_json(file_path, model=model)
    end_time = time.perf_counter()
    
    processing_time = round(end_time - start_time, 2)
    
    logger.info(f"get_nhcx_json execution time: {processing_time} seconds")
    print(f"\n⏱ get_nhcx_json execution time: {processing_time} seconds")
    
    return JSONResponse(content={
        "message": "File uploaded successfully for NHCX processing",
        "file_path": file_path,
        "processing_time": f"{processing_time} seconds",
        "bundle": bundle,
        "bundle_names": ["NHCX Bundle"] if bundle else [],
        "model_used": model,
        "ocr_engine_used": ocr_engine,
    })

@app.post("/pdf2nhcxurl", tags=["Processing"], summary="Convert local PDF to NHCX Bundle via file path")
async def convert_pdf_to_nhcx_url(request: LocalFileRequest):
    file_path = request.file_path
    model = request.model
    ocr_engine = request.ocr_engine

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"message": f"File not found: {file_path}"})

    logger.info(f"Received local PDF request for: {file_path}")
    logger.info(f"🤖 Model selected: {model} | 👁 OCR engine: {ocr_engine}")
    print(f"🤖 Model: {model}  |  👁 OCR: {ocr_engine}")

    # ── Validate file size + page count ─────────────────────────────────
    validate_pdf_upload(file_path)

    # ── Upload PDF to GCS ──────────────────────────────────────────────────
    from utils.gcs_storage import upload_pdf_to_gcs
    gcs_uri = upload_pdf_to_gcs(file_path, "pdf2fhir/PDF2NHCX")
    if gcs_uri:
        logger.info(f"PDF uploaded to GCS: {gcs_uri}")
    # ───────────────────────────────────────────────────────────────────────

    start_time = time.perf_counter()
    logger.info("Starting get_nhcx_json processing...")
    bundle = await get_nhcx_json(file_path, model=model)
    end_time = time.perf_counter()
    
    processing_time = round(end_time - start_time, 2)
    
    logger.info(f"get_nhcx_json execution time: {processing_time} seconds")
    print(f"\n⏱ get_nhcx_json execution time: {processing_time} seconds")
    
    return JSONResponse(content={
        "message": "Local file processed successfully for NHCX processing",
        "file_path": file_path,
        "processing_time": f"{processing_time} seconds",
        "bundle": bundle,
        "bundle_names": ["NHCX Bundle"] if bundle else [],
        "model_used": model,
        "ocr_engine_used": ocr_engine,
    })

@app.post("/pdf2nhcx-async", tags=["Processing"], summary="Submit PDF for async processing")
async def convert_pdf_to_nhcx_async(
    file: UploadFile = File(...),
    model: str = Form("gemma4"),
):
    """
    Submits a PDF for asynchronous processing.
    Returns a task ID that can be used to poll for results.
    """
    file.filename = file.filename.replace(" ", "_")
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    task = process_document_task.delay(file_path, model=model)
    return {"task_id": task.id, "status": "queued"}

@app.get("/task-status/{task_id}", tags=["Processing"], summary="Get status of an async task")
async def get_task_status(task_id: str):
    """
    Poll this endpoint with the task ID to check progress and get final results.
    """
    res = AsyncResult(task_id)
    if res.ready():
        result = res.result
        return {"task_id": task_id, "status": "completed", "result": result}
    
    # Check for progress updates
    state = res.state
    info = res.info if isinstance(res.info, dict) else {"progress": 0, "step": "Pending"}
    return {"task_id": task_id, "status": state, "info": info}


@app.post("/validate")
async def validate_fhir(request: Request):
    # 1. Receive data from the frontend
    body = await request.json()
    json_content = body.get("json_data")
    
    # 2. Create a unique temporary file to validate
    # This prevents multiple users from overwriting the same file
    temp_file = f"validate_{uuid.uuid4()}.json"
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(json_content)

            # 3. Run the HL7 Validator command
        # Compute absolute path for the JAR so that it works regardless of cwd
        validator_jar = os.path.join(BASE_DIR, "validator_cli.jar")
        if not os.path.exists(validator_jar):
            logger.error(f"Validator JAR not found at {validator_jar}")
            return {"report": "Error @ System: validator_cli.jar not found"}

        cmd = [
            "/usr/bin/java", "-Xmx2G", "-jar", validator_jar,
            temp_file,
            "-version", "4.0.1",
            "-ig", "nrces.in.ndhm#6.0.0"
        ]

        process = subprocess.run(cmd, capture_output=True, text=True)
        raw_output = process.stdout

        # 4. Clean the output using your regex logic
        # Remove ANSI color codes
        clean = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', raw_output)

        # Extract only the Error lines
        errors = []
        for line in clean.splitlines():
            line = line.strip()
            if line.startswith("Error @"):
                errors.append(line)

        # 5. Return the cleaned string back to the frontend
        return {"report": "\n".join(errors)}

    except Exception as e:
        return {"report": f"Error @ System: Failed to run validator. {str(e)}"}
        
    finally:
        # 6. Delete the temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)


def main():
    parser = argparse.ArgumentParser(description="OCR PDF to ABDM FHIR Converter (Local)")
    parser.add_argument("input", help="Path to input PDF file or directory")
    
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Go up 2 levels to get to NHCX_HACKATHON root
    # Level 1: pdf2nhcx
    # Level 2: NHCX_HACKATHON
    repo_root = os.path.dirname(os.path.dirname(current_dir))
    
    # 3. Define the relative root for results
    # Path: .../NHCX_HACKATHON/fhir_results
    relative_root = os.path.join(repo_root, "nhcx_results")
    
    # 4. Extract clean filename (e.g., "Test 1")
    file_name_only = os.path.splitext(os.path.basename(args.input))[0]
    
    # 5. Create path: .../NHCX_HACKATHON/fhir_results/Test 1/
    target_output_dir = os.path.join(relative_root, file_name_only)
    os.makedirs(target_output_dir, exist_ok=True)
    
    args = parser.parse_args()

    if os.path.isfile(args.input):
        start_time = time.perf_counter()   # ⏱ Start timer
        
        import asyncio
        bundle = asyncio.run(get_nhcx_json(args.input, target_output_dir))
        
        end_time = time.perf_counter()     # ⏱ End timer
        total_time = end_time - start_time
        
        print(f"\n⏱ get_nhcx_json execution time: {total_time:.2f} seconds")
        
    else:
        logger.error(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()
