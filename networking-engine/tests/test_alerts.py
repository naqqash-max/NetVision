import os
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base
from models.device import Device
from models.alert import Alert
from services.alert_engine import AlertEngine, trigger_or_update_alert, resolve_alert_if_active

def get_test_db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        url = "postgresql://admin:supersecretpassword123@localhost:5432/netvision"
    return url

@pytest.fixture(scope="module")
def db_session():
    db_url = get_test_db_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def test_device(db_session):
    device = Device(
        name="Alert Test Device",
        hostname="alert-test-host",
        ip_address="192.168.99.99",
        device_type="server",
        monitoring_enabled=True,
        ping_interval=30
    )
    db_session.add(device)
    db_session.commit()
    yield device
    
    # Cleanup alerts and device
    db_session.query(Alert).filter(Alert.device_id == device.id).delete()
    db_session.delete(device)
    db_session.commit()

def test_alert_helpers(db_session, test_device):
    # Test triggering a new alert
    alert = trigger_or_update_alert(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        alert_type="TEST_ALERT",
        severity="WARNING",
        title="Test Title",
        message="Test Message",
        monitored_resource="test_res",
        current_value="10",
        threshold="5"
    )
    assert alert is not None
    assert alert.id is not None
    assert alert.status == "OPEN"
    assert alert.severity == "WARNING"

    # Test deduplication: triggering again does not create a duplicate
    alert2 = trigger_or_update_alert(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        alert_type="TEST_ALERT",
        severity="CRITICAL",  # update severity
        title="Test Title",
        message="Test Message Updated",
        monitored_resource="test_res",
        current_value="20",
        threshold="5"
    )
    assert alert2.id == alert.id
    assert alert2.severity == "CRITICAL"
    assert alert2.message == "Test Message Updated"
    
    active_alerts = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "TEST_ALERT"
    ).all()
    assert len(active_alerts) == 1

    # Test resolution
    resolved = resolve_alert_if_active(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        alert_type="TEST_ALERT",
        monitored_resource="test_res"
    )
    assert resolved is not None
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at is not None

    # Test triggering again after resolution creates a NEW incident
    alert3 = trigger_or_update_alert(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        alert_type="TEST_ALERT",
        severity="WARNING",
        title="Test Title",
        message="Test Message Again",
        monitored_resource="test_res"
    )
    assert alert3.id != alert.id
    assert alert3.status == "OPEN"

def test_icmp_alert_offline(db_session, test_device):
    # Device offline creates CRITICAL alert
    AlertEngine.process_icmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        is_online=False,
        packet_loss_pct=100.0,
        average_latency=None
    )
    
    alert = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "DEVICE_OFFLINE",
        Alert.status == "OPEN"
    ).first()
    assert alert is not None
    assert alert.severity == "CRITICAL"

    # Device comes back online -> offline alert resolves
    AlertEngine.process_icmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        is_online=True,
        packet_loss_pct=0.0,
        average_latency=15.0
    )
    
    alert_resolved = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "DEVICE_OFFLINE"
    ).first()
    assert alert_resolved.status == "RESOLVED"

def test_icmp_thresholds(db_session, test_device):
    # Packet loss warning threshold
    AlertEngine.process_icmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        is_online=True,
        packet_loss_pct=15.0,
        average_latency=15.0
    )
    alert = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "PACKET_LOSS",
        Alert.status == "OPEN"
    ).first()
    assert alert is not None
    assert alert.severity == "WARNING"

    # Packet loss critical threshold
    AlertEngine.process_icmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        is_online=True,
        packet_loss_pct=35.0,
        average_latency=15.0
    )
    alert_crit = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "PACKET_LOSS",
        Alert.status == "OPEN"
    ).first()
    assert alert_crit is not None
    assert alert_crit.id == alert.id
    assert alert_crit.severity == "CRITICAL"

    # High latency warning threshold
    AlertEngine.process_icmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        is_online=True,
        packet_loss_pct=0.0,
        average_latency=250.0
    )
    alert_lat = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "HIGH_LATENCY",
        Alert.status == "OPEN"
    ).first()
    assert alert_lat is not None
    assert alert_lat.severity == "WARNING"

