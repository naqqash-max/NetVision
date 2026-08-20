from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class NocSummaryResponse(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    degraded_devices: int
    active_alerts_count: int
    critical_alerts_count: int
    warning_alerts_count: int
    info_alerts_count: int
    network_health_score: float
    avg_latency_ms: Optional[float] = None
    avg_packet_loss_pct: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class IcmpHistoryPoint(BaseModel):
    timestamp: datetime
    device_id: UUID
    hostname: str
    latency_ms: Optional[float] = None
    packet_loss_pct: float
    is_online: bool

    model_config = ConfigDict(from_attributes=True)

class TcpHistoryPoint(BaseModel):
    timestamp: datetime
    device_id: UUID
    hostname: str
    port: int
    response_time_ms: Optional[float] = None
    is_open: bool

    model_config = ConfigDict(from_attributes=True)

class SnmpHistoryPoint(BaseModel):
    timestamp: datetime
    device_id: UUID
    hostname: str
    cpu_util: Optional[float] = None
    mem_util: Optional[float] = None
    in_rate_bps: float = 0.0
    out_rate_bps: float = 0.0

    model_config = ConfigDict(from_attributes=True)

class HistoricalMetricsResponse(BaseModel):
    time_range: str
    start_time: datetime
    end_time: datetime
    icmp_metrics: List[IcmpHistoryPoint]
    tcp_metrics: List[TcpHistoryPoint]
    snmp_metrics: List[SnmpHistoryPoint]

    model_config = ConfigDict(from_attributes=True)
