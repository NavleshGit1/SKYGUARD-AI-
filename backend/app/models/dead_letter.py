"""
SkyGuard AI — Dead-Letter Queue ORM Model
Blueprint §4 Component 3.9: Quarantine table for malformed/corrupted records
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, TIMESTAMP, Integer
from backend.app.core.database import Base


class DeadLetterRecord(Base):
    """
    Append-only quarantine table for any record that fails Pydantic validation,
    HMAC verification, or encounters a processing error during ingestion.
    Enables forensic replay and root-cause analysis without data loss.
    """
    __tablename__ = "dead_letter_queue"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    received_at    = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    station_id     = Column(String(64),  nullable=True,  index=True)
    raw_payload    = Column(Text,        nullable=False,
                            comment="Raw JSON body of the rejected record")
    failure_reason = Column(String(256), nullable=False,
                            comment="Failure category: SCHEMA_VALIDATION | HMAC_FAILURE | PROCESSING_ERROR | REPLAY_DUPLICATE")
    error_detail   = Column(Text,        nullable=True,
                            comment="Full exception traceback or validation error message")
    source_ip      = Column(String(45),  nullable=True)
    is_replayed    = Column(Integer,     default=0,
                            comment="1 if this record was replayed after fixing the root cause")
    replayed_at    = Column(TIMESTAMP(timezone=True), nullable=True)
