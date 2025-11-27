import os
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def cleanup_old_logs(
    log_dir: str = "logs",
    retention_days: int = 7,
    file_pattern: str = "*.log"
):
    """Удаляет старые логи с настраиваемыми параметрами"""
    try:
        directory = Path(log_dir)
        
        if not directory.exists():
            logger.warning(f"Директория логов не существует: {directory}")
            return
        
        current_time = time.time()
        retention_seconds = retention_days * 24 * 60 * 60
        deleted_count = 0
        
        for file_path in directory.glob(file_pattern):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                
                if file_age > retention_seconds:
                    delete_log_file(file_path)
                    deleted_count += 1
        
        logger.info(f"Удалено файлов: {deleted_count} (паттерн: {file_pattern})")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке логов: {e}")

def delete_log_file(file_path: Path):
    """Безопасно удаляет лог-файл"""
    try:
        file_age_days = (time.time() - file_path.stat().st_mtime) / (60 * 60 * 24)
        file_path.unlink()
        logger.info(f"Удален: {file_path.name} (возраст: {file_age_days:.1f} дней)")
    except Exception as e:
        logger.error(f"Ошибка удаления {file_path}: {e}")