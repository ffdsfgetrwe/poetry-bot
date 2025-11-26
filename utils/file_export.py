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
