import asyncio
import time
import aiohttp
from typing import Dict, Optional, Any

class SMSServiceError(Exception):
"""Custom exception for SMS Service API errors."""
pass

class SMSService:
def init(self, api_key: str):
self.api_key = api_key
self.base_url = "https://api.sms-activate.org/stubs/handler_api.php"

async def _request(self, action: str, **kwargs) -> str:
    params = {"api_key": self.api_key, "action": action}
    params.update(kwargs)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    raise SMSServiceError(f"HTTP Error: {response.status}")
                text = await response.text()
                return text.strip()
    except aiohttp.ClientError as e:
        raise SMSServiceError(f"Connection error: {e}")

async def get_number(self, service: str, country: str = "0") -> Dict[str, str]:
    response = await self._request("getNumber", service=service, country=country)
    if response.startswith("ACCESS_NUMBER"):
        parts = response.split(":")
        return {"id": parts[1], "number": parts[2]}
    raise SMSServiceError(f"API Error (getNumber): {response}")

async def get_status(self, order_id: str) -> Dict[str, Optional[str]]:
    response = await self._request("getStatus", id=order_id)
    if response == "STATUS_WAIT_CODE":
        return {"status": "WAITING", "sms": None}
    if response.startswith("STATUS_OK"):
        return {"status": "RECEIVED", "sms": response.split(":")[1]}
    if response == "STATUS_CANCEL":
        return {"status": "CANCELLED", "sms": None}
    return {"status": "UNKNOWN", "sms": None}

async def wait_for_sms(self, order_id: str, timeout: int = 120) -> Dict[str, Optional[str]]:
    start = time.time()
    while (time.time() - start) < timeout:
        res = await self.get_status(order_id)
        if res["status"] == "RECEIVED":
            return res
        if res["status"] == "CANCELLED":
            raise SMSServiceError("Order was cancelled.")
        await asyncio.sleep(5)
    raise SMSServiceError(f"Timeout waiting for SMS after {timeout}s.")

async def cancel_number(self, order_id: str) -> bool:
    response = await self._request("setStatus", id=order_id, status="8")
    return response == "ACCESS_CANCEL"
if name == "main":
async def main():
# Replace with your actual key
service = SMSService(api_key="YOUR_API_KEY")
try:
# Example: Requesting number for Telegram (tg) from Russia (0)
data = await service.get_number("tg", "0")
print(f"Number: {data['number']} (ID: {data['id']})")

        print("Waiting for SMS...")
        result = await service.wait_for_sms(data["id"])
        print(f"SMS Received: {result['sms']}")
    except SMSServiceError as e:
        print(f"Service Error: {e}")
    except Exception as e:
        print(f"System Error: {e}")

asyncio.run(main())
