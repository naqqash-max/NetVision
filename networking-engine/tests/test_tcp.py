import pytest
import socket
import threading
import time
import asyncio
from services.tcp_monitor import check_port_sync, check_device_ports

LOCALHOST_IP = "127.0.0.1"
UNREACHABLE_IP = "192.0.2.1"

@pytest.fixture(scope="module")
def local_tcp_server():
    """
    Spins up a lightweight local TCP server in a background thread to mock an open port.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LOCALHOST_IP, 0))
    host, port = sock.getsockname()
    sock.listen(5)
    
    stop_event = threading.Event()
    
    def run_server():
        sock.settimeout(0.2)
        while not stop_event.is_set():
            try:
                conn, addr = sock.accept()
                conn.close()
            except socket.timeout:
                continue
            except Exception:
                break
        sock.close()
        
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    yield host, port
    
    stop_event.set()
    thread.join()

def test_open_port(local_tcp_server):
    host, port = local_tcp_server
    result = check_port_sync(host, port, timeout=1.0)
    assert result["is_open"] is True
    assert result["status"] == "open"
    assert isinstance(result["response_time_ms"], float)
    assert result["response_time_ms"] > 0
    assert result["error_msg"] is None

def test_closed_port():
    result = check_port_sync(LOCALHOST_IP, 59999, timeout=1.0)
    assert result["is_open"] is False
    assert result["status"] == "closed"
    assert "refused" in result["error_msg"].lower() or "closed" in result["error_msg"].lower()

def test_timeout():
    result = check_port_sync(UNREACHABLE_IP, 80, timeout=0.2)
    assert result["is_open"] is False
    assert result["status"] in ("timeout", "unreachable")
    if result["status"] == "timeout":
        assert "timeout" in result["error_msg"].lower() or "timed out" in result["error_msg"].lower()

@pytest.mark.asyncio
async def test_invalid_ports():
    results = await check_device_ports(LOCALHOST_IP, [0, 80, 70000])
    assert results[0]["status"] == "error"
    assert "invalid" in results[0]["error_msg"].lower()
    assert results[1]["port"] == 80
    assert results[2]["status"] == "error"
    assert "invalid" in results[2]["error_msg"].lower()

@pytest.mark.asyncio
async def test_multiple_ports(local_tcp_server):
    host, port = local_tcp_server
    results = await check_device_ports(host, [port, 59999])
    assert len(results) == 2
    assert results[0]["port"] == port
    assert results[0]["status"] == "open"
    assert results[1]["port"] == 59999
    assert results[1]["status"] == "closed"
