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
            InlineKeyboardButton("✅ Да, удалить все", callback_data="confirm_delete_all"),
            InlineKeyboardButton("❌ Отмена", callback_data="admin_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)