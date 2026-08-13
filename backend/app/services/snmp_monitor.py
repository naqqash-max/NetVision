import asyncio
import time
import logging
import os
import aiosnmp
from datetime import datetime, timezone

logger = logging.getLogger("NetVisionAPI.SNMP")

# OID Constants
OID_SYS_NAME = ".1.3.6.1.2.1.1.5.0"
OID_SYS_DESCR = ".1.3.6.1.2.1.1.1.0"
OID_SYS_UPTIME = ".1.3.6.1.2.1.1.3.0"

OID_IF_INDEX = ".1.3.6.1.2.1.2.2.1.1"
OID_IF_DESCR = ".1.3.6.1.2.1.2.2.1.2"
OID_IF_SPEED = ".1.3.6.1.2.1.2.2.1.5"
OID_IF_ADMIN = ".1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER = ".1.3.6.1.2.1.2.2.1.8"
OID_IF_IN_OCTETS = ".1.3.6.1.2.1.2.2.1.10"
OID_IF_OUT_OCTETS = ".1.3.6.1.2.1.2.2.1.16"
OID_IF_NAME = ".1.3.6.1.2.1.31.1.1.1.1"  # Optional ifXTable Name

def decode_bytes(val) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val) if val is not None else ""

def parse_column_walk(varbinds, base_oid: str) -> dict:
    """
    Parses walk results for a column OID and returns a dict mapping index suffix to value.
    """
    results = {}
    normalized_base = base_oid.rstrip(".") + "."
    for vb in varbinds:
        oid = vb.oid
        if oid.startswith(normalized_base):
            suffix = oid[len(normalized_base):]
            results[suffix] = vb.value
        else:
            # Fallback suffix extraction
            suffix = oid.split(".")[-1]
            results[suffix] = vb.value
    return results

def calculate_traffic_rate(
    current_val: int, 
    prev_val: int, 
    time_delta_sec: float
) -> tuple:
    """
    Calculates bytes/sec and bits/sec handling counter rollovers.
    """
    if time_delta_sec <= 0 or current_val is None or prev_val is None:
        return 0.0, 0.0
        
    diff = current_val - prev_val
    if diff < 0:
        # Rollover check: try 32-bit then 64-bit rollover
        if diff > -4294967296:
            diff += 4294967296
        else:
            diff += 18446744073709551616
            
    # If still negative or unreasonable, default to 0
    if diff < 0:
        diff = 0
        
    bytes_sec = diff / time_delta_sec
    bits_sec = bytes_sec * 8.0
    return bytes_sec, bits_sec

