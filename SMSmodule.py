import asyncio
import aiohttp
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

System logging configuration
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s [SYSTEM_CORE] %(levelname)s: %(message)s'
)
logger = logging.getLogger("VirtualNumberManager")

class VirtualNumberError(Exception):
"""Base exception for the module."""
pass

class NoNumbersAvailable(VirtualNumberError):
"""Raised when no numbers are available in the pool."""
pass

class SMSWaitTimeout(VirtualNumberError):
"""Raised when SMS wait time exceeds limit."""
pass

class APIError(VirtualNumberError):
"""Raised on external gateway errors."""
pass

class VirtualNumberManager:
"""
Manages virtual communication lines.
Abstracts SMS-Activate API to simulate internal number generation.
"""

def __init__(self, api_key: str, country_id: int = 0):
    self.__api_key = api_key
    self.__base_url = "[https://sms-activate.org/stubs/handler_api.php](https://sms-activate.org/stubs/handler_api.php)"
    self.__country_id = country_id
    self._active_orders: Dict[str, Dict[str, Any]] = {}
    self._session: Optional[aiohttp.ClientSession] = None
    self._is_running = True
    
    # Background cleanup task
    self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop())

async def __get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        self._session = aiohttp.ClientSession()
    return self._session

async def _request(self, params: Dict[str, Any], retries: int = 3) -> str:
    params["api_key"] = self.__api_key
    session = await self.__get_session()
    
    for attempt in range(retries):
        try:
            async with session.get(self.__base_url, params=params, timeout=15) as response:
                text = await response.text()
                if "BAD_KEY" in text:
                    raise APIError("Invalid System API Key.")
                if "ERROR" in text or "BAD_ACTION" in text:
                    raise APIError(f"Gateway error: {text}")
                return text
        except Exception as e:
            if attempt == retries - 1:
                raise APIError(f"Connection failed: {e}")
            await asyncio.sleep(2)
    return ""

async def get_virtual_number(self, service: str) -> dict:
    """Initializes a new virtual line allocation."""
    logger.info(f"Generating new line for service: {service}...")
    
    params = {
        "action": "getNumber",
        "service": service,
        "country": self.__country_id
    }

    result = await self._request(params)

    if "NO_NUMBERS" in result:
        raise NoNumbersAvailable(f"No resources available for '{service}'.")
    
    if "ACCESS_NUMBER" in result:
        parts = result.split(":")
        order_id = parts[1]
        phone_number = parts[2]

        order_data = {
            "system_id": order_id,
            "phone": f"+{phone_number}",
            "service": service,
            "created_at": time.time(),
            "status": "ACTIVE"
        }

        self._active_orders[order_id] = order_data
        logger.info(f"Line {order_id} initialized: {phone_number}")
        
        return {
            "status": "success",
            "internal_id": order_id,
            "virtual_number": f"+{phone_number}",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    raise APIError(f"Unexpected system response: {result}")

async def wait_for_sms(self, order_id: str, timeout: int = 300) -> dict:
    """Listens for incoming signals on the allocated line."""
    if order_id not in self._active_orders:
        raise VirtualNumberError("ID not found in active pool.")

    logger.info(f"Listening for SMS on line {order_id}...")
    
    start_time = time.time()
    params = {"action": "getStatus", "id": order_id}

    while time.time() - start_time < timeout:
        result = await self._request(params)

        if "STATUS_OK" in result:
            code = result.split(":")[1]
            logger.info(f"Signal received on line {order_id}: {code}")
            
            self._active_orders[order_id]["status"] = "RECEIVED"
            self._active_orders[order_id]["code"] = code
            
            return {
                "order_id": order_id,
                "code": code,
                "received_at": datetime.utcnow().isoformat()
            }

        if "STATUS_WAIT_CODE" not in result:
            raise APIError(f"Line interrupted by remote side: {result}")

        await asyncio.sleep(5)

    raise SMSWaitTimeout(f"Wait timeout for line {order_id}.")

async def release_number(self, order_id: str):
    """Releases the virtual line and deactivates it."""
    logger.info(f"Deactivating line {order_id}...")
    params = {"action": "setStatus", "status": 8, "id": order_id}

    try:
        await self._request(params)
        self._active_orders.pop(order_id, None)
        logger.info(f"Line {order_id} closed.")
    except Exception as e:
        logger.error(f"Failed to close line {order_id}: {e}")

async def _auto_cleanup_loop(self):
    """Internal loop to prevent memory leaks."""
    while self._is_running:
        try:
            now = time.time()
            to_delete = [oid for oid, d in self._active_orders.items() if now - d["created_at"] > 1200]
            for oid in to_delete:
                self._active_orders.pop(oid, None)
        except Exception:
            pass
        await asyncio.sleep(60)

async def close(self):
    """Shuts down the manager."""
    self._is_running = False
    if self._session:
        await self._session.close()
    self._cleanup_task.cancel()
Example usage pattern
async def main():
# Replace with real API key
key = "YOUR_API_KEY"
vm = VirtualNumberManager(key)
try:
# res = await vm.get_virtual_number("tg")
# print(res)
pass
finally:
await vm.close()

if name == "main":
asyncio.run(main())
