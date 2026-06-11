import json
import os
from datetime import datetime, timedelta
import statistics

# Определяем путь к папке с данными
# На Railway нужно использовать постоянный путь
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Функция для гарантированного создания папки
def ensure_data_dir():
    """Создаёт папку data, если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"📁 Создана папка для данных: {DATA_DIR}")
    return DATA_DIR

def get_cat_file(cat_name: str) -> str:
    """Возвращает путь к файлу кота, гарантируя существование папки"""
    ensure_data_dir()  # ВАЖНО: создаём папку при каждом обращении
    
    # Очищаем имя файла от недопустимых символов
    safe_name = "".join(c for c in cat_name if c.isalnum() or c in " _-").strip()
    if not safe_name:
        safe_name = "unknown"
    
    filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
    return filepath

def load_cat_data(cat_name: str) -> dict:
    """Загружает данные кота из файла"""
    filepath = get_cat_file(cat_name)
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Если файл повреждён, создаём новый
            return {"name": cat_name, "poops": []}
    else:
        return {"name": cat_name, "poops": []}

def save_cat_data(cat_name: str, data: dict):
    """Сохраняет данные кота в файл"""
    filepath = get_cat_file(cat_name)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Сохранён кот {cat_name}, записей: {len(data['poops'])}")
    except Exception as e:
        print(f"❌ Ошибка сохранения {cat_name}: {e}")

def add_poop(cat_name: str) -> datetime:
    """Добавляет запись о том, что кот покакал"""
    data = load_cat_data(cat_name)
    now = datetime.now().isoformat()
    data["poops"].append(now)
    save_cat_data(cat_name, data)
    return datetime.fromisoformat(now)

def get_last_poop_time(cat_name: str):
    """Возвращает время последней какашки"""
    data = load_cat_data(cat_name)
    if not data["poops"]:
        return None
    last = data["poops"][-1]
    return datetime.fromisoformat(last)

def get_time_since_last_poop(cat_name: str) -> str:
    """Возвращает человеко-читаемое время с последней какашки"""
    last_time = get_last_poop_time(cat_name)
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

def get_history(cat_name: str, limit: int = 10):
    """Возвращает последние N записей истории"""
    data = load_cat_data(cat_name)
    poops = data["poops"][-limit:][::-1]  # последние, в обратном порядке
    
    if not poops:
        return ["📭 История пуста"]
    
    result = []
    for i, p in enumerate(poops, 1):
        dt = datetime.fromisoformat(p)
        result.append(f"{i}. {dt.strftime('%d.%m.%Y %H:%M:%S')}")
    return result

def get_stats_last_3_months(cat_name: str) -> str:
    """Рассчитывает статистику за последние 3 месяца"""
    data = load_cat_data(cat_name)
    three_months_ago = datetime.now() - timedelta(days=90)
    
    # Фильтруем записи за последние 3 месяца
    recent_poops = []
    for p in data["poops"]:
        dt = datetime.fromisoformat(p)
        if dt >= three_months_ago:
            recent_poops.append(dt)
    
    if len(recent_poops) < 2:
        if len(recent_poops) == 1:
            return "📊 За последние 3 месяца: только одна какашка. Недостаточно данных для статистики"
        return "📊 За последние 3 месяца записей нет"
    
    # Вычисляем интервалы между какашками
    intervals = []
    for i in range(1, len(recent_poops)):
        delta = recent_poops[i] - recent_poops[i-1]
        intervals.append(delta.total_seconds() / 3600)  # в часах
    
    avg_hours = sum(intervals) / len(intervals)
    
    if avg_hours < 24:
        return f"📊 За последние 3 месяца (всего {len(recent_poops)} раз):\n⏱ В среднем каждые {avg_hours:.1f} часов"
    else:
        avg_days = avg_hours / 24
        return f"📊 За последние 3 месяца (всего {len(recent_poops)} раз):\n📅 В среднем каждые {avg_days:.1f} дней"

def get_all_cat_names():
    """Возвращает список всех имён котов"""
    ensure_data_dir()
    cats = []
    try:
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json"):
                name = filename[:-5]
                cats.append(name)
    except FileNotFoundError:
        pass
    return cats

def cat_exists(cat_name: str) -> bool:
    """Проверяет, существует ли кот с таким именем"""
    return os.path.exists(get_cat_file(cat_name))
