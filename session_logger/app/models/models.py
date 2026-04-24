from sqlalchemy import Column, BigInteger, SmallInteger, Float, String, Text, Enum, TIMESTAMP
from sqlalchemy.sql import text
from ..db.session import Base


class SessionLog(Base):
    """One row per document inference request across pdf2abdm and pdf2nhcx."""

    __tablename__ = "session_logs"

    id              = Column(BigInteger,   primary_key=True, index=True, autoincrement=True)
    session_id      = Column(String(36),   nullable=False, unique=True,
                             comment="UUID v4 generated per request")
    service         = Column(Enum("pdf2abdm", "pdf2nhcx"), nullable=False,
                             comment="Which pipeline produced this log")
    filename        = Column(String(512),  nullable=True,
                             comment="Original uploaded PDF filename")
    document_type   = Column(String(128),  nullable=True,
                             comment="Classified doc type")
    model_used      = Column(String(64),   nullable=True,
                             comment="LLM model identifier (e.g. gemma4)")
    ocr_engine_used = Column(String(64),   nullable=True,
                             comment="OCR engine used (e.g. docling, auto)")
    processing_time = Column(Float,        nullable=True,
                             comment="End-to-end processing time in seconds")
    gcs_uri         = Column(Text,         nullable=True,
                             comment="GCS URI of the uploaded source PDF")
    bundle_count    = Column(SmallInteger, nullable=True, default=1,
                             comment="Number of FHIR bundles returned")
    status          = Column(Enum("success", "failed"), nullable=False, default="success")
    error_message   = Column(Text,         nullable=True,
                             comment="Populated only when status = failed")
    client_ip       = Column(String(64),   nullable=True,
                             comment="Public IP of the end user")
    created_at      = Column(TIMESTAMP,    server_default=text("CURRENT_TIMESTAMP"))
