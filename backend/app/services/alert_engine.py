import logging
from datetime import datetime, timezone
from app.models.alert import Alert
from sqlalchemy import text

logger = logging.getLogger("NetVision.AlertEngine")

def get_threshold(db, key, default):
    try:
        row = db.execute(
            text("SELECT value FROM global_settings WHERE key = :key"), 
            {"key": key}
        ).first()
        if row:
            return float(row[0])
    except Exception as e:
        logger.warning(f"Error querying global setting {key}, using default {default}: {e}")
    return float(default)

def trigger_or_update_alert(db, device_id, hostname, alert_type, severity, title, message, monitored_resource=None, current_value=None, threshold=None):
    try:
        # Check if there is an active (OPEN or ACKNOWLEDGED) alert
        existing = db.query(Alert).filter(
            Alert.device_id == device_id,
            Alert.alert_type == alert_type,
            Alert.monitored_resource == monitored_resource,
            Alert.status.in_(["OPEN", "ACKNOWLEDGED"])
        ).first()

        if existing:
            # Update current state if anything changed
            existing.severity = severity
            existing.title = title
            existing.message = message
            existing.current_value = str(current_value) if current_value is not None else None
            existing.threshold = str(threshold) if threshold is not None else None
            db.commit()
            return existing
        else:
            new_alert = Alert(
                device_id=device_id,
                alert_type=alert_type,
                severity=severity,
                status="OPEN",
                title=title,
                message=message,
                monitored_resource=monitored_resource,
                current_value=str(current_value) if current_value is not None else None,
                threshold=str(threshold) if threshold is not None else None,
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_alert)
            db.commit()
            logger.info(f"Alert created: {alert_type} for {hostname} ({monitored_resource or 'device'})")
            return new_alert
    except Exception as e:
        logger.error(f"Alert creation/update failed for device {hostname}: {e}")
        db.rollback()

def resolve_alert_if_active(db, device_id, hostname, alert_type, monitored_resource=None):
    try:
        existing = db.query(Alert).filter(
            Alert.device_id == device_id,
            Alert.alert_type == alert_type,
            Alert.monitored_resource == monitored_resource,
            Alert.status.in_(["OPEN", "ACKNOWLEDGED"])
        ).first()

        if existing:
            existing.status = "RESOLVED"
            existing.resolved_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Alert resolved: {alert_type} for {hostname} ({monitored_resource or 'device'})")
            return existing
        return None
    except Exception as e:
        logger.error(f"Alert resolution failed for device {hostname}: {e}")
        db.rollback()


