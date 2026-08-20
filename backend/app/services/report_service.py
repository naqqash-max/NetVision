import io
import csv
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.device import Device
from app.models.alert import Alert
from app.models.metric import PingLog, PortLog, SnmpLog

from app.schemas.report import (
    NetworkHealthReport,
    DeviceAvailabilityReport, DeviceAvailabilityItem,
    AlertReport, AlertReportItem,
    IcmpReport, IcmpReportItem,
    TcpReport, TcpReportItem,
    SnmpReport, SnmpReportItem
)

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.pdfgen import canvas


def resolve_time_range(
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)
    
    if start_time and end_time:
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        period_str = f"Custom Range ({start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC)"
        return start_time, end_time, period_str

    tr = (time_range or "24h").strip().lower()
    if tr == "15m":
        st = now - timedelta(minutes=15)
        period_str = "Last 15 Minutes"
    elif tr == "1h":
        st = now - timedelta(hours=1)
        period_str = "Last 1 Hour"
    elif tr == "6h":
        st = now - timedelta(hours=6)
        period_str = "Last 6 Hours"
    elif tr == "24h":
        st = now - timedelta(hours=24)
        period_str = "Last 24 Hours"
    elif tr == "7d":
        st = now - timedelta(days=7)
        period_str = "Last 7 Days"
    else:
        st = now - timedelta(hours=24)
        period_str = "Last 24 Hours"

    return st, now, period_str


def get_network_health_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None,
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None
) -> NetworkHealthReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    # Base Device Query
    dev_query = db.query(Device)
    if device_id:
        dev_query = dev_query.filter(Device.id == device_id)
    if device_type and device_type.upper() != "ALL":
        dev_query = dev_query.filter(Device.device_type == device_type.lower())
    if status and status.upper() != "ALL":
        dev_query = dev_query.filter(Device.status == status.lower())

    devices = dev_query.all()
    device_ids = [d.id for d in devices]

    total_devices = len(devices)
    online_devices = sum(1 for d in devices if d.status == "online")
    degraded_devices = sum(1 for d in devices if d.status == "degraded")
    offline_devices = sum(1 for d in devices if d.status == "offline")

    # Alert Statistics in Period
    alert_q = db.query(Alert).filter(Alert.created_at >= st, Alert.created_at <= et)
    if device_ids:
        alert_q = alert_q.filter(Alert.device_id.in_(device_ids))
    elif device_id:
        alert_q = alert_q.filter(Alert.device_id == device_id)

    if severity and severity.upper() != "ALL":
        alert_q = alert_q.filter(Alert.severity == severity.upper())
    if alert_type and alert_type.upper() != "ALL":
        alert_q = alert_q.filter(Alert.alert_type == alert_type)

    all_alerts = alert_q.all()
    active_alerts_count = sum(1 for a in all_alerts if a.status in ["OPEN", "ACKNOWLEDGED"])
    critical_alerts_count = sum(1 for a in all_alerts if a.severity == "CRITICAL")
    warning_alerts_count = sum(1 for a in all_alerts if a.severity == "WARNING")
    info_alerts_count = sum(1 for a in all_alerts if a.severity == "INFO")

    # Telemetry Ping Logs in Period
    ping_q = db.query(PingLog).filter(PingLog.timestamp >= st, PingLog.timestamp <= et)
    if device_ids:
        ping_q = ping_q.filter(PingLog.device_id.in_(device_ids))
    pings = ping_q.all()

    latencies = [p.latency_ms for p in pings if p.latency_ms is not None]
    losses = [p.packet_loss_pct for p in pings if p.packet_loss_pct is not None]

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
    avg_loss = round(sum(losses) / len(losses), 2) if losses else None

    # Calculate NOC Health Score using canonical formula
    if total_devices == 0:
        health_score = 100.0
    else:
        device_health_ratio = ((online_devices * 1.0) + (degraded_devices * 0.5)) / total_devices
        base_score = device_health_ratio * 100.0
        alert_penalty = (critical_alerts_count * 6.0) + (warning_alerts_count * 2.0)
        loss_penalty = (avg_loss or 0.0) * 0.5
        raw_score = base_score - alert_penalty - loss_penalty
        health_score = max(0.0, min(100.0, round(raw_score, 1)))

    return NetworkHealthReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        network_health_score=health_score,
        total_devices=total_devices,
        online_devices=online_devices,
        degraded_devices=degraded_devices,
        offline_devices=offline_devices,
        avg_latency_ms=avg_latency,
        avg_packet_loss_pct=avg_loss,
        active_alerts_count=active_alerts_count,
        critical_alerts_count=critical_alerts_count,
        warning_alerts_count=warning_alerts_count,
        info_alerts_count=info_alerts_count
    )


