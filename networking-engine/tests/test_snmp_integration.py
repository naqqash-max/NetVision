import asyncio
import os
import socket
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.snmp_monitor import poll_device_snmp
from services.monitor_scheduler import MonitorScheduler
from db import Base
from models.device import Device
from models.metric import SnmpLog

def resolve_snmp_host():
    for host in ["snmpsim", "localhost", "127.0.0.1"]:
        try:
            socket.gethostbyname(host)
            return host
        except socket.gaierror:
            continue
    return "127.0.0.1"

def get_test_db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        # Fallback for running locally on host
        url = "postgresql://admin:supersecretpassword123@localhost:5432/netvision"
    else:
        # Replace database host for container to host if needed, but within docker-compose "database" is correct
        pass
    return url

@pytest.mark.asyncio
async def test_real_snmp_query_success():
    snmp_host = resolve_snmp_host()
    config = {
        "snmp_enabled": True,
        "community": "public",
        "port": 1161,
        "timeout": 2.0,
        "retries": 1
    }
    
    result = await poll_device_snmp(snmp_host, config)
    
    assert result["status"] == "ok", f"Expected ok status, got error: {result.get('error_msg')}"
    assert "system" in result
    assert result["system"]["sysName"] == "test-snmp-device"
    assert "Simulated SNMP device" in result["system"]["sysDescr"]
    assert isinstance(result["system"]["sysUpTime"], int)
    assert result["system"]["sysUpTime"] > 0
    
    assert "interfaces" in result
    assert len(result["interfaces"]) > 0
    
    # Check interface fields
    first_if = result["interfaces"][0]
    assert "index" in first_if
    assert "name" in first_if
    assert "op_status" in first_if
    assert first_if["op_status"] in ["up", "down", "testing", "unknown"]
    assert "speed" in first_if
    assert "in_octets" in first_if
    assert "out_octets" in first_if

@pytest.mark.asyncio
async def test_real_snmp_rate_calculations():
    snmp_host = resolve_snmp_host()
    config = {
        "snmp_enabled": True,
        "community": "public",
        "port": 1161,
        "timeout": 2.0,
        "retries": 1
    }
    
    # Poll 1
    poll_1_time = datetime.now(timezone.utc)
    result_1 = await poll_device_snmp(snmp_host, config)
    assert result_1["status"] == "ok"
    
    # Wait a bit
    await asyncio.sleep(1.0)
    
    # Poll 2 passing prev_metrics and prev_timestamp
    result_2 = await poll_device_snmp(
        snmp_host, 
        config, 
        prev_metrics=result_1, 
        prev_timestamp=poll_1_time
    )
    
    assert result_2["status"] == "ok"
    for iface in result_2["interfaces"]:
        assert "in_rate_bps" in iface
        assert "out_rate_bps" in iface
        assert isinstance(iface["in_rate_bps"], float)
        assert isinstance(iface["out_rate_bps"], float)

@pytest.mark.asyncio
async def test_real_snmp_timeout_error():
    # Use invalid port to trigger timeout
    snmp_host = resolve_snmp_host()
    config = {
        "snmp_enabled": True,
        "community": "public",
        "port": 9999, # invalid port
        "timeout": 0.5,
        "retries": 0
    }
    
    result = await poll_device_snmp(snmp_host, config)
    assert result["status"] == "error"
    assert "error_msg" in result
    assert "timeout" in result["error_msg"].lower() or "failure" in result["error_msg"].lower() or "exception" in result["error_msg"].lower()

@pytest.mark.asyncio
async def test_real_snmp_db_persistence():
    db_url = get_test_db_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    snmp_host = resolve_snmp_host()
    
    # Check if device with same ip_address already exists
    existing = session.query(Device).filter(Device.ip_address == snmp_host).first()
    created_new = False
    if existing:
        test_device = existing
        device_id = existing.id
        # Ensure it has SNMP enabled for testing
        test_device.snmp_config = {
            "snmp_enabled": True,
            "community": "public",
            "port": 1161,
            "polling_interval": 30
        }
        session.commit()
    else:
        test_device = Device(
            name="Integration SNMP Test Device",
            hostname="integration-snmp-test",
            ip_address=snmp_host,
            device_type="switch",
            description="Temp device for SNMP integration test",
            monitoring_enabled=True,
            ping_interval=30,
            snmp_config={
                "snmp_enabled": True,
                "community": "public",
                "port": 1161,
                "polling_interval": 30
            }
        )
        session.add(test_device)
        session.commit()
        device_id = test_device.id
        created_new = True
    
    try:
        scheduler = MonitorScheduler()
        # Trigger background task
        await scheduler.poll_device_snmp_task(
            device_id=device_id,
            ip_address=test_device.ip_address,
            hostname=test_device.hostname,
            snmp_config=test_device.snmp_config
        )
        
        # Verify result was saved in database
        saved_log = session.query(SnmpLog).filter(
            SnmpLog.device_id == device_id
        ).order_by(SnmpLog.timestamp.desc()).first()
        
        assert saved_log is not None
        assert saved_log.metrics["status"] == "ok"
        assert saved_log.metrics["system"]["sysName"] == "test-snmp-device"
        assert len(saved_log.metrics["interfaces"]) > 0
        
    finally:
        # Cleanup
        session.query(SnmpLog).filter(SnmpLog.device_id == device_id).delete()
        if created_new:
            session.delete(test_device)
        session.commit()
        session.close()
