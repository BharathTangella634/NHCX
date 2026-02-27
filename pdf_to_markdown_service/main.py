import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
import pymupdf4llm
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PDF to Markdown Converter Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIR = "pdf_uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/pdf2fhir")
async def convert_pdf_to_markdown(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return JSONResponse(content={
        "message": "File uploaded successfully for FHIR processing",
        "file_path": file_path
    })

@app.post("/pdf2nhcx")
async def convert_pdf_to_nhcx(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return JSONResponse(content={
        "message": "File uploaded successfully for NHCX processing",
        "file_path": file_path
    })

@app.get("/health")
def health_check():
    return {"status": "healthy"}