def get_device_availability_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None,
    device_type: Optional[str] = None,
    status: Optional[str] = None
) -> DeviceAvailabilityReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    dev_query = db.query(Device)
    if device_id:
        dev_query = dev_query.filter(Device.id == device_id)
    if device_type and device_type.upper() != "ALL":
        dev_query = dev_query.filter(Device.device_type == device_type.lower())
    if status and status.upper() != "ALL":
        dev_query = dev_query.filter(Device.status == status.lower())

    devices = dev_query.all()
    total_period_hours = max(0.01, (et - st).total_seconds() / 3600.0)

    device_ids = [d.id for d in devices]

    # Query aggregated ping statistics for all devices in the period
    ping_stats_map = {}
    if device_ids:
        from sqlalchemy import case
        ping_stats = db.query(
            PingLog.device_id,
            func.count(PingLog.id).label("total_checks"),
            func.sum(case((PingLog.is_online == True, 1), else_=0)).label("online_checks"),
            func.avg(PingLog.latency_ms).label("avg_latency"),
            func.avg(PingLog.packet_loss_pct).label("avg_loss")
        ).filter(
            PingLog.device_id.in_(device_ids),
            PingLog.timestamp >= st,
            PingLog.timestamp <= et
        ).group_by(PingLog.device_id).all()

        ping_stats_map = {
            row.device_id: {
                "total_checks": row.total_checks,
                "online_checks": row.online_checks or 0,
                "avg_latency": row.avg_latency,
                "avg_loss": row.avg_loss
            }
            for row in ping_stats
        }

    # Query aggregated incident counts for all devices in the period
    alert_stats_map = {}
    if device_ids:
        alert_stats = db.query(
            Alert.device_id,
            func.count(Alert.id).label("incident_count")
        ).filter(
            Alert.device_id.in_(device_ids),
            Alert.created_at >= st,
            Alert.created_at <= et
        ).group_by(Alert.device_id).all()

        alert_stats_map = {row.device_id: row.incident_count for row in alert_stats}

    items: List[DeviceAvailabilityItem] = []
    total_avail_sum = 0.0

    for dev in devices:
        stats = ping_stats_map.get(dev.id)
        if stats:
            total_checks = stats["total_checks"]
            online_checks = stats["online_checks"]
            offline_checks = total_checks - online_checks
            avail_pct = round((online_checks / total_checks) * 100.0, 2)
            avg_lat = round(stats["avg_latency"], 2) if stats["avg_latency"] is not None else None
            avg_loss = round(stats["avg_loss"], 2) if stats["avg_loss"] is not None else None
        else:
            total_checks = 0
            online_checks = 0
            offline_checks = 0
            avail_pct = 100.0 if dev.status == "online" else (50.0 if dev.status == "degraded" else 0.0)
            avg_lat = None
            avg_loss = 0.0 if dev.status == "online" else 100.0

        online_hours = round((avail_pct / 100.0) * total_period_hours, 2)
        offline_hours = round(total_period_hours - online_hours, 2)
        incidents = alert_stats_map.get(dev.id, 0)

        total_avail_sum += avail_pct

        items.append(DeviceAvailabilityItem(
            device_id=dev.id,
            device_name=dev.name or dev.hostname,
            ip_address=dev.ip_address,
            device_type=dev.device_type,
            monitoring_period=period_str,
            total_checks=total_checks,
            online_checks=online_checks,
            offline_checks=offline_checks,
            availability_pct=avail_pct,
            online_duration_hours=online_hours,
            offline_duration_hours=offline_hours,
            avg_latency_ms=avg_lat,
            packet_loss_pct=avg_loss,
            incident_count=incidents
        ))

    avg_avail = round(total_avail_sum / len(devices), 2) if devices else 100.0

    return DeviceAvailabilityReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        total_devices=len(devices),
        avg_availability_pct=avg_avail,
        items=items
    )


