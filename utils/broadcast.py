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
