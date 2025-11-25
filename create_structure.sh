#!/bin/bash

# Создание структуры папок
mkdir -p app/{data,logs,handlers,keyboards,models,utils}

# Создание файлов в папке app/
cat > app/config.py << 'EOF'
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
EOF

cat > app/main.py << 'EOF'
import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN, ADMIN_ID
from models import Database

# Импорты обработчиков
from handlers.user_handlers import (
    start, 
    handle_main_menu_callbacks, 
    handle_second_block_choice
)
from handlers.admin_handlers import handle_admin_callbacks
from handlers.content_edit_handlers import handle_content_edit_callback
from handlers.message_router import route_message

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/app/logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_handlers(application):
    """Настройка всех обработчиков в правильном порядке"""
    
    # 1. Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # 2. Обработчики callback-запросов
    
    # Главное меню
    application.add_handler(CallbackQueryHandler(
        handle_main_menu_callbacks, 
        pattern="^(main_menu|apply|about|rules|admin_menu)$"
    ))
    
    # Заявки пользователей
    application.add_handler(CallbackQueryHandler(
        handle_second_block_choice, 
        pattern="^(second_block_yes|second_block_no|cancel_application)$"
    ))
    
    # Редактирование контента
    application.add_handler(CallbackQueryHandler(
        handle_content_edit_callback,
        pattern="^(admin_rules|admin_about|cancel_edit)$"
    ))
    
    # Админ-меню (остальные админские callback'ы)
    application.add_handler(CallbackQueryHandler(
        handle_admin_callbacks, 
        pattern="^admin_"
    ))
    
    # 3. ЕДИНЫЙ обработчик сообщений для всех
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        route_message
    ))

