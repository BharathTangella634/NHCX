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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@app.post("/pdf2fhir")
async def convert_pdf_to_markdown(file: UploadFile = File(...)):
    return JSONResponse(content={
        "message": "I was tested and I'm alive"
    })

@app.get("/health")
def health_check():
    return {"status": "healthy"}