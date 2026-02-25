# NHCX_HACKATHON
National Health Claims Exchange Hackathon

## PDF to ABDM FHIR OCR Service

This project provides a tool for processing PDF files into ABDM-compliant FHIR formats using OCR (Docling/Tesseract).

### Architecture
- **OCR Service**: Python script that:
  - Performs OCR using `docling`.
  - Converts extracted text into FHIR Bundle (ABDM style).
  - Saves results locally as JSON files.

### Getting Started

1. **Prerequisites**:
   - Python 3.11+
   - Tesseract OCR installed on your system.
     - macOS: `brew install tesseract`
     - Ubuntu: `sudo apt-get install tesseract-ocr`

2. **Install Dependencies**:
   ```bash
   pip install -r ocr_service/requirements.txt
   ```

3. **Process a PDF**:
   ```bash
   python ocr_service/app/main.py path/to/your_document.pdf --md_dir markdown_results
   ```
   The `--md_dir` flag allows you to specify a location to save the intermediate Markdown file extracted during OCR.

   Or process a directory of PDFs:
   ```bash
   python ocr_service/app/main.py path/to/pdf_directory/ --output_dir fhir_results --md_dir markdown_results
   ```

4. **View Results**:
   Results will be saved in the `fhir_results` directory by default.

### Requirements
- Python 3.11+
- Tesseract OCR
- Docling
- fhir.resources

### Reference Tables
LOINC mappings and other FHIR-related lookup tables are stored in the `reference/` directory.
- `reference/LOINC-codes.xlsx`: Maps test names found in reports to their respective LOINC codes, display names, and units.
