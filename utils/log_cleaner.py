import os
import logging
import time
from datetime import datetime, timedelta
from config import LOG_FILE, LOG_ROTATION_DAYS

logger = logging.getLogger(__name__)

def cleanup_old_logs():
    """Очистка старых логов"""
    try:
        if not os.path.exists(LOG_FILE):
            return
        
        # Получаем время модификации файла
        file_mtime = os.path.getmtime(LOG_FILE)
        file_age_days = (time.time() - file_mtime) / (60 * 60 * 24)
        
        if file_age_days >= LOG_ROTATION_DAYS:
            # Создаем backup старого файла
            backup_name = f"{LOG_FILE}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            os.rename(LOG_FILE, backup_name)
            
            logger.info(f"Лог-файл очищен. Старый файл сохранен как: {backup_name}")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке логов: {e}")

# Альтернативная версия если функция не используется
def cleanup_old_logs_safe():
    """Безопасная версия очистки логов (если не критично)"""
    try:
        # Просто логируем что функция вызвана
        logger.info("Функция очистки логов вызвана")
    except Exception as e:
        logger.error(f"Ошибка в cleanup_old_logs: {e}")
