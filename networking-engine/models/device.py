import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from db import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    device_type = Column(String(50), default="server")
    is_authorized = Column(Boolean, default=False)
    monitoring_enabled = Column(Boolean, default=True)
    status = Column(String(20), default="offline")
    ping_interval = Column(Integer, default=30)
    snmp_config = Column(JSONB, default=dict)
    tcp_ports = Column(ARRAY(Integer), default=list)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True))

    ping_logs = relationship(
        "PingLog",
        back_populates="device",
        cascade="all, delete-orphan"
    )

    port_logs = relationship(
        "PortLog",
        back_populates="device",
        cascade="all, delete-orphan"
    )

    snmp_logs = relationship(
        "SnmpLog",
        back_populates="device",
        cascade="all, delete-orphan"
    )

    alerts = relationship(
        "Alert",
        back_populates="device",
        cascade="all, delete-orphan"
    )
