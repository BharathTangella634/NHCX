import os
import subprocess
import sys
from pathlib import Path

def process_all_files():
    test_files_dir = Path("test_files/Problem_Statement_2_630a8c8cb6")
    output_dir = "fhir_results"
    md_dir = "markdown_results"
    
    # Ensure output directories exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)
    
    # Find all pdf files in the test_files directory and its subdirectories
    pdf_files = list(test_files_dir.rglob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {test_files_dir}")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] Processing: {pdf_path}")
        
        # Run the ocr_service for each file
        command = [
            sys.executable,
            "ocr_service/app/main.py",
            str(pdf_path),
            "--output_dir", output_dir,
            "--md_dir", md_dir
        ]
        
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Successfully processed {pdf_path.name}")
            else:
                print(f"Failed to process {pdf_path.name}. Return code: {result.returncode}")
                print(f"Error output: {result.stderr.strip()}")
        except Exception as e:
            print(f"Exception occurred while processing {pdf_path.name}: {e}")

if __name__ == "__main__":
    process_all_files()
