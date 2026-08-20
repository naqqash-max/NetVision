from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class PingLogResponse(BaseModel):
    id: int
    device_id: UUID
    latency_ms: Optional[float] = None
    min_latency: Optional[float] = None
    max_latency: Optional[float] = None
    packet_loss_pct: float
    is_online: bool
    status: str
    error_msg: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class DeviceStatusResponse(BaseModel):
    device_id: UUID
    status: str
    last_seen: Optional[datetime] = None
    is_online: bool

class ManualMonitorResponse(BaseModel):
    device_id: UUID
    timestamp: datetime
    is_online: bool
    status: str
    latency_ms: Optional[float] = None
    min_latency: Optional[float] = None
    max_latency: Optional[float] = None
    packet_loss_pct: float
    error_msg: Optional[str] = None

class PortLogResponse(BaseModel):
    id: int
    device_id: UUID
    port: int
    is_open: bool
    response_time_ms: Optional[float] = None
    status: str
    error_msg: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class PortStatusResponse(BaseModel):
    port: int
    is_open: bool
    status: str
    response_time_ms: Optional[float] = None
    last_checked: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
