import logging
import time
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from models import Database
from keyboards.admin_keyboards import (
    get_admin_menu, 
    get_blacklist_menu, 
    get_application_moderation_keyboard, 
    get_confirmation_keyboard
)
from config import ADMIN_ID
from utils.broadcast import send_broadcast, get_broadcast_recipients_count, get_broadcast_recipients_preview
from utils.file_export import export_approved_poems_to_file, export_second_block_speakers_to_file
from .state_manager import state_manager  # оставляем старый state_manager для совместимости

logger = logging.getLogger(__name__)
db = Database()

class AdminConfig:
    """Конфигурация админ-панели"""
    MAX_APPLICATIONS_PER_PAGE = 10
    BROADCAST_CHUNK_SIZE = 30
    STATE_TIMEOUT = 300  # 5 минут
    MAX_BLACKLIST_DISPLAY = 50

class AdminStateManager:
    """Менеджер состояний администратора"""
    
    def __init__(self):
        self._states = {}
    
    def set_state(self, user_id: int, state: str, data: Optional[Dict] = None):
        """Установить состояние с временной меткой"""
        self._states[user_id] = {
            'state': state,
            'data': data or {},
            'timestamp': time.time()
        }
    
    def get_state(self, user_id: int) -> Optional[Dict]:
        """Получить состояние с проверкой таймаута"""
        if user_id not in self._states:
            return None
            
        state_data = self._states[user_id]
        if time.time() - state_data['timestamp'] > AdminConfig.STATE_TIMEOUT:
            del self._states[user_id]
            return None
            
        return state_data
    
    def clear_state(self, user_id: int):
        """Очистить состояние"""
        if user_id in self._states:
            del self._states[user_id]
    
    def cleanup_expired(self):
        """Очистить просроченные состояния"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, state_data in self._states.items()
            if current_time - state_data['timestamp'] > AdminConfig.STATE_TIMEOUT
        ]
        for user_id in expired_users:
            del self._states[user_id]

# Инициализация менеджера состояний
admin_state_manager = AdminStateManager()

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик callback-запросов админ-меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not await _validate_admin_access(user_id, query):
        return
    
    callback_data = query.data
    logger.info(f"Админ callback: {callback_data}")

    # Обработка навигации по заявкам
    if callback_data.startswith("nav_"):
        index = int(callback_data.split("_")[1])
        await navigate_applications(query, index, context)
    
    # Обработка пагинации черного списка
    elif callback_data.startswith("blacklist_page_"):
        page = int(callback_data.split("_")[2])
        await show_blacklist_details(query, page)
    
    # Обработка принятия/отклонения заявок
    elif callback_data.startswith("approve_"):
        application_id = int(callback_data.split("_")[1])
        await handle_application_action(query, application_id, 'approve', context)
    
    elif callback_data.startswith("reject_"):
        application_id = int(callback_data.split("_")[1])
        await handle_application_action(query, application_id, 'reject', context)
    
    # Обработка подтверждения удаления
    elif callback_data == "confirm_delete_all":
        await delete_all_applications(query, context)
    
    elif callback_data == "cancel_delete_all":
        await show_admin_menu(query)
    
    # Основное админ-меню
    elif callback_data == "admin_menu":
        await show_admin_menu(query)
    
    elif callback_data == "admin_pending_applications":
        await show_pending_applications(query, context)
    
    elif callback_data == "admin_approved_poems":
        await export_approved_poems(query, context)
    
    elif callback_data == "admin_second_block":
        await export_second_block_speakers(query, context)
    
    elif callback_data == "admin_delete_all":
        await confirm_delete_all_applications(query)
    
    elif callback_data == "admin_blacklist":
        await show_blacklist_menu(query)
    
    elif callback_data == "admin_broadcast":
        await handle_admin_broadcast_callback(query)
    
    # Черный список
    elif callback_data in ["blacklist_add", "blacklist_remove", "blacklist_view"]:
        await handle_blacklist_actions(query, callback_data, context)
    
    # Редактирование контента
    elif callback_data in ["admin_rules", "admin_about"]:
        from handlers.content_edit_handlers import handle_content_edit_callback
        await handle_content_edit_callback(update, context)
    
    # Пустой callback (для кнопок-заглушек)
    elif callback_data == "noop":
        await query.answer()
    
    else:
        logger.warning(f"Неизвестный callback: {callback_data}")
        await query.answer("❌ Неизвестная команда")

async def _validate_admin_access(user_id: int, query) -> bool:
    """Проверка прав доступа администратора"""
    if user_id != ADMIN_ID:
        await safe_edit_message_text(
            query, 
            "⛔ У вас нет прав доступа.",
            reply_markup=get_admin_menu()
        )
        return False
    return True

async def safe_edit_message_text(query, text: str, **kwargs):
    """Безопасное редактирование сообщения с обработкой исключений"""
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        # Пытаемся отправить новое сообщение
        try:
            await query.message.reply_text(text, **kwargs)
        except Exception as e2:
            logger.error(f"Не удалось отправить сообщение: {e2}")

async def show_admin_menu(query):
    """Показать меню администратора"""
    await safe_edit_message_text(
        query,
        "⚙️ <b>Меню организатора:</b>",
        parse_mode='HTML',
        reply_markup=get_admin_menu()
    )

async def show_pending_applications(query, context: ContextTypes.DEFAULT_TYPE):
    """Показать заявки на модерацию"""
    pending_applications = db.get_pending_applications()
    
    if not pending_applications:
        await safe_edit_message_text(
            query,
            "📭 <b>Нет заявок на рассмотрение.</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        return
    
    # Сохраняем список заявок в context для навигации
    user_id = query.from_user.id
    context.user_data['admin_applications'] = pending_applications
    context.user_data['admin_applications_timestamp'] = time.time()
    
    # Показываем первую заявку
    await show_application_detail(query, 0, context)

async def show_application_detail(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали заявки по индексу"""
    user_id = query.from_user.id
    applications = context.user_data.get('admin_applications', [])
    timestamp = context.user_data.get('admin_applications_timestamp', 0)
    
    # Проверяем актуальность данных (10 минут)
    if time.time() - timestamp > 600:
        applications = db.get_pending_applications()
        context.user_data['admin_applications'] = applications
        context.user_data['admin_applications_timestamp'] = time.time()
    
    if not applications or index >= len(applications):
        await safe_edit_message_text(
            query,
            "❌ Заявка не найдена.", 
            reply_markup=get_admin_menu()
        )
        return
    
    application = applications[index]
    
    # Формируем текст заявки
    application_text = (
        f"📨 <b>Заявка #{application['application_id']}</b>\n\n"
        f"👤 <b>Автор:</b> {application['first_name']} {application['last_name'] or ''}\n"
        f"📛 <b>Username:</b> @{application['username'] or 'нет'}\n"
        f"🆔 <b>ID:</b> {application['user_id']}\n"
        f"🎭 <b>Второй блок:</b> {'✅ Да' if application['second_block'] else '❌ Нет'}\n"
        f"📅 <b>Дата:</b> {application['created_at']}\n\n"
        f"📝 <b>Стихотворение:</b>\n{application['poem_text']}"
    )
    
    keyboard = get_application_moderation_keyboard(
        application['application_id'], 
        index, 
        len(applications)
    )
    
    await safe_edit_message_text(
        query,
        application_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def navigate_applications(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Навигация по заявкам"""
    await show_application_detail(query, index, context)

async def handle_application_action(query, application_id: int, action: str, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик действий с заявками"""
    logger.info(f"=== ОБРАБОТКА ЗАЯВКИ {application_id} ДЕЙСТВИЕ: {action} ===")
    
    try:
        # Проверяем существование заявки
        application = db.get_application_by_id(application_id)
        if not application:
            logger.error(f"Заявка {application_id} не найдена в базе")
            await query.answer("❌ Заявка не найдена")
            return
        
        # Определяем параметры действия
        action_config = {
            'approve': {
                'status': 'approved',
                'admin_msg': "✅ Заявка одобрена!",
                'user_msg': "🎉 <b>Ваша заявка одобрена!</b>\n\nМы ждем вас на поэтическом вечере!",
                'log_action': 'одобрена'
            },
            'reject': {
                'status': 'rejected', 
                'admin_msg': "❌ Заявка отклонена",
                'user_msg': "❌ <b>Ваша заявка отклонена.</b>\n\nПо всем вопросам обращайтесь к организаторам.",
                'log_action': 'отклонена'
            }
        }
        
        config = action_config[action]
        
        # Обновляем статус заявки
        db.update_application_status(application_id, config['status'])
        logger.info(f"Заявка {application_id} {config['log_action']}")
        
        # Уведомляем пользователя
        await _notify_user_about_application(application, config['user_msg'], context)
        
        await query.answer(config['admin_msg'])
        
        # Обновляем список заявок
        await _refresh_applications_list(query, application_id, context)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке заявки {application_id}: {e}", exc_info=True)
        await query.answer("❌ Ошибка при обработке заявки")

async def _notify_user_about_application(application: Dict, message: str, context: ContextTypes.DEFAULT_TYPE):
    """Уведомить пользователя о статусе заявки"""
    try:
        await context.bot.send_message(
            chat_id=application['user_id'],
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Пользователь {application['user_id']} уведомлен")
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {application['user_id']}: {e}")

async def _refresh_applications_list(query, processed_application_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Обновить список заявок после обработки"""
    user_id = query.from_user.id
    applications = context.user_data.get('admin_applications', [])
    
    if applications:
        # Удаляем обработанную заявку из списка
        context.user_data['admin_applications'] = [
            app for app in applications 
            if app['application_id'] != processed_application_id
        ]
        
        applications = context.user_data['admin_applications']
        logger.info(f"Обновлен список заявок для пользователя {user_id}. Осталось: {len(applications)}")
        
        if applications:
            await show_application_detail(query, 0, context)
        else:
            await safe_edit_message_text(
                query,
                "✅ <b>Все заявки обработаны!</b>",
                parse_mode='HTML',
                reply_markup=get_admin_menu()
            )
    else:
        # Если список пуст, возвращаем в меню
        await show_admin_menu(query)

async def export_approved_poems(query, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт принятых стихотворений"""
    try:
        file = export_approved_poems_to_file()
        if file:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=file,
                filename="стихи_первого_блока.txt",
                caption="📄 <b>Стихи первого блока</b>",
                parse_mode='HTML'
            )
            await query.answer("✅ Файл отправлен!")
        else:
            await query.answer("❌ Нет принятых заявок для экспорта")
    except Exception as e:
        logger.error(f"Ошибка при экспорте стихов: {e}")
        await query.answer("❌ Ошибка при экспорте")

async def export_second_block_speakers(query, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт списка выступающих второго блока"""
    try:
        file = export_second_block_speakers_to_file()
        if file:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=file,
                filename="список_второго_блока.txt",
                caption="👥 <b>Список выступающих второго блока</b>",
                parse_mode='HTML'
            )
            await query.answer("✅ Файл отправлен!")
        else:
            await query.answer("❌ Нет выступающих во втором блоке")
    except Exception as e:
        logger.error(f"Ошибка при экспорте списка второго блока: {e}")
        await query.answer("❌ Ошибка при экспорте")

async def confirm_delete_all_applications(query):
    """Подтверждение удаления всех заявок"""
    applications_count = db.get_applications_count()
    
    await safe_edit_message_text(
        query,
        f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        f"Вы собираетесь удалить <b>ВСЕ</b> заявки ({applications_count} шт.).\n"
        f"Это действие <b>необратимо</b>!\n\n"
        f"Продолжить?",
        parse_mode='HTML',
        reply_markup=get_confirmation_keyboard("delete_all")
    )

async def delete_all_applications(query, context: ContextTypes.DEFAULT_TYPE):
    """Удаление всех заявок"""
    try:
        deleted_count = db.delete_all_applications()
        
        # Очищаем данные навигации
        user_id = query.from_user.id
        if 'admin_applications' in context.user_data:
            del context.user_data['admin_applications']
        
        await safe_edit_message_text(
            query,
            f"✅ <b>Удалено {deleted_count} заявок</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        
        logger.info(f"Админ {user_id} удалил все заявки ({deleted_count} шт.)")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении всех заявок: {e}")
        await safe_edit_message_text(
            query,
            "❌ <b>Ошибка при удалении заявок</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )

async def show_blacklist_menu(query):
    """Показать меню черного списка"""
    blacklist_count = len(db.get_blacklist())
    
    await safe_edit_message_text(
        query,
        f"🚫 <b>Управление черным списком</b>\n\n"
        f"Текущее количество: {blacklist_count} пользователей",
        parse_mode='HTML',
        reply_markup=get_blacklist_menu()
    )

async def handle_blacklist_actions(query, action: str, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с черным списком"""
    if action == "blacklist_add":
        await safe_edit_message_text(
            query,
            "➕ <b>Добавление в черный список</b>\n\n"
            "Отправьте ID пользователя для добавления:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_blacklist")]
            ])
        )
        # Используем оба менеджера состояний для совместимости
        admin_state_manager.set_state(query.from_user.id, 'awaiting_blacklist_add')
        state_manager.set_admin_state(query.from_user.id, 'awaiting_blacklist_add')
        
    elif action == "blacklist_remove":
        await safe_edit_message_text(
            query,
            "➖ <b>Удаление из черного списка</b>\n\n"
            "Отправьте ID пользователя для удаления:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_blacklist")]
            ])
        )
        admin_state_manager.set_state(query.from_user.id, 'awaiting_blacklist_remove')
        state_manager.set_admin_state(query.from_user.id, 'awaiting_blacklist_remove')
        
    elif action == "blacklist_view":
        await show_blacklist_details(query)

