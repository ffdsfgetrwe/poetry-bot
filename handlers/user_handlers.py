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
    context.user_data['awaiting_poem'] = True
    context.user_data['application_started'] = True
    
    if user_id == ADMIN_ID:
        context.user_data['admin_as_user'] = True
    
    # Сохраняем ID оригинального сообщения (которое мы редактируем)
    context.user_data['original_message_id'] = query.message.message_id
    logger.info(f"Сохранен ID оригинального сообщения: {query.message.message_id}")
    
    # Редактируем оригинальное сообщение
    await query.edit_message_text(
        "📝 Начата подача заявки...",
        reply_markup=None
    )
    
    # Отправляем новое сообщение с инструкцией и СОХРАНЯЕМ ЕГО ID
    instruction_message = await query.message.reply_text(
        "📝 Подача заявки на поэтический вечер:\n\n"
        "Пожалуйста, введите текст вашего стихотворения:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="cancel_application")]])
    )
    
    # Сохраняем ID сообщения с инструкцией для последующего удаления
    context.user_data['instruction_message_id'] = instruction_message.message_id
    logger.info(f"Сохранен ID сообщения с инструкцией: {instruction_message.message_id}")

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
        
        # УДАЛЯЕМ ОБА сообщения бота
        deleted_count = 0
        
        # 1. Удаляем сообщение "Начата подача заявки..." (оригинальное сообщение)
        original_message_id = context.user_data.get('original_message_id')
        if original_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=user.id,
                    message_id=original_message_id
                )
                logger.info(f"Оригинальное сообщение {original_message_id} удалено")
                context.user_data.pop('original_message_id', None)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Не удалось удалить оригинальное сообщение: {e}")
        
        # 2. Удаляем сообщение с инструкцией
        instruction_message_id = context.user_data.get('instruction_message_id')
        if instruction_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=user.id,
                    message_id=instruction_message_id
                )
                logger.info(f"Сообщение с инструкцией {instruction_message_id} удалено")
                context.user_data.pop('instruction_message_id', None)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение с инструкцией: {e}")
        
        logger.info(f"Удалено сообщений: {deleted_count}")
        
        # Отправляем новое сообщение с выбором второго блока
        await update.message.reply_text(
            "✅ Стихотворение получено!\n\n"
            "Хотите ли вы также выступить во втором блоке вечера?",
            reply_markup=get_second_block_keyboard()
        )
    else:
        logger.info(f"Пользователь {user.id} не в состоянии подачи заявки - игнорируем текст")

async def handle_second_block_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора участия во втором блоке"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    # Обработка отмены заявки
    if choice == "cancel_application":
        # УДАЛЯЕМ ОБА сообщения бота при отмене
        deleted_count = 0
        
        # 1. Удаляем сообщение "Начата подача заявки..."
        original_message_id = context.user_data.get('original_message_id')
        if original_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=original_message_id
                )
                logger.info(f"Оригинальное сообщение {original_message_id} удалено при отмене")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Не удалось удалить оригинальное сообщение при отмене: {e}")
        
        # 2. Удаляем сообщение с инструкцией
        instruction_message_id = context.user_data.get('instruction_message_id')
        if instruction_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=instruction_message_id
                )
                logger.info(f"Сообщение с инструкцией {instruction_message_id} удалено при отмене")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение с инструкцией при отмене: {e}")
        
        logger.info(f"Удалено сообщений при отмене: {deleted_count}")
        
        # ДЛЯ АДМИНА: снимаем флаг режима пользователя
        if user_id == ADMIN_ID:
            context.user_data.pop('admin_as_user', None)
            logger.info(f"Админ {user_id} вышел из режима пользователя (отмена заявки)")
        
        context.user_data.clear()
        
        # Отправляем новое сообщение с главным меню
        await query.message.reply_text(
            "❌ Подача заявки отменена.", 
            reply_markup=get_main_menu(user_id)
        )
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

