import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json
from typing import List, Optional
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CatPoopDatabase:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.setup_connection()
    
    def setup_connection(self):
        """Подключение к Google Sheets"""
        try:
            # Пробуем получить credentials из переменной окружения (Railway)
            creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            
            if creds_json:
                logger.info("Использую credentials из переменной окружения")
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                # Локальная разработка: файл credentials.json
                logger.info("Использую файл credentials.json")
                creds = Credentials.from_service_account_file(
                    'credentials.json',
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            
            self.client = gspread.authorize(creds)
            
            # Получаем ID таблицы
            sheet_key = os.getenv("GOOGLE_SHEETS_KEY")
            if not sheet_key:
                raise ValueError("GOOGLE_SHEETS_KEY не найден в переменных окружения!")
            
            logger.info(f"Подключаюсь к таблице: {sheet_key}")
            self.sheet = self.client.open_by_key(sheet_key)
            
            # Инициализируем листы
            self.init_sheets()
            logger.info("✅ Подключение к Google Sheets установлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise
    
    def init_sheets(self):
        """Создаёт необходимые листы, если их нет"""
        try:
            # Лист для котов
            try:
                cats_worksheet = self.sheet.worksheet("cats")
                logger.info("Лист 'cats' уже существует")
            except gspread.WorksheetNotFound:
                logger.info("Создаю лист 'cats'")
                cats_worksheet = self.sheet.add_worksheet("cats", rows=1, cols=3)
                cats_worksheet.update('A1:C1', [['name', 'created_at', 'last_updated']])
                logger.info("✅ Лист 'cats' создан")
            
            # Лист для записей о какашках
            try:
                poops_worksheet = self.sheet.worksheet("poops")
                logger.info("Лист 'poops' уже существует")
            except gspread.WorksheetNotFound:
                logger.info("Создаю лист 'poops'")
                poops_worksheet = self.sheet.add_worksheet("poops", rows=1, cols=4)
                poops_worksheet.update('A1:D1', [['cat_name', 'timestamp', 'date', 'time']])
                logger.info("✅ Лист 'poops' создан")
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка при инициализации листов: {e}")
            raise
    
    def add_cat(self, cat_name: str) -> bool:
        """Добавляет нового кота"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            
            # Проверяем, существует ли уже кот (без учёта регистра)
            if self.cat_exists(cat_name):
                logger.info(f"Кот {cat_name} уже существует")
                return False
            
            now = datetime.now().isoformat()
            cats_ws.append_row([str(cat_name), str(now), str(now)], value_input_option='USER_ENTERED')
            logger.info(f"✅ Добавлен кот: {cat_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления кота {cat_name}: {e}")
            return False
    
    def cat_exists(self, cat_name: str) -> bool:
        """Проверяет существование кота (без учёта регистра)"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            # Получаем все имена котов
            records = cats_ws.get_all_records()
            
            # Нормализуем имя для сравнения (приводим к нижнему регистру)
            search_name = cat_name.strip().lower()
            
            for record in records:
                existing_name = record.get('name', '').strip().lower()
                if existing_name == search_name:
                    logger.info(f"Кот {cat_name} найден (совпадение с {record.get('name')})")
                    return True
            
            logger.info(f"Кот {cat_name} не найден")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки кота {cat_name}: {e}")
            return False
    
    def add_poop(self, cat_name: str) -> datetime:
        """Добавляет запись о какашке"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            now = datetime.now()
            
            # Подготавливаем данные с правильным форматированием
            timestamp = now.isoformat()
            date_str = now.strftime("%d.%m.%Y")
            time_str = now.strftime("%H:%M:%S")
            
            # Используем append_row с явным преобразованием в строки
            row_data = [str(cat_name), str(timestamp), str(date_str), str(time_str)]
            
            # Добавляем строку с опцией USER_ENTERED для правильной обработки данных
            poops_ws.append_row(row_data, value_input_option='USER_ENTERED')
            
            # Обновляем last_updated у кота
            try:
                cats_ws = self.sheet.worksheet("cats")
                # Находим кота без учёта регистра
                records = cats_ws.get_all_records()
                for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовок
                    if record.get('name', '').strip().lower() == cat_name.strip().lower():
                        cats_ws.update(f"C{i}", now.isoformat(), value_input_option='USER_ENTERED')
                        break
            except Exception as e:
                logger.warning(f"Не удалось обновить last_updated: {e}")
            
            logger.info(f"✅ Добавлена какашка для кота {cat_name} в {now.strftime('%d.%m.%Y %H:%M:%S')}")
            return now
        except Exception as e:
            logger.error(f"❌ Ошибка добавления какашки для {cat_name}: {e}")
            raise
    
    def get_last_poop_time(self, cat_name: str) -> Optional[datetime]:
        """Получает время последней какашки"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            # Нормализуем имя для поиска
            search_name = cat_name.strip().lower()
            
            # Фильтруем записи для конкретного кота
            cat_poops = []
            for record in records:
                record_name = record.get('cat_name', '').strip().lower()
                if record_name == search_name:
                    timestamp = record.get('timestamp')
                    if timestamp:
                        cat_poops.append(timestamp)
            
            if not cat_poops:
                logger.info(f"Нет записей о какашках для кота {cat_name}")
                return None
            
            # Находим последнюю запись
            last_timestamp = max(cat_poops)
            result = datetime.fromisoformat(last_timestamp)
            logger.info(f"Последняя какашка кота {cat_name}: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения последней какашки для {cat_name}: {e}")
            return None
    
    def get_time_since_last_poop(self, cat_name: str) -> str:
        """Возвращает время с последней какашки в человеко-читаемом формате"""
        try:
            last_time = self.get_last_poop_time(cat_name)
            
            if not last_time:
                return f"😿 У кота **{cat_name}** нет записей о том, что он какал!"
            
            now = datetime.now()
            diff = now - last_time
            
            # Рассчитываем дни, часы и минуты
            total_seconds = diff.total_seconds()
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            # Форматируем вывод
            if days > 0:
                if hours > 0:
                    return f"📅 **{cat_name}** покакал {days} дн. {hours} ч. {minutes} мин. назад\n\n🕐 Последний раз: {last_time.strftime('%d.%m.%Y в %H:%M:%S')}"
                else:
                    return f"📅 **{cat_name}** покакал {days} дн. {minutes} мин. назад\n\n🕐 Последний раз: {last_time.strftime('%d.%m.%Y в %H:%M:%S')}"
            elif hours > 0:
                return f"⏰ **{cat_name}** покакал {hours} ч. {minutes} мин. назад\n\n🕐 Последний раз: {last_time.strftime('%d.%m.%Y в %H:%M:%S')}"
            else:
                if minutes > 0:
                    return f"⏰ **{cat_name}** покакал {minutes} мин. назад\n\n🕐 Последний раз: {last_time.strftime('%d.%m.%Y в %H:%M:%S')}"
                else:
                    return f"🆕 **{cat_name}** только что покакал!\n\n🕐 Время: {last_time.strftime('%d.%m.%Y в %H:%M:%S')}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка в get_time_since_last_poop для {cat_name}: {e}")
            return f"❌ Ошибка получения времени: {str(e)}"
    
    def get_history(self, cat_name: str, limit: int = 10) -> List[str]:
        """Возвращает последние записи истории"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            # Нормализуем имя для поиска
            search_name = cat_name.strip().lower()
            
            # Фильтруем записи для конкретного кота
            cat_poops = []
            for record in records:
                record_name = record.get('cat_name', '').strip().lower()
                if record_name == search_name:
                    timestamp = record.get('timestamp')
                    if timestamp:
                        cat_poops.append(timestamp)
            
            # Сортируем по времени (сначала новые)
            cat_poops.sort(reverse=True)
            
            logger.info(f"Найдено {len(cat_poops)} записей для кота {cat_name}")
            
            if not cat_poops:
                return ["📭 История пуста"]
            
            # Форматируем результат
            result = []
            for i, timestamp in enumerate(cat_poops[:limit], 1):
                dt = datetime.fromisoformat(timestamp)
                result.append(f"{i}. {dt.strftime('%d.%m.%Y %H:%M:%S')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории для {cat_name}: {e}")
            return [f"❌ Ошибка загрузки истории: {str(e)}"]
    
    def get_stats_last_3_months(self, cat_name: str) -> str:
        """Рассчитывает статистику за последние 3 месяца"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            three_months_ago = datetime.now() - timedelta(days=90)
            
            # Нормализуем имя для поиска
            search_name = cat_name.strip().lower()
            
            # Собираем записи за последние 3 месяца
            cat_poops = []
            for record in records:
                record_name = record.get('cat_name', '').strip().lower()
                if record_name == search_name:
                    try:
                        timestamp = record.get('timestamp')
                        if timestamp:
                            dt = datetime.fromisoformat(timestamp)
                            if dt >= three_months_ago:
                                cat_poops.append(dt)
                    except:
                        continue
            
            cat_poops.sort()
            
            if len(cat_poops) < 2:
                if len(cat_poops) == 1:
                    return "📊 За последние 3 месяца: только одна какашка. Недостаточно данных для статистики"
                return "📊 За последние 3 месяца записей нет"
            
            # Вычисляем интервалы
            intervals = []
            for i in range(1, len(cat_poops)):
                delta = cat_poops[i] - cat_poops[i-1]
                intervals.append(delta.total_seconds() / 3600)
            
            avg_hours = sum(intervals) / len(intervals)
            
            if avg_hours < 24:
                return f"📊 **Статистика за последние 3 месяца**\n📝 Всего записей: {len(cat_poops)}\n⏱ В среднем каждые {avg_hours:.1f} часов"
            else:
                avg_days = avg_hours / 24
                return f"📊 **Статистика за последние 3 месяца**\n📝 Всего записей: {len(cat_poops)}\n📅 В среднем каждые {avg_days:.1f} дней ({avg_hours:.1f} часов)"
        
        except Exception as e:
            logger.error(f"❌ Ошибка статистики для {cat_name}: {e}")
            return f"❌ Ошибка расчёта статистики: {str(e)}"
    
    def get_all_cats(self) -> List[str]:
        """Возвращает список всех котов"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            records = cats_ws.get_all_records()
            cats = [record['name'] for record in records if record.get('name')]
            logger.info(f"Найдено котов: {len(cats)}")
            return cats
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка котов: {e}")
            return []

# Создаём глобальный экземпляр БД
db = CatPoopDatabase()