class AlertEngine:
    @staticmethod
    def process_icmp_result(db, device_id, hostname, ip_address, is_online, packet_loss_pct, average_latency):
        try:
            if not is_online:
                trigger_or_update_alert(
                    db=db,
                    device_id=device_id,
                    hostname=hostname,
                    alert_type="DEVICE_OFFLINE",
                    severity="CRITICAL",
                    title="Device Offline",
                    message=f"{hostname} ({ip_address}) is offline",
                    monitored_resource=None,
                    current_value="offline",
                    threshold="online"
                )
                resolve_alert_if_active(db, device_id, hostname, "PACKET_LOSS")
                resolve_alert_if_active(db, device_id, hostname, "HIGH_LATENCY")
                return

            resolve_alert_if_active(db, device_id, hostname, "DEVICE_OFFLINE")

            loss_warning = get_threshold(db, "packet_loss_warning", 10.0)
            loss_critical = get_threshold(db, "packet_loss_critical", 30.0)
            latency_warning = get_threshold(db, "icmp_latency_warning", 200.0)
            latency_critical = get_threshold(db, "icmp_latency_critical", 500.0)

            # Evaluate Packet Loss
            if packet_loss_pct >= loss_critical:
                trigger_or_update_alert(
                    db=db,
                    device_id=device_id,
                    hostname=hostname,
                    alert_type="PACKET_LOSS",
                    severity="CRITICAL",
                    title="High Packet Loss",
                    message=f"{hostname} packet loss is {packet_loss_pct}% (threshold: {loss_critical}%)",
                    monitored_resource=None,
                    current_value=f"{packet_loss_pct}%",
                    threshold=f"{loss_critical}%"
                )
            elif packet_loss_pct >= loss_warning:
                trigger_or_update_alert(
                    db=db,
                    device_id=device_id,
                    hostname=hostname,
                    alert_type="PACKET_LOSS",
                    severity="WARNING",
                    title="Packet Loss Warning",
                    message=f"{hostname} packet loss is {packet_loss_pct}% (threshold: {loss_warning}%)",
                    monitored_resource=None,
                    current_value=f"{packet_loss_pct}%",
                    threshold=f"{loss_warning}%"
                )
            else:
                resolve_alert_if_active(db, device_id, hostname, "PACKET_LOSS")

            # Evaluate Latency
            if average_latency is not None:
                if average_latency >= latency_critical:
                    trigger_or_update_alert(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        alert_type="HIGH_LATENCY",
                        severity="CRITICAL",
                        title="High Latency",
                        message=f"{hostname} average latency is {average_latency:.1f} ms (threshold: {latency_critical} ms)",
                        monitored_resource=None,
                        current_value=f"{average_latency:.1f} ms",
                        threshold=f"{latency_critical} ms"
                    )
                elif average_latency >= latency_warning:
                    trigger_or_update_alert(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        alert_type="HIGH_LATENCY",
                        severity="WARNING",
                        title="Latency Warning",
                        message=f"{hostname} average latency is {average_latency:.1f} ms (threshold: {latency_warning} ms)",
                        monitored_resource=None,
                        current_value=f"{average_latency:.1f} ms",
                        threshold=f"{latency_warning} ms"
                    )
                else:
                    resolve_alert_if_active(db, device_id, hostname, "HIGH_LATENCY")
            else:
                resolve_alert_if_active(db, device_id, hostname, "HIGH_LATENCY")

        except Exception as e:
            logger.error(f"Alert evaluation failed for device {hostname} (ICMP): {e}")

    @staticmethod
    def process_tcp_result(db, device_id, hostname, ip_address, port, is_open, status):
        try:
            resource = f"port {port}"
            if is_open:
                resolve_alert_if_active(db, device_id, hostname, "TCP_PORT_UNAVAILABLE", resource)
            else:
                if status == "closed":
                    trigger_or_update_alert(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        alert_type="TCP_PORT_UNAVAILABLE",
                        severity="WARNING",
                        title="TCP Port Closed",
                        message=f"TCP port {port} on {hostname} is closed",
                        monitored_resource=resource,
                        current_value="closed",
                        threshold="open"
                    )
                else:
                    trigger_or_update_alert(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        alert_type="TCP_PORT_UNAVAILABLE",
                        severity="CRITICAL",
                        title="TCP Port Unavailable",
                        message=f"TCP port {port} on {hostname} is {status}",
                        monitored_resource=resource,
                        current_value=status,
                        threshold="open"
                    )
        except Exception as e:
            logger.error(f"Alert evaluation failed for device {hostname} (TCP port {port}): {e}")

    @staticmethod
    def process_snmp_result(db, device_id, hostname, ip_address, poll_result):
        try:
            if poll_result["status"] == "error":
                trigger_or_update_alert(
                    db=db,
                    device_id=device_id,
                    hostname=hostname,
                    alert_type="SNMP_POLLING_FAILURE",
                    severity="WARNING",
                    title="SNMP Polling Failure",
                    message=f"Failed to poll SNMP daemon on {hostname} ({ip_address}): {poll_result.get('error_msg')}",
                    monitored_resource="snmp",
                    current_value="failed",
                    threshold="success"
                )
                return

            resolve_alert_if_active(db, device_id, hostname, "SNMP_POLLING_FAILURE", "snmp")

            traffic_threshold = get_threshold(db, "snmp_traffic_warning_bps", 80000000.0)

            for iface in poll_result.get("interfaces", []):
                name = iface.get("name")
                resource = f"interface {name}"
                admin_status = iface.get("admin_status")
                op_status = iface.get("op_status")
                
                if admin_status == "down":
                    trigger_or_update_alert(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        alert_type="INTERFACE_ADMIN_DOWN",
                        severity="INFO",
                        title="Interface Admin Down",
                        message=f"Interface {name} on {hostname} is administratively disabled",
                        monitored_resource=resource,
                        current_value="admin down",
                        threshold="admin up"
                    )
                    resolve_alert_if_active(db, device_id, hostname, "INTERFACE_DOWN", resource)
                else:
                    resolve_alert_if_active(db, device_id, hostname, "INTERFACE_ADMIN_DOWN", resource)

                    if op_status == "down":
                        trigger_or_update_alert(
                            db=db,
                            device_id=device_id,
                            hostname=hostname,
                            alert_type="INTERFACE_DOWN",
                            severity="WARNING",
                            title="Interface Down",
                            message=f"Interface {name} on {hostname} is operational down",
                            monitored_resource=resource,
                            current_value="down",
                            threshold="up"
                        )
                    else:
                        resolve_alert_if_active(db, device_id, hostname, "INTERFACE_DOWN", resource)

                in_rate = iface.get("in_rate_bps")
                out_rate = iface.get("out_rate_bps")
                if in_rate is not None and out_rate is not None:
                    max_rate = max(in_rate, out_rate)
                    if max_rate >= traffic_threshold:
                        trigger_or_update_alert(
                            db=db,
                            device_id=device_id,
                            hostname=hostname,
                            alert_type="INTERFACE_TRAFFIC_HIGH",
                            severity="WARNING",
                            title="High Interface Traffic",
                            message=f"Interface {name} traffic on {hostname} ({max_rate/1e6:.1f} Mbps) exceeds threshold ({traffic_threshold/1e6:.1f} Mbps)",
                            monitored_resource=resource,
                            current_value=f"{max_rate/1e6:.1f} Mbps",
                            threshold=f"{traffic_threshold/1e6:.1f} Mbps"
                        )
                    else:
                        resolve_alert_if_active(db, device_id, hostname, "INTERFACE_TRAFFIC_HIGH", resource)
                else:
                    resolve_alert_if_active(db, device_id, hostname, "INTERFACE_TRAFFIC_HIGH", resource)

        except Exception as e:
            logger.error(f"Alert evaluation failed for device {hostname} (SNMP): {e}")
