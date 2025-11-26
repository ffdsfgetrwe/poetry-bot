import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from models import Database
from keyboards.admin_keyboards import get_admin_menu, get_blacklist_menu, get_application_moderation_keyboard, get_confirmation_keyboard
from config import ADMIN_ID
from utils.broadcast import send_broadcast, get_broadcast_recipients_count, get_broadcast_recipients_preview
from utils.file_export import export_approved_poems_to_file, export_second_block_speakers_to_file
from .state_manager import state_manager

logger = logging.getLogger(__name__)
db = Database()

# Глобальные переменные для навигации по заявкам
application_navigation = {}

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик callback-запросов админ-меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ У вас нет прав доступа.")
        return
    
    callback_data = query.data
    logger.info(f"Админ callback: {callback_data}")

    # Обработка навигации по заявкам
    if callback_data.startswith("nav_"):
        index = int(callback_data.split("_")[1])
        await navigate_applications(query, index, context)
    
    # Обработка принятия/отклонения заявок
    elif callback_data.startswith("approve_"):
        application_id = int(callback_data.split("_")[1])
        await approve_application(query, application_id, context)
    
    elif callback_data.startswith("reject_"):
        application_id = int(callback_data.split("_")[1])
        await reject_application(query, application_id, context)
    
    # Обработка подтверждения удаления
    elif callback_data == "confirm_delete_all":
        await delete_all_applications(query, context)
    
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
    
    # Редактирование контента - перенаправляем в соответствующий обработчик
    elif callback_data in ["admin_rules", "admin_about"]:
        from handlers.content_edit_handlers import handle_content_edit_callback
        await handle_content_edit_callback(update, context)
    
    else:
        logger.warning(f"Неизвестный callback: {callback_data}")
        await query.answer("❌ Неизвестная команда")

async def show_admin_menu(query):
    """Показать меню администратора"""
    await query.edit_message_text(
        "⚙️ <b>Меню организатора:</b>",
        parse_mode='HTML',
        reply_markup=get_admin_menu()
    )

