import os
from dotenv import load_dotenv

load_dotenv()

# Безопасное получение переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не найден в переменных окружения")

# Настройки базы данных
DB_NAME = os.getenv('DB_NAME', '/app/data/poetry_bot.db')

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.getenv('LOG_FILE', '/app/logs/bot.log')
LOG_ROTATION_DAYS = int(os.getenv('LOG_ROTATION_DAYS', '7'))

# Создание директорий если не существуют
os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
