from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timezone

from app.core.db import get_db
from app.models import Device, PingLog, PortLog, SnmpLog
from app.models.user import User
from app.api.deps import require_viewer, require_operator, require_admin
from app.services.audit import log_audit_event
from app.schemas import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    PingLogResponse,
    DeviceStatusResponse,
    ManualMonitorResponse,
    PortLogResponse,
    PortStatusResponse,
    SnmpStatusResponse,
    SnmpSystemResponse,
    SnmpInterfaceResponse,
    SnmpLogResponse,
    AlertResponse
)

router = APIRouter()

@router.get("/", response_model=List[DeviceResponse])
def get_devices(db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve all devices from the database.
    """
    try:
        return db.query(Device).all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred while fetching devices: {str(e)}"
        )

@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve details of a single device by ID.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    return device

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(device_in: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """
    Register a new network device. Checks for IP conflicts.
    """
    # Check if a device with this IP address already exists
    existing_device = db.query(Device).filter(Device.ip_address == device_in.ip_address).first()
    if existing_device:
        raise HTTPException(
            status_code=400,
            detail=f"A device with IP address {device_in.ip_address} is already registered"
        )

    db_device = Device(
        ip_address=device_in.ip_address,
        hostname=device_in.hostname,
        name=device_in.name,
        description=device_in.description,
        device_type=device_in.device_type,
        monitoring_enabled=device_in.monitoring_enabled,
        ping_interval=device_in.ping_interval,
        snmp_config=device_in.snmp_config,
        tcp_ports=device_in.tcp_ports,
        status="offline"  # Newly created devices default to offline
    )
    
    db.add(db_device)
    try:
        db.commit()
        db.refresh(db_device)
        log_audit_event(
            db=db,
            action="device_creation",
            user=current_user,
            details={"device_id": str(db_device.id), "ip_address": db_device.ip_address, "hostname": db_device.hostname}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save device: {str(e)}"
        )
    return db_device

@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: UUID, device_in: DeviceUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """
    Update a device's attributes. Handles IP address changes and conflict checking.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )

    update_data = device_in.model_dump(exclude_unset=True)

    # If IP is being updated, verify it doesn't conflict with another device
    if "ip_address" in update_data and update_data["ip_address"] != device.ip_address:
        existing_device = db.query(Device).filter(Device.ip_address == update_data["ip_address"]).first()
        if existing_device:
            raise HTTPException(
                status_code=400,
                detail=f"A device with IP address {update_data['ip_address']} is already registered"
            )

    for field, value in update_data.items():
        setattr(device, field, value)

    try:
        is_monitoring_change = any(k in update_data for k in ["monitoring_enabled", "ping_interval", "snmp_config", "tcp_ports"])
        action_name = "monitoring_configuration_changes" if is_monitoring_change else "device_update"
        db.commit()
        db.refresh(device)
        log_audit_event(
            db=db,
            action=action_name,
            user=current_user,
            details={"device_id": str(device.id), "updated_fields": list(update_data.keys())}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update device: {str(e)}"
        )
    return device

@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """
    Delete a device. All related links and logs are cascaded in PostgreSQL.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )

    try:
        db.delete(device)
        db.commit()
        log_audit_event(
            db=db,
            action="device_deletion",
            user=current_user,
            details={"device_id": str(device_id), "ip_address": device.ip_address, "hostname": device.hostname}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete device: {str(e)}"
        )
    return None

@router.get("/{device_id}/metrics", response_model=List[PingLogResponse])
def get_device_metrics(device_id: UUID, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve recent ICMP monitoring ping logs for a specific device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    
    try:
        logs = db.query(PingLog).filter(
            PingLog.device_id == device_id
        ).order_by(PingLog.timestamp.desc()).limit(limit).all()
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve device metrics: {str(e)}"
        )

@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
def get_device_status(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve the latest real monitoring status of a device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    
    is_online = device.status in ["online", "degraded"]
    return DeviceStatusResponse(
        device_id=device.id,
        status=device.status,
        last_seen=device.last_seen,
        is_online=is_online
    )

@router.post("/{device_id}/monitor", response_model=ManualMonitorResponse)
async def trigger_manual_monitor(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    """
    Trigger an immediate manual ICMP ping check on a device and store the result.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    
    from app.services.ping import ping_ipv4
    
    # Perform immediate real ping
    result = await ping_ipv4(device.ip_address, timeout=1.0, count=4)
    
    avg_latency = result["latency_ms"]
    loss = result["packet_loss_pct"]
    status = result["status"]
    is_online = result["is_online"]
    
    # Store result in Postgres
    ping_log = PingLog(
        device_id=device_id,
        latency_ms=avg_latency,
        min_latency=result["min_latency"],
        max_latency=result["max_latency"],
        packet_loss_pct=loss,
        is_online=is_online,
        status=status,
        error_msg=result["error_msg"],
        timestamp=datetime.now(timezone.utc)
    )
    db.add(ping_log)
    
    # Update device properties
    device.status = status
    if is_online:
        device.last_seen = datetime.now(timezone.utc)
        
    # Evaluate ICMP alerts
    try:
        from app.services.alert_engine import AlertEngine
        AlertEngine.process_icmp_result(
            db=db,
            device_id=device_id,
            hostname=device.hostname,
            ip_address=device.ip_address,
            is_online=is_online,
            packet_loss_pct=loss,
            average_latency=avg_latency
        )
    except Exception as alert_err:
        import logging
        logging.getLogger("NetVision.API").error(f"Alert engine manual ICMP processing failed: {alert_err}")

    try:
        db.commit()
        db.refresh(ping_log)
        db.refresh(device)
        log_audit_event(
            db=db,
            action="manual_monitoring",
            user=current_user,
            details={"device_id": str(device_id), "type": "ICMP", "ip_address": device.ip_address}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to commit manual check to database: {str(e)}"
        )
        
    return ManualMonitorResponse(
        device_id=device_id,
        timestamp=ping_log.timestamp,
        is_online=is_online,
        status=status,
        latency_ms=avg_latency,
        min_latency=result["min_latency"],
        max_latency=result["max_latency"],
        packet_loss_pct=loss,
        error_msg=result["error_msg"]
    )

@router.post("/{device_id}/ports/check", response_model=List[PortLogResponse])
async def trigger_manual_port_check(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    """
    Trigger an immediate manual TCP check of configured ports for a device and persist results.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    
    configured_ports = device.tcp_ports or []
    if not configured_ports:
        return []
        
    from app.services.tcp_monitor import check_device_ports
    
    try:
        results = await check_device_ports(device.ip_address, configured_ports, timeout=2.0)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform TCP port diagnostics: {str(e)}"
        )
        
    port_logs = []
    for res in results:
        port_log = PortLog(
            device_id=device_id,
            port=res["port"],
            is_open=res["is_open"],
            response_time_ms=res["response_time_ms"],
            status=res["status"],
            error_msg=res["error_msg"],
            timestamp=datetime.now(timezone.utc)
        )
        db.add(port_log)
        port_logs.append(port_log)
        
    # Evaluate TCP alerts
    try:
        from app.services.alert_engine import AlertEngine
        for res in results:
            AlertEngine.process_tcp_result(
                db=db,
                device_id=device_id,
                hostname=device.hostname,
                ip_address=device.ip_address,
                port=res["port"],
                is_open=res["is_open"],
                status=res["status"]
            )
    except Exception as alert_err:
        import logging
        logging.getLogger("NetVision.API").error(f"Alert engine manual TCP processing failed: {alert_err}")
        
    try:
        db.commit()
        for log in port_logs:
            db.refresh(log)
        log_audit_event(
            db=db,
            action="manual_monitoring",
            user=current_user,
            details={"device_id": str(device_id), "type": "TCP", "ports": device.tcp_ports}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save manual TCP check results: {str(e)}"
        )
        
    return port_logs

@router.get("/{device_id}/ports", response_model=List[PortStatusResponse])
def get_device_ports_status(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve the latest status of each configured TCP port for a device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
        
    configured_ports = device.tcp_ports or []
    response_data = []
    
    for port in configured_ports:
        # Get latest log entry for this device and port
        latest_log = db.query(PortLog).filter(
            PortLog.device_id == device_id,
            PortLog.port == port
        ).order_by(PortLog.timestamp.desc()).first()
        
        if latest_log:
            response_data.append(PortStatusResponse(
                port=port,
                is_open=latest_log.is_open,
                status=latest_log.status,
                response_time_ms=latest_log.response_time_ms,
                last_checked=latest_log.timestamp
            ))
        else:
            # Never checked before
            response_data.append(PortStatusResponse(
                port=port,
                is_open=False,
                status="unchecked",
                response_time_ms=None,
                last_checked=None
            ))
            
    return response_data

@router.get("/{device_id}/ports/metrics", response_model=List[PortLogResponse])
def get_device_ports_metrics(device_id: UUID, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve recent historical TCP port check logs for a specific device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
        
    try:
        logs = db.query(PortLog).filter(
            PortLog.device_id == device_id
        ).order_by(PortLog.timestamp.desc()).limit(limit).all()
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve TCP metrics: {str(e)}"
        )


@router.get("/{device_id}/snmp/status", response_model=SnmpStatusResponse)
def get_device_snmp_status(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve whether SNMP monitoring is currently working.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    snmp_config = device.snmp_config or {}
    snmp_enabled = snmp_config.get("snmp_enabled", False)
    
    latest_log = db.query(SnmpLog).filter(
        SnmpLog.device_id == device_id
    ).order_by(SnmpLog.timestamp.desc()).first()
    
    working = False
    error_msg = None
    last_polled = None
    
    if latest_log:
        last_polled = latest_log.timestamp
        status = latest_log.metrics.get("status", "error")
        working = (status == "ok")
        if not working:
            error_msg = latest_log.metrics.get("error_msg", "Unknown SNMP error")
            
    return SnmpStatusResponse(
        device_id=device_id,
        snmp_enabled=snmp_enabled,
        working=working,
        error_msg=error_msg,
        last_polled=last_polled
    )


@router.get("/{device_id}/snmp/system", response_model=SnmpSystemResponse)
def get_device_snmp_system(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve system info (hostname, description, uptime) from latest SNMP poll.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    latest_log = db.query(SnmpLog).filter(
        SnmpLog.device_id == device_id
    ).order_by(SnmpLog.timestamp.desc()).first()
    
    hostname = device.hostname
    description = device.description
    uptime = None
    
    if latest_log and latest_log.metrics.get("status") == "ok":
        sys_data = latest_log.metrics.get("system", {})
        hostname = sys_data.get("sysName") or hostname
        description = sys_data.get("sysDescr") or description
        uptime = sys_data.get("sysUpTime")
        
    return SnmpSystemResponse(
        device_id=device_id,
        hostname=hostname,
        description=description,
        uptime=uptime
    )


@router.get("/{device_id}/snmp/interfaces", response_model=List[SnmpInterfaceResponse])
def get_device_snmp_interfaces(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve interface information and statuses from the latest SNMP poll.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    latest_log = db.query(SnmpLog).filter(
        SnmpLog.device_id == device_id
    ).order_by(SnmpLog.timestamp.desc()).first()
    
    if not latest_log or latest_log.metrics.get("status") != "ok":
        return []
        
    interfaces_data = latest_log.metrics.get("interfaces", [])
    
    res = []
    for interface in interfaces_data:
        res.append(SnmpInterfaceResponse(
            index=interface.get("index"),
            name=interface.get("name"),
            description=interface.get("description", ""),
            op_status=interface.get("op_status", "unknown"),
            admin_status=interface.get("admin_status", "unknown"),
            speed=interface.get("speed", 0),
            in_octets=interface.get("in_octets", 0),
            out_octets=interface.get("out_octets", 0),
            in_rate_bps=interface.get("in_rate_bps", 0.0),
            out_rate_bps=interface.get("out_rate_bps", 0.0),
            in_rate_bytes_sec=interface.get("in_rate_bytes_sec", 0.0),
            out_rate_bytes_sec=interface.get("out_rate_bytes_sec", 0.0)
        ))
    return res


@router.get("/{device_id}/snmp/metrics", response_model=List[SnmpLogResponse])
def get_device_snmp_metrics(device_id: UUID, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve historical SNMP metrics.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    logs = db.query(SnmpLog).filter(
        SnmpLog.device_id == device_id
    ).order_by(SnmpLog.timestamp.desc()).limit(limit).all()
    
    return logs


@router.post("/{device_id}/snmp/poll", response_model=SnmpLogResponse)
async def trigger_manual_snmp_poll(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    """
    Trigger an immediate SNMP poll for an authorized and enabled device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not device.is_authorized:
        raise HTTPException(
            status_code=403,
            detail="SNMP monitoring is only allowed for authorized devices."
        )
        
    snmp_config = device.snmp_config or {}
    if not snmp_config.get("snmp_enabled", False):
        raise HTTPException(
            status_code=400,
            detail="SNMP monitoring is not enabled on this device."
        )
        
    # Retrieve previous log to calculate delta counters
    prev_log = db.query(SnmpLog).filter(
        SnmpLog.device_id == device_id
    ).order_by(SnmpLog.timestamp.desc()).first()
    
    prev_metrics = prev_log.metrics if prev_log else None
    prev_timestamp = prev_log.timestamp if prev_log else None
    
    from app.services.snmp_monitor import poll_device_snmp
    
    poll_result = await poll_device_snmp(
        ip_address=device.ip_address,
        snmp_config=snmp_config,
        prev_metrics=prev_metrics,
        prev_timestamp=prev_timestamp
    )
    
    snmp_log = SnmpLog(
        device_id=device_id,
        metrics=poll_result,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(snmp_log)
    
    # Evaluate SNMP alerts
    try:
        from app.services.alert_engine import AlertEngine
        AlertEngine.process_snmp_result(
            db=db,
            device_id=device_id,
            hostname=device.hostname,
            ip_address=device.ip_address,
            poll_result=poll_result
        )
    except Exception as alert_err:
        import logging
        logging.getLogger("NetVision.API").error(f"Alert engine manual SNMP processing failed: {alert_err}")
    
    try:
        db.commit()
        db.refresh(snmp_log)
        log_audit_event(
            db=db,
            action="manual_monitoring",
            user=current_user,
            details={"device_id": str(device_id), "type": "SNMP", "ip_address": device.ip_address}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save SNMP poll result: {str(e)}"
        )
        
    return snmp_log


@router.get("/{device_id}/alerts", response_model=List[AlertResponse])
def get_device_alerts(device_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_viewer)):
    """
    Retrieve alerts belonging to a specific device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=404,
            detail=f"Device with ID {device_id} not found"
        )
    try:
        from app.models.alert import Alert
        return db.query(Alert).filter(Alert.device_id == device_id).order_by(Alert.created_at.desc()).all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch alerts for device: {str(e)}"
        )

