from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class ReportFilterParams(BaseModel):
    time_range: Optional[str] = "24h"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    device_id: Optional[UUID] = None
    device_type: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    alert_type: Optional[str] = None
    port: Optional[int] = None


# 1. Network Health Report
class NetworkHealthReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    network_health_score: float
    total_devices: int
    online_devices: int
    degraded_devices: int
    offline_devices: int
    avg_latency_ms: Optional[float] = None
    avg_packet_loss_pct: Optional[float] = None
    active_alerts_count: int
    critical_alerts_count: int
    warning_alerts_count: int
    info_alerts_count: int


# 2. Device Availability Report
class DeviceAvailabilityItem(BaseModel):
    device_id: UUID
    device_name: str
    ip_address: str
    device_type: str
    monitoring_period: str
    total_checks: int
    online_checks: int
    offline_checks: int
    availability_pct: float
    online_duration_hours: float
    offline_duration_hours: float
    avg_latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    incident_count: int

class DeviceAvailabilityReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    total_devices: int
    avg_availability_pct: float
    items: List[DeviceAvailabilityItem]


# 3. Alert / Incident Report
class AlertReportItem(BaseModel):
    alert_id: UUID
    device_id: UUID
    device_name: str
    ip_address: str
    alert_type: str
    severity: str
    title: str
    status: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    incident_duration_mins: Optional[float] = None

class AlertReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    total_incidents: int
    critical_incidents: int
    warning_incidents: int
    info_incidents: int
    open_incidents: int
    acknowledged_incidents: int
    resolved_incidents: int
    avg_incident_duration_mins: Optional[float] = None
    items: List[AlertReportItem]


# 4. ICMP Performance Report
class IcmpReportItem(BaseModel):
    device_id: UUID
    device_name: str
    ip_address: str
    total_checks: int
    avg_latency_ms: Optional[float] = None
    min_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    availability_pct: float

class IcmpReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    total_checks: int
    avg_latency_ms: Optional[float] = None
    avg_packet_loss_pct: Optional[float] = None
    avg_availability_pct: float
    items: List[IcmpReportItem]


# 5. TCP Service Report
class TcpReportItem(BaseModel):
    device_id: UUID
    device_name: str
    ip_address: str
    port: int
    service_status: str
    total_checks: int
    open_checks: int
    failed_checks: int
    avg_response_time_ms: Optional[float] = None
    availability_pct: float
    last_check_timestamp: Optional[datetime] = None

class TcpReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    total_checks: int
    avg_response_time_ms: Optional[float] = None
    overall_availability_pct: float
    items: List[TcpReportItem]


# 6. SNMP Interface Traffic Report
class SnmpReportItem(BaseModel):
    device_id: UUID
    device_name: str
    ip_address: str
    interface_name: str
    interface_status: str
    interface_speed_bps: Optional[int] = None
    avg_inbound_bps: Optional[float] = None
    avg_outbound_bps: Optional[float] = None
    traffic_utilization_pct: Optional[float] = None

class SnmpReport(BaseModel):
    reporting_period: str
    start_time: datetime
    end_time: datetime
    total_devices: int
    items: List[SnmpReportItem]
