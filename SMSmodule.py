import asyncio
import time
import aiohttp
from typing import Dict, Optional, Any

class SMSServiceError(Exception):
"""Кастомное исключение для ошибок API сервиса SMS."""
pass

class SMSService:
"""
Класс для работы с API sms-activate.org
Позволяет получать номера, проверять статус и ожидать SMS.
"""

def __init__(self, api_key: str):
    """
    Инициализация сервиса.
    :param api_key: API ключ от сервиса (например, sms-activate).
    """
    self.api_key = api_key
    self.base_url = "[https://api.sms-activate.org/stubs/handler_api.php](https://api.sms-activate.org/stubs/handler_api.php)"

async def _request(self, action: str, **kwargs) -> str:
    """
    Внутренний метод для выполнения запросов к API.
    """
    params = {
        "api_key": self.api_key,
        "action": action
    }
    params.update(kwargs)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    raise SMSServiceError(f"HTTP ошибка: {response.status}")
                text = await response.text()
                return text.strip()
    except aiohttp.ClientError as e:
        raise SMSServiceError(f"Сетевая ошибка при запросе к API: {e}")

async def get_number(self, service: str, country: str = "0") -> Dict[str, str]:
    """
    Получает номер для указанного сервиса и страны.
    :param service: Код сервиса (например 'vk', 'tg').
    :param country: Код страны (по умолчанию '0' - Россия).
    :return: Словарь с id заказа и номером телефона.
    """
    response = await self._request("getNumber", service=service, country=country)
    
    if response.startswith("ACCESS_NUMBER"):
        parts = response.split(":")
        if len(parts) >= 3:
            return {
                "id": parts[1],
                "number": parts[2]
            }
    raise SMSServiceError(f"Не удалось получить номер. Ответ API: {response}")

async def get_status(self, order_id: str) -> Dict[str, Optional[str]]:
    """
    Проверяет статус конкретного заказа.
    :param order_id: ID заказа.
    :return: Словарь со статусом и кодом SMS (если есть).
    """
    response = await self._request("getStatus", id=order_id)
    
    if response == "STATUS_WAIT_CODE":
        return {"status": "WAITING", "sms": None}
    elif response.startswith("STATUS_OK"):
        parts = response.split(":")
        return {"status": "RECEIVED", "sms": parts[1] if len(parts) > 1 else None}
    elif response == "STATUS_CANCEL":
        return {"status": "CANCELLED", "sms": None}
    else:
        raise SMSServiceError(f"Неизвестный статус. Ответ API: {response}")

async def wait_for_sms(self, order_id: str, timeout: int = 120) -> Dict[str, Optional[str]]:
    """
    Ожидает получение SMS (polling) с заданным таймаутом.
    :param order_id: ID заказа.
    :param timeout: Время ожидания в секундах.
    :return: Словарь со статусом 'RECEIVED' и полученным кодом.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        result = await self.get_status(order_id)
        
        if result["status"] == "RECEIVED":
            return result
        elif result["status"] == "CANCELLED":
            raise SMSServiceError("Заказ был отменен во время ожидания SMS.")
        
        await asyncio.sleep(5)  # Пауза между запросами (polling)
        
    raise SMSServiceError(f"Таймаут {timeout}с. истек при ожидании SMS.")

async def cancel_number(self, order_id: str) -> bool:
    """
    Отменяет заказ.
    :param order_id: ID заказа.
    :return: True если успешно, иначе False.
    """
    response = await self._request("setStatus", id=order_id, status="8")
    if response == "ACCESS_CANCEL":
        return True
    return False
if name == "main":
async def main():
# Пример использования (замените 'YOUR_API_KEY_HERE' на реальный ключ)
API_KEY = "YOUR_API_KEY_HERE"
SERVICE_CODE = "tg" # Telegram
COUNTRY_CODE = "0"  # Россия

    sms_service = SMSService(api_key=API_KEY)
    order_id = None
    
    try:
        print("1. Запрашиваем номер...")
        number_info = await sms_service.get_number(service=SERVICE_CODE, country=COUNTRY_CODE)
        order_id = number_info["id"]
        phone = number_info["number"]
        print(f"[+] Номер получен: {phone} (ID: {order_id})")
        
        print(f"2. Ожидаем SMS (до 120 секунд)...")
        sms_data = await sms_service.wait_for_sms(order_id=order_id, timeout=120)
        print(f"[+] SMS успешно получено! Код: {sms_data['sms']}")
        
    except SMSServiceError as e:
        print(f"[-] Ошибка сервиса SMS: {e}")
    except Exception as e:
        print(f"[-] Непредвиденная ошибка: {e}")
    finally:
        if order_id:
            print("3. Завершение работы/Отмена заказа...")
            # При необходимости отменяем или завершаем статус
            # await sms_service.cancel_number(order_id)
            print("[*] Готово.")

# Запуск асинхронного примера
asyncio.run(main())