async def poll_device_snmp(
    ip_address: str,
    snmp_config: dict,
    prev_metrics: dict = None,
    prev_timestamp: datetime = None
) -> dict:
    """
    Asynchronously queries an SNMP v2c device for system and interface metrics.
    """
    # 1. Retrieve configurations safely
    # If credentials are not specified, fallback to safe env variables or default public string
    community = snmp_config.get("community") or os.getenv("SNMP_COMMUNITY", "public")
    port = int(snmp_config.get("port") or 161)
    timeout = float(snmp_config.get("timeout") or 2.0)
    retries = int(snmp_config.get("retries") or 1)
    
    # 2. SNMP Client context manager
    try:
        async with aiosnmp.Snmp(
            host=ip_address, 
            port=port, 
            community=community, 
            timeout=timeout, 
            retries=retries,
            validate_source_addr=False
        ) as snmp:
            
            # Fetch system variables
            try:
                sys_varbinds = await snmp.get([OID_SYS_NAME, OID_SYS_DESCR, OID_SYS_UPTIME])
                sys_data = {vb.oid: vb.value for vb in sys_varbinds}
            except Exception as e:
                logger.warning(f"Failed to query system OIDs for {ip_address}: {e}")
                return {
                    "status": "error",
                    "error_msg": f"SNMP Connection timeout or auth failure: {str(e)}",
                    "system": {},
                    "interfaces": []
                }
                
            sys_name = decode_bytes(sys_data.get(OID_SYS_NAME, ""))
            sys_descr = decode_bytes(sys_data.get(OID_SYS_DESCR, ""))
            sys_uptime = sys_data.get(OID_SYS_UPTIME, 0)
            
            # Fetch interface tables concurrently
            walk_tasks = [
                snmp.walk(OID_IF_DESCR),
                snmp.walk(OID_IF_SPEED),
                snmp.walk(OID_IF_ADMIN),
                snmp.walk(OID_IF_OPER),
                snmp.walk(OID_IF_IN_OCTETS),
                snmp.walk(OID_IF_OUT_OCTETS),
            ]
            
            # Optional IF-MIB table for interface names
            try:
                walk_tasks.append(snmp.walk(OID_IF_NAME))
            except Exception:
                walk_tasks.append(asyncio.sleep(0, result=[]))
                
            walk_results = await asyncio.gather(*walk_tasks, return_exceptions=True)
            
            # Check if main walks succeeded
            for res in walk_results[:6]:
                if isinstance(res, Exception):
                    logger.warning(f"Walk operation failed on {ip_address}: {res}")
                    return {
                        "status": "error",
                        "error_msg": f"SNMP Walk failure: {str(res)}",
                        "system": {
                            "sysName": sys_name,
                            "sysDescr": sys_descr,
                            "sysUpTime": sys_uptime
                        },
                        "interfaces": []
                    }
                    
            # Parse result mappings
            descrs = parse_column_walk(walk_results[0], OID_IF_DESCR)
            speeds = parse_column_walk(walk_results[1], OID_IF_SPEED)
            admins = parse_column_walk(walk_results[2], OID_IF_ADMIN)
            opers = parse_column_walk(walk_results[3], OID_IF_OPER)
            in_octets_map = parse_column_walk(walk_results[4], OID_IF_IN_OCTETS)
            out_octets_map = parse_column_walk(walk_results[5], OID_IF_OUT_OCTETS)
            
            names = {}
            if len(walk_results) > 6 and not isinstance(walk_results[6], Exception):
                names = parse_column_walk(walk_results[6], OID_IF_NAME)
                
            # Status mapping
            status_map = {1: "up", 2: "down", 3: "testing"}
            
            # Build interface list
            interfaces = []
            
            # Extract previous index counters for rates
            prev_interfaces_map = {}
            time_delta = 0.0
            if prev_metrics and prev_timestamp:
                time_delta = (datetime.now(timezone.utc) - prev_timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                for p_if in prev_metrics.get("interfaces", []):
                    idx = str(p_if.get("index"))
                    prev_interfaces_map[idx] = p_if
                    
            for idx in sorted(descrs.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                descr = decode_bytes(descrs.get(idx, ""))
                name = decode_bytes(names.get(idx, descr))
                if not name:
                    name = f"port-{idx}"
                    
                op_status = status_map.get(opers.get(idx), "unknown")
                admin_status = status_map.get(admins.get(idx), "unknown")
                speed = int(speeds.get(idx) or 0)
                in_octets = int(in_octets_map.get(idx) or 0)
                out_octets = int(out_octets_map.get(idx) or 0)
                
                # Rate Calculations
                in_rate_bps, out_rate_bps = 0.0, 0.0
                in_rate_bytes, out_rate_bytes = 0.0, 0.0
                
                if idx in prev_interfaces_map and time_delta > 0:
                    prev_if = prev_interfaces_map[idx]
                    prev_in = prev_if.get("in_octets", 0)
                    prev_out = prev_if.get("out_octets", 0)
                    
                    in_rate_bytes, in_rate_bps = calculate_traffic_rate(in_octets, prev_in, time_delta)
                    out_rate_bytes, out_rate_bps = calculate_traffic_rate(out_octets, prev_out, time_delta)
                    
                interfaces.append({
                    "index": int(idx) if idx.isdigit() else idx,
                    "name": name,
                    "description": descr,
                    "op_status": op_status,
                    "admin_status": admin_status,
                    "speed": speed,
                    "in_octets": in_octets,
                    "out_octets": out_octets,
                    "in_rate_bps": round(in_rate_bps, 2),
                    "out_rate_bps": round(out_rate_bps, 2),
                    "in_rate_bytes_sec": round(in_rate_bytes, 2),
                    "out_rate_bytes_sec": round(out_rate_bytes, 2)
                })
                
            return {
                "status": "ok",
                "system": {
                    "sysName": sys_name,
                    "sysDescr": sys_descr,
                    "sysUpTime": sys_uptime
                },
                "interfaces": interfaces
            }
            
    except Exception as e:
        logger.error(f"Unexpected SNMP exception: {e}")
        return {
            "status": "error",
            "error_msg": f"SNMP failure: {str(e)}",
            "system": {},
            "interfaces": []
        }
