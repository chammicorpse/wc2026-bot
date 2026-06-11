import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json
from typing import List, Dict, Optional

class CatPoopDatabase:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.setup_connection()
    
    def setup_connection(self):
        """Подключение к Google Sheets"""
        try:
            # Для Railway: credentials хранятся в переменной окружения
            creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            
            if creds_json:
                # Если credentials в переменной окружения (для Railway)
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            else:
                # Локальная разработка: файл credentials.json
                creds = Credentials.from_service_account_file(
                    'credentials.json',
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
            
            self.client = gspread.authorize(creds)
            
            # Открываем таблицу по ID
            sheet_key = os.getenv("GOOGLE_SHEETS_KEY")
            if not sheet_key:
                raise ValueError("GOOGLE_SHEETS_KEY not found!")
            
            self.sheet = self.client.open_by_key(sheet_key)
            self.init_sheets()
            print("✅ Подключение к Google Sheets установлено")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise
    
    def init_sheets(self):
        """Создаёт необходимые листы, если их нет"""
        try:
            # Лист для котов
            try:
                cats_worksheet = self.sheet.worksheet("cats")
            except gspread.WorksheetNotFound:
                cats_worksheet = self.sheet.add_worksheet("cats", rows=1, cols=3)
                cats_worksheet.append_row(["name", "created_at", "last_updated"])
            
            # Лист для записей о какашках
            try:
                self.sheet.worksheet("poops")
            except gspread.WorksheetNotFound:
                poops_worksheet = self.sheet.add_worksheet("poops", rows=1, cols=4)
                poops_worksheet.append_row(["cat_name", "timestamp", "date", "time"])
            
        except Exception as e:
            print(f"⚠️ Ошибка при инициализации листов: {e}")
    
    def add_cat(self, cat_name: str) -> bool:
        """Добавляет нового кота"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            
            # Проверяем, существует ли уже кот
            existing = cats_ws.findall(cat_name)
            if existing:
                return False
            
            now = datetime.now().isoformat()
            cats_ws.append_row([cat_name, now, now])
            return True
        except Exception as e:
            print(f"Ошибка добавления кота: {e}")
            return False
    
    def cat_exists(self, cat_name: str) -> bool:
        """Проверяет существование кота"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            cells = cats_ws.findall(cat_name)
            return len(cells) > 0
        except Exception as e:
            print(f"Ошибка проверки кота: {e}")
            return False
    
    def add_poop(self, cat_name: str) -> datetime:
        """Добавляет запись о какашке"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            now = datetime.now()
            
            poops_ws.append_row([
                cat_name,
                now.isoformat(),
                now.strftime("%d.%m.%Y"),
                now.strftime("%H:%M:%S")
            ])
            
            # Обновляем last_updated у кота
            cats_ws = self.sheet.worksheet("cats")
            cell = cats_ws.find(cat_name)
            if cell:
                cats_ws.update(f"C{cell.row}", now.isoformat())
            
            return now
        except Exception as e:
            print(f"Ошибка добавления какашки: {e}")
            raise
    
    def get_last_poop_time(self, cat_name: str) -> Optional[datetime]:
        """Получает время последней какашки"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            cat_poops = [r for r in records if r['cat_name'] == cat_name]
            if not cat_poops:
                return None
            
            last_poop = max(cat_poops, key=lambda x: x['timestamp'])
            return datetime.fromisoformat(last_poop['timestamp'])
        except Exception as e:
            print(f"Ошибка получения последней какашки: {e}")
            return None
    
    def get_time_since_last_poop(self, cat_name: str) -> str:
        """Возвращает время с последней какашки"""
        last_time = self.get_last_poop_time(cat_name)
        
        if not last_time:
            return "😿 У кота нет записей о том, что он какал!"
        
        now = datetime.now()
        diff = now - last_time
        
        total_seconds = diff.total_seconds()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours >= 24:
            days = hours // 24
            remainder_hours = hours % 24
            if remainder_hours > 0:
                return f"📅 Кот покакал {int(days)} дн. {int(remainder_hours)} ч. {int(minutes)} мин. назад"
            else:
                return f"📅 Кот покакал {int(days)} дн. {int(minutes)} мин. назад"
        elif hours > 0:
            return f"⏰ Кот покакал {int(hours)} ч. {int(minutes)} мин. назад"
        else:
            return f"⏰ Кот покакал {int(minutes)} мин. назад"
    
    def get_history(self, cat_name: str, limit: int = 10) -> List[str]:
        """Возвращает последние записи истории"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            cat_poops = [r for r in records if r['cat_name'] == cat_name]
            cat_poops.sort(key=lambda x: x['timestamp'], reverse=True)
            
            if not cat_poops:
                return ["📭 История пуста"]
            
            result = []
            for i, poop in enumerate(cat_poops[:limit], 1):
                dt = datetime.fromisoformat(poop['timestamp'])
                result.append(f"{i}. {dt.strftime('%d.%m.%Y %H:%M:%S')}")
            
            return result
        except Exception as e:
            print(f"Ошибка получения истории: {e}")
            return ["❌ Ошибка загрузки истории"]
    
    def get_stats_last_3_months(self, cat_name: str) -> str:
        """Рассчитывает статистику за последние 3 месяца"""
        try:
            poops_ws = self.sheet.worksheet("poops")
            records = poops_ws.get_all_records()
            
            three_months_ago = datetime.now() - timedelta(days=90)
            
            cat_poops = [
                datetime.fromisoformat(r['timestamp']) 
                for r in records 
                if r['cat_name'] == cat_name 
                and datetime.fromisoformat(r['timestamp']) >= three_months_ago
            ]
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
                return f"📊 За последние 3 месяца (всего {len(cat_poops)} раз):\n⏱ В среднем каждые {avg_hours:.1f} часов"
            else:
                avg_days = avg_hours / 24
                return f"📊 За последние 3 месяца (всего {len(cat_poops)} раз):\n📅 В среднем каждые {avg_days:.1f} дней"
        
        except Exception as e:
            print(f"Ошибка статистики: {e}")
            return "❌ Ошибка расчёта статистики"
    
    def get_all_cats(self) -> List[str]:
        """Возвращает список всех котов"""
        try:
            cats_ws = self.sheet.worksheet("cats")
            records = cats_ws.get_all_records()
            return [r['name'] for r in records]
        except Exception as e:
            print(f"Ошибка получения списка котов: {e}")
            return []

# Создаём глобальный экземпляр БД
db = CatPoopDatabase()