async def show_pending_applications(query, context: ContextTypes.DEFAULT_TYPE):
    """Показать заявки на модерацию"""
    pending_applications = db.get_pending_applications()
    
    if not pending_applications:
        await query.edit_message_text(
            "📭 <b>Нет заявок на рассмотрение.</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        return
    
    # Сохраняем список заявок для навигации
    user_id = query.from_user.id
    application_navigation[user_id] = pending_applications
    
    # Показываем первую заявку
    await show_application_detail(query, 0, context)

async def show_application_detail(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Показать детали заявки по индексу"""
    user_id = query.from_user.id
    applications = application_navigation.get(user_id, [])
    
    if not applications or index >= len(applications):
        await query.edit_message_text("❌ Заявка не найдена.", reply_markup=get_admin_menu())
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
    
    await query.edit_message_text(
        application_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def navigate_applications(query, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Навигация по заявкам"""
    await show_application_detail(query, index, context)

# В admin_handlers.py ОБНОВИТЕ функции approve_application и reject_application:

async def approve_application(query, application_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Одобрить заявку"""
    logger.info(f"=== ПЫТАЕМСЯ ОДОБРИТЬ ЗАЯВКУ {application_id} ===")
    
    try:
        # Проверяем существование заявки перед обновлением
        application = db.get_application_by_id(application_id)
        if not application:
            logger.error(f"Заявка {application_id} не найдена в базе")
            await query.answer("❌ Заявка не найдена")
            return
        
        logger.info(f"Найдена заявка: {application}")
        
        db.update_application_status(application_id, 'approved')
        logger.info(f"Статус заявки {application_id} изменен на 'approved'")
        
        # Проверяем обновление
        updated_application = db.get_application_by_id(application_id)
        logger.info(f"Заявка после обновления: {updated_application}")
        
        # Уведомление пользователя
        if application:
            try:
                await context.bot.send_message(
                    chat_id=application['user_id'],
                    text="🎉 <b>Ваша заявка одобрена!</b>\n\nМы ждем вас на поэтическом вечере!",
                    parse_mode='HTML'
                )
                logger.info(f"Пользователь {application['user_id']} уведомлен об одобрении")
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {application['user_id']}: {e}")
        
        await query.answer("✅ Заявка одобрена!")
        
        # Обновляем список заявок
        user_id = query.from_user.id
        if user_id in application_navigation:
            # Удаляем одобренную заявку из списка
            application_navigation[user_id] = [
                app for app in application_navigation[user_id] 
                if app['application_id'] != application_id
            ]
            logger.info(f"Обновлен navigation для пользователя {user_id}. Осталось заявок: {len(application_navigation[user_id])}")
            
            if application_navigation[user_id]:
                await show_application_detail(query, 0, context)
            else:
                await query.edit_message_text(
                    "✅ <b>Все заявки обработаны!</b>",
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
        
    except Exception as e:
        logger.error(f"Ошибка при одобрении заявки {application_id}: {e}", exc_info=True)
        await query.answer("❌ Ошибка при одобрении заявки")

async def reject_application(query, application_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Отклонить заявку"""
    logger.info(f"=== ПЫТАЕМСЯ ОТКЛОНИТЬ ЗАЯВКУ {application_id} ===")
    
    try:
        # Проверяем существование заявки перед обновлением
        application = db.get_application_by_id(application_id)
        if not application:
            logger.error(f"Заявка {application_id} не найдена в базе")
            await query.answer("❌ Заявка не найдена")
            return
        
        logger.info(f"Найдена заявка: {application}")
        
        db.update_application_status(application_id, 'rejected')
        logger.info(f"Статус заявки {application_id} изменен на 'rejected'")
        
        # Проверяем обновление
        updated_application = db.get_application_by_id(application_id)
        logger.info(f"Заявка после обновления: {updated_application}")
        
        # Уведомление пользователя
        if application:
            try:
                await context.bot.send_message(
                    chat_id=application['user_id'],
                    text="❌ <b>Ваша заявка отклонена.</b>\n\nПо всем вопросам обращайтесь к организаторам.",
                    parse_mode='HTML'
                )
                logger.info(f"Пользователь {application['user_id']} уведомлен об отклонении")
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {application['user_id']}: {e}")
        
        await query.answer("❌ Заявка отклонена")
        
        # Обновляем список заявок
        user_id = query.from_user.id
        if user_id in application_navigation:
            # Удаляем отклоненную заявку из списка
            application_navigation[user_id] = [
                app for app in application_navigation[user_id] 
                if app['application_id'] != application_id
            ]
            logger.info(f"Обновлен navigation для пользователя {user_id}. Осталось заявок: {len(application_navigation[user_id])}")
            
            if application_navigation[user_id]:
                await show_application_detail(query, 0, context)
            else:
                await query.edit_message_text(
                    "✅ <b>Все заявки обработаны!</b>",
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении заявки {application_id}: {e}", exc_info=True)
        await query.answer("❌ Ошибка при отклонении заявки")

async def reject_application(query, application_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Отклонить заявку"""
    try:
        logger.info(f"Попытка отклонить заявку {application_id}")
        
        # Проверяем существование заявки
        application = db.get_application_by_id(application_id)
        if not application:
            logger.error(f"Заявка {application_id} не найдена")
            await query.answer("❌ Заявка не найдена")
            return
            
        db.update_application_status(application_id, 'rejected')
        logger.info(f"Заявка {application_id} отклонена")
        
        # Получаем информацию о заявке для уведомления пользователя
        application = db.get_application_by_id(application_id)
        if application:
            try:
                await context.bot.send_message(
                    chat_id=application['user_id'],
                    text="❌ <b>Ваша заявка отклонена.</b>\n\nПо всем вопросам обращайтесь к организаторам.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {application['user_id']}: {e}")
        
        await query.answer("❌ Заявка отклонена")
        
        # Обновляем список заявок
        user_id = query.from_user.id
        if user_id in application_navigation:
            # Удаляем отклоненную заявку из списка
            application_navigation[user_id] = [
                app for app in application_navigation[user_id] 
                if app['application_id'] != application_id
            ]
            
            if application_navigation[user_id]:
                await show_application_detail(query, 0, context)
            else:
                await query.edit_message_text(
                    "✅ <b>Все заявки обработаны!</b>",
                    parse_mode='HTML',
                    reply_markup=get_admin_menu()
                )
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении заявки {application_id}: {e}")
        await query.answer("❌ Ошибка при отклонении заявки")

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
    
    await query.edit_message_text(
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
        
        # Очищаем навигацию
        user_id = query.from_user.id
        if user_id in application_navigation:
            del application_navigation[user_id]
        
        await query.edit_message_text(
            f"✅ <b>Удалено {deleted_count} заявок</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )
        
        logger.info(f"Админ {user_id} удалил все заявки ({deleted_count} шт.)")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении всех заявок: {e}")
        await query.edit_message_text(
            "❌ <b>Ошибка при удалении заявок</b>",
            parse_mode='HTML',
            reply_markup=get_admin_menu()
        )

async def show_blacklist_menu(query):
    """Показать меню черного списка"""
    blacklist_count = len(db.get_blacklist())
    
    await query.edit_message_text(
        f"🚫 <b>Управление черным списком</b>\n\n"
        f"Текущее количество: {blacklist_count} пользователей",
        parse_mode='HTML',
        reply_markup=get_blacklist_menu()
    )

async def handle_blacklist_actions(query, action: str, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с черным списком"""
    if action == "blacklist_add":
        await query.edit_message_text(
            "➕ <b>Добавление в черный список</b>\n\n"
            "Отправьте ID пользователя для добавления:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_blacklist")]
            ])
        )
        state_manager.set_admin_state(query.from_user.id, 'awaiting_blacklist_add')
        
    elif action == "blacklist_remove":
        await query.edit_message_text(
            "➖ <b>Удаление из черного списка</b>\n\n"
            "Отправьте ID пользователя для удаления:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_blacklist")]
            ])
        )
        state_manager.set_admin_state(query.from_user.id, 'awaiting_blacklist_remove')
        
    elif action == "blacklist_view":
        blacklist = db.get_blacklist()
        if not blacklist:
            await query.edit_message_text(
                "📝 <b>Черный список пуст</b>",
                parse_mode='HTML',
                reply_markup=get_blacklist_menu()
            )
            return
        
        blacklist_text = "🚫 <b>Черный список:</b>\n\n"
        for i, user_id in enumerate(blacklist, 1):
            user = db.get_user(user_id)
            if user:
                username = f"@{user['username']}" if user['username'] else "без username"
                blacklist_text += f"{i}. {user['first_name']} {user['last_name'] or ''} ({username}) - ID: {user_id}\n"
            else:
                blacklist_text += f"{i}. Пользователь не найден - ID: {user_id}\n"
        
        await query.edit_message_text(
            blacklist_text,
            parse_mode='HTML',
            reply_markup=get_blacklist_menu()
        )

