import asyncio
import os
import sys
import json

# Add backend dirs to path
sys.path.append(os.path.abspath("pdf2abdm"))
sys.path.append(os.path.abspath("pdf2nhcx"))

from pdf2abdm.app.main import get_abdm_json
from pdf2nhcx.app.main import get_nhcx_json

async def process_clinical(file_path):
    print(f"\n🚀 Processing Clinical Document: {file_path}")
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
        
    try:
        bundles, doc_types = await get_abdm_json(file_path, model="gemma4")
        output_file = f"output_{os.path.basename(file_path)}.json"
        
        with open(output_file, "w") as f:
            json.dump({"bundles": bundles, "doc_types": doc_types}, f, indent=2)
            
        print(f"✅ Success! Extracted {len(bundles)} bundles.")
        print(f"💾 Saved to {output_file}")
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

async def process_insurance(file_path):
    print(f"\n🚀 Processing Insurance Document: {file_path}")
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
        
    try:
        bundles, _ = await get_nhcx_json(file_path, model="gemma4")
        output_file = f"output_{os.path.basename(file_path)}.json"
        
        with open(output_file, "w") as f:
            json.dump({"bundles": bundles}, f, indent=2)
            
        print(f"✅ Success! Extracted {len(bundles)} bundles.")
        print(f"💾 Saved to {output_file}")
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

async def main():
    # Process clinical documents
    await process_clinical("test_files/abdm_diagnostic_report.pdf")
    await process_clinical("test_files/abdm_discharge_summary.pdf")
    
    # Process insurance document
    # Note: user provided "/test_files/nhcx_demo_doc.pdf", stripping the leading slash for relative path
    await process_insurance("test_files/nhcx_demo_doc.pdf")

if __name__ == "__main__":
    asyncio.run(main())
