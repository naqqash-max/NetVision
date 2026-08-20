import os
import asyncio
import logging
from datetime import datetime, timezone
from db import SessionLocal
from models.device import Device
from models.metric import PingLog, PortLog
from services.icmp_monitor import ping_ipv4
from services.tcp_monitor import check_device_ports

logger = logging.getLogger("NetVisionWorker.Scheduler")

class MonitorScheduler:
    def __init__(self):
        self.device_tasks = {}  # Tracks device_id -> last_check_time (datetime)
        self.snmp_tasks = {}    # Tracks device_id -> last_snmp_check_time (datetime)
        self.running = False
        
        limit_str = os.getenv("MONITOR_CONCURRENCY_LIMIT", "10")
        try:
            self.concurrency_limit = int(limit_str)
        except ValueError:
            self.concurrency_limit = 10
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)

    async def monitor_device_wrapped(self, device_id, ip_address, hostname):
        async with self.semaphore:
            await self.monitor_device(device_id, ip_address, hostname)

    async def poll_device_snmp_task_wrapped(self, device_id, ip_address, hostname, snmp_config):
        async with self.semaphore:
            await self.poll_device_snmp_task(device_id, ip_address, hostname, snmp_config)

    async def start(self):
        """
        Starts the monitoring loop. Checks every second for devices due for a ping.
        """
        self.running = True
        logger.info("Starting NetVision Network Monitor Scheduler daemon...")

        while self.running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Error encountered in scheduler heartbeat tick: {str(e)}")
            await asyncio.sleep(1)

    def stop(self):
        """
        Stops the scheduler loop.
        """
        self.running = False
        logger.info("Shutting down NetVision Network Monitor Scheduler...")

    async def tick(self):
        db = SessionLocal()
        try:
            # Query only devices that are authorized and have monitoring enabled
            devices = db.query(Device).filter(
                Device.is_authorized == True,
                Device.monitoring_enabled == True
            ).all()

            current_time = datetime.now(timezone.utc)

            # Evict devices that have been removed or disabled
            active_device_ids = {d.id for d in devices}
            self.device_tasks = {k: v for k, v in self.device_tasks.items() if k in active_device_ids}
            self.snmp_tasks = {k: v for k, v in self.snmp_tasks.items() if k in active_device_ids}

            for device in devices:
                device_id = device.id
                
                # 1. ICMP / TCP checking
                interval = device.ping_interval or 30  # Default to 30s if not specified
                last_check = self.device_tasks.get(device_id)

                if last_check is None or (current_time - last_check).total_seconds() >= interval:
                    self.device_tasks[device_id] = current_time
                    # Fire task asynchronously to prevent blocking the scheduler loop
                    asyncio.create_task(
                        self.monitor_device_wrapped(device_id, device.ip_address, device.hostname)
                    )

                # 2. SNMP checking
                snmp_config = device.snmp_config or {}
                if snmp_config.get("snmp_enabled", False):
                    snmp_interval = snmp_config.get("polling_interval") or device.ping_interval or 30
                    last_snmp_check = self.snmp_tasks.get(device_id)
                    
                    if last_snmp_check is None or (current_time - last_snmp_check).total_seconds() >= snmp_interval:
                        self.snmp_tasks[device_id] = current_time
                        asyncio.create_task(
                            self.poll_device_snmp_task_wrapped(device_id, device.ip_address, device.hostname, snmp_config)
                        )
                else:
                    if device_id in self.snmp_tasks:
                        del self.snmp_tasks[device_id]
        finally:
            db.close()

    async def monitor_device(self, device_id, ip_address, hostname):
        """
        Performs ICMP check, TCP ports checks, outputs status logs, and records results to Postgres.
        """
        logger.info(f"Starting monitoring cycle for device {hostname} ({ip_address})...")
        
        try:
            # 1. ICMP ping check
            result = await ping_ipv4(ip_address, timeout=1.0, count=4)
        except Exception as e:
            logger.error(f"Fatal exception during monitoring of {hostname} ({ip_address}): {str(e)}")
            return

        avg_latency = result["latency_ms"]
        loss = result["packet_loss_pct"]
        status = result["status"]
        is_online = result["is_online"]

        # Output structured log reports
        if status == "online":
            logger.info(f"Device {hostname} ({ip_address}) is ONLINE - average latency: {avg_latency:.2f} ms")
        elif status == "degraded":
            logger.warning(
                f"Device {hostname} ({ip_address}) status is DEGRADED - average latency: "
                f"{avg_latency:.2f} ms, packet loss: {loss:.1f}%"
            )
        else:
            logger.error(
                f"Device {hostname} ({ip_address}) is OFFLINE - packet loss: {loss:.1f}%. "
                f"Reason: {result['error_msg']}"
            )

        # Write to database
        db = SessionLocal()
        try:
            # 1. Store the PingLog
            ping_log = PingLog(
                device_id=device_id,
                latency_ms=avg_latency,
                min_latency=result["min_latency"],
                max_latency=result["max_latency"],
                packet_loss_pct=loss,
                is_online=is_online,
                status=status,
                error_msg=result["error_msg"],
                timestamp=datetime.now(timezone.utc)
            )
            db.add(ping_log)

            # 2. Update Device Status and Last Seen
            db_device = db.query(Device).filter(Device.id == device_id).first()
            if db_device:
                db_device.status = status
                if is_online:
                    db_device.last_seen = datetime.now(timezone.utc)

                # 3. Check and record configured TCP ports
                configured_ports = db_device.tcp_ports or []
                port_results = []
                if configured_ports:
                    logger.info(f"Checking configured TCP ports {configured_ports} for {hostname} ({ip_address})...")
                    port_results = await check_device_ports(ip_address, configured_ports, timeout=2.0)
                    for port_res in port_results:
                        port_log = PortLog(
                            device_id=device_id,
                            port=port_res["port"],
                            is_open=port_res["is_open"],
                            response_time_ms=port_res["response_time_ms"],
                            status=port_res["status"],
                            error_msg=port_res["error_msg"],
                            timestamp=datetime.now(timezone.utc)
                        )
                        db.add(port_log)

                # 4. Alert Engine Evaluation
                try:
                    from services.alert_engine import AlertEngine
                    # ICMP
                    AlertEngine.process_icmp_result(
                        db=db,
                        device_id=device_id,
                        hostname=hostname,
                        ip_address=ip_address,
                        is_online=is_online,
                        packet_loss_pct=loss,
                        average_latency=avg_latency
                    )
                    # TCP Ports
                    for port_res in port_results:
                        AlertEngine.process_tcp_result(
                            db=db,
                            device_id=device_id,
                            hostname=hostname,
                            ip_address=ip_address,
                            port=port_res["port"],
                            is_open=port_res["is_open"],
                            status=port_res["status"]
                        )
                except Exception as alert_err:
                    logger.error(f"Alert engine processing failed for ICMP/TCP on {hostname}: {alert_err}")

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database write error saving metrics for {hostname} ({ip_address}): {str(e)}")
        finally:
            db.close()

    async def poll_device_snmp_task(self, device_id, ip_address, hostname, snmp_config):
        """
        Polls SNMP device metrics in background.
        """
        logger.info(f"Starting background SNMP poll task for device {hostname} ({ip_address})...")
        
        # Query previous log to compute counter differences
        db = SessionLocal()
        prev_metrics = None
        prev_timestamp = None
        try:
            from models.metric import SnmpLog
            prev_log = db.query(SnmpLog).filter(
                SnmpLog.device_id == device_id
            ).order_by(SnmpLog.timestamp.desc()).first()
            if prev_log:
                prev_metrics = prev_log.metrics
                prev_timestamp = prev_log.timestamp
        except Exception as e:
            logger.error(f"Error fetching previous SNMP logs for {hostname}: {e}")
        finally:
            db.close()
            
        from services.snmp_monitor import poll_device_snmp
        try:
            poll_result = await poll_device_snmp(
                ip_address=ip_address,
                snmp_config=snmp_config,
                prev_metrics=prev_metrics,
                prev_timestamp=prev_timestamp
            )
        except Exception as e:
            logger.error(f"Fatal SNMP exception during background poll for {hostname}: {e}")
            return
            
        db = SessionLocal()
        try:
            from models.metric import SnmpLog
            snmp_log = SnmpLog(
                device_id=device_id,
                metrics=poll_result,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(snmp_log)

            # Evaluate SNMP alerts
            try:
                from services.alert_engine import AlertEngine
                AlertEngine.process_snmp_result(
                    db=db,
                    device_id=device_id,
                    hostname=hostname,
                    ip_address=ip_address,
                    poll_result=poll_result
                )
            except Exception as alert_err:
                logger.error(f"Alert engine processing failed for SNMP on {hostname}: {alert_err}")

            db.commit()
            logger.info(f"Successfully saved SNMP background poll metrics for {hostname}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error persisting background SNMP poll for {hostname}: {e}")
        finally:
            db.close()

