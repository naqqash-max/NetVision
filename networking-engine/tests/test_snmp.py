import pytest
from unittest.mock import AsyncMock, MagicMock
from services.snmp_monitor import poll_device_snmp, calculate_traffic_rate

class MockVarbind:
    def __init__(self, oid, value):
        self.oid = oid
        self.value = value

@pytest.mark.asyncio
async def test_calculate_traffic_rate():
    # Regular rate
    b_sec, bit_sec = calculate_traffic_rate(2000, 1000, 10.0)
    assert b_sec == 100.0
    assert bit_sec == 800.0

    # Rollover 32-bit
    b_sec, bit_sec = calculate_traffic_rate(100, 4294967200, 10.0)
    assert b_sec == 19.6
    assert bit_sec == 156.8

@pytest.mark.asyncio
async def test_poll_device_snmp_success(monkeypatch):
    # Mock aiosnmp.Snmp class
    mock_snmp_instance = MagicMock()
    mock_snmp_instance.__aenter__ = AsyncMock()
    mock_snmp_instance.__aexit__ = AsyncMock()
    
    # Configure mock get/walk methods
    mock_snmp = mock_snmp_instance.__aenter__.return_value
    mock_snmp.get = AsyncMock(return_value=[
        MockVarbind(".1.3.6.1.2.1.1.5.0", b"test-host"),
        MockVarbind(".1.3.6.1.2.1.1.1.0", b"Test Device Description"),
        MockVarbind(".1.3.6.1.2.1.1.3.0", 123456)
    ])
    
    mock_snmp.walk = AsyncMock(side_effect=lambda oid: {
        ".1.3.6.1.2.1.2.2.1.2": [MockVarbind(".1.3.6.1.2.1.2.2.1.2.1", b"eth0")],
        ".1.3.6.1.2.1.2.2.1.5": [MockVarbind(".1.3.6.1.2.1.2.2.1.5.1", 100000000)],
        ".1.3.6.1.2.1.2.2.1.7": [MockVarbind(".1.3.6.1.2.1.2.2.1.7.1", 1)],
        ".1.3.6.1.2.1.2.2.1.8": [MockVarbind(".1.3.6.1.2.1.2.2.1.8.1", 1)],
        ".1.3.6.1.2.1.2.2.1.10": [MockVarbind(".1.3.6.1.2.1.2.2.1.10.1", 1000)],
        ".1.3.6.1.2.1.2.2.1.16": [MockVarbind(".1.3.6.1.2.1.2.2.1.16.1", 2000)],
        ".1.3.6.1.2.1.31.1.1.1.1": [MockVarbind(".1.3.6.1.2.1.31.1.1.1.1.1", b"eth0")],
    }.get(oid, []))

    # Mock the aiosnmp.Snmp constructor to return our instance
    monkeypatch.setattr("aiosnmp.Snmp", lambda **kwargs: mock_snmp_instance)

    result = await poll_device_snmp("127.0.0.1", {"community": "public", "port": 161})
    
    assert result["status"] == "ok"
    assert result["system"]["sysName"] == "test-host"
    assert result["system"]["sysDescr"] == "Test Device Description"
    assert result["system"]["sysUpTime"] == 123456
    assert len(result["interfaces"]) == 1
    assert result["interfaces"][0]["name"] == "eth0"
    assert result["interfaces"][0]["op_status"] == "up"
    assert result["interfaces"][0]["admin_status"] == "up"
    assert result["interfaces"][0]["speed"] == 100000000
    assert result["interfaces"][0]["in_octets"] == 1000
    assert result["interfaces"][0]["out_octets"] == 2000