def check_environment():
    """Проверка необходимых переменных окружения"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения")
        return False
    
    if not ADMIN_ID:
        logger.error("ADMIN_ID не найден в переменных окружения")
        return False
    
    logger.info(f"Бот настроен для админа: {ADMIN_ID}")
    return True

def create_directories():
    """Создание необходимых директорий"""
    directories = ['/app/data', '/app/logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Директория создана/проверена: {directory}")

def main():
    """Основная функция запуска бота"""
    try:
        # Создание директорий
        create_directories()
        
        # Проверка переменных окружения
        if not check_environment():
            return
        
        # Инициализация базы данных
        db = Database()
        logger.info("База данных инициализирована")
        
        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("Приложение бота создано")
        
        # Настройка обработчиков
        setup_handlers(application)
        logger.info("Обработчики настроены")
        
        # Запуск бота
        logger.info("Бот запускается...")
        application.run_polling(
            poll_interval=1.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()
EOF

# Создание файлов в папке app/models/
cat > app/models/__init__.py << 'EOF'
from .database import Database
EOF

cat > app/models/database.py << 'EOF'
import sqlite3
import datetime
import logging
from config import DB_NAME

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.init_content()
    
    def create_tables(self):
        """Создание всех необходимых таблиц"""
        cursor = self.conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заявок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                poem_text TEXT NOT NULL,
                second_block BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Черный список
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Контент (правила, информация об организаторе)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        logger.info("Таблицы базы данных созданы/проверены")
    
    def init_content(self):
        """Инициализация базового контента"""
        cursor = self.conn.cursor()
        
        default_content = [
            ('rules', '📝 Правила участия в поэтическом вечере:\n\n1. Стихотворение должно быть авторским\n2. Длительность выступления - до 5 минут\n3. Уважительное отношение к другим участникам\n4. Соблюдение регламента мероприятия'),
            ('about_organizer', '🎭 Об организаторе:\n\nМы проводим поэтические вечера уже более 5 лет. Наша цель - создать пространство для творчества и самовыражения поэтов.')
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO content (key, value) 
            VALUES (?, ?)
        ''', default_content)
        
        self.conn.commit()
    
    # Методы для работы с пользователями
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Добавление/обновление пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def get_user(self, user_id: int):
        """Получение информации о пользователе"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    # Методы для работы с черным списком
    def is_user_blacklisted(self, user_id: int) -> bool:
        """Проверка, находится ли пользователь в черном списке"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM blacklist WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def add_to_blacklist(self, user_id: int):
        """Добавление пользователя в черный список"""
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)', (user_id,))
        self.conn.commit()
    
    def remove_from_blacklist(self, user_id: int):
        """Удаление пользователя из черного списка"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def get_blacklist(self):
        """Получение всего черного списка"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM blacklist')
        return [row[0] for row in cursor.fetchall()]
    
    # Методы для работы с контентом
    def get_content(self, key: str):
        """Получение контента по ключу"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM content WHERE key = ?', (key,))
        result = cursor.fetchone()
        
        # Добавляем логирование для отладки
        if result:
            logger.info(f"Найден контент для ключа '{key}': {result[0][:100]}...")
        else:
            logger.warning(f"Контент для ключа '{key}' не найден")
        
        return result[0] if result else None
    
    def update_content(self, key: str, value: str):
        """Обновление контента"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO content (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        self.conn.commit()
    
    # Методы для работы с заявками
    def get_user_application(self, user_id: int):
        """Получение активной заявки пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM applications 
            WHERE user_id = ? AND status IN ('pending', 'approved')
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        return cursor.fetchone()
    
    def create_application(self, user_id: int, poem_text: str, second_block: bool = False):
        """Создание новой заявки"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO applications (user_id, poem_text, second_block, status)
            VALUES (?, ?, ?, 'pending')
        ''', (user_id, poem_text, second_block))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_users(self):
        """Получение всех пользователей для рассылки"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]
    
    def get_pending_applications(self):
        """Получение всех заявок со статусом pending"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.*, u.username, u.first_name, u.last_name 
            FROM applications a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'pending'
            ORDER BY a.created_at ASC
        ''')
        return cursor.fetchall()
    
    def get_application_by_id(self, application_id: int):
        """Получение заявки по ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.*, u.username, u.first_name, u.last_name 
            FROM applications a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.application_id = ?
        ''', (application_id,))
        return cursor.fetchone()
    
    def update_application_status(self, application_id: int, status: str):
        """Обновление статуса заявки"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE applications 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE application_id = ?
        ''', (status, application_id))
        self.conn.commit()

    def get_applications_count(self):
        """Получение количества заявок"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM applications')
        return cursor.fetchone()[0]
    
    def delete_all_applications(self):
        """Удаление всех заявок"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM applications')
        self.conn.commit()
        return cursor.rowcount
    
    def delete_application(self, application_id: int):
        """Удаление заявки"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM applications WHERE application_id = ?', (application_id,))
        self.conn.commit()
    
    def get_approved_applications(self):
        """Получение всех принятых заявок"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.*, u.username, u.first_name, u.last_name 
            FROM applications a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'approved'
            ORDER BY a.created_at ASC
        ''')
        return cursor.fetchall()
    
    def get_second_block_speakers(self):
        """Получение списка выступающих во втором блоке"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT a.*, u.username, u.first_name, u.last_name 
            FROM applications a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'approved' AND a.second_block = TRUE
            ORDER BY a.created_at ASC
        ''')
        return cursor.fetchall()
EOF

# Создание файлов в папке app/handlers/
cat > app/handlers/__init__.py << 'EOF'
from .user_handlers import (
    start, 
    handle_main_menu_callbacks, 
    handle_application_text, 
    handle_second_block_choice
)
from .admin_handlers import (
    handle_admin_callbacks,
    handle_broadcast_message,
    handle_blacklist_message
)
from .content_edit_handlers import (
    handle_content_edit_callback,
    handle_content_text_input
)
from .message_router import route_message
from .state_manager import state_manager

__all__ = [
    'start',
    'handle_main_menu_callbacks',
    'handle_application_text', 
    'handle_second_block_choice',
    'handle_admin_callbacks',
    'handle_broadcast_message',
    'handle_blacklist_message',
    'handle_content_edit_callback',
    'handle_content_text_input',
    'route_message',
    'state_manager'
]
EOF

