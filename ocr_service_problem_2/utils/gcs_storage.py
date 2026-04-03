"""
gcs_storage.py — GCS upload utility for NHCX Hackathon services
Uses the service account JSON if provided, otherwise falls back to ADC.
"""

import os
import logging

logger = logging.getLogger(__name__)

GCS_BUCKET      = os.getenv("GCS_BUCKET", "tanuh-bcd-bucket")
GCS_SA_KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")  # optional


def upload_pdf_to_gcs(local_file_path: str, gcs_folder: str) -> str | None:
    """
    Upload a PDF file to GCS.

    Args:
        local_file_path: Absolute path to the local PDF file.
        gcs_folder:      Destination folder inside the bucket
                         e.g. 'pdf2fhir/PDF2ABDM' or 'pdf2fhir/PDF2NHCX'.

    Returns:
        GCS URI string like 'gs://tanuh-bcd-bucket/pdf2fhir/PDF2ABDM/file.pdf',
        or None if upload failed (so the main flow is never interrupted).
    """
    try:
        from google.cloud import storage as gcs

        if GCS_SA_KEY_PATH and os.path.isfile(GCS_SA_KEY_PATH):
            client = gcs.Client.from_service_account_json(GCS_SA_KEY_PATH)
            logger.info("GCS: using service account JSON credentials")
        else:
            client = gcs.Client()          # ADC (GCP VM metadata server)
            logger.info("GCS: using Application Default Credentials (ADC)")

        bucket   = client.bucket(GCS_BUCKET)
        filename = os.path.basename(local_file_path)
        blob_name = f"{gcs_folder.rstrip('/')}/{filename}"
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(local_file_path, content_type="application/pdf")
        gcs_uri = f"gs://{GCS_BUCKET}/{blob_name}"
        logger.info(f"GCS upload successful: {gcs_uri}")
        return gcs_uri

    except ImportError:
        logger.warning("google-cloud-storage not installed — skipping GCS upload")
        return None
    except Exception as e:
        logger.warning(f"GCS upload failed (non-fatal): {e}")
        return None