def test_tcp_alert_states(db_session, test_device):
    # Port becomes closed -> WARNING
    AlertEngine.process_tcp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        port=80,
        is_open=False,
        status="closed"
    )
    alert = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "TCP_PORT_UNAVAILABLE",
        Alert.monitored_resource == "port 80",
        Alert.status == "OPEN"
    ).first()
    assert alert is not None
    assert alert.severity == "WARNING"

    # Port becomes unreachable -> CRITICAL
    AlertEngine.process_tcp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        port=80,
        is_open=False,
        status="timeout"
    )
    alert_crit = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "TCP_PORT_UNAVAILABLE",
        Alert.monitored_resource == "port 80",
        Alert.status == "OPEN"
    ).first()
    assert alert_crit is not None
    assert alert_crit.id == alert.id
    assert alert_crit.severity == "CRITICAL"

    # Port recovery -> RESOLVED
    AlertEngine.process_tcp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        port=80,
        is_open=True,
        status="open"
    )
    alert_res = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "TCP_PORT_UNAVAILABLE",
        Alert.monitored_resource == "port 80"
    ).first()
    assert alert_res.status == "RESOLVED"

def test_snmp_alert_states(db_session, test_device):
    # Polling failure alert
    AlertEngine.process_snmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        poll_result={"status": "error", "error_msg": "Timeout connecting to host"}
    )
    alert_poll = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "SNMP_POLLING_FAILURE",
        Alert.status == "OPEN"
    ).first()
    assert alert_poll is not None
    assert alert_poll.severity == "WARNING"

    # Polling success -> resolves polling failure
    AlertEngine.process_snmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        poll_result={
            "status": "ok",
            "interfaces": [
                {
                    "name": "eth0",
                    "admin_status": "up",
                    "op_status": "down"
                }
            ]
        }
    )
    alert_poll_res = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "SNMP_POLLING_FAILURE"
    ).first()
    assert alert_poll_res.status == "RESOLVED"

    # Interface Down alert
    alert_if = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "INTERFACE_DOWN",
        Alert.monitored_resource == "interface eth0",
        Alert.status == "OPEN"
    ).first()
    assert alert_if is not None
    assert alert_if.severity == "WARNING"

    # Interface Admin down -> INTERFACE_ADMIN_DOWN (INFO) and resolves INTERFACE_DOWN
    AlertEngine.process_snmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        poll_result={
            "status": "ok",
            "interfaces": [
                {
                    "name": "eth0",
                    "admin_status": "down",
                    "op_status": "down"
                }
            ]
        }
    )
    alert_if_res = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "INTERFACE_DOWN",
        Alert.monitored_resource == "interface eth0"
    ).first()
    assert alert_if_res.status == "RESOLVED"

    alert_admin = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "INTERFACE_ADMIN_DOWN",
        Alert.monitored_resource == "interface eth0",
        Alert.status == "OPEN"
    ).first()
    assert alert_admin is not None
    assert alert_admin.severity == "INFO"

    # Interface recovery (both admin and op up) -> resolves INTERFACE_ADMIN_DOWN
    AlertEngine.process_snmp_result(
        db=db_session,
        device_id=test_device.id,
        hostname=test_device.hostname,
        ip_address=test_device.ip_address,
        poll_result={
            "status": "ok",
            "interfaces": [
                {
                    "name": "eth0",
                    "admin_status": "up",
                    "op_status": "up",
                    "in_rate_bps": 120000000.0, # exceeds default 80 Mbps warning
                    "out_rate_bps": 1000.0
                }
            ]
        }
    )
    alert_admin_res = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "INTERFACE_ADMIN_DOWN",
        Alert.monitored_resource == "interface eth0"
    ).first()
    assert alert_admin_res.status == "RESOLVED"

    # High traffic alert triggered
    alert_traffic = db_session.query(Alert).filter(
        Alert.device_id == test_device.id,
        Alert.alert_type == "INTERFACE_TRAFFIC_HIGH",
        Alert.monitored_resource == "interface eth0",
        Alert.status == "OPEN"
    ).first()
    assert alert_traffic is not None
    assert alert_traffic.severity == "WARNING"
