import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_cat_file(cat_name: str) -> str:
    safe_name = "".join(c for c in cat_name if c.isalnum() or c in " _-").strip()
    if not safe_name:
        safe_name = "unknown"
    return os.path.join(DATA_DIR, f"{safe_name}.json")

def load_cat_data(cat_name: str) -> dict:
    filepath = get_cat_file(cat_name)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"name": cat_name, "poops": []}

def save_cat_data(cat_name: str, data: dict):
    filepath = get_cat_file(cat_name)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_poop(cat_name: str) -> datetime:
    data = load_cat_data(cat_name)
    now = datetime.now().isoformat()
    data["poops"].append(now)
    save_cat_data(cat_name, data)
    return datetime.fromisoformat(now)

def get_last_poop_time(cat_name: str):
    data = load_cat_data(cat_name)
    if not data["poops"]:
        return None
    last = data["poops"][-1]
    return datetime.fromisoformat(last)

def get_time_since_last_poop(cat_name: str) -> str:
    last_time = get_last_poop_time(cat_name)
    if not last_time:
        return "😿 У кота пока нет записей о том, что он какал!"
    
    now = datetime.now()
    diff = now - last_time
    
    hours = diff.total_seconds() // 3600
    minutes = (diff.total_seconds() % 3600) // 60
    
    if hours >= 24:
        days = hours // 24
        remainder_hours = hours % 24
        return f"📅 Кот покакал {int(days)} дн. {int(remainder_hours)} ч. {int(minutes)} мин. назад"
    else:
        return f"⏰ Кот покакал {int(hours)} ч. {int(minutes)} мин. назад"

def get_history(cat_name: str, limit: int = 10):
    data = load_cat_data(cat_name)
    poops = data["poops"][-limit:][::-1]
    result = []
    for i, p in enumerate(poops, 1):
        dt = datetime.fromisoformat(p)
        result.append(f"{i}. {dt.strftime('%d.%m.%Y %H:%M:%S')}")
    return result if result else ["📭 История пуста"]

def get_stats_last_3_months(cat_name: str) -> str:
    data = load_cat_data(cat_name)
    three_months_ago = datetime.now() - timedelta(days=90)
    
    recent_poops = []
    for p in data["poops"]:
        dt = datetime.fromisoformat(p)
        if dt >= three_months_ago:
            recent_poops.append(dt)
    
    if len(recent_poops) < 2:
        return "📊 Недостаточно данных за последние 3 месяца для статистики"
    
    intervals = []
    for i in range(1, len(recent_poops)):
        delta = recent_poops[i] - recent_poops[i-1]
        intervals.append(delta.total_seconds() / 3600)  # в часах
    
    avg_hours = statistics.mean(intervals)
    avg_days = avg_hours / 24
    
    if avg_days < 1:
        return f"📊 За последние 3 месяца: кот какал в среднем каждые {avg_hours:.1f} часов"
    else:
        return f"📊 За последние 3 месяца: кот какал в среднем каждые {avg_days:.1f} дней ({avg_hours:.1f} часов)"

def get_all_cat_names():
    cats = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            name = filename[:-5]
            cats.append(name)
    return cats

def cat_exists(cat_name: str) -> bool:
    return os.path.exists(get_cat_file(cat_name))
