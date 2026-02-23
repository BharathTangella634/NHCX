from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
import os

def extract_text_from_pdf(pdf_path):
    """Extracts text from PDF using Docling."""
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    return result.document.export_to_markdown() # Or export_to_dict/text
