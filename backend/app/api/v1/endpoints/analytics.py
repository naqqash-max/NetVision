from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from app.core.db import get_db
from app.models.device import Device
from app.models.alert import Alert
from app.models.metric import PingLog, PortLog, SnmpLog
from app.models.user import User
from app.schemas.analytics import (
    NocSummaryResponse,
    HistoricalMetricsResponse,
    IcmpHistoryPoint,
    TcpHistoryPoint,
    SnmpHistoryPoint
)
from app.api.deps import require_viewer

router = APIRouter()

@router.get("/noc-summary", response_model=NocSummaryResponse)
def get_noc_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve real-time NOC network overview statistics and health score calculated from real database metrics.
    """
    try:
        total_devices = db.query(Device).count()
        online_devices = db.query(Device).filter(Device.status == "online").count()
        offline_devices = db.query(Device).filter(Device.status == "offline").count()
        degraded_devices = db.query(Device).filter(Device.status == "degraded").count()

        active_alerts_query = db.query(Alert).filter(Alert.status.in_(["OPEN", "ACKNOWLEDGED"]))
        active_alerts_count = active_alerts_query.count()
        critical_alerts_count = active_alerts_query.filter(Alert.severity == "CRITICAL").count()
        warning_alerts_count = active_alerts_query.filter(Alert.severity == "WARNING").count()
        info_alerts_count = active_alerts_query.filter(Alert.severity == "INFO").count()

        # Query recent ICMP ping logs for average latency & packet loss
        fifteen_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
        recent_pings = db.query(PingLog).filter(PingLog.timestamp >= fifteen_mins_ago).all()

        if not recent_pings:
            # Fallback to last 50 ping logs if no pings in last 15 minutes
            recent_pings = db.query(PingLog).order_by(PingLog.timestamp.desc()).limit(50).all()

        latencies = [p.latency_ms for p in recent_pings if p.latency_ms is not None]
        packet_losses = [p.packet_loss_pct for p in recent_pings if p.packet_loss_pct is not None]

        avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else None
        avg_packet_loss_pct = round(sum(packet_losses) / len(packet_losses), 2) if packet_losses else None

        # Network Health Score Calculation (0 - 100%)
        if total_devices == 0:
            health_score = 100.0
        else:
            device_health_ratio = ((online_devices * 1.0) + (degraded_devices * 0.5)) / total_devices
            base_score = device_health_ratio * 100.0
            alert_penalty = (critical_alerts_count * 6.0) + (warning_alerts_count * 2.0)
            loss_penalty = (avg_packet_loss_pct or 0.0) * 0.5
            raw_score = base_score - alert_penalty - loss_penalty
            health_score = max(0.0, min(100.0, round(raw_score, 1)))

        return NocSummaryResponse(
            total_devices=total_devices,
            online_devices=online_devices,
            offline_devices=offline_devices,
            degraded_devices=degraded_devices,
            active_alerts_count=active_alerts_count,
            critical_alerts_count=critical_alerts_count,
            warning_alerts_count=warning_alerts_count,
            info_alerts_count=info_alerts_count,
            network_health_score=health_score,
            avg_latency_ms=avg_latency_ms,
            avg_packet_loss_pct=avg_packet_loss_pct
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while generating NOC summary: {str(e)}"
        )

@router.get("/history", response_model=HistoricalMetricsResponse)
def get_historical_analytics(
    time_range: str = Query("1h", description="Time range: 15m, 1h, 6h, 24h, 7d"),
    device_id: Optional[UUID] = Query(None, description="Filter metrics by specific device ID"),
    limit: int = Query(500, ge=1, le=2000, description="Max historical points per metric type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve historical time-series analytics (ICMP latency/loss, TCP response times, SNMP traffic) from real PostgreSQL metric tables.
    """
    now = datetime.now(timezone.utc)
    
    # Calculate start time based on time_range parameter
    time_range_clean = time_range.strip().lower()
    if time_range_clean == "15m":
        start_time = now - timedelta(minutes=15)
    elif time_range_clean == "1h":
        start_time = now - timedelta(hours=1)
    elif time_range_clean == "6h":
        start_time = now - timedelta(hours=6)
    elif time_range_clean == "24h":
        start_time = now - timedelta(hours=24)
    elif time_range_clean == "7d":
        start_time = now - timedelta(days=7)
    else:
        # Default to 1 hour if invalid range specified
        start_time = now - timedelta(hours=1)
        time_range_clean = "1h"

    try:
        # 1. ICMP Ping Logs
        ping_query = db.query(PingLog, Device.hostname).join(Device, PingLog.device_id == Device.id)
        ping_query = ping_query.filter(PingLog.timestamp >= start_time)
        if device_id:
            ping_query = ping_query.filter(PingLog.device_id == device_id)
        
        ping_rows = ping_query.order_by(PingLog.timestamp.asc()).limit(limit).all()

        icmp_metrics = [
            IcmpHistoryPoint(
                timestamp=p.timestamp,
                device_id=p.device_id,
                hostname=hostname,
                latency_ms=p.latency_ms,
                packet_loss_pct=p.packet_loss_pct,
                is_online=p.is_online
            )
            for p, hostname in ping_rows
        ]

        # 2. TCP Port Logs
        port_query = db.query(PortLog, Device.hostname).join(Device, PortLog.device_id == Device.id)
        port_query = port_query.filter(PortLog.timestamp >= start_time)
        if device_id:
            port_query = port_query.filter(PortLog.device_id == device_id)

        port_rows = port_query.order_by(PortLog.timestamp.asc()).limit(limit).all()

        tcp_metrics = [
            TcpHistoryPoint(
                timestamp=p.timestamp,
                device_id=p.device_id,
                hostname=hostname,
                port=p.port,
                response_time_ms=p.response_time_ms,
                is_open=p.is_open
            )
            for p, hostname in port_rows
        ]

        # 3. SNMP Logs
        snmp_query = db.query(SnmpLog, Device.hostname).join(Device, SnmpLog.device_id == Device.id)
        snmp_query = snmp_query.filter(SnmpLog.timestamp >= start_time)
        if device_id:
            snmp_query = snmp_query.filter(SnmpLog.device_id == device_id)

        snmp_rows = snmp_query.order_by(SnmpLog.timestamp.asc()).limit(limit).all()

        snmp_metrics = []
        for s, hostname in snmp_rows:
            metrics_data = s.metrics or {}
            system_data = metrics_data.get("system", {})
            interfaces_data = metrics_data.get("interfaces", [])

            cpu_util = metrics_data.get("cpu_util")
            mem_util = metrics_data.get("mem_util")

            # Sum in_rate_bps and out_rate_bps across interfaces
            total_in_bps = sum(iface.get("in_rate_bps", 0.0) for iface in interfaces_data)
            total_out_bps = sum(iface.get("out_rate_bps", 0.0) for iface in interfaces_data)

            snmp_metrics.append(SnmpHistoryPoint(
                timestamp=s.timestamp,
                device_id=s.device_id,
                hostname=hostname,
                cpu_util=cpu_util,
                mem_util=mem_util,
                in_rate_bps=total_in_bps,
                out_rate_bps=total_out_bps
            ))

        return HistoricalMetricsResponse(
            time_range=time_range_clean,
            start_time=start_time,
            end_time=now,
            icmp_metrics=icmp_metrics,
            tcp_metrics=tcp_metrics,
            snmp_metrics=snmp_metrics
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving historical analytics: {str(e)}"
        )
