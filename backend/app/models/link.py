import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.db import Base

class Link(Base):
    __tablename__ = "links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    target_device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    source_interface = Column(String(100), nullable=True)
    target_interface = Column(String(100), nullable=True)
    link_type = Column(String(50), default="ethernet")
    status = Column(String(20), default="active")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    source_device = relationship(
        "Device",
        foreign_keys=[source_device_id],
        back_populates="links_as_source"
    )
    target_device = relationship(
        "Device",
        foreign_keys=[target_device_id],
        back_populates="links_as_target"
    )
