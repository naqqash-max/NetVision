import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from services.monitor_scheduler import MonitorScheduler

@pytest.mark.asyncio
async def test_scheduler_concurrency_limit_configuration():
    with patch.dict(os.environ, {"MONITOR_CONCURRENCY_LIMIT": "5"}):
        scheduler = MonitorScheduler()
        assert scheduler.concurrency_limit == 5
        assert scheduler.semaphore._value == 5

@pytest.mark.asyncio
async def test_scheduler_concurrency_execution():
    scheduler = MonitorScheduler()
    # Set limit to 2
    scheduler.concurrency_limit = 2
    scheduler.semaphore = asyncio.Semaphore(2)
    
    # We will track active concurrent calls
    active_calls = 0
    max_concurrent_calls = 0
    
    async def mock_monitor_device(device_id, ip_address, hostname):
        nonlocal active_calls, max_concurrent_calls
        active_calls += 1
        max_concurrent_calls = max(max_concurrent_calls, active_calls)
        await asyncio.sleep(0.05)
        active_calls -= 1

    scheduler.monitor_device = mock_monitor_device
    
    # Spawn 5 concurrent tasks through monitor_device_wrapped
    tasks = [
        asyncio.create_task(scheduler.monitor_device_wrapped(i, "127.0.0.1", f"dev_{i}"))
        for i in range(5)
    ]
    
    await asyncio.gather(*tasks)
    
    # Max concurrent calls should have been capped at the semaphore limit (2)
    assert max_concurrent_calls <= 2
    assert active_calls == 0