def get_alert_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None,
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None
) -> AlertReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    alert_q = db.query(Alert, Device).join(Device, Alert.device_id == Device.id)
    alert_q = alert_q.filter(Alert.created_at >= st, Alert.created_at <= et)

    if device_id:
        alert_q = alert_q.filter(Alert.device_id == device_id)
    if device_type and device_type.upper() != "ALL":
        alert_q = alert_q.filter(Device.device_type == device_type.lower())
    if status and status.upper() != "ALL":
        alert_q = alert_q.filter(Alert.status == status.upper())
    if severity and severity.upper() != "ALL":
        alert_q = alert_q.filter(Alert.severity == severity.upper())
    if alert_type and alert_type.upper() != "ALL":
        alert_q = alert_q.filter(Alert.alert_type == alert_type)

    rows = alert_q.order_by(Alert.created_at.desc()).all()

    items: List[AlertReportItem] = []
    durations: List[float] = []

    for alert, dev in rows:
        if alert.resolved_at:
            duration_mins = (alert.resolved_at - alert.created_at).total_seconds() / 60.0
        else:
            duration_mins = (et - alert.created_at).total_seconds() / 60.0

        duration_mins = max(0.0, round(duration_mins, 1))
        durations.append(duration_mins)

        items.append(AlertReportItem(
            alert_id=alert.id,
            device_id=dev.id,
            device_name=dev.name or dev.hostname,
            ip_address=dev.ip_address,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            status=alert.status,
            created_at=alert.created_at,
            acknowledged_at=alert.acknowledged_at,
            resolved_at=alert.resolved_at,
            incident_duration_mins=duration_mins
        ))

    total_incidents = len(items)
    crit_count = sum(1 for i in items if i.severity == "CRITICAL")
    warn_count = sum(1 for i in items if i.severity == "WARNING")
    info_count = sum(1 for i in items if i.severity == "INFO")

    open_count = sum(1 for i in items if i.status == "OPEN")
    ack_count = sum(1 for i in items if i.status == "ACKNOWLEDGED")
    res_count = sum(1 for i in items if i.status == "RESOLVED")

    avg_dur = round(sum(durations) / len(durations), 1) if durations else None

    return AlertReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        total_incidents=total_incidents,
        critical_incidents=crit_count,
        warning_incidents=warn_count,
        info_incidents=info_count,
        open_incidents=open_count,
        acknowledged_incidents=ack_count,
        resolved_incidents=res_count,
        avg_incident_duration_mins=avg_dur,
        items=items
    )


def get_icmp_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None,
    device_type: Optional[str] = None
) -> IcmpReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    dev_q = db.query(Device)
    if device_id:
        dev_q = dev_q.filter(Device.id == device_id)
    if device_type and device_type.upper() != "ALL":
        dev_q = dev_q.filter(Device.device_type == device_type.lower())

    devices = dev_q.all()

    device_ids = [d.id for d in devices]

    # Query aggregated ping statistics for all devices in the period
    ping_stats_map = {}
    if device_ids:
        from sqlalchemy import case
        ping_stats = db.query(
            PingLog.device_id,
            func.count(PingLog.id).label("check_count"),
            func.sum(case((PingLog.is_online == True, 1), else_=0)).label("online_count"),
            func.avg(PingLog.latency_ms).label("avg_latency"),
            func.min(func.coalesce(PingLog.min_latency, PingLog.latency_ms)).label("min_latency"),
            func.max(func.coalesce(PingLog.max_latency, PingLog.latency_ms)).label("max_latency"),
            func.avg(PingLog.packet_loss_pct).label("avg_loss")
        ).filter(
            PingLog.device_id.in_(device_ids),
            PingLog.timestamp >= st,
            PingLog.timestamp <= et
        ).group_by(PingLog.device_id).all()

        ping_stats_map = {
            row.device_id: {
                "check_count": row.check_count,
                "online_count": row.online_count or 0,
                "avg_latency": row.avg_latency,
                "min_latency": row.min_latency,
                "max_latency": row.max_latency,
                "avg_loss": row.avg_loss
            }
            for row in ping_stats
        }

    items: List[IcmpReportItem] = []
    all_latencies = []
    all_losses = []
    total_checks_sum = 0
    total_online_checks = 0

    for dev in devices:
        stats = ping_stats_map.get(dev.id)
        if stats:
            check_count = stats["check_count"]
            online_count = stats["online_count"]
            total_checks_sum += check_count
            total_online_checks += online_count
            avail_pct = round((online_count / check_count) * 100.0, 2)
            avg_lat = round(stats["avg_latency"], 2) if stats["avg_latency"] is not None else None
            min_lat = round(stats["min_latency"], 2) if stats["min_latency"] is not None else None
            max_lat = round(stats["max_latency"], 2) if stats["max_latency"] is not None else None
            avg_loss = round(stats["avg_loss"], 2) if stats["avg_loss"] is not None else None

            if avg_lat: all_latencies.append(avg_lat)
            if avg_loss is not None: all_losses.append(avg_loss)
        else:
            check_count = 0
            avail_pct = 100.0 if dev.status == "online" else 0.0
            avg_lat = None
            min_lat = None
            max_lat = None
            avg_loss = 0.0 if dev.status == "online" else 100.0

        items.append(IcmpReportItem(
            device_id=dev.id,
            device_name=dev.name or dev.hostname,
            ip_address=dev.ip_address,
            total_checks=check_count,
            avg_latency_ms=avg_lat,
            min_latency_ms=min_lat,
            max_latency_ms=max_lat,
            packet_loss_pct=avg_loss,
            availability_pct=avail_pct
        ))

    overall_avg_lat = round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else None
    overall_avg_loss = round(sum(all_losses) / len(all_losses), 2) if all_losses else None
    overall_avail = round((total_online_checks / total_checks_sum * 100.0), 2) if total_checks_sum > 0 else 100.0

    return IcmpReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        total_checks=total_checks_sum,
        avg_latency_ms=overall_avg_lat,
        avg_packet_loss_pct=overall_avg_loss,
        avg_availability_pct=overall_avail,
        items=items
    )


