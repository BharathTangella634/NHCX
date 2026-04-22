"""
gcs_storage.py — GCS upload utility for NHCX Hackathon services

Auth priority:
  1. GCS_CREDENTIALS_JSON env var → dedicated SA for GCS (tanuh-bcd-application2)
  2. GOOGLE_APPLICATION_CREDENTIALS → shared SA or ADC
  3. Plain ADC (GCP metadata server)

Failures are non-fatal — main FHIR pipeline always completes.
"""

import os
import logging

logger = logging.getLogger(__name__)

GCS_BUCKET           = os.getenv("GCS_BUCKET", "tanuh-bcd-bucket")
GCS_CREDENTIALS_JSON = os.getenv("GCS_CREDENTIALS_JSON", "")   # dedicated GCS SA
GOOGLE_CREDENTIALS   = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")


def upload_pdf_to_gcs(local_file_path: str, gcs_folder: str) -> str | None:
    """
    Upload a PDF file to GCS.

    Args:
        local_file_path: Absolute path to the local PDF file.
        gcs_folder:      Destination folder inside the bucket
                         e.g. 'pdf2fhir/PDF2ABDM' or 'pdf2fhir/PDF2NHCX'.

    Returns:
        GCS URI string, or None if upload failed (non-fatal).
    """
    try:
        from google.cloud import storage as gcs

        # Priority 1: dedicated GCS service account JSON
        if GCS_CREDENTIALS_JSON and os.path.isfile(GCS_CREDENTIALS_JSON):
            client = gcs.Client.from_service_account_json(GCS_CREDENTIALS_JSON)
            logger.info(f"GCS: using dedicated GCS service account ({GCS_CREDENTIALS_JSON})")
        # Priority 2: shared GOOGLE_APPLICATION_CREDENTIALS
        elif GOOGLE_CREDENTIALS and os.path.isfile(GOOGLE_CREDENTIALS):
            client = gcs.Client.from_service_account_json(GOOGLE_CREDENTIALS)
            logger.info(f"GCS: using GOOGLE_APPLICATION_CREDENTIALS ({GOOGLE_CREDENTIALS})")
        # Priority 3: ADC (GCP metadata server)
        else:
            client = gcs.Client()
            logger.info("GCS: using Application Default Credentials (ADC)")

        bucket    = client.bucket(GCS_BUCKET)
        filename  = os.path.basename(local_file_path)
        blob_name = f"{gcs_folder.rstrip('/')}/{filename}"
        blob      = bucket.blob(blob_name)

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
