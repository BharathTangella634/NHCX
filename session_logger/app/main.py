"""
session_logger — FastAPI microservice (port 8002)
=================================================
Receives fire-and-forget log payloads from pdf2abdm and pdf2nhcx after each
document inference and persists them to nhcx.session_logs in Cloud SQL.

Endpoints:
  POST /log              Internal — called by peer services (no auth required
                         since the service is only reachable inside Docker network)
  GET  /health           Liveness probe
  GET  /logs             Paginated read of all session logs
  GET  /logs/stats       Aggregated counts by service & status (dashboard use)
"""

import logging
from typing import Optional, Literal

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from .core.config import settings
from .db.session import Base, engine, get_db
from .models.models import SessionLog

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Create tables on startup (idempotent) ─────────────────────────────────────
Base.metadata.create_all(bind=engine)
logger.info("session_logs table ensured.")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Internal logging service for the NHCX pipeline. "
        "Receives structured payloads from pdf2abdm / pdf2nhcx and writes them "
        "to the nhcx.session_logs table in Cloud SQL."
    ),
    openapi_tags=[
        {"name": "Health",    "description": "Liveness probes."},
        {"name": "Logging",   "description": "Ingest log entries from peer services."},
        {"name": "Analytics", "description": "Read / aggregate session logs."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SessionLogCreate(BaseModel):
    """Payload sent by pdf2abdm / pdf2nhcx after a completed inference."""
    session_id:      str
    service:         Literal["pdf2abdm", "pdf2nhcx"]
    filename:        Optional[str]   = None
    document_type:   Optional[str]   = None
    model_used:      Optional[str]   = None
    ocr_engine_used: Optional[str]   = None
    processing_time: Optional[float] = None
    gcs_uri:         Optional[str]   = None
    bundle_count:    Optional[int]   = 1
    status:          Literal["success", "failed"] = "success"
    error_message:   Optional[str]   = None
    client_ip:       Optional[str]   = None


class SessionLogRead(SessionLogCreate):
    id:         int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Liveness probe")
@app.get("/session-logger/health", tags=["Health"], include_in_schema=False)
def health_check():
    return {"status": "ok", "service": "session-logger"}


# ── Write endpoint ─────────────────────────────────────────────────────────────

@app.post("/log", tags=["Logging"], summary="Ingest a session log entry",
          status_code=201)
def create_log(payload: SessionLogCreate, db: Session = Depends(get_db)):
    """
    Called internally by pdf2abdm and pdf2nhcx via a BackgroundTask.
    Inserts one row into nhcx.session_logs.
    Returns 409 (idempotent) if session_id already exists.
    """
    existing = db.query(SessionLog).filter(
        SessionLog.session_id == payload.session_id
    ).first()

    if existing:
        logger.warning(f"Duplicate session_id received: {payload.session_id} — skipping.")
        return JSONResponse(
            status_code=409,
            content={"detail": "Session already logged.", "session_id": payload.session_id},
        )

    log_entry = SessionLog(**payload.model_dump())
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(
        f"Logged [{payload.service}] session={payload.session_id} "
        f"status={payload.status} time={payload.processing_time}s"
    )
    return {"id": log_entry.id, "session_id": log_entry.session_id}


# ── Read endpoints ─────────────────────────────────────────────────────────────

@app.get("/logs", tags=["Analytics"], summary="Paginated session log listing")
def list_logs(
    skip:    int = 0,
    limit:   int = 50,
    service: Optional[Literal["pdf2abdm", "pdf2nhcx"]] = None,
    status:  Optional[Literal["success", "failed"]]     = None,
    db: Session = Depends(get_db),
):
    """
    Returns paginated session logs, optionally filtered by service or status.
    Default page size is 50 rows; use `skip` + `limit` for pagination.
    """
    query = db.query(SessionLog)
    if service:
        query = query.filter(SessionLog.service == service)
    if status:
        query = query.filter(SessionLog.status == status)

    total = query.count()
    rows  = query.order_by(SessionLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total":  total,
        "skip":   skip,
        "limit":  limit,
        "items": [
            {
                "id":              r.id,
                "session_id":      r.session_id,
                "service":         r.service,
                "filename":        r.filename,
                "document_type":   r.document_type,
                "model_used":      r.model_used,
                "ocr_engine_used": r.ocr_engine_used,
                "processing_time": r.processing_time,
                "gcs_uri":         r.gcs_uri,
                "bundle_count":    r.bundle_count,
                "status":          r.status,
                "error_message":   r.error_message,
                "client_ip":       r.client_ip,
                "created_at":      str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
    }


@app.get("/logs/stats", tags=["Analytics"],
         summary="Aggregated counts for dashboard cards")
def log_stats(db: Session = Depends(get_db)):
    """
    Returns aggregate statistics used by the FHIR Converter dashboard:
      - total_sessions      — all-time unique document inferences
      - clinical_documents  — pdf2abdm successes
      - insurance_policies  — pdf2nhcx successes
      - failed              — total failures across both services
      - avg_processing_time — mean seconds across all successful sessions
    """
    total = db.query(func.count(SessionLog.id)).scalar() or 0

    clinical = (
        db.query(func.count(SessionLog.id))
        .filter(SessionLog.service == "pdf2abdm", SessionLog.status == "success")
        .scalar() or 0
    )
    insurance = (
        db.query(func.count(SessionLog.id))
        .filter(SessionLog.service == "pdf2nhcx", SessionLog.status == "success")
        .scalar() or 0
    )
    failed = (
        db.query(func.count(SessionLog.id))
        .filter(SessionLog.status == "failed")
        .scalar() or 0
    )
    avg_time = (
        db.query(func.avg(SessionLog.processing_time))
        .filter(SessionLog.status == "success")
        .scalar()
    )

    return {
        "total_sessions":      total,
        "clinical_documents":  clinical,
        "insurance_policies":  insurance,
        "failed":              failed,
        "avg_processing_time": round(float(avg_time), 2) if avg_time else None,
    }