def get_tcp_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None,
    port: Optional[int] = None
) -> TcpReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    port_q = db.query(PortLog, Device).join(Device, PortLog.device_id == Device.id)
    port_q = port_q.filter(PortLog.timestamp >= st, PortLog.timestamp <= et)

    if device_id:
        port_q = port_q.filter(PortLog.device_id == device_id)
    if port:
        port_q = port_q.filter(PortLog.port == port)

    logs = port_q.all()

    # Group by (device_id, port)
    grouped = {}
    for plog, dev in logs:
        key = (dev.id, plog.port)
        if key not in grouped:
            grouped[key] = {"dev": dev, "port": plog.port, "logs": []}
        grouped[key]["logs"].append(plog)

    items: List[TcpReportItem] = []
    total_checks_all = 0
    open_checks_all = 0
    all_resp_times = []

    for key, data in grouped.items():
        dev = data["dev"]
        p_num = data["port"]
        p_logs = data["logs"]

        check_count = len(p_logs)
        open_count = sum(1 for p in p_logs if p.is_open)
        fail_count = check_count - open_count

        total_checks_all += check_count
        open_checks_all += open_count

        avail_pct = round((open_count / check_count) * 100.0, 2) if check_count > 0 else 0.0

        r_times = [p.response_time_ms for p in p_logs if p.response_time_ms is not None]
        avg_resp = round(sum(r_times) / len(r_times), 2) if r_times else None
        if avg_resp: all_resp_times.append(avg_resp)

        last_check = max(p_logs, key=lambda x: x.timestamp) if p_logs else None
        service_status = "open" if (last_check and last_check.is_open) else "closed"

        items.append(TcpReportItem(
            device_id=dev.id,
            device_name=dev.name or dev.hostname,
            ip_address=dev.ip_address,
            port=p_num,
            service_status=service_status,
            total_checks=check_count,
            open_checks=open_count,
            failed_checks=fail_count,
            avg_response_time_ms=avg_resp,
            availability_pct=avail_pct,
            last_check_timestamp=last_check.timestamp if last_check else None
        ))

    overall_avail = round((open_checks_all / total_checks_all * 100.0), 2) if total_checks_all > 0 else 100.0
    overall_avg_resp = round(sum(all_resp_times) / len(all_resp_times), 2) if all_resp_times else None

    return TcpReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        total_checks=total_checks_all,
        avg_response_time_ms=overall_avg_resp,
        overall_availability_pct=overall_avail,
        items=items
    )


