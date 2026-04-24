"""
pdf2nhcx/tasks.py — Dedicated Celery background task for NHCX (Insurance) processing.

Flow:
  1. OCR the PDF (Docling waterfall)
  2. Classify / select NHCX resources
  3. Run NHCX insurance pipeline (generates bundle, uploads to GCS)
  4. Store GCS URI in Redis under key  result:<task_id>  with 24 h TTL
  5. Fire-and-forget log to session_logger service
"""

import os
import sys
import asyncio
import json
import logging
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.celery_app import celery_app

logger = logging.getLogger(__name__)

RESULT_TTL = int(os.getenv("TASK_RESULT_TTL", 86400))   # 24 h
SESSION_LOGGER_URL = os.getenv("SESSION_LOGGER_URL", "http://session-logger:8002")


def _get_redis():
    import redis as _redis
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return _redis.from_url(url, decode_responses=True)


def _fire_log(payload: dict):
    """POST a session log entry to the logger service. Never raises."""
    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{SESSION_LOGGER_URL}/log", json=payload)
    except Exception as exc:
        logger.warning(f"[session-logger] fire-and-forget failed: {exc}")


@celery_app.task(bind=True, name="pdf2nhcx.tasks.process_nhcx_task",
                 time_limit=1800, soft_time_limit=1740)
def process_nhcx_task(self, pdf_path: str, model: str = "gemma4"):
    """
    Async Celery task for NHCX insurance bundle generation.
    Returns a result dict that is also cached in Redis for /task-result/{task_id}.
    """
    task_id = self.request.id
    session_id = str(uuid.uuid4())
    task_filename = os.path.basename(pdf_path)
    start_time = time.perf_counter()

    def update(step: str, progress: int):
        self.update_state(state="PROGRESS",
                          meta={"step": step, "progress": progress,
                                "task_id": task_id})

    log_payload = {
        "service": "pdf2nhcx",
        "ip_address": "unknown",
    }

    try:
        # ── Step 1: OCR ──────────────────────────────────────────────────────
        update("OCR", 15)
        from utils.ocr_engine import extract_distilled_text_from_nhcx_pdf, select_nhcx_resources
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        distilled_text, pdf_base64 = loop.run_until_complete(
            extract_distilled_text_from_nhcx_pdf(pdf_path)
        )

        # ── Step 2: Classify ─────────────────────────────────────────────────
        update("Classifying document", 30)
        doc_type, must_resources, selected_other_resources = select_nhcx_resources(distilled_text)
        logger.info(f"[{task_id}] Document type: {doc_type}")

        # ── Step 3: NHCX Pipeline ─────────────────────────────────────────────
        update("LLM Extraction", 50)
        from utils.llm_requirements import run_nhcx_insurance_pipeline

        bundle = run_nhcx_insurance_pipeline(
            distilled_text, doc_type, selected_other_resources,
            pdf_base64=pdf_base64, idx=0, model=model
        )

        # ── Step 4: Store result in Redis ─────────────────────────────────────
        update("Storing results", 95)
        processing_time = round(time.perf_counter() - start_time, 2)
        filename_json = f"FHIR_BUNDLE_{doc_type}_Patient_0.json"
        gcs_uri = f"json_output/nhcx/{filename_json}"

        result_payload = {
            "status": "completed",
            "task_id": task_id,
            "doc_type": doc_type,
            "bundle": bundle,
            "gcs_uri": gcs_uri,
            "model_used": model,
        }
        r = _get_redis()
        r.setex(f"result:{task_id}", RESULT_TTL, json.dumps(result_payload))

        log_payload.update({
            "pdf_location": f"pdf_uploads/nhcx/{task_filename}",
            "json_location": gcs_uri,
        })

        update("Completed", 100)
        logger.info(f"[{task_id}] NHCX task completed")
        return result_payload

    except Exception as exc:
        logger.exception(f"[{task_id}] NHCX task failed: {exc}")
        error_payload = {"status": "failed", "task_id": task_id, "error": str(exc)}
        try:
            r = _get_redis()
            r.setex(f"result:{task_id}", RESULT_TTL, json.dumps(error_payload))
        except Exception:
            pass
        log_payload["pdf_location"] = f"pdf_uploads/nhcx/{task_filename}"
        raise

    finally:
        # Always attempt to log — success or failure
        _fire_log(log_payload)
