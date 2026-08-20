import sys
import os
import asyncio

# Append networking-engine directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, "..", "networking-engine")))

from services.monitor_scheduler import MonitorScheduler
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NetVisionWorker")

async def main():
    logger.info("Initializing NetVision Background Network Monitoring Engine...")
    scheduler = MonitorScheduler()
    try:
        await scheduler.start()
    except asyncio.CancelledError:
        logger.info("Monitoring engine task cancelled.")
    except Exception as e:
        logger.fatal(f"Monitoring engine crashed: {str(e)}")
    finally:
        scheduler.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitoring engine stopped.")
