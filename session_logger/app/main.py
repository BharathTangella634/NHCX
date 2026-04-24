"""
session_logger — FastAPI microservice (port 8002)
=================================================
Persists session data into the pre-existing nhcx.session_logs table on Cloud SQL.

Table schema (existing):
    session_id    binary(16)  PK
    user_id       binary(16)  unique per ip_address (deterministic UUID from IP)
    ip_address    varchar(45)
    state         varchar(100)
    city          varchar(100)
    document_type enum('clinical_document','insurance_document')
    pdf_location  text   — GCS URI of uploaded PDF
    json_location text   — GCS URI of output JSON
    created_at    datetime (auto IST)

Endpoints:
  POST /log              — called by pdf2abdm / pdf2nhcx after each inference
  GET  /health           — liveness probe
  GET  /logs             — paginated read of all session logs
  GET  /logs/stats       — aggregated counts (feeds dashboard cards)
"""

import uuid
import logging
from typing import Optional, Literal

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from .core.config import settings
from .db.session import Base, engine, get_db
from .models.models import SessionLog

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── NOTE: We do NOT call Base.metadata.create_all() — the table already exists
#    on Cloud SQL with a specific schema we must not overwrite.
logger.info("session_logger started — using pre-existing nhcx.session_logs schema.")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Internal logging service for the NHCX pipeline. "
        "Persists session data into nhcx.session_logs on Cloud SQL."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ip_to_user_id(ip: str) -> bytes:
    """Derive a deterministic binary(16) UUID from an IP address."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, ip or "unknown").bytes

def _new_session_id() -> bytes:
    return uuid.uuid4().bytes

def _doc_type_enum(service: str) -> str:
    """Map service name to the existing enum values."""
    return "clinical_document" if service == "pdf2abdm" else "insurance_document"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SessionLogCreate(BaseModel):
    """Payload sent by pdf2abdm / pdf2nhcx after each completed inference."""
    service:      Literal["pdf2abdm", "pdf2nhcx"]
    ip_address:   Optional[str]  = "unknown"
    state:        Optional[str]  = None
    city:         Optional[str]  = None
    pdf_location: Optional[str]  = None   # GCS URI of uploaded PDF
    json_location: Optional[str] = None   # GCS URI of output JSON bundle


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Liveness probe")
def health_check():
    return {"status": "ok", "service": "session-logger"}


# ── Write endpoint ─────────────────────────────────────────────────────────────

@app.post("/log", tags=["Logging"], summary="Ingest a session log entry",
          status_code=201)
def create_log(payload: SessionLogCreate, db: Session = Depends(get_db)):
    """
    Called internally by pdf2abdm and pdf2nhcx via a BackgroundTask.
    Inserts one row per inference into nhcx.session_logs.

    Note: the table has UNIQUE KEY (user_id, ip_address) — duplicate IP+service
    combinations will be inserted as separate rows because session_id (PK) is
    always new.  The unique key covers user_id+ip_address, not per inference.
    We INSERT IGNORE to gracefully handle the unique constraint if the same
    user submits multiple documents.
    """
    session_id = _new_session_id()
    user_id    = _ip_to_user_id(payload.ip_address or "unknown")
    doc_type   = _doc_type_enum(payload.service)

    try:
        # Use INSERT IGNORE to skip duplicate (user_id, ip_address) pairs
        db.execute(
            text("""
                INSERT IGNORE INTO session_logs
                    (session_id, user_id, ip_address, state, city,
                     document_type, pdf_location, json_location)
                VALUES
                    (:session_id, :user_id, :ip_address, :state, :city,
                     :document_type, :pdf_location, :json_location)
            """),
            {
                "session_id":    session_id,
                "user_id":       user_id,
                "ip_address":    payload.ip_address or "unknown",
                "state":         payload.state,
                "city":          payload.city,
                "document_type": doc_type,
                "pdf_location":  payload.pdf_location,
                "json_location": payload.json_location,
            }
        )
        db.commit()
        logger.info(
            f"Logged [{payload.service}] ip={payload.ip_address} "
            f"doc_type={doc_type} pdf={payload.pdf_location}"
        )
        return {"status": "logged", "document_type": doc_type}

    except Exception as exc:
        db.rollback()
        logger.error(f"[session-logger] DB write failed: {exc}")
        return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── Read endpoints ─────────────────────────────────────────────────────────────

@app.get("/logs", tags=["Analytics"], summary="Paginated session log listing")
def list_logs(
    skip:  int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Returns the most recent session logs (newest first)."""
    total = db.query(func.count(SessionLog.session_id)).scalar() or 0
    rows  = (
        db.query(SessionLog)
        .order_by(SessionLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "skip":  skip,
        "limit": limit,
        "items": [
            {
                "ip_address":    r.ip_address,
                "state":         r.state,
                "city":          r.city,
                "document_type": r.document_type,
                "pdf_location":  r.pdf_location,
                "json_location": r.json_location,
                "created_at":    str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
    }


@app.get("/logs/stats", tags=["Analytics"],
         summary="Aggregated counts for dashboard cards")
def log_stats(db: Session = Depends(get_db)):
    """
    Returns aggregate statistics for the NHCX dashboard:
      total_sessions     — all rows (every unique user+IP inference)
      clinical_documents — rows where document_type = 'clinical_document'
      insurance_policies — rows where document_type = 'insurance_document'
      unique_ips         — distinct IP addresses seen
    """
    total = db.query(func.count(SessionLog.session_id)).scalar() or 0

    clinical = (
        db.query(func.count(SessionLog.session_id))
        .filter(SessionLog.document_type == "clinical_document")
        .scalar() or 0
    )
    insurance = (
        db.query(func.count(SessionLog.session_id))
        .filter(SessionLog.document_type == "insurance_document")
        .scalar() or 0
    )
    unique_ips = (
        db.query(func.count(func.distinct(SessionLog.ip_address)))
        .scalar() or 0
    )

    return {
        "total_sessions":      total,
        "clinical_documents":  clinical,
        "insurance_policies":  insurance,
        "unique_ips":          unique_ips,
    }
