from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.documentreference import DocumentReference
from fhir.resources.attachment import Attachment
import base64
import uuid
from datetime import datetime

def text_to_abdm_fhir(text, original_filename="document.pdf"):
    """
    Wraps extracted text into a basic ABDM-compliant FHIR Bundle (DocumentReference).
    Note: ABDM usually requires specific profiles, this is a simplified version.
    """
    
    # Create an Attachment with the text (or encoded content)
    attachment = Attachment(
        contentType="text/plain",
        data=base64.b64encode(text.encode('utf-8')).decode('utf-8'),
        title=f"Extracted text from {original_filename}"
    )

    # Create DocumentReference
    doc_ref = DocumentReference(
        status="current",
        docStatus="final",
        type={"coding": [{"system": "http://loinc.org", "code": "11488-4", "display": "Consult Note"}]},
        subject={"display": "Patient"},  # Placeholder
        date=datetime.now().isoformat(),
        content=[{"attachment": attachment}]
    )

    # Create Bundle
    bundle = Bundle(
        type="document",
        identifier={"system": "https://www.abdm.gov.in/bundle", "value": str(uuid.uuid4())},
        entry=[BundleEntry(resource=doc_ref)]
    )

    return bundle.json()