cat > app/handlers/state_manager.py << 'EOF'
class StateManager:
    def __init__(self):
        self.edit_states = {}
        self.admin_states = {}
    
    def set_edit_state(self, user_id: int, state: str):
        self.edit_states[user_id] = state
    
    def get_edit_state(self, user_id: int) -> str:
        return self.edit_states.get(user_id)
    
    def clear_edit_state(self, user_id: int):
        self.edit_states.pop(user_id, None)
    
    def set_admin_state(self, user_id: int, state: str):
        self.admin_states[user_id] = state
    
    def get_admin_state(self, user_id: int) -> str:
        return self.admin_states.get(user_id)
    
    def clear_admin_state(self, user_id: int):
        self.admin_states.pop(user_id, None)
    
    def clear_all_states(self, user_id: int):
        """Очистить все состояния пользователя"""
        self.clear_edit_state(user_id)
        self.clear_admin_state(user_id)

# Глобальный экземпляр
state_manager = StateManager()
EOF

cat > app/handlers/message_router.py << 'EOF'
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from .state_manager import state_manager
from .user_handlers import handle_application_text
from .content_edit_handlers import handle_content_text_input
from .admin_handlers import handle_broadcast_message, handle_blacklist_message

logger = logging.getLogger(__name__)

async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Центральный маршрутизатор сообщений для админа"""
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"=== МАРШРУТИЗАЦИЯ СООБЩЕНИЯ ===")
    logger.info(f"User ID: {user.id}, ADMIN_ID: {ADMIN_ID}")
    logger.info(f"Текст: {message_text[:100]}...")
    
    # Если пользователь не админ - всегда обрабатываем как заявку
    if user.id != ADMIN_ID:
        logger.info("Пользователь не админ - маршрутизируем в handle_application_text")
        return await handle_application_text(update, context)
    
    # Если админ в режиме подачи заявки
    if context.user_data.get('admin_as_user'):
        logger.info("Админ в режиме пользователя - маршрутизируем в handle_application_text")
        return await handle_application_text(update, context)
    
    # Проверяем состояния редактирования
    edit_state = state_manager.get_edit_state(user.id)
    admin_state = state_manager.get_admin_state(user.id)
    
    logger.info(f"Состояние редактирования: {edit_state}")
    logger.info(f"Состояние админа: {admin_state}")
    
    # Приоритет 1: Редактирование контента
    if edit_state in ['editing_rules', 'editing_about']:
        logger.info(f"Маршрутизируем в handle_content_text_input (состояние: {edit_state})")
        return await handle_content_text_input(update, context)
    
    # Приоритет 2: Рассылка
    if admin_state == 'awaiting_broadcast':
        logger.info("Маршрутизируем в handle_broadcast_message")
        return await handle_broadcast_message(update, context)
    
    # Приоритет 3: Черный список
    if admin_state in ['awaiting_blacklist_add', 'awaiting_blacklist_remove']:
        logger.info("Маршрутизируем в handle_blacklist_message")
        return await handle_blacklist_message(update, context)
    
    # Если нет активных состояний - игнорируем сообщение
    logger.info("Админское сообщение без активного состояния - игнорируем")
    await update.message.reply_text(
        "ℹ️ Используйте меню для взаимодействия с ботом.",
        reply_markup=await get_admin_main_menu()
    )

async def get_admin_main_menu():
    """Получение главного меню для админа"""
    from keyboards.admin_keyboards import get_admin_menu
    from keyboards.user_keyboards import get_main_menu
    return get_admin_menu()
EOF

# Продолжение для остальных файлов handlers...
cat > app/handlers/user_handlers.py << 'EOF'
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from models import Database
from keyboards.user_keyboards import get_main_menu, get_back_to_menu, get_second_block_keyboard
from keyboards.admin_keyboards import get_admin_menu
from config import ADMIN_ID

logger = logging.getLogger(__name__)
db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверка черного списка
    if db.is_user_blacklisted(user.id) and user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ к боту ограничен.")
        return
    
    # Добавляем/обновляем пользователя в базе
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        f"Добро пожаловать в бот для подачи заявок на поэтические вечера!",
        reply_markup=get_main_menu(user.id)
    )

async def handle_main_menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов главного меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка черного списка (кроме админа)
    if db.is_user_blacklisted(user_id) and user_id != ADMIN_ID:
        await query.edit_message_text("⛔ Доступ к боту ограничен.")
        return
    
    callback_data = query.data
    
    if callback_data == "main_menu":
        await show_main_menu(query, user_id)
    
    elif callback_data == "apply":
        await start_application(query, context)
    
    elif callback_data == "about":
        await show_about(query)
    
    elif callback_data == "rules":
        await show_rules(query)
    
    elif callback_data == "admin_menu":
        await show_admin_menu(query)

async def show_main_menu(query, user_id):
    """Показать главное меню"""
    await query.edit_message_text(
        "🎭 Главное меню поэтического вечера:",
        reply_markup=get_main_menu(user_id)
    )

async def start_application(query, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса подачи заявки"""
    user_id = query.from_user.id
    
    logger.info(f"=== НАЧАЛО ПОДАЧИ ЗАЯВКИ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id} ===")
    logger.info(f"Админ подает заявку: {user_id == ADMIN_ID}")
    
    # Проверяем, есть ли активная заявка
    existing_application = db.get_user_application(user_id)
    if existing_application:
        status_text = "принята" if existing_application['status'] == 'approved' else "на рассмотрении"
        await query.edit_message_text(
            f"⚠️ У вас уже есть активная заявка (статус: {status_text}).",
            reply_markup=get_back_to_menu()
        )
        return
    
    # Очищаем предыдущие состояния
    context.user_data.clear()
    
    # Устанавливаем состояние для ожидания текста стихотворения
    context.user_data['awaiting_poem'] = True
    context.user_data['application_started'] = True
    
    # ДЛЯ АДМИНА: устанавливаем флаг, что он действует как пользователь
    if user_id == ADMIN_ID:
        context.user_data['admin_as_user'] = True
        logger.info(f"Админ {user_id} переключен в режим пользователя для подачи заявки")
    
    logger.info(f"Установлен awaiting_poem для пользователя {user_id}")
    
    await query.edit_message_text(
        "📝 Подача заявки на поэтический вечер:\n\n"
        "Пожалуйста, введите текст вашего стихотворения:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="cancel_application")]])
    )

