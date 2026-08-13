from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import ipaddress

class DeviceBase(BaseModel):
    ip_address: str
    hostname: str
    name: Optional[str] = None
    description: Optional[str] = None
    device_type: str = "server"
    monitoring_enabled: bool = True
    ping_interval: int = 30
    snmp_config: Dict[str, Any] = Field(default_factory=dict)
    tcp_ports: List[int] = Field(default_factory=list)

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v):
        try:
            ipaddress.IPv4Address(v)
            return v
        except ValueError:
            import re
            if re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
                return v
            raise ValueError("Invalid IPv4 address or hostname format")

    @field_validator('tcp_ports')
    @classmethod
    def validate_ports(cls, v):
        if v is not None:
            for port in v:
                if not (1 <= port <= 65535):
                    raise ValueError(f"Invalid TCP port: {port}. Must be between 1 and 65535.")
        return v

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    device_type: Optional[str] = None
    is_authorized: Optional[bool] = None
    monitoring_enabled: Optional[bool] = None
    ping_interval: Optional[int] = None
    snmp_config: Optional[Dict[str, Any]] = None
    tcp_ports: Optional[List[int]] = None
    status: Optional[str] = None

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v):
        if v is None:
            return v
        try:
            ipaddress.IPv4Address(v)
            return v
        except ValueError:
            import re
            if re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
                return v
            raise ValueError("Invalid IPv4 address or hostname format")

    @field_validator('tcp_ports')
    @classmethod
    def validate_ports(cls, v):
        if v is not None:
            for port in v:
                if not (1 <= port <= 65535):
                    raise ValueError(f"Invalid TCP port: {port}. Must be between 1 and 65535.")
        return v

class DeviceResponse(DeviceBase):
    id: UUID
    is_authorized: bool
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime

    @field_validator('snmp_config')
    @classmethod
    def sanitize_snmp_config(cls, v):
        if isinstance(v, dict):
            safe_config = {k: val for k, val in v.items() if k not in ("community", "auth_key", "priv_key", "username")}
            if "snmp_enabled" not in safe_config:
                safe_config["snmp_enabled"] = v.get("snmp_enabled", False)
            return safe_config
        return v

    class Config:
        from_attributes = True


class SnmpStatusResponse(BaseModel):
    device_id: UUID
    snmp_enabled: bool
    working: bool
    error_msg: Optional[str] = None
    last_polled: Optional[datetime] = None


class SnmpSystemResponse(BaseModel):
    device_id: UUID
    hostname: Optional[str] = None
    description: Optional[str] = None
    uptime: Optional[int] = None


class SnmpInterfaceResponse(BaseModel):
    index: int
    name: str
    description: str
    op_status: str
    admin_status: str
    speed: int
    in_octets: int
    out_octets: int
    in_rate_bps: float
    out_rate_bps: float
    in_rate_bytes_sec: float
    out_rate_bytes_sec: float


class SnmpLogResponse(BaseModel):
    id: int
    device_id: UUID
    metrics: Dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True

