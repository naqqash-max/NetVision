from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class DeviceNameOnly(BaseModel):
    name: Optional[str] = None
    hostname: str

    model_config = ConfigDict(from_attributes=True)

class AlertBase(BaseModel):
    device_id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: str
    monitored_resource: Optional[str] = None
    current_value: Optional[str] = None
    threshold: Optional[str] = None
    details: Dict[str, Any] = {}

class AlertResponse(AlertBase):
    id: UUID
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    device: Optional[DeviceNameOnly] = None

    model_config = ConfigDict(from_attributes=True)

class AlertSummaryResponse(BaseModel):
    total_active: int
    critical: int
    warning: int
    acknowledged: int
    resolved: int

class AlertSettingsResponse(BaseModel):
    icmp_latency_warning: float
    icmp_latency_critical: float
    packet_loss_warning: float
    packet_loss_critical: float
    snmp_traffic_warning_bps: float

class AlertSettingsUpdate(BaseModel):
    icmp_latency_warning: Optional[float] = None
    icmp_latency_critical: Optional[float] = None
    packet_loss_warning: Optional[float] = None
    packet_loss_critical: Optional[float] = None
    snmp_traffic_warning_bps: Optional[float] = None