async def handle_admin_broadcast_callback(query):
    """Обработчик кнопки рассылки"""
    recipients_count = get_broadcast_recipients_count()
    preview_info = get_broadcast_recipients_preview(5)
    
    await query.edit_message_text(
        f"📢 <b>Рассылка для {recipients_count} пользователей:</b>\n\n"
        f"<i>Пример получателей:</i>\n{preview_info['preview']}\n\n"
        "✏️ <b>Отправьте текст для рассылки:</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Отмена", callback_data="admin_menu")]
        ])
    )
    
    state_manager.set_admin_state(query.from_user.id, 'awaiting_broadcast')

# Функции для обработки сообщений (будут вызываться из message_router.py)
async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста для рассылки (вызывается из message_router)"""
    user = update.effective_user
    message_text = update.message.text
    
    if user.id != ADMIN_ID:
        return
    
    if state_manager.get_admin_state(user.id) == 'awaiting_broadcast':
        logger.info(f"Админ {user.id} начинает рассылку: {message_text[:100]}...")
        
        # Сбрасываем состояние
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
    """Обработчик сообщений для черного списка (вызывается из message_router)"""
    user = update.effective_user
    message_text = update.message.text
    
    if user.id != ADMIN_ID:
        return
    
    admin_state = state_manager.get_admin_state(user.id)
    
    if admin_state == 'awaiting_blacklist_add':
        try:
            user_id_to_add = int(message_text.strip())
            db.add_to_blacklist(user_id_to_add)
            
            await update.message.reply_text(
                f"✅ <b>Пользователь {user_id_to_add} добавлен в черный список</b>",
                parse_mode='HTML',
                reply_markup=get_admin_menu()
            )
            state_manager.clear_admin_state(user.id)
            
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Неверный формат ID.</b> Отправьте числовой ID:",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка при добавлении в черный список: {e}")
            await update.message.reply_text(
                f"❌ <b>Ошибка:</b> {e}",
                parse_mode='HTML',
                reply_markup=get_admin_menu()
            )
            state_manager.clear_admin_state(user.id)
    
    elif admin_state == 'awaiting_blacklist_remove':
        try:
            user_id_to_remove = int(message_text.strip())
            db.remove_from_blacklist(user_id_to_remove)
            
            await update.message.reply_text(
                f"✅ <b>Пользователь {user_id_to_remove} удален из черного списка</b>",
                parse_mode='HTML',
                reply_markup=get_admin_menu()
            )
            state_manager.clear_admin_state(user.id)
            
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Неверный формат ID.</b> Отправьте числовой ID:",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка при удалении из черного списка: {e}")
            await update.message.reply_text(
                f"❌ <b>Ошибка:</b> {e}",
                parse_mode='HTML',
                reply_markup=get_admin_menu()
            )
            state_manager.clear_admin_state(user.id)