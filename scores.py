"""
Модуль получения результатов ЧМ-2026.

Источник: openfootball/worldcup.json — бесплатный публичный JSON без ключа API,
обновляется автором ~1 раз в день.
URL: https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json

Структура одного матча в JSON:
{
  "round": "Matchday 1",
  "date": "2026-06-11",
  "team1": "Mexico",
  "team2": "South Africa",
  "group": "Group A",
  "score": {"ft": [2, 0]}        # появляется после окончания матча
}

Для плей-офф поле score может содержать:
  {"ft": [1, 1], "et": [1, 1], "p": [4, 3]}
"""

import aiohttp
import asyncio
import re
from difflib import get_close_matches

JSON_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

# Словарь: английские названия → русские (из нашей игры)
TEAM_MAP = {
    "Mexico":               "Мексика",
    "South Africa":         "ЮАР",
    "South Korea":          "Южная Корея",
    "Czech Republic":       "Чехия",
    "Canada":               "Канада",
    "Bosnia & Herzegovina": "Босния и Герцеговина",
    "Qatar":                "Катар",
    "Switzerland":          "Швейцария",
    "Brazil":               "Бразилия",
    "Morocco":              "Марокко",
    "Haiti":                "Гаити",
    "Scotland":             "Шотландия",
    "USA":                  "США",
    "Paraguay":             "Парагвай",
    "Australia":            "Австралия",
    "Turkey":               "Турция",
    "Germany":              "Германия",
    "Curaçao":              "Кюрасао",
    "Ivory Coast":          "Кот-д'Ивуар",
    "Ecuador":              "Эквадор",
    "Netherlands":          "Нидерланды",
    "Japan":                "Япония",
    "Sweden":               "Швеция",
    "Tunisia":              "Тунис",
    "Belgium":              "Бельгия",
    "Egypt":                "Египет",
    "Iran":                 "Иран",
    "New Zealand":          "Новая Зеландия",
    "Spain":                "Испания",
    "Cape Verde":           "Кабо-Верде",
    "Saudi Arabia":         "Саудовская Аравия",
    "Uruguay":              "Уругвай",
    "France":               "Франция",
    "Senegal":              "Сенегал",
    "Iraq":                 "Ирак",
    "Norway":               "Норвегия",
    "Argentina":            "Аргентина",
    "Algeria":              "Алжир",
    "Austria":              "Австрия",
    "Jordan":               "Иордания",
    "Portugal":             "Португалия",
    "DR Congo":             "ДР Конго",
    "Uzbekistan":           "Узбекистан",
    "Colombia":             "Колумбия",
    "England":              "Англия",
    "Croatia":              "Хорватия",
    "Ghana":                "Гана",
    "Panama":               "Панама",
}

# Обратный словарь: русские → английские
TEAM_MAP_RU = {v: k for k, v in TEAM_MAP.items()}


def _en(ru_name: str) -> str | None:
    """Русское название → английское."""
    return TEAM_MAP_RU.get(ru_name)


def _ru(en_name: str) -> str:
    """Английское → русское (с фолбэком)."""
    return TEAM_MAP.get(en_name, en_name)


async def fetch_all_results() -> list[dict]:
    """Скачать JSON и вернуть список матчей с результатами."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(JSON_URL) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
    except Exception:
        return []

    # JSON structure: {"name": "...", "matches": [...]}
    # Each match: {"round": "Matchday 1", "team1": "Mexico", "team2": "South Africa",
    #              "score": {"ft": [2, 0]}, ...}
    results = []
    for m in data.get("matches", []):
        score = m.get("score")
        if not score:
            continue
        ft = score.get("ft")
        if ft is None or len(ft) < 2:
            continue
        p = score.get("p")  # пенальти
        entry = {
            "team1_en": m.get("team1", ""),
            "team2_en": m.get("team2", ""),
            "team1_ru": _ru(m.get("team1", "")),
            "team2_ru": _ru(m.get("team2", "")),
            "score_ft": f"{ft[0]}:{ft[1]}",
            "score_p": f"{p[0]}:{p[1]}" if p else None,
            "date": m.get("date", ""),
            "round": m.get("round", ""),
        }
        results.append(entry)
    return results


def _normalize(name: str) -> str:
    """Убрать лишние пробелы, привести к нижнему регистру."""
    return re.sub(r'\s+', ' ', name).strip().lower()


def find_match_result(team1_ru: str, team2_ru: str, all_results: list[dict]) -> dict | None:
    """
    Найти результат матча по русским названиям команд (нечёткий поиск).
    Возвращает dict с ключами score_ft, score_p или None.
    """
    t1 = _normalize(team1_ru)
    t2 = _normalize(team2_ru)

    for r in all_results:
        r1 = _normalize(r["team1_ru"])
        r2 = _normalize(r["team2_ru"])
        if (r1 == t1 and r2 == t2) or (r1 == t2 and r2 == t1):
            return r

    # Нечёткий поиск — на случай небольших расхождений в названиях
    all_ru_names = list({_normalize(r["team1_ru"]) for r in all_results} |
                        {_normalize(r["team2_ru"]) for r in all_results})
    close1 = get_close_matches(t1, all_ru_names, n=1, cutoff=0.75)
    close2 = get_close_matches(t2, all_ru_names, n=1, cutoff=0.75)
    if close1 and close2:
        c1, c2 = close1[0], close2[0]
        for r in all_results:
            r1 = _normalize(r["team1_ru"])
            r2 = _normalize(r["team2_ru"])
            if (r1 == c1 and r2 == c2) or (r1 == c2 and r2 == c1):
                return r

    return None


async def get_match_result(team1_ru: str, team2_ru: str) -> dict | None:
    """
    Основная функция для использования в боте.
    Возвращает:
      {"score_ft": "2:1", "score_p": None, "team1_ru": ..., "team2_ru": ...}
      или None если матч ещё не сыгран / не найден.
    """
    all_results = await fetch_all_results()
    return find_match_result(team1_ru, team2_ru, all_results)


async def get_todays_results() -> list[dict]:
    """Все сыгранные матчи из источника."""
    return await fetch_all_results()
