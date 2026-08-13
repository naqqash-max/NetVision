import pytest
import socket
import asyncio
from services.icmp_monitor import ping_ipv4

LOCALHOST_IP = "127.0.0.1"
UNREACHABLE_IP = "192.0.2.1"
INVALID_IP = "999.999.999.999"

@pytest.mark.asyncio
async def test_successful_ping():
    """
    Test pinging a live local interface (localhost).
    """
    result = await ping_ipv4(LOCALHOST_IP, timeout=1.0, count=2)
    assert result["is_online"] is True
    assert result["status"] == "online"
    assert result["packet_loss_pct"] == 0.0
    assert isinstance(result["latency_ms"], float)
    assert isinstance(result["min_latency"], float)
    assert isinstance(result["max_latency"], float)
    assert result["error_msg"] is None

@pytest.mark.asyncio
async def test_multiple_attempts():
    """
    Test setting the ping count attempt parameter.
    """
    result = await ping_ipv4(LOCALHOST_IP, timeout=1.0, count=3)
    assert result["packet_loss_pct"] == 0.0
    assert result["latency_ms"] > 0

@pytest.mark.asyncio
async def test_completely_unreachable():
    """
    Test pinging an unreachable IP target.
    """
    result = await ping_ipv4(UNREACHABLE_IP, timeout=0.5, count=2)
    assert result["is_online"] is False
    assert result["status"] == "offline"
    assert result["packet_loss_pct"] == 100.0
    assert result["latency_ms"] is None
    assert "timeout" in result["error_msg"].lower()

@pytest.mark.asyncio
async def test_invalid_address():
    """
    Test handling of invalid IP addresses.
    """
    result = await ping_ipv4(INVALID_IP, timeout=1.0, count=1)
    assert result["is_online"] is False
    assert result["status"] == "offline"
    assert result["packet_loss_pct"] == 100.0
    assert "invalid" in result["error_msg"].lower()
