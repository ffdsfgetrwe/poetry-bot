
import sqlite3
import datetime
import logging
from config import DB_NAME

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.init_content()
    
    def create_tables(self):
        """Создание всех необходимых таблиц"""
        cursor = self.conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заявок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                poem_text TEXT NOT NULL,
                second_block BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Черный список
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Контент (правила, информация об организаторе)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        logger.info("Таблицы базы данных созданы/проверены")
    
    def init_content(self):
        """Инициализация базового контента"""
        cursor = self.conn.cursor()
        
        default_content = [
            ('rules', '📝 Правила участия в поэтическом вечере:\n\n1. Стихотворение должно быть авторским\n2. Длительность выступления - до 5 минут\n3. Уважительное отношение к другим участникам\n4. Соблюдение регламента мероприятия'),
            ('about_organizer', '🎭 Об организаторе:\n\nМы проводим поэтические вечера уже более 5 лет. Наша цель - создать пространство для творчества и самовыражения поэтов.')
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO content (key, value) 
            VALUES (?, ?)
        ''', default_content)
        
        self.conn.commit()
    
    # Методы для работы с пользователями
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Добавление/обновление пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def get_user(self, user_id: int):
        """Получение информации о пользователе"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    # Методы для работы с черным списком
    def is_user_blacklisted(self, user_id: int) -> bool:
        """Проверка, находится ли пользователь в черном списке"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM blacklist WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def add_to_blacklist(self, user_id: int):
        """Добавление пользователя в черный список"""
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)', (user_id,))
        self.conn.commit()
    
    def remove_from_blacklist(self, user_id: int):
        """Удаление пользователя из черного списка"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def get_blacklist(self):
        """Получение всего черного списка"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM blacklist')
        return [row[0] for row in cursor.fetchall()]
    
    # Методы для работы с контентом
    def get_content(self, key: str):
        """Получение контента по ключу"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM content WHERE key = ?', (key,))
        result = cursor.fetchone()
        
        # Добавляем логирование для отладки
        if result:
            logger.info(f"Найден контент для ключа '{key}': {result[0][:100]}...")
        else:
            logger.warning(f"Контент для ключа '{key}' не найден")
        
        return result[0] if result else None
    
    def update_content(self, key: str, value: str):
        """Обновление контента"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO content (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        self.conn.commit()
    
    # Методы для работы с заявками
    def get_user_application(self, user_id: int):
        """Получение активной заявки пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM applications 
            WHERE user_id = ? AND status IN ('pending', 'approved')
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        return cursor.fetchone()
    
    def create_application(self, user_id: int, poem_text: str, second_block: bool = False):
        """Создание новой заявки"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO applications (user_id, poem_text, second_block, status)
            VALUES (?, ?, ?, 'pending')
        ''', (user_id, poem_text, second_block))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_users(self):
        """Получение всех пользователей для рассылки"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]
    
    def get_pending_applications(self):
        """Получение всех заявок со статусом pending - ИСПРАВЛЕННЫЙ ЗАПРОС"""
        cursor = self.conn.cursor()
        
        # Сначала логируем все заявки для отладки
        cursor.execute('SELECT application_id, user_id, status FROM applications')
        all_apps = cursor.fetchall()
        logger.info(f"Все заявки в базе: {len(all_apps)}")
        for app in all_apps:
            logger.info(f"Заявка {app['application_id']}: user_id={app['user_id']}, status={app['status']}")
        
        # Основной запрос с LEFT JOIN и обработкой отсутствующих пользователей
        cursor.execute('''
            SELECT 
                a.application_id, 
                a.user_id, 
                a.poem_text, 
                a.second_block, 
                a.status, 
                a.created_at,
                a.updated_at,
                COALESCE(u.username, 'неизвестно') as username,
                COALESCE(u.first_name, 'Неизвестный') as first_name,
                COALESCE(u.last_name, '') as last_name
            FROM applications a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'pending'
            ORDER BY a.created_at ASC
        ''')
        
        results = cursor.fetchall()
        logger.info(f"Найдено заявок со статусом 'pending': {len(results)}")
        
        return results
    
    def get_application_by_id(self, application_id: int):
        """Получение заявки по ID - ИСПРАВЛЕННЫЙ ЗАПРОС"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                a.*,
                COALESCE(u.username, 'неизвестно') as username,
                COALESCE(u.first_name, 'Неизвестный') as first_name,
                COALESCE(u.last_name, '') as last_name
            FROM applications a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.application_id = ?
        ''', (application_id,))
        return cursor.fetchone()
    

    # В models/database.py ПРОВЕРЬТЕ функцию:
    def update_application_status(self, application_id: int, status: str):
        """Обновление статуса заявки"""
        cursor = self.conn.cursor()
        cursor.execute('''
           UPDATE applications 
           SET status = ?, updated_at = CURRENT_TIMESTAMP
           WHERE application_id = ?
        ''', (status, application_id))
        self.conn.commit()
        logger.info(f"Статус заявки {application_id} изменен на {status}")
    


    def get_applications_count(self):
        """Получение количества заявок"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM applications')
        return cursor.fetchone()[0]
    
    def delete_all_applications(self):
        """Удаление всех заявок"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM applications')
        self.conn.commit()
        return cursor.rowcount
    
    def delete_application(self, application_id: int):
        """Удаление заявки"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM applications WHERE application_id = ?', (application_id,))
        self.conn.commit()
    
    def get_approved_applications(self):
        """Получение всех принятых заявок - ИСПРАВЛЕННЫЙ ЗАПРОС"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                a.*,
                COALESCE(u.username, 'неизвестно') as username,
                COALESCE(u.first_name, 'Неизвестный') as first_name,
                COALESCE(u.last_name, '') as last_name
            FROM applications a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'approved'
            ORDER BY a.created_at ASC
        ''')
        return cursor.fetchall()
    
    def get_second_block_speakers(self):
        """Получение списка выступающих во втором блоке - ИСПРАВЛЕННЫЙ ЗАПРОС"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                a.*,
                COALESCE(u.username, 'неизвестно') as username,
                COALESCE(u.first_name, 'Неизвестный') as first_name,
                COALESCE(u.last_name, '') as last_name
            FROM applications a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.status = 'approved' AND a.second_block = 1
            ORDER BY a.created_at ASC
        ''')
        return cursor.fetchall()