def get_snmp_report(
    db: Session,
    time_range: Optional[str] = "24h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_id: Optional[UUID] = None
) -> SnmpReport:
    st, et, period_str = resolve_time_range(time_range, start_time, end_time)

    snmp_q = db.query(SnmpLog, Device).join(Device, SnmpLog.device_id == Device.id)
    snmp_q = snmp_q.filter(SnmpLog.timestamp >= st, SnmpLog.timestamp <= et)

    if device_id:
        snmp_q = snmp_q.filter(SnmpLog.device_id == device_id)

    rows = snmp_q.all()

    # Aggregate telemetry by (device_id, interface_name)
    interface_summary = {}

    for slog, dev in rows:
        m_data = slog.metrics or {}
        ifaces = m_data.get("interfaces", [])

        for iface in ifaces:
            if_name = iface.get("name", "eth0")
            key = (dev.id, if_name)

            if key not in interface_summary:
                interface_summary[key] = {
                    "dev": dev,
                    "if_name": if_name,
                    "status": iface.get("status", "up"),
                    "speed_bps": iface.get("speed_bps"),
                    "in_bps_list": [],
                    "out_bps_list": []
                }

            in_rate = iface.get("in_rate_bps")
            out_rate = iface.get("out_rate_bps")

            if in_rate is not None: interface_summary[key]["in_bps_list"].append(in_rate)
            if out_rate is not None: interface_summary[key]["out_bps_list"].append(out_rate)

    items: List[SnmpReportItem] = []
    unique_devices = set()

    for key, data in interface_summary.items():
        dev = data["dev"]
        unique_devices.add(dev.id)

        in_list = data["in_bps_list"]
        out_list = data["out_bps_list"]

        avg_in = round(sum(in_list) / len(in_list), 2) if in_list else None
        avg_out = round(sum(out_list) / len(out_list), 2) if out_list else None

        speed = data["speed_bps"]

        # Requirement 8: Do not invent utilization if interface speed or traffic data is unavailable.
        if speed and speed > 0 and (avg_in is not None or avg_out is not None):
            tot_traffic = (avg_in or 0.0) + (avg_out or 0.0)
            util_pct = min(100.0, round((tot_traffic / speed) * 100.0, 2))
        else:
            util_pct = None

        items.append(SnmpReportItem(
            device_id=dev.id,
            device_name=dev.name or dev.hostname,
            ip_address=dev.ip_address,
            interface_name=data["if_name"],
            interface_status=data["status"],
            interface_speed_bps=speed,
            avg_inbound_bps=avg_in,
            avg_outbound_bps=avg_out,
            traffic_utilization_pct=util_pct
        ))

    return SnmpReport(
        reporting_period=period_str,
        start_time=st,
        end_time=et,
        total_devices=len(unique_devices),
        items=items
    )


# ----------------------------------------------------
# CSV EXPORT GENERATORS
# ----------------------------------------------------

