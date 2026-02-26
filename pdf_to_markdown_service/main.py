import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
import pymupdf4llm
from fastapi.responses import JSONResponse

app = FastAPI(title="PDF to Markdown Converter Service")

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