async def show_blacklist_details(query, page: int = 0):
    """Показать детали черного списка с пагинацией и кнопкой назад"""
    blacklist = db.get_blacklist()
    
    if not blacklist:
        await safe_edit_message_text(
            query,
            "📝 <b>Черный список пуст</b>",
            parse_mode='HTML',
            reply_markup=get_blacklist_menu()
        )
        return
    
    # Пагинация
    start_idx = page * AdminConfig.MAX_BLACKLIST_DISPLAY
    end_idx = start_idx + AdminConfig.MAX_BLACKLIST_DISPLAY
    paginated_blacklist = blacklist[start_idx:end_idx]
    
    blacklist_text = f"🚫 <b>Черный список:</b> ({len(blacklist)} пользователей)\n\n"
    
    for i, user_id in enumerate(paginated_blacklist, start_idx + 1):
        user = db.get_user(user_id)
        if user:
            username = f"@{user['username']}" if user['username'] else "без username"
            name = f"{user['first_name']} {user['last_name'] or ''}".strip()
            blacklist_text += f"{i}. {name} ({username}) - ID: {user_id}\n"
        else:
            blacklist_text += f"{i}. Пользователь не найден - ID: {user_id}\n"
    
    # Добавляем информацию о странице
    total_pages = max(1, (len(blacklist) + AdminConfig.MAX_BLACKLIST_DISPLAY - 1) // AdminConfig.MAX_BLACKLIST_DISPLAY)
    if total_pages > 1:
        blacklist_text += f"\n📄 Страница {page + 1} из {total_pages}"
    
    # Создаем клавиатуру с пагинацией и кнопкой назад
    keyboard_buttons = []
    
    # Кнопки пагинации (только если больше одной страницы)
    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"blacklist_page_{page-1}"))
        
        # Кнопка с текущей страницей (неактивная)
        pagination_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        
        if page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"blacklist_page_{page+1}"))
        
        keyboard_buttons.append(pagination_row)
    
    # Кнопка "Назад" - всегда в отдельном ряду
    keyboard_buttons.append([InlineKeyboardButton("🔙 Назад в меню ЧС", callback_data="admin_blacklist")])
    
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    
    await safe_edit_message_text(
        query,
        blacklist_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def handle_admin_broadcast_callback(query):
    """Обработчик кнопки рассылки"""
    recipients_count = get_broadcast_recipients_count()
    preview_info = get_broadcast_recipients_preview(5)
    
    await safe_edit_message_text(
        query,
        f"📢 <b>Рассылка для {recipients_count} пользователей:</b>\n\n"
        f"<i>Пример получателей:</i>\n{preview_info['preview']}\n\n"
        "✏️ <b>Отправьте текст для рассылки:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="admin_menu")]
        ])
    )
    
    # Используем оба менеджера состояний для совместимости
    admin_state_manager.set_state(query.from_user.id, 'awaiting_broadcast')
    state_manager.set_admin_state(query.from_user.id, 'awaiting_broadcast')

