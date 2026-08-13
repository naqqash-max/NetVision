import asyncio
import logging
import sys
from services.monitor_scheduler import MonitorScheduler

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
        logger.info("Monitoring engine stopped via KeyboardInterrupt.")
