import uuid
import enum
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.core.db import Base

class DeviceType(str, enum.Enum):
    ROUTER = "router"
    SWITCH = "switch"
    SERVER = "server"
    FIREWALL = "firewall"
    IOT = "iot"

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    # Note: Use string references to avoid circular import issues
    links_as_source = relationship(
        "Link",
        foreign_keys="Link.source_device_id",
        back_populates="source_device",
        cascade="all, delete-orphan"
    )
    links_as_target = relationship(
        "Link",
        foreign_keys="Link.target_device_id",
        back_populates="target_device",
        cascade="all, delete-orphan"
    )
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
