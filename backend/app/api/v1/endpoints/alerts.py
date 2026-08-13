from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.core.db import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.user import User
from app.schemas.alert import AlertResponse, AlertSummaryResponse, AlertSettingsResponse, AlertSettingsUpdate
from app.api.deps import require_viewer, require_operator, require_admin
from app.services.audit import log_audit_event

router = APIRouter()

@router.get("/", response_model=List[AlertResponse])
def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    device_id: Optional[UUID] = None,
    alert_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve alerts, with optional filters for status, severity, device_id, and alert_type (VIEWER or higher).
    """
    try:
        query = db.query(Alert)
        
        if status:
            query = query.filter(Alert.status == status)
        if severity:
            query = query.filter(Alert.severity == severity)
        if device_id:
            query = query.filter(Alert.device_id == device_id)
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
            
        return query.order_by(Alert.created_at.desc()).all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred while fetching alerts: {str(e)}"
        )

@router.get("/summary", response_model=AlertSummaryResponse)
def get_alerts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve statistics/counts of alerts (VIEWER or higher).
    """
    try:
        total_active = db.query(Alert).filter(Alert.status.in_(["OPEN", "ACKNOWLEDGED"])).count()
        critical = db.query(Alert).filter(Alert.status.in_(["OPEN", "ACKNOWLEDGED"]), Alert.severity == "CRITICAL").count()
        warning = db.query(Alert).filter(Alert.status.in_(["OPEN", "ACKNOWLEDGED"]), Alert.severity == "WARNING").count()
        acknowledged = db.query(Alert).filter(Alert.status == "ACKNOWLEDGED").count()
        resolved = db.query(Alert).filter(Alert.status == "RESOLVED").count()
        
        return {
            "total_active": total_active,
            "critical": critical,
            "warning": warning,
            "acknowledged": acknowledged,
            "resolved": resolved
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while generating alert summary: {str(e)}"
        )

@router.get("/settings", response_model=AlertSettingsResponse)
def get_alert_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve configured thresholds (VIEWER or higher).
    """
    try:
        from sqlalchemy import text
        rows = db.execute(text("SELECT key, value FROM global_settings")).all()
        settings = {row[0]: float(row[1]) for row in rows}
        
        return {
            "icmp_latency_warning": settings.get("icmp_latency_warning", 200.0),
            "icmp_latency_critical": settings.get("icmp_latency_critical", 500.0),
            "packet_loss_warning": settings.get("packet_loss_warning", 10.0),
            "packet_loss_critical": settings.get("packet_loss_critical", 30.0),
            "snmp_traffic_warning_bps": settings.get("snmp_traffic_warning_bps", 80000000.0)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch global settings: {str(e)}"
        )

@router.put("/settings", response_model=AlertSettingsResponse)
def update_alert_settings(
    settings: AlertSettingsUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update configured thresholds (ADMIN only).
    """
    try:
        from sqlalchemy import text
        update_dict = settings.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            if val is not None:
                db.execute(
                    text("INSERT INTO global_settings (key, value) VALUES (:key, :val) ON CONFLICT (key) DO UPDATE SET value = :val"),
                    {"key": key, "val": str(val)}
                )
        db.commit()
        
        # Log audit log
        log_audit_event(
            db=db,
            action="alert_threshold_changes",
            user=current_user,
            details=update_dict
        )
        
        rows = db.execute(text("SELECT key, value FROM global_settings")).all()
        updated = {row[0]: float(row[1]) for row in rows}
        return {
            "icmp_latency_warning": updated.get("icmp_latency_warning", 200.0),
            "icmp_latency_critical": updated.get("icmp_latency_critical", 500.0),
            "packet_loss_warning": updated.get("packet_loss_warning", 10.0),
            "packet_loss_critical": updated.get("packet_loss_critical", 30.0),
            "snmp_traffic_warning_bps": updated.get("snmp_traffic_warning_bps", 80000000.0)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update global settings: {str(e)}"
        )

@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer)
):
    """
    Retrieve details of a single alert by ID (VIEWER or higher).
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Acknowledge an active/open alert (OPERATOR or higher).
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Alert with ID {alert_id} not found"
        )
        
    if alert.status == "RESOLVED":
        raise HTTPException(
            status_code=400,
            detail="Cannot acknowledge a resolved alert"
        )
        
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    
    try:
        db.commit()
        db.refresh(alert)
        
        # Log audit log
        log_audit_event(
            db=db,
            action="alert_acknowledgement",
            user=current_user,
            details={"alert_id": str(alert_id), "alert_type": alert.alert_type, "device_id": str(alert.device_id)}
        )
        return alert
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )

@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Manually resolve an active alert (OPERATOR or higher).
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Alert with ID {alert_id} not found"
        )
        
    if alert.status == "RESOLVED":
        return alert
        
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.now(timezone.utc)
    
    try:
        db.commit()
        db.refresh(alert)
        
        # Log audit log
        log_audit_event(
            db=db,
            action="alert_resolution",
            user=current_user,
            details={"alert_id": str(alert_id), "alert_type": alert.alert_type, "device_id": str(alert.device_id)}
        )
        return alert
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to manually resolve alert: {str(e)}"
        )
