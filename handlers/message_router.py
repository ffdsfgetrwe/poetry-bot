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

async def handle_admin_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений для администратора"""
    user = update.effective_user
    
    # Проверяем, является ли пользователь администратором
    if user.id != ADMIN_ID:
        return
    
    # Обработка сообщений для черного списка и рассылки
    await handle_broadcast_message(update, context)
    await handle_blacklist_message(update, context)