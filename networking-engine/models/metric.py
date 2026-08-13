from sqlalchemy import Column, String, BigInteger, Float, Boolean, ForeignKey, DateTime, func, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db import Base

class PingLog(Base):
    __tablename__ = "ping_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    latency_ms = Column(Float, nullable=True)  # Average latency
    min_latency = Column(Float, nullable=True)
    max_latency = Column(Float, nullable=True)
    packet_loss_pct = Column(Float, nullable=False)
    is_online = Column(Boolean, nullable=False)
    status = Column(String(20), default="offline")
    error_msg = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="ping_logs")


class PortLog(Base):
    __tablename__ = "port_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    port = Column(Integer, nullable=False)
    is_open = Column(Boolean, nullable=False)
    response_time_ms = Column(Float, nullable=True)
    status = Column(String(50), default="closed")
    error_msg = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="port_logs")


class SnmpLog(Base):
    __tablename__ = "snmp_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False
    )
    metrics = Column(JSONB, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="snmp_logs")

