import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
import pymupdf4llm
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PDF to Markdown Converter Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@app.post("/PDF2FHIRJSON")
async def convert_pdf_to_markdown(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # Read the file content
    content = await file.read()
    
    # Check the size (up to 10 MB)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds the 10 MB limit.")
    
    # Save the uploaded content to a temporary file
    # pymupdf4llm requires a file path to process the PDF
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Convert the PDF to Markdown
        md_text = pymupdf4llm.to_markdown(tmp_path)
        
        # Save the result in markdown_results folder
        results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markdown_results")
        os.makedirs(results_dir, exist_ok=True)
        
        # Create a clean markdown filename based on the original pdf name
        base_name = os.path.splitext(file.filename)[0]
        md_filename = f"{base_name}.md"
        md_filepath = os.path.join(results_dir, md_filename)
        
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(md_text)
        
        return JSONResponse(content={
            "filename": file.filename,
            "markdown": md_text
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process the PDF file: {str(e)}")
    finally:
        # Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
