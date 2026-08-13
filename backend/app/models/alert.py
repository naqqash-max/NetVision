import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.db import Base

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # INFO, WARNING, CRITICAL
    status = Column(String(20), default="OPEN")     # OPEN, ACKNOWLEDGED, RESOLVED
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    monitored_resource = Column(String(255), nullable=True)
    current_value = Column(String(255), nullable=True)
    threshold = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    details = Column(JSONB, default=dict)

    device = relationship("Device", back_populates="alerts")
