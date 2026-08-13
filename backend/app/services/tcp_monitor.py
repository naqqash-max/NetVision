import socket
import time
import errno
import asyncio
import logging

logger = logging.getLogger("NetVisionAPI.TCP")

def check_port_sync(ip_address: str, port: int, timeout: float = 2.0) -> dict:
    """
    Synchronously attempts a TCP connection to a specific port.
    Returns status: 'open', 'closed', 'timeout', 'unreachable', or 'error'.
    """
    start_time = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    
    status = "error"
    error_msg = None
    is_open = False
    
    try:
        sock.connect((ip_address, port))
        is_open = True
        status = "open"
    except socket.timeout:
        status = "timeout"
        error_msg = "Connection timed out"
    except ConnectionRefusedError:
        status = "closed"
        error_msg = "Connection refused"
    except OSError as e:
        # Check standard socket error codes for reachability/route failures
        if e.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
            status = "unreachable"
            error_msg = "Host or network unreachable"
        elif e.errno == errno.ECONNREFUSED:
            status = "closed"
            error_msg = "Connection refused"
        else:
            status = "error"
            error_msg = f"OS Error {e.errno}: {e.strerror}"
    except Exception as e:
        status = "error"
        error_msg = str(e)
    finally:
        try:
            sock.close()
        except Exception:
            pass
            
    latency_ms = (time.time() - start_time) * 1000.0
    
    return {
        "port": port,
        "is_open": is_open,
        "status": status,
        "response_time_ms": latency_ms if status == "open" else None,
        "error_msg": error_msg
    }

async def check_device_ports(ip_address: str, ports: list, timeout: float = 2.0) -> list:
    """
    Checks multiple configured TCP ports asynchronously in parallel, maintaining original order.
    """
    results = [None] * len(ports)
    tasks = []
    task_indices = []
    
    for idx, port in enumerate(ports):
        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                raise ValueError()
            tasks.append(asyncio.to_thread(check_port_sync, ip_address, port_num, timeout))
            task_indices.append(idx)
        except (ValueError, TypeError):
            results[idx] = {
                "port": port,
                "is_open": False,
                "status": "error",
                "response_time_ms": None,
                "error_msg": f"Invalid port number: {port}. Port must be between 1 and 65535."
            }
            
    if tasks:
        checked_results = await asyncio.gather(*tasks)
        for task_idx, res in zip(task_indices, checked_results):
            results[task_idx] = res
            
    return results
