import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from models import Database
from keyboards.admin_keyboards import get_admin_menu
from config import ADMIN_ID
from .state_manager import state_manager

logger = logging.getLogger(__name__)
db = Database()

async def handle_content_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик для редактуры контента"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ У вас нет прав доступа.")
        return
    
    callback_data = query.data
    logger.info(f"Редактирование контента: {callback_data}")
    
    if callback_data == "admin_rules":
        await start_rules_editing(query)
    elif callback_data == "admin_about":
        await start_about_editing(query)
    elif callback_data == "cancel_edit":
        await cancel_editing(query)

async def start_rules_editing(query):
    """Начало редактирования правил"""
    current_rules = db.get_content('rules')
    
    await query.edit_message_text(
        f"📝 <b>Редактирование правил:</b>\n\n"
        f"<i>Текущие правила:</i>\n{current_rules}\n\n"
        "✏️ <b>Отправьте новый текст правил:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")]
        ])
    )
    
    state_manager.set_edit_state(query.from_user.id, 'editing_rules')
    logger.info(f"Админ {query.from_user.id} начал редактирование правил")

async def start_about_editing(query):
    """Начало редактирования информации об организаторе"""
    current_about = db.get_content('about_organizer')
    
    await query.edit_message_text(
        f"🎭 <b>Редактирование информации об организаторе:</b>\n\n"
        f"<i>Текущая информация:</i>\n{current_about}\n\n"
        "✏️ <b>Отправьте новый текст:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")]
        ])
    )
    
    state_manager.set_edit_state(query.from_user.id, 'editing_about')
    logger.info(f"Админ {query.from_user.id} начал редактирование информации об организаторе")

async def cancel_editing(query):
    """Отмена редактирования"""
    user_id = query.from_user.id
    state_manager.clear_edit_state(user_id)
    
    await query.edit_message_text(
        "❌ Редактирование отменено.",
        reply_markup=get_admin_menu()
    )

# Функция для обработки сообщений (будет вызываться из message_router.py)
async def handle_content_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового ввода для редактирования контента (вызывается из message_router)"""
    user = update.effective_user
    message_text = update.message.text
    
    if user.id != ADMIN_ID:
        return
    
    current_edit_state = state_manager.get_edit_state(user.id)
    
    if not current_edit_state:
        # Если нет активного состояния редактирования, пропускаем
        return
    
    try:
        if current_edit_state == 'editing_rules':
            success = await save_rules(user.id, message_text, context)
            if success:
                await update.message.reply_text(
                    "✅ <b>Правила успешно обновлены!</b>", 
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ <b>Ошибка при сохранении правил.</b>",
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
                
        elif current_edit_state == 'editing_about':
            success = await save_about(user.id, message_text, context)
            if success:
                await update.message.reply_text(
                    "✅ <b>Информация об организаторе успешно обновлена!</b>", 
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ <b>Ошибка при сохранении информации.</b>",
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
                
    except Exception as e:
        logger.error(f"Ошибка при сохранении контента: {e}")
        state_manager.clear_edit_state(user.id)
        await update.message.reply_text(
            f"❌ <b>Произошла ошибка:</b> {e}",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )

async def save_rules(user_id: int, new_rules: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Сохранение новых правил"""
    try:
        db.update_content('rules', new_rules)
        state_manager.clear_edit_state(user_id)
        
        # Проверяем сохранение
        updated_rules = db.get_content('rules')
        success = updated_rules == new_rules
        
        if success:
            logger.info(f"Админ {user_id} успешно обновил правила")
        else:
            logger.error(f"Ошибка: правила не сохранились для админа {user_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении правил: {e}")
        state_manager.clear_edit_state(user_id)
        return False

async def save_about(user_id: int, new_about: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Сохранение новой информации об организаторе"""
    try:
        db.update_content('about_organizer', new_about)
        state_manager.clear_edit_state(user_id)
        
        # Проверяем сохранение
        updated_about = db.get_content('about_organizer')
        success = updated_about == new_about
        
        if success:
            logger.info(f"Админ {user_id} успешно обновил информацию об организаторе")
        else:
            logger.error(f"Ошибка: информация об организаторе не сохранилась для админа {user_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении информации об организаторе: {e}")
        state_manager.clear_edit_state(user_id)
        return False