async def show_about(query):
    """Показать информацию об организаторе"""
    about_text = db.get_content('about_organizer')
    await query.edit_message_text(about_text, reply_markup=get_back_to_menu())

async def show_rules(query):
    """Показать правила"""
    rules_text = db.get_content('rules')
    await query.edit_message_text(rules_text, reply_markup=get_back_to_menu())

async def show_admin_menu(query):
    """Показать меню администратора"""
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ У вас нет прав доступа.", reply_markup=get_back_to_menu())
        return
    await query.edit_message_text("⚙️ Меню организатора:", reply_markup=get_admin_menu())

async def handle_application_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста стихотворения (только для заявок)"""
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"=== ОБРАБОТКА ТЕКСТА ЗАЯВКИ ===")
    logger.info(f"User ID: {user.id}")
    logger.info(f"awaiting_poem: {context.user_data.get('awaiting_poem')}")
    logger.info(f"admin_as_user: {context.user_data.get('admin_as_user')}")
    
    # Проверка черного списка (кроме админа)
    if db.is_user_blacklisted(user.id) and user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ к боту ограничен.")
        return
    
    # Обработка текста стихотворения ТОЛЬКО если пользователь в состоянии подачи заявки
    if context.user_data.get('awaiting_poem') and context.user_data.get('application_started'):
        logger.info(f"Обрабатываем стих для пользователя {user.id}")
        
        # Сохраняем текст стихотворения
        context.user_data['poem_text'] = message_text
        context.user_data['awaiting_poem'] = False
        
        await update.message.reply_text(
            "✅ Стихотворение получено!\n\n"
            "Хотите ли вы также выступить во втором блоке вечера?",
            reply_markup=get_second_block_keyboard()
        )
    else:
        logger.info(f"Пользователь {user.id} не в состоянии подачи заявки - игнорируем текст")
        # Не отправляем сообщение, чтобы не спамить

async def handle_second_block_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора участия во втором блоке"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    # Обработка отмены заявки
    if choice == "cancel_application":
        # ДЛЯ АДМИНА: снимаем флаг режима пользователя
        if user_id == ADMIN_ID:
            context.user_data.pop('admin_as_user', None)
            logger.info(f"Админ {user_id} вышел из режима пользователя (отмена заявки)")
        
        context.user_data.clear()
        await query.edit_message_text("❌ Подача заявки отменена.", reply_markup=get_main_menu(user_id))
        return
    
    if choice == "second_block_yes":
        second_block = True
        choice_text = "с участием во втором блоке"
    else:
        second_block = False
        choice_text = "без участия во втором блоке"
    
    # Создаем заявку только если есть текст стихотворения
    poem_text = context.user_data.get('poem_text')
    if poem_text:
        application_id = db.create_application(user_id, poem_text, second_block)
        
        # ДЛЯ АДМИНА: снимаем флаг режима пользователя после успешной подачи
        if user_id == ADMIN_ID:
            context.user_data.pop('admin_as_user', None)
            logger.info(f"Админ {user_id} вышел из режима пользователя (заявка подана)")
        
        # Очищаем временные данные
        context.user_data.clear()
        
        await query.edit_message_text(
            f"✅ Ваша заявка {choice_text} принята на рассмотрение!\n\n"
            f"Мы свяжемся с вами когда проверим ваше стихотворение.",
            reply_markup=get_back_to_menu()
        )
        
        # Уведомление администратору о новой заявке (кроме случая когда заявку подает сам админ)
        if user_id != ADMIN_ID:
            user = query.from_user
            admin_message = (
                f"📨 Новая заявка! (ID: {application_id})\n\n"
                f"👤 Имя: {user.first_name} {user.last_name or ''}\n"
                f"📛 Username: @{user.username or 'нет'}\n"
                f"🆔 ID: {user.id}\n"
                f"🎭 Второй блок: {'✅ Да' if second_block else '❌ Нет'}\n\n"
                f"📝 Стихотворение:\n{poem_text[:500]}{'...' if len(poem_text) > 500 else ''}"
            )
            
            # Отправляем уведомление администратору
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📨 Перейти к заявкам", callback_data="admin_pending_applications")]
                ])
                
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору: {e}")
        else:
            logger.info(f"Админ {user_id} подал заявку самостоятельно, уведомление не отправляется")
    else:
        # ДЛЯ АДМИНА: снимаем флаг режима пользователя при ошибке
        if user_id == ADMIN_ID:
            context.user_data.pop('admin_as_user', None)
            logger.info(f"Админ {user_id} вышел из режима пользователя (ошибка заявки)")
        
        context.user_data.clear()
        await query.edit_message_text("❌ Ошибка при обработке заявки.", reply_markup=get_main_menu(user_id))
EOF

# Создание файлов в папке app/keyboards/
cat > app/keyboards/__init__.py << 'EOF'
from .user_keyboards import get_main_menu, get_back_to_menu, get_second_block_keyboard
from .admin_keyboards import get_admin_menu, get_blacklist_menu, get_application_moderation_keyboard
EOF

cat > app/keyboards/user_keyboards.py << 'EOF'
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID

def get_main_menu(user_id: int):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📝 Подать заявку на вечер", callback_data="apply")],
        [InlineKeyboardButton("🎭 Об организаторе", callback_data="about")],
        [InlineKeyboardButton("📋 Правила", callback_data="rules")]
    ]
    
    # Добавляем меню организатора только для админа
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Меню Организатора", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu():
    """Кнопка возврата в меню"""
    keyboard = [
        [InlineKeyboardButton("🔙 Вернуться в меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_second_block_keyboard():
    """Клавиатура для выбора участия во втором блоке"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="second_block_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="second_block_no")
        ],
        [InlineKeyboardButton("🔙 Отмена", callback_data="cancel_application")]
    ]
    return InlineKeyboardMarkup(keyboard)
