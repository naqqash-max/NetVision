import ipaddress
import socket
import logging
import asyncio
import os
import struct
import time
import select

logger = logging.getLogger("NetVisionAPI.Ping")

ICMP_ECHO_REQUEST = 8

def checksum(source_string):
    """
    Calculates the internet checksum of the source bytes.
    """
    countTo = (len(source_string) // 2) * 2
    sum = 0
    count = 0
    while count < countTo:
        thisVal = source_string[count + 1] * 256 + source_string[count]
        sum = sum + thisVal
        sum = sum & 0xffffffff
        count = count + 2
    if countTo < len(source_string):
        sum = sum + source_string[len(source_string) - 1]
        sum = sum & 0xffffffff
    sum = (sum >> 16) + (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def ping_one(dest_addr, timeout=1.0, seq=1, packet_id=None):
    """
    Synchronous single packet raw socket echo request-reply transaction.
    """
    if packet_id is None:
        packet_id = os.getpid() & 0xFFFF

    try:
        my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        raise PermissionError("Raw socket permission denied. CAP_NET_RAW capability is required.")

    try:
        my_checksum = 0
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, packet_id, seq)
        data = struct.pack("d", time.time())
        my_checksum = checksum(header + data)
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), packet_id, seq)
        packet = header + data

        my_socket.sendto(packet, (dest_addr, 1))

        start_time = time.time()
        while True:
            time_left = timeout - (time.time() - start_time)
            if time_left <= 0:
                return None

            ready = select.select([my_socket], [], [], time_left)
            if ready[0] == []:
                return None

            time_received = time.time()
            rec_packet, addr = my_socket.recvfrom(1024)
            
            # Extract header and parse details
            icmp_header = rec_packet[20:28]
            type, code, checksum_val, p_id, p_seq = struct.unpack("bbHHh", icmp_header)
            
            if p_id == packet_id and p_seq == seq and type == 0:
                return (time_received - start_time) * 1000.0
    finally:
        my_socket.close()

async def ping_ipv4(ip_address: str, timeout: float = 1.0, count: int = 4) -> dict:
    """
    Async wrapper executing ping_one in thread pools.
    """
    try:
        ipaddress.IPv4Address(ip_address)
    except ValueError:
        logger.error(f"Invalid IPv4 address format specified: '{ip_address}'")
        return {
            "is_online": False,
            "status": "offline",
            "packet_loss_pct": 100.0,
            "latency_ms": None,
            "min_latency": None,
            "max_latency": None,
            "error_msg": f"Invalid IPv4 address format: {ip_address}"
        }

    delays = []
    lost_count = 0
    error_details = None
    permission_error_triggered = False
    packet_id = os.getpid() & 0xFFFF

    for attempt in range(count):
        try:
            # Execute synchronous raw socket ping in a background worker thread
            delay = await asyncio.to_thread(ping_one, ip_address, timeout, attempt + 1, packet_id)
            if delay is not None:
                delays.append(delay)
            else:
                lost_count += 1
                error_details = "Request timeout"
        except PermissionError:
            logger.error("PermissionError: Raw socket access denied. Ensure container has CAP_NET_RAW capability.")
            permission_error_triggered = True
            error_details = "Permission denied: CAP_NET_RAW capability missing"
            break
        except socket.gaierror as ge:
            logger.warning(f"DNS/Address resolution failure pinging {ip_address}: {str(ge)}")
            lost_count += 1
            error_details = "Address resolution failure"
        except Exception as e:
            logger.warning(f"Unexpected exception pinging {ip_address}: {str(e)}")
            lost_count += 1
            error_details = f"Networking error: {str(e)}"

        if attempt < count - 1 and not permission_error_triggered:
            await asyncio.sleep(0.1)

    if permission_error_triggered:
        return {
            "is_online": False,
            "status": "offline",
            "packet_loss_pct": 100.0,
            "latency_ms": None,
            "min_latency": None,
            "max_latency": None,
            "error_msg": error_details
        }

    if len(delays) == 0:
        return {
            "is_online": False,
            "status": "offline",
            "packet_loss_pct": 100.0,
            "latency_ms": None,
            "min_latency": None,
            "max_latency": None,
            "error_msg": error_details or "Request timed out"
        }

    min_latency = min(delays)
    max_latency = max(delays)
    avg_latency = sum(delays) / len(delays)
    packet_loss_pct = (lost_count / count) * 100.0

    if packet_loss_pct > 0.0 or avg_latency > 150.0:
        status = "degraded"
    else:
        status = "online"

    return {
        "is_online": True,
        "status": status,
        "packet_loss_pct": packet_loss_pct,
        "latency_ms": avg_latency,
        "min_latency": min_latency,
        "max_latency": max_latency,
        "error_msg": None
    }
