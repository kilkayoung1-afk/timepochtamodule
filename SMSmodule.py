import asyncio
import aiohttp
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

Настройка логирования для "системного" вида
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s [SYSTEM_CORE] %(levelname)s: %(message)s'
)
logger = logging.getLogger("VirtualNumberManager")

class VirtualNumberError(Exception):
"""Базовое исключение модуля управления номерами."""
pass

class NoNumbersAvailable(VirtualNumberError):
"""Исключение при отсутствии доступных номеров в пуле."""
pass

class SMSWaitTimeout(VirtualNumberError):
"""Исключение при превышении времени ожидания сообщения."""
pass

class APIError(VirtualNumberError):
"""Ошибка взаимодействия с внешним шлюзом."""
pass

class VirtualNumberManager:
"""
Класс управления виртуальными линиями связи.
Реализует абстракцию над API SMS-Activate для создания эффекта
внутренней генерации номеров.
"""

def __init__(self, api_key: str, country_id: int = 0):
    self.__api_key = api_key
    self.__base_url = "[https://sms-activate.org/stubs/handler_api.php](https://sms-activate.org/stubs/handler_api.php)"
    self.__country_id = country_id
    self._active_orders: Dict[str, Dict[str, Any]] = {}
    self._session: Optional[aiohttp.ClientSession] = None
    self._is_running = True
    
    # Фоновая очистка старых записей
    self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop())

async def __get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        self._session = aiohttp.ClientSession()
    return self._session

async def _request(self, params: Dict[str, Any], retries: int = 3) -> str:
    """Приватный метод для выполнения запросов к шлюзу."""
    params["api_key"] = self.__api_key
    session = await self.__get_session()
    
    for attempt in range(retries):
        try:
            async with session.get(self.__base_url, params=params, timeout=15) as response:
                text = await response.text()
                if "BAD_KEY" in text:
                    raise APIError("Неверный API ключ системы.")
                if "ERROR" in text or "BAD_ACTION" in text:
                    raise APIError(f"Ошибка шлюза: {text}")
                return text
        except Exception as e:
            if attempt == retries - 1:
                raise APIError(f"Не удалось связаться с подсистемой: {e}")
            await asyncio.sleep(2)
    return ""

async def get_virtual_number(self, service: str) -> dict:
    """
    Инициализирует выделение новой виртуальной линии.
    """
    logger.info(f"Запрос на генерацию новой линии для сервиса: {service}...")
    
    params = {
        "action": "getNumber",
        "service": service,
        "country": self.__country_id
    }

    result = await self._request(params)

    if "NO_NUMBERS" in result:
        raise NoNumbersAvailable(f"В данный момент нет свободных ресурсов для '{service}'.")
    
    if "ACCESS_NUMBER" in result:
        # Формат: ACCESS_NUMBER:ID:NUMBER
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
        
        logger.info(f"Линия {order_id} успешно инициализирована: {phone_number}")
        
        return {
            "status": "success",
            "internal_id": order_id,
            "virtual_number": f"+{phone_number}",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    raise APIError(f"Непредвиденный ответ системы: {result}")

async def wait_for_sms(self, order_id: str, timeout: int = 300) -> dict:
    """
    Переводит систему в режим прослушивания входящих сигналов на линии.
    """
    if order_id not in self._active_orders:
        raise VirtualNumberError("Указанный ID линии не найден в активном пуле.")

    logger.info(f"Ожидание входящего SMS на линии {order_id} (таймаут {timeout}с)...")
    
    start_time = time.time()
    params = {
        "action": "getStatus",
        "id": order_id
    }

    while time.time() - start_time < timeout:
        result = await self._request(params)

        if "STATUS_OK" in result:
            code = result.split(":")[1]
            logger.info(f"Сигнал получен на линии {order_id}. Код: {code}")
            
            # Обновляем кэш
            self._active_orders[order_id]["status"] = "RECEIVED"
            self._active_orders[order_id]["code"] = code
            
            return {
                "order_id": order_id,
                "code": code,
                "raw_response": result,
                "received_at": datetime.utcnow().isoformat()
            }

        if "STATUS_WAIT_CODE" not in result:
            raise APIError(f"Линия была прервана удаленной стороной: {result}")

        await asyncio.sleep(5)

    raise SMSWaitTimeout(f"Время ожидания сообщения на линии {order_id} истекло.")

async def release_number(self, order_id: str):
    """
    Освобождает виртуальную линию и деактивирует её в системе.
    """
    logger.info(f"Деактивация линии {order_id}...")
    
    params = {
        "action": "setStatus",
        "status": 8,  # Отмена/закрытие в терминах API
        "id": order_id
    }

    try:
        await self._request(params)
        if order_id in self._active_orders:
            del self._active_orders[order_id]
        logger.info(f"Линия {order_id} успешно закрыта.")
    except Exception as e:
        logger.error(f"Ошибка при закрытии линии {order_id}: {e}")

async def _auto_cleanup_loop(self):
    """Внутренний цикл для очистки памяти от устаревших данных."""
    while self._is_running:
        try:
            now = time.time()
            to_delete = []
            for oid, data in self._active_orders.items():
                # Очистка через 20 минут активности или если статус не актуален
                if now - data["created_at"] > 1200:
                    to_delete.append(oid)
            
            for oid in to_delete:
                self._active_orders.pop(oid, None)
                
        except Exception as e:
            logger.error(f"Ошибка в цикле очистки: {e}")
        
        await asyncio.sleep(60)

async def close(self):
    """Полная остановка менеджера."""
    self._is_running = False
    if self._session:
        await self._session.close()
    self._cleanup_task.cancel()
--- ПРИМЕР ИСПОЛЬЗОВАНИЯ ---
async def main():
# Замените на ваш реальный API ключ
API_KEY = "YOUR_API_KEY_HERE"

manager = VirtualNumberManager(api_key=API_KEY)

try:
    # 1. "Генерируем" номер для Telegram
    number_info = await manager.get_virtual_number(service="tg")
    print(f"\n[!] Сгенерирован номер: {number_info['virtual_number']}")
    print(f"[!] ID транзакции: {number_info['internal_id']}")

    # 2. Ожидаем SMS (в реальности здесь нужно нажать 'отправить код' в приложении)
    print("\n[*] Система перешла в режим ожидания SMS...")
    # sms_data = await manager.wait_for_sms(number_info['internal_id'], timeout=60)
    # print(f"[!] Получен код: {sms_data['code']}")

except NoNumbersAvailable:
    print("Ошибка: Нет доступных номеров.")
except SMSWaitTimeout:
    print("Ошибка: Код не пришел вовремя.")
except Exception as e:
    print(f"Произошла ошибка: {e}")
finally:
    # В реальном коде номер стоит закрывать после использования или таймаута
    # await manager.release_number(number_info['internal_id'])
    await manager.close()
if name == "main":
try:
asyncio.run(main())
except KeyboardInterrupt:
pass