def generate_csv_export(report_type: str, data) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([f"# NetVision NOC - {report_type.upper().replace('-', ' ')} REPORT"])
    writer.writerow([f"# Generated At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    writer.writerow([])

    if report_type == "network-health":
        r: NetworkHealthReport = data
        writer.writerow(["Reporting Period", r.reporting_period])
        writer.writerow(["Network Health Score", f"{r.network_health_score}%"])
        writer.writerow(["Total Devices", r.total_devices])
        writer.writerow(["Online Devices", r.online_devices])
        writer.writerow(["Degraded Devices", r.degraded_devices])
        writer.writerow(["Offline Devices", r.offline_devices])
        writer.writerow(["Average Latency (ms)", r.avg_latency_ms if r.avg_latency_ms is not None else "N/A"])
        writer.writerow(["Average Packet Loss (%)", f"{r.avg_packet_loss_pct}%" if r.avg_packet_loss_pct is not None else "N/A"])
        writer.writerow(["Active Alerts", r.active_alerts_count])
        writer.writerow(["Critical Alerts", r.critical_alerts_count])
        writer.writerow(["Warning Alerts", r.warning_alerts_count])
        writer.writerow(["Info Alerts", r.info_alerts_count])

    elif report_type == "device-availability":
        r: DeviceAvailabilityReport = data
        writer.writerow(["Device Name", "IP Address", "Type", "Total Checks", "Online Checks", "Offline Checks", "Availability (%)", "Online Duration (h)", "Offline Duration (h)", "Avg Latency (ms)", "Packet Loss (%)", "Incidents"])
        for item in r.items:
            writer.writerow([
                item.device_name, item.ip_address, item.device_type,
                item.total_checks, item.online_checks, item.offline_checks,
                f"{item.availability_pct}%", item.online_duration_hours, item.offline_duration_hours,
                item.avg_latency_ms if item.avg_latency_ms is not None else "N/A",
                f"{item.packet_loss_pct}%" if item.packet_loss_pct is not None else "N/A",
                item.incident_count
            ])

    elif report_type == "alerts":
        r: AlertReport = data
        writer.writerow(["Alert ID", "Device Name", "IP Address", "Alert Type", "Severity", "Title", "Status", "Created At", "Acknowledged At", "Resolved At", "Duration (mins)"])
        for item in r.items:
            writer.writerow([
                str(item.alert_id), item.device_name, item.ip_address,
                item.alert_type, item.severity, item.title, item.status,
                item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                item.acknowledged_at.strftime('%Y-%m-%d %H:%M:%S') if item.acknowledged_at else "N/A",
                item.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if item.resolved_at else "Active",
                item.incident_duration_mins if item.incident_duration_mins is not None else "N/A"
            ])

    elif report_type == "icmp":
        r: IcmpReport = data
        writer.writerow(["Device Name", "IP Address", "Total Checks", "Avg Latency (ms)", "Min Latency (ms)", "Max Latency (ms)", "Packet Loss (%)", "Availability (%)"])
        for item in r.items:
            writer.writerow([
                item.device_name, item.ip_address, item.total_checks,
                item.avg_latency_ms if item.avg_latency_ms is not None else "N/A",
                item.min_latency_ms if item.min_latency_ms is not None else "N/A",
                item.max_latency_ms if item.max_latency_ms is not None else "N/A",
                f"{item.packet_loss_pct}%" if item.packet_loss_pct is not None else "N/A",
                f"{item.availability_pct}%"
            ])

    elif report_type == "tcp":
        r: TcpReport = data
        writer.writerow(["Device Name", "IP Address", "Port", "Status", "Total Checks", "Open Checks", "Failed Checks", "Avg Response (ms)", "Availability (%)", "Last Check"])
        for item in r.items:
            writer.writerow([
                item.device_name, item.ip_address, item.port, item.service_status,
                item.total_checks, item.open_checks, item.failed_checks,
                item.avg_response_time_ms if item.avg_response_time_ms is not None else "N/A",
                f"{item.availability_pct}%",
                item.last_check_timestamp.strftime('%Y-%m-%d %H:%M:%S') if item.last_check_timestamp else "N/A"
            ])

    elif report_type == "snmp":
        r: SnmpReport = data
        writer.writerow(["Device Name", "IP Address", "Interface", "Status", "Speed (Mbps)", "Inbound (Mbps)", "Outbound (Mbps)", "Utilization (%)"])
        for item in r.items:
            spd_mbps = round(item.interface_speed_bps / 1e6, 2) if item.interface_speed_bps else "N/A"
            in_mbps = round(item.avg_inbound_bps / 1e6, 3) if item.avg_inbound_bps is not None else "N/A"
            out_mbps = round(item.avg_outbound_bps / 1e6, 3) if item.avg_outbound_bps is not None else "N/A"
            writer.writerow([
                item.device_name, item.ip_address, item.interface_name, item.interface_status,
                spd_mbps, in_mbps, out_mbps,
                f"{item.traffic_utilization_pct}%" if item.traffic_utilization_pct is not None else "N/A"
            ])

    return output.getvalue()


# ----------------------------------------------------
# PDF EXPORT GENERATOR (ReportLab)
# ----------------------------------------------------

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header line
        self.setStrokeColor(colors.HexColor("#334155"))
        self.setLineWidth(0.5)
        self.line(36, 576, 756, 576) # Landscape dimensions: 792 x 612

        # Header text
        self.drawString(36, 584, "NetVision Operations Center - Official Monitoring Report")
        
        # Footer line
        self.line(36, 40, 756, 40)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(756, 26, page_str)
        self.drawString(36, 26, f"Confidential & Proprietary - NetVision System Analytics")
        self.restoreState()


def generate_pdf_export(report_type: str, data) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36, rightMargin=36,
        topMargin=54, bottomMargin=54
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A")
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4F46E5")
    )
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569")
    )
    cell_head_style = ParagraphStyle(
        'CellHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    cell_body_style = ParagraphStyle(
        'CellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Title & Branding
    story.append(Paragraph("NetVision Enterprise", subtitle_style))
    story.append(Spacer(1, 2))
    report_title_name = report_type.upper().replace('-', ' ') + " REPORT"
    story.append(Paragraph(report_title_name, title_style))
    story.append(Spacer(1, 10))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Extract metadata details based on report_type
    period_str = getattr(data, 'reporting_period', 'N/A')
    
    meta_text = f"<b>Generated:</b> {now_str} &nbsp;|&nbsp; <b>Reporting Window:</b> {period_str}"
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 12))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=12))

    # Render Report Summary KPI Cards
    if report_type == "network-health":
        r: NetworkHealthReport = data
        kpi_data = [
            [
                Paragraph("<b>Health Score</b>", meta_style),
                Paragraph("<b>Total Devices</b>", meta_style),
                Paragraph("<b>Online / Degraded / Offline</b>", meta_style),
                Paragraph("<b>Avg Latency / Loss</b>", meta_style),
                Paragraph("<b>Active Alerts (Crit/Warn)</b>", meta_style)
            ],
            [
                Paragraph(f"<font color='#4F46E5' size=14><b>{r.network_health_score}%</b></font>", meta_style),
                Paragraph(f"<b>{r.total_devices}</b>", meta_style),
                Paragraph(f"<font color='#10B981'><b>{r.online_devices}</b></font> / <font color='#F59E0B'><b>{r.degraded_devices}</b></font> / <font color='#EF4444'><b>{r.offline_devices}</b></font>", meta_style),
                Paragraph(f"<b>{r.avg_latency_ms or 'N/A'} ms</b> / <b>{r.avg_packet_loss_pct or 0.0}%</b>", meta_style),
                Paragraph(f"<b>{r.active_alerts_count}</b> ({r.critical_alerts_count} / {r.warning_alerts_count})", meta_style)
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[140, 140, 150, 140, 150])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 14))

    elif report_type == "device-availability":
        r: DeviceAvailabilityReport = data
        story.append(Paragraph(f"<b>Average Device Availability:</b> {r.avg_availability_pct}% across {r.total_devices} monitored nodes.", meta_style))
        story.append(Spacer(1, 10))

        headers = ["Device Name", "IP Address", "Type", "Checks", "Availability", "Online (h)", "Offline (h)", "Avg Latency", "Packet Loss", "Incidents"]
        col_widths = [100, 85, 65, 45, 65, 60, 60, 65, 65, 55]

        table_rows = [[Paragraph(h, cell_head_style) for h in headers]]
        for item in r.items:
            table_rows.append([
                Paragraph(item.device_name, cell_body_style),
                Paragraph(item.ip_address, cell_body_style),
                Paragraph(item.device_type.capitalize(), cell_body_style),
                Paragraph(str(item.total_checks), cell_body_style),
                Paragraph(f"<b>{item.availability_pct}%</b>", cell_body_style),
                Paragraph(f"{item.online_duration_hours}h", cell_body_style),
                Paragraph(f"{item.offline_duration_hours}h", cell_body_style),
                Paragraph(f"{item.avg_latency_ms} ms" if item.avg_latency_ms is not None else "N/A", cell_body_style),
                Paragraph(f"{item.packet_loss_pct}%" if item.packet_loss_pct is not None else "N/A", cell_body_style),
                Paragraph(str(item.incident_count), cell_body_style)
            ])

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 5)
        ]))
        story.append(t)

    elif report_type == "alerts":
        r: AlertReport = data
        story.append(Paragraph(f"<b>Total Incidents:</b> {r.total_incidents} (Critical: {r.critical_incidents}, Warning: {r.warning_incidents}, Info: {r.info_incidents}) &nbsp;|&nbsp; <b>Avg Duration:</b> {r.avg_incident_duration_mins or 0.0} mins", meta_style))
        story.append(Spacer(1, 10))

        headers = ["Device Name", "IP Address", "Type", "Severity", "Title", "Status", "Created At", "Resolved At", "Duration"]
        col_widths = [90, 80, 75, 55, 140, 60, 90, 90, 45]

        table_rows = [[Paragraph(h, cell_head_style) for h in headers]]
        for item in r.items:
            table_rows.append([
                Paragraph(item.device_name, cell_body_style),
                Paragraph(item.ip_address, cell_body_style),
                Paragraph(item.alert_type, cell_body_style),
                Paragraph(f"<b>{item.severity}</b>", cell_body_style),
                Paragraph(item.title, cell_body_style),
                Paragraph(item.status, cell_body_style),
                Paragraph(item.created_at.strftime('%m-%d %H:%M'), cell_body_style),
                Paragraph(item.resolved_at.strftime('%m-%d %H:%M') if item.resolved_at else "Active", cell_body_style),
                Paragraph(f"{item.incident_duration_mins}m" if item.incident_duration_mins is not None else "-", cell_body_style)
            ])

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 4)
        ]))
        story.append(t)

    elif report_type == "icmp":
        r: IcmpReport = data
        story.append(Paragraph(f"<b>Overall Average Latency:</b> {r.avg_latency_ms or 'N/A'} ms &nbsp;|&nbsp; <b>Avg Packet Loss:</b> {r.avg_packet_loss_pct or 0.0}% &nbsp;|&nbsp; <b>Overall Availability:</b> {r.avg_availability_pct}%", meta_style))
        story.append(Spacer(1, 10))

        headers = ["Device Name", "IP Address", "Total Checks", "Avg Latency", "Min Latency", "Max Latency", "Packet Loss", "Availability"]
        col_widths = [120, 100, 80, 80, 80, 80, 90, 90]

        table_rows = [[Paragraph(h, cell_head_style) for h in headers]]
        for item in r.items:
            table_rows.append([
                Paragraph(item.device_name, cell_body_style),
                Paragraph(item.ip_address, cell_body_style),
                Paragraph(str(item.total_checks), cell_body_style),
                Paragraph(f"{item.avg_latency_ms} ms" if item.avg_latency_ms is not None else "N/A", cell_body_style),
                Paragraph(f"{item.min_latency_ms} ms" if item.min_latency_ms is not None else "N/A", cell_body_style),
                Paragraph(f"{item.max_latency_ms} ms" if item.max_latency_ms is not None else "N/A", cell_body_style),
                Paragraph(f"{item.packet_loss_pct}%" if item.packet_loss_pct is not None else "N/A", cell_body_style),
                Paragraph(f"<b>{item.availability_pct}%</b>", cell_body_style)
            ])

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 5)
        ]))
        story.append(t)

    elif report_type == "tcp":
        r: TcpReport = data
        story.append(Paragraph(f"<b>Overall TCP Availability:</b> {r.overall_availability_pct}% &nbsp;|&nbsp; <b>Avg Response Time:</b> {r.avg_response_time_ms or 'N/A'} ms", meta_style))
        story.append(Spacer(1, 10))

        headers = ["Device Name", "IP Address", "Port", "Status", "Checks", "Open", "Failed", "Avg Response", "Availability", "Last Check"]
        col_widths = [110, 85, 45, 55, 50, 50, 50, 80, 75, 95]

        table_rows = [[Paragraph(h, cell_head_style) for h in headers]]
        for item in r.items:
            table_rows.append([
                Paragraph(item.device_name, cell_body_style),
                Paragraph(item.ip_address, cell_body_style),
                Paragraph(str(item.port), cell_body_style),
                Paragraph(f"<b>{item.service_status.upper()}</b>", cell_body_style),
                Paragraph(str(item.total_checks), cell_body_style),
                Paragraph(str(item.open_checks), cell_body_style),
                Paragraph(str(item.failed_checks), cell_body_style),
                Paragraph(f"{item.avg_response_time_ms} ms" if item.avg_response_time_ms is not None else "N/A", cell_body_style),
                Paragraph(f"<b>{item.availability_pct}%</b>", cell_body_style),
                Paragraph(item.last_check_timestamp.strftime('%m-%d %H:%M') if item.last_check_timestamp else "N/A", cell_body_style)
            ])

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 5)
        ]))
        story.append(t)

    elif report_type == "snmp":
        r: SnmpReport = data
        story.append(Paragraph(f"<b>Total Monitored Devices:</b> {r.total_devices} nodes with SNMP telemetry interfaces.", meta_style))
        story.append(Spacer(1, 10))

        headers = ["Device Name", "IP Address", "Interface", "Status", "Speed", "Inbound Traffic", "Outbound Traffic", "Utilization"]
        col_widths = [110, 95, 80, 55, 80, 95, 95, 85]

        table_rows = [[Paragraph(h, cell_head_style) for h in headers]]
        for item in r.items:
            spd_str = f"{round(item.interface_speed_bps / 1e6, 1)} Mbps" if item.interface_speed_bps else "N/A"
            in_str = f"{round(item.avg_inbound_bps / 1e6, 3)} Mbps" if item.avg_inbound_bps is not None else "N/A"
            out_str = f"{round(item.avg_outbound_bps / 1e6, 3)} Mbps" if item.avg_outbound_bps is not None else "N/A"
            util_str = f"<b>{item.traffic_utilization_pct}%</b>" if item.traffic_utilization_pct is not None else "N/A"

            table_rows.append([
                Paragraph(item.device_name, cell_body_style),
                Paragraph(item.ip_address, cell_body_style),
                Paragraph(item.interface_name, cell_body_style),
                Paragraph(item.interface_status.upper(), cell_body_style),
                Paragraph(spd_str, cell_body_style),
                Paragraph(in_str, cell_body_style),
                Paragraph(out_str, cell_body_style),
                Paragraph(util_str, cell_body_style)
            ])

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 5)
        ]))
        story.append(t)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
