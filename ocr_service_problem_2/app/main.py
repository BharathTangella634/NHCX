import os
import sys
import argparse
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import time

import subprocess
import json
import re
import uuid
from fastapi import FastAPI, Request

# Add the parent directory to sys.path to allow importing from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ocr_engine import extract_text_from_abdm_pdf, classify_document
# from utils.fhir_converter import convert_diagnostic_report_to_fhir, convert_discharge_summary_to_fhir
from utils.llm_requirements import *

from utils.logger import get_logger

logger = get_logger(__name__)

def get_abdm_json(pdf_path, output_dir=None):
    try:
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing {filename}...")
        
        # Perform OCR
        unique_patients_text_list, pdf_base64 = extract_text_from_abdm_pdf(pdf_path)

        bundles = []
        for i, extracted_text in enumerate(unique_patients_text_list):
            # Classify Document
            doc_type, must_resources, selected_other_resources = classify_document(extracted_text, llm)
            logger.info(f"Document classified as: {doc_type}")
            print(f"Document classified as: {doc_type}")

            # Save result
            if output_dir:
                # if not os.path.exists(output_dir):
                #     os.makedirs(output_dir)
                # output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_{doc_type}_fhir_Patient{i}.json")
                
                bundle = run_abdm_pipeline(extracted_text, doc_type, selected_other_resources, output_dir=output_dir, pdf_base64=pdf_base64, idx=i)
                bundles.append(bundle)
                logger.info(f"Successfully processed {filename} and saved to {output_dir}")
            else:
                error_msg = "Output directory must be provided to save the results."
                logger.error(error_msg)
                raise ValueError(error_msg)

        return bundles

    except Exception as e:
        logger.exception(f"Error processing {pdf_path}: {e}")



app = FastAPI(title="OCR Service Problem 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Map UPLOAD_DIR to /app/pdf_uploads if in Docker, else relative to app
UPLOAD_DIR = "/app/pdf_uploads" if os.environ.get("PYTHONUNBUFFERED") else os.path.join(BASE_DIR, "pdf_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/pdf2fhir")
async def convert_pdf_to_fhir(file: UploadFile = File(...)):
    logger.info(f"Received PDF upload: {file.filename}")
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info(f"Saved uploaded PDF to {file_path}")
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(current_dir))
    relative_root = "/app/fhir_results_problem_2" if os.environ.get("PYTHONUNBUFFERED") else os.path.join(repo_root, "fhir_results_problem_2")
    file_name_only = os.path.splitext(os.path.basename(file_path))[0]
    target_output_dir = os.path.join(relative_root, file_name_only)
    os.makedirs(target_output_dir, exist_ok=True)
    logger.info(f"Target output directory: {target_output_dir}")
    
    start_time = time.perf_counter()
    logger.info("Starting get_abdm_json processing...")
    bundle = get_abdm_json(file_path, target_output_dir)
    end_time = time.perf_counter()
    
    logger.info(f"get_abdm_json execution time: {(end_time - start_time):.2f} seconds")
    print(f"\n⏱ get_abdm_json execution time: {(end_time - start_time):.2f} seconds")
    
    return JSONResponse(content={
        "message": "File uploaded successfully for FHIR processing",
        "file_path": file_path
    })

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
        # Ensure validator_cli.jar is in the same folder as this script
        cmd = [
            "java", "-Xmx2G", "-jar", "validator_cli.jar",
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
    # parser.add_argument("--output_dir", help="Directory to save FHIR JSON results", default="fhir_results")
    # parser.add_argument("--md_dir", help="Directory to save intermediate Markdown results", default=None)
    
    args = parser.parse_args()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Go up 2 levels to get to NHCX_HACKATHON root
    # Level 1: ocr_service_problem_2
    # Level 2: NHCX_HACKATHON
    repo_root = os.path.dirname(os.path.dirname(current_dir))
    
    # 3. Define the relative root for results
    # Path: .../NHCX_HACKATHON/fhir_results
    relative_root = os.path.join(repo_root, "fhir_results_problem_2")
    
    # 4. Extract clean filename (e.g., "Test 1")
    file_name_only = os.path.splitext(os.path.basename(args.input))[0]
    
    # 5. Create path: .../NHCX_HACKATHON/fhir_results/Test 1/
    target_output_dir = os.path.join(relative_root, file_name_only)
    os.makedirs(target_output_dir, exist_ok=True)
    

    if os.path.isfile(args.input):
        start_time = time.perf_counter()   # ⏱ Start timer
        
        bundle = get_abdm_json(args.input, target_output_dir)
        
        end_time = time.perf_counter()     # ⏱ End timer
        total_time = end_time - start_time
        
        print(f"\n⏱ get_abdm_json execution time: {total_time:.2f} seconds")
        
    else:
        logger.error(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()

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

