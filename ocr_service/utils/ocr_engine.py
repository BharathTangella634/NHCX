from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
import os

def extract_text_from_pdf(pdf_path):
    """Extracts text from PDF using Docling and inserts page break markers."""
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document

    markdown_parts = []
    current_page = 1
    for item, _level in doc.iterate_items():
        page_no = None
        if hasattr(item, 'prov') and item.prov:
            page_no = item.prov[0].page_no

        if page_no and page_no > current_page:
            # Insert page break marker
            markdown_parts.append("\n\n<!-- PAGE_BREAK -->\n\n")
            current_page = page_no

        # Use the document's method to export individual items if possible.
        if hasattr(item, 'export_to_markdown'):
            try:
                # Some items might require the doc context
                markdown_parts.append(item.export_to_markdown(doc) + "\n")
            except TypeError:
                markdown_parts.append(item.export_to_markdown() + "\n")
        elif hasattr(item, 'text'):
            markdown_parts.append(item.text + "\n")

    return "".join(markdown_parts)
