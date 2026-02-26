#!/bin/bash

# Target PDF path
PDF_PATH="test_files/Problem_Statement_2_630a8c8cb6/New Diagnostic Reports/Copy of Copy of report4.pdf"
#/Users/ashwinrajkumar/PycharmProjects/NHCX_HACKATHON/test_files/Problem_Statement_2_630a8c8cb6/New Diagnostic Reports/Copy of Copy of report4.pdf
OUTPUT_DIR="fhir_results"

# Check if file exists
if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file not found at $PDF_PATH"
    exit 1
fi

# Run the OCR service
echo "Running OCR service on $PDF_PATH..."
python3 ocr_service/app/main.py "$PDF_PATH" --output_dir "$OUTPUT_DIR" --md_dir "markdown_results"

# Verify output (using wildcard to match doc type like diagnostic_report)
FILENAME=$(basename "$PDF_PATH")
BASE_FILENAME="${FILENAME%.pdf}"

if ls "${OUTPUT_DIR}/${BASE_FILENAME}"*_fhir.json 1> /dev/null 2>&1; then
    echo "Successfully generated FHIR JSON."
else
    echo "Failed to generate FHIR JSON."
    exit 1
fi
