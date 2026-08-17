from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.core.db import get_db
from app.models.user import User
from app.api.deps import require_viewer

from app.schemas.report import (
    NetworkHealthReport,
    DeviceAvailabilityReport,
    AlertReport,
    IcmpReport,
    TcpReport,
    SnmpReport
)

from app.services.report_service import (
    get_network_health_report,
    get_device_availability_report,
    get_alert_report,
    get_icmp_report,
    get_tcp_report,
    get_snmp_report,
    generate_csv_export,
    generate_pdf_export
)

router = APIRouter()


# Helper function to handle export formats (CSV, PDF, JSON)
def handle_report_response(report_type: str, data, export_format: str):
    fmt = (export_format or "json").strip().lower()
    if fmt == "csv":
        csv_content = generate_csv_export(report_type, data)
        filename = f"netvision_{report_type}_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    elif fmt == "pdf":
        pdf_bytes = generate_pdf_export(report_type, data)
        filename = f"netvision_{report_type}_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    return data


# 1. Network Health Report Endpoint
@router.get("/network-health")
def get_network_health(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_network_health_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("network-health", data, format)


@router.get("/network-health/csv")
def get_network_health_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_network_health_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("network-health", data, "csv")


@router.get("/network-health/pdf")
def get_network_health_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_network_health_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("network-health", data, "pdf")


# 2. Device Availability Report Endpoint
@router.get("/device-availability")
def get_device_availability(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_device_availability_report(
        db, time_range, start_time, end_time, device_id, device_type, status
    )
    return handle_report_response("device-availability", data, format)


@router.get("/device-availability/csv")
def get_device_availability_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_device_availability_report(
        db, time_range, start_time, end_time, device_id, device_type, status
    )
    return handle_report_response("device-availability", data, "csv")


@router.get("/device-availability/pdf")
def get_device_availability_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_device_availability_report(
        db, time_range, start_time, end_time, device_id, device_type, status
    )
    return handle_report_response("device-availability", data, "pdf")


# 3. Alert / Incident Report Endpoint
@router.get("/alerts")
def get_alerts_report(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_alert_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("alerts", data, format)


@router.get("/alerts/csv")
def get_alerts_report_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_alert_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("alerts", data, "csv")


@router.get("/alerts/pdf")
def get_alerts_report_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_alert_report(
        db, time_range, start_time, end_time, device_id, device_type, status, severity, alert_type
    )
    return handle_report_response("alerts", data, "pdf")


# 4. ICMP Performance Report Endpoint
@router.get("/icmp")
def get_icmp_performance(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_icmp_report(db, time_range, start_time, end_time, device_id, device_type)
    return handle_report_response("icmp", data, format)


@router.get("/icmp/csv")
def get_icmp_performance_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_icmp_report(db, time_range, start_time, end_time, device_id, device_type)
    return handle_report_response("icmp", data, "csv")


@router.get("/icmp/pdf")
def get_icmp_performance_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    device_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_icmp_report(db, time_range, start_time, end_time, device_id, device_type)
    return handle_report_response("icmp", data, "pdf")


# 5. TCP Service Report Endpoint
@router.get("/tcp")
def get_tcp_services(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    port: Optional[int] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_tcp_report(db, time_range, start_time, end_time, device_id, port)
    return handle_report_response("tcp", data, format)


@router.get("/tcp/csv")
def get_tcp_services_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    port: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_tcp_report(db, time_range, start_time, end_time, device_id, port)
    return handle_report_response("tcp", data, "csv")


@router.get("/tcp/pdf")
def get_tcp_services_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    port: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_tcp_report(db, time_range, start_time, end_time, device_id, port)
    return handle_report_response("tcp", data, "pdf")


# 6. SNMP Interface Traffic Report Endpoint
@router.get("/snmp")
def get_snmp_traffic(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    format: Optional[str] = Query("json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_snmp_report(db, time_range, start_time, end_time, device_id)
    return handle_report_response("snmp", data, format)


@router.get("/snmp/csv")
def get_snmp_traffic_csv(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_snmp_report(db, time_range, start_time, end_time, device_id)
    return handle_report_response("snmp", data, "csv")


@router.get("/snmp/pdf")
def get_snmp_traffic_pdf(
    time_range: Optional[str] = Query("24h"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    device_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    data = get_snmp_report(db, time_range, start_time, end_time, device_id)
    return handle_report_response("snmp", data, "pdf")
