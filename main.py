# ./main.py
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
    
    # Главное меню пользователя
    application.add_handler(CallbackQueryHandler(
        handle_main_menu_callbacks, 
        pattern="^(main_menu|apply|about|rules|admin_menu)$"
    ))
    
    # Заявки пользователей (второй блок и отмена)
    application.add_handler(CallbackQueryHandler(
        handle_second_block_choice, 
        pattern="^(second_block_yes|second_block_no|cancel_application)$"
    ))
    
    # Админ-меню (основные функции)
    application.add_handler(CallbackQueryHandler(
        handle_admin_callbacks, 
        pattern="^admin_"
    ))
    
    # И ДОБАВЬТЕ обработчик для кнопок принятия/отклонения:
    application.add_handler(CallbackQueryHandler(
        handle_admin_callbacks,
        pattern="^(approve_|reject_|nav_)"
    ))


    # Черный список
    application.add_handler(CallbackQueryHandler(
        handle_admin_callbacks,
        pattern="^(blacklist_add|blacklist_remove|blacklist_view)$"
    ))
    
    # Навигация по заявкам и модерация
    application.add_handler(CallbackQueryHandler(
        handle_admin_callbacks,
        pattern="^(nav_|approve_|reject_|confirm_delete_all)$"
    ))
    
    # Редактирование контента
    application.add_handler(CallbackQueryHandler(
        handle_content_edit_callback,
        pattern="^(admin_rules|admin_about|cancel_edit)$"
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