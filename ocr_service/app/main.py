import os
import sys
import argparse

# Add the parent directory to sys.path to allow importing from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ocr_engine import extract_text_from_pdf
from utils.fhir_converter import text_to_abdm_fhir

def process_pdf(pdf_path, output_dir=None, md_dir=None):
    try:
        filename = os.path.basename(pdf_path)
        print(f"Processing {filename}...")
        
        # Perform OCR
        extracted_text = extract_text_from_pdf(pdf_path)

        # Save intermediate Markdown if requested
        if md_dir:
            if not os.path.exists(md_dir):
                os.makedirs(md_dir)
            md_path = os.path.join(md_dir, f"{os.path.splitext(filename)[0]}.md")
            with open(md_path, "w") as f:
                f.write(extracted_text)
            print(f"Saved intermediate markdown to {md_path}")

        # Convert to FHIR
        fhir_json = text_to_abdm_fhir(extracted_text, filename)

        # Save result
        if output_dir:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_fhir.json")
            with open(output_path, "w") as f:
                f.write(fhir_json)
            print(f"Successfully processed {filename} and saved to {output_path}")
        else:
            print(f"Successfully processed {filename}. Result:")
            print(fhir_json)

    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="OCR PDF to ABDM FHIR Converter (Local)")
    parser.add_argument("input", help="Path to input PDF file or directory")
    parser.add_argument("--output_dir", help="Directory to save FHIR JSON results", default="fhir_results")
    parser.add_argument("--md_dir", help="Directory to save intermediate Markdown results", default=None)
    
    args = parser.parse_args()

    if os.path.isfile(args.input):
        process_pdf(args.input, args.output_dir, args.md_dir)
    elif os.path.isdir(args.input):
        for file in os.listdir(args.input):
            if file.lower().endswith(".pdf"):
                process_pdf(os.path.join(args.input, file), args.output_dir, args.md_dir)
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()
