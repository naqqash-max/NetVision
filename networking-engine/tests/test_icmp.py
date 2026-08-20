import pytest
import socket
import asyncio
import struct
from unittest.mock import MagicMock, patch
from services.icmp_monitor import ping_ipv4, ping_one

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


def test_ping_one_matching_logic():
    """
    Unit test for ping_one matching logic:
    - Correct IP + correct packet ID + correct sequence = accepted
    - Wrong IP + otherwise matching packet = rejected
    - Wrong sequence = rejected
    - Wrong packet ID = rejected
    """
    mock_socket = MagicMock()
    
    with patch('socket.socket', return_value=mock_socket), \
         patch('select.select', return_value=([mock_socket], [], [])):
         
         correct_ip = "192.168.1.1"
         correct_pid = 1234
         correct_seq = 1
         
         # 1. Correct IP + correct packet ID + correct sequence = accepted
         icmp_hdr = struct.pack("bbHHh", 0, 0, 0, correct_pid, correct_seq)
         mock_packet = b'\x00' * 20 + icmp_hdr
         mock_socket.recvfrom.return_value = (mock_packet, (correct_ip, 0))
         
         latency = ping_one(correct_ip, timeout=0.1, seq=correct_seq, packet_id=correct_pid)
         assert latency is not None
         
         # 2. Wrong IP + otherwise matching packet = rejected (should time out and return None)
         mock_socket.recvfrom.return_value = (mock_packet, ("192.168.1.2", 0))
         latency = ping_one(correct_ip, timeout=0.1, seq=correct_seq, packet_id=correct_pid)
         assert latency is None
         
         # 3. Wrong sequence = rejected
         icmp_hdr_wrong_seq = struct.pack("bbHHh", 0, 0, 0, correct_pid, 999)
         mock_packet_wrong_seq = b'\x00' * 20 + icmp_hdr_wrong_seq
         mock_socket.recvfrom.return_value = (mock_packet_wrong_seq, (correct_ip, 0))
         latency = ping_one(correct_ip, timeout=0.1, seq=correct_seq, packet_id=correct_pid)
         assert latency is None
         
         # 4. Wrong packet ID = rejected
         icmp_hdr_wrong_pid = struct.pack("bbHHh", 0, 0, 0, 9999, correct_seq)
         mock_packet_wrong_pid = b'\x00' * 20 + icmp_hdr_wrong_pid
         mock_socket.recvfrom.return_value = (mock_packet_wrong_pid, (correct_ip, 0))
         latency = ping_one(correct_ip, timeout=0.1, seq=correct_seq, packet_id=correct_pid)
         assert latency is None

