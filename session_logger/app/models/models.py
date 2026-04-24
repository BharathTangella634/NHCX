import uuid
from sqlalchemy import Column, String, Text, Enum, DateTime
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.sql import text
from ..db.session import Base


def _new_binary_uuid() -> bytes:
    """Generate a UUID4 and return its 16-byte binary representation."""
    return uuid.uuid4().bytes


class SessionLog(Base):
    """
    Maps to the existing nhcx.session_logs table.

    Schema (pre-existing on Cloud SQL):
        session_id    binary(16)  PK
        user_id       binary(16)  NOT NULL  (unique per ip_address)
        ip_address    varchar(45) NOT NULL
        state         varchar(100)
        city          varchar(100)
        document_type enum('clinical_document','insurance_document')
        pdf_location  text        (GCS URI of the uploaded PDF)
        json_location text        (GCS URI of the output JSON bundle)
        created_at    datetime    default IST now()
    """

    __tablename__ = "session_logs"

    session_id    = Column(BINARY(16),   primary_key=True, default=_new_binary_uuid,
                           comment="UUID v4 stored as binary(16)")
    user_id       = Column(BINARY(16),   nullable=False,
                           comment="Unique per ip_address — deterministic UUID from IP")
    ip_address    = Column(String(45),   nullable=False)
    state         = Column(String(100),  nullable=True)
    city          = Column(String(100),  nullable=True)
    document_type = Column(Enum("clinical_document", "insurance_document"), nullable=True)
    pdf_location  = Column(Text,         nullable=True,
                           comment="GCS URI of the uploaded PDF")
    json_location = Column(Text,         nullable=True,
                           comment="GCS URI of the output JSON bundle")
    created_at    = Column(DateTime,     server_default=text(
                           "convert_tz(now(),'UTC','+05:30')"))