EOF

cat > app/keyboards/admin_keyboards.py << 'EOF'
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_admin_menu():
    """Меню администратора"""
    keyboard = [
        [InlineKeyboardButton("📨 Заявки в первый блок", callback_data="admin_pending_applications")],
        [InlineKeyboardButton("📄 Стихи первого блока", callback_data="admin_approved_poems")],
        [InlineKeyboardButton("👥 Список второго блока", callback_data="admin_second_block")],
        [InlineKeyboardButton("🗑️ Удалить все заявки", callback_data="admin_delete_all")],
        [InlineKeyboardButton("📋 Правила", callback_data="admin_rules")],
        [InlineKeyboardButton("🎭 Об организаторе", callback_data="admin_about")],
        [InlineKeyboardButton("🚫 Черный список", callback_data="admin_blacklist")],
        [InlineKeyboardButton("📢 Сделать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_blacklist_menu():
    """Меню управления черным списком"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить в ЧС", callback_data="blacklist_add")],
        [InlineKeyboardButton("➖ Удалить из ЧС", callback_data="blacklist_remove")],
        [InlineKeyboardButton("👁️ Просмотр ЧС", callback_data="blacklist_view")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_application_moderation_keyboard(application_id: int, current_index: int, total_count: int):
    """Клавиатура для модерации заявки"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"approve_{application_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{application_id}")
        ]
    ]
    
    # Кнопки навигации
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"nav_{current_index-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"{current_index+1}/{total_count}", callback_data="count"))
    
    if current_index < total_count - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"nav_{current_index+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(action: str):
    """Клавиатура подтверждения для опасных действий"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить все", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
EOF

# Создание файлов в папке app/utils/
cat > app/utils/__init__.py << 'EOF'
from .broadcast import send_broadcast, get_broadcast_recipients_count, get_broadcast_recipients_preview
from .file_export import export_approved_poems_to_file, export_second_block_speakers_to_file
from .log_cleaner import cleanup_old_logs
EOF

cat > app/utils/broadcast.py << 'EOF'
import logging
import asyncio
from telegram.error import TelegramError
from models import Database

logger = logging.getLogger(__name__)
db = Database()

async def send_broadcast(context, broadcast_text: str) -> dict:
    """
    Отправка рассылки всем пользователям кроме черного списка
    Возвращает статистику: {'success': int, 'failed': int, 'total': int}
    """
    all_users = db.get_all_users()
    blacklist = db.get_blacklist()
    
    # Исключаем черный список
    users_to_send = [user_id for user_id in all_users if user_id not in blacklist]
    
    success = 0
    failed = 0
    
    logger.info(f"Начинаем рассылку для {len(users_to_send)} пользователей")
    
    for user_id in users_to_send:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_text
            )
            success += 1
            
            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.1)
            
        except TelegramError as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"Ошибка при рассылке пользователю {user_id}: {e}")
            failed += 1
    
    return {
        'success': success,
        'failed': failed,
        'total': len(users_to_send)
    }

def get_broadcast_recipients_count():
    """Получение количества получателей рассылки"""
    all_users = db.get_all_users()
    blacklist = db.get_blacklist()
    users_to_send = [user_id for user_id in all_users if user_id not in blacklist]
    return len(users_to_send)

def get_broadcast_recipients_preview(limit: int = 10):
    """Получение предпросмотра списка получателей"""
    all_users = db.get_all_users()
    blacklist = db.get_blacklist()
    users_to_send = [user_id for user_id in all_users if user_id not in blacklist]
    
    # Получаем информацию о пользователях для предпросмотра
    cursor = db.conn.cursor()
    preview_users = []
    
    for user_id in users_to_send[:limit]:
        cursor.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            name = f"{user_data[0]} {user_data[1] or ''}".strip()
            username = f"@{user_data[2]}" if user_data[2] else "без username"
            preview_users.append(f"• {name} ({username}) - ID: {user_id}")
    
    total_count = len(users_to_send)
    preview_text = "\n".join(preview_users)
    
    if total_count > limit:
        preview_text += f"\n... и еще {total_count - limit} пользователей"
    
    return {
        'preview': preview_text,
        'total_count': total_count
    }
EOF

cat > app/utils/file_export.py << 'EOF'
import io
import logging
from models import Database

logger = logging.getLogger(__name__)
db = Database()

def export_approved_poems_to_file():
    """Экспорт принятых стихотворений в файл"""
    approved_applications = db.get_approved_applications()
    
    if not approved_applications:
        return None
    
    # Формируем текстовый файл
    file_content = "Стихи первого блока:\n\n"
    
    for i, app in enumerate(approved_applications, 1):
        file_content += f"{i}. {app['first_name']} {app['last_name'] or ''} (@{app['username'] or 'нет'})\n"
        file_content += f"ID заявки: {app['application_id']}\n"
        file_content += f"Участие во втором блоке: {'Да' if app['second_block'] else 'Нет'}\n"
        file_content += f"Стих:\n{app['poem_text']}\n"
        file_content += "=" * 50 + "\n\n"
    
    # Создаем файл в памяти
    file = io.BytesIO(file_content.encode('utf-8'))
    file.name = "стихи_первого_блока.txt"
    
    return file

def export_second_block_speakers_to_file():
    """Экспорт списка выступающих второго блока в файл"""
    second_block_speakers = db.get_second_block_speakers()
    
    if not second_block_speakers:
        return None
    
    # Формируем текстовый файл
    file_content = "Список выступающих второго блока:\n\n"
    
    for i, speaker in enumerate(second_block_speakers, 1):
        file_content += f"{i}. {speaker['first_name']} {speaker['last_name'] or ''} (@{speaker['username'] or 'нет'})\n"
        file_content += f"ID заявки: {speaker['application_id']}\n"
        file_content += f"Стих: {speaker['poem_text'][:100]}{'...' if len(speaker['poem_text']) > 100 else ''}\n"
        file_content += "-" * 30 + "\n"
    
    # Создаем файл в памяти
    file = io.BytesIO(file_content.encode('utf-8'))
    file.name = "список_второго_блока.txt"
    
    return file
EOF

cat > app/utils/log_cleaner.py << 'EOF'
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
EOF

# Создание .env файла
cat > app/.env.example << 'EOF'
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_admin_id_here
DB_NAME=/app/data/poetry_bot.db
LOG_LEVEL=INFO
LOG_FILE=/app/logs/bot.log
LOG_ROTATION_DAYS=7
EOF

# Создание requirements.txt
cat > app/requirements.txt << 'EOF'
python-telegram-bot==20.7
python-dotenv==1.0.0
EOF

# Создание README.md
cat > app/README.md << 'EOF'
# Poetry Bot

Бот для подачи заявок на поэтические вечера.

## Установка

1. Скопируйте `.env.example` в `.env` и настройте переменные окружения
2. Установите зависимости: `pip install -r requirements.txt`
3. Запустите бота: `python main.py`

## Структура проекта

- `main.py` - основной файл запуска бота
- `config.py` - конфигурация приложения
- `models/` - модели базы данных
- `handlers/` - обработчики сообщений
- `keyboards/` - клавиатуры бота
- `utils/` - вспомогательные утилиты
EOF

echo "Структура проекта создана в папке app/"
echo "Не забудьте:"
echo "1. Настроить .env файл"
echo "2. Установить зависимости: pip install -r app/requirements.txt"
echo "3. Запустить бота: cd app && python main.py"