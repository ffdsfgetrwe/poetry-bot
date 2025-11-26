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