# Функции для обработки сообщений
async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста для рассылки"""
    user = update.effective_user
    message_text = update.message.text
    
    if user.id != ADMIN_ID:
        return
    
    # Проверяем состояние в обоих менеджерах для совместимости
    state_data = admin_state_manager.get_state(user.id)
    old_state = state_manager.get_admin_state(user.id)
    
    is_broadcast_state = (
        (state_data and state_data['state'] == 'awaiting_broadcast') or
        old_state == 'awaiting_broadcast'
    )
    
    if is_broadcast_state:
        logger.info(f"Админ {user.id} начинает рассылку: {message_text[:100]}...")
        
        # Сбрасываем состояние в обоих менеджерах
        admin_state_manager.clear_state(user.id)
        state_manager.clear_admin_state(user.id)
        
        # Показываем сообщение о начале рассылки
        processing_msg = await update.message.reply_text("🔄 <b>Начинаем рассылку...</b>", parse_mode='HTML')
        
        # Выполняем рассылку
        stats = await send_broadcast(context, message_text)
        
        await processing_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"• ✅ Успешно: {stats['success']}\n"
            f"• ❌ Не удалось: {stats['failed']}\n"
            f"• 📊 Всего: {stats['total']}",
            parse_mode='HTML'
        )

async def handle_blacklist_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений для черного списка"""
    user = update.effective_user
    message_text = update.message.text.strip()
    
    if user.id != ADMIN_ID:
        return
    
    # Проверяем состояние в обоих менеджерах для совместимости
    state_data = admin_state_manager.get_state(user.id)
    old_state = state_manager.get_admin_state(user.id)
    
    if not state_data and not old_state:
        return
    
    # Определяем тип действия
    action = None
    if state_data:
        if state_data['state'] == 'awaiting_blacklist_add':
            action = 'add'
        elif state_data['state'] == 'awaiting_blacklist_remove':
            action = 'remove'
    elif old_state:
        if old_state == 'awaiting_blacklist_add':
            action = 'add'
        elif old_state == 'awaiting_blacklist_remove':
            action = 'remove'
    
    if action == 'add':
        await _handle_blacklist_add(update, message_text)
    elif action == 'remove':
        await _handle_blacklist_remove(update, message_text)

async def _handle_blacklist_add(update: Update, user_id_str: str):
    """Обработка добавления в черный список"""
    try:
        user_id_to_add = int(user_id_str)
        
        # Проверяем, существует ли пользователь
        user = db.get_user(user_id_to_add)
        if not user:
            await update.message.reply_text(
                "❌ <b>Пользователь с таким ID не найден.</b>\n\n"
                "Проверьте ID и попробуйте снова:",
                parse_mode='HTML'
            )
            return
        
        db.add_to_blacklist(user_id_to_add)
        
        await update.message.reply_text(
            f"✅ <b>Пользователь добавлен в черный список</b>\n\n"
            f"👤 {user['first_name']} {user['last_name'] or ''}\n"
            f"📛 @{user['username'] or 'нет'}\n"
            f"🆔 ID: {user_id_to_add}",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        
        # Очищаем состояние в обоих менеджерах
        admin_state_manager.clear_state(update.effective_user.id)
        state_manager.clear_admin_state(update.effective_user.id)
        
    except ValueError:
        await update.message.reply_text(
            "❌ <b>Неверный формат ID.</b> Отправьте числовой ID:",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении в черный список: {e}")
        await update.message.reply_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        admin_state_manager.clear_state(update.effective_user.id)
        state_manager.clear_admin_state(update.effective_user.id)

async def _handle_blacklist_remove(update: Update, user_id_str: str):
    """Обработка удаления из черного списка"""
    try:
        user_id_to_remove = int(user_id_str)
        db.remove_from_blacklist(user_id_to_remove)
        
        await update.message.reply_text(
            f"✅ <b>Пользователь {user_id_to_remove} удален из черного списка</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        
        # Очищаем состояние в обоих менеджерах
        admin_state_manager.clear_state(update.effective_user.id)
        state_manager.clear_admin_state(update.effective_user.id)
        
    except ValueError:
        await update.message.reply_text(
            "❌ <b>Неверный формат ID.</b> Отправьте числовой ID:",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении из черного списка: {e}")
        await update.message.reply_text(
            f"❌ <b>Ошибка:</b> {str(e)}",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        admin_state_manager.clear_state(update.effective_user.id)
        state_manager.clear_admin_state(update.effective_user.id)

# Функция для периодической очистки состояний
def cleanup_admin_states():

    """Очистка просроченных состояний администратора"""
    admin_state_manager.cleanup_expired()
