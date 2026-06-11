import asyncio
import json
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from scores import get_match_result, get_todays_results

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATA_FILE = "data.json"

# ── FSM ────────────────────────────────────────────────────────────────────────

class AddMatch(StatesGroup):
    waiting_match_name = State()
    waiting_stage = State()
    waiting_pred_m = State()
    waiting_pred_p = State()

class EnterResult(StatesGroup):
    waiting_match_id = State()
    waiting_result = State()
    waiting_pen_winner = State()

class UpdateFav(StatesGroup):
    waiting_player = State()
    waiting_team = State()
    waiting_stage = State()

class UpdateOut(StatesGroup):
    waiting_player = State()
    waiting_team = State()
    waiting_penalty = State()

# ── Данные ─────────────────────────────────────────────────────────────────────

DEFAULT_STATE = {
    "matches": [
        {"id": 1, "match": "Мексика – ЮАР", "stage": "group",
         "m_pred": "3:0", "p_pred": "2:0", "result": None, "m_pts": None, "p_pts": None, "pen_winner": None},
        {"id": 2, "match": "Южная Корея – Чехия", "stage": "group",
         "m_pred": "1:0", "p_pred": "2:1", "result": None, "m_pts": None, "p_pts": None, "pen_winner": None},
    ],
    "next_id": 3,
    "favorites": {
        "m": [
            {"cont": "Европа",        "team": "Испания",      "pts": 0},
            {"cont": "Юж. Америка",   "team": "Аргентина",    "pts": 0},
            {"cont": "Азия",          "team": "Япония",       "pts": 0},
            {"cont": "Африка",        "team": "Кот-д'Ивуар", "pts": 0},
            {"cont": "CONCACAF/OFC",  "team": "Мексика",      "pts": 0},
        ],
        "p": [
            {"cont": "Европа",        "team": "Португалия",   "pts": 0},
            {"cont": "Юж. Америка",   "team": "Бразилия",     "pts": 0},
            {"cont": "Азия",          "team": "Южная Корея",  "pts": 0},
            {"cont": "Африка",        "team": "Сенегал",      "pts": 0},
            {"cont": "CONCACAF/OFC",  "team": "Канада",       "pts": 0},
        ],
    },
    "outsiders": {
        "m": [
            {"team": "Канада", "penalty": 0}, {"team": "Эквадор", "penalty": 0},
            {"team": "Шотландия", "penalty": 0}, {"team": "Норвегия", "penalty": 0},
            {"team": "Швеция", "penalty": 0}, {"team": "Парагвай", "penalty": 0},
            {"team": "Иран", "penalty": 0}, {"team": "ЮАР", "penalty": 0},
            {"team": "Кабо-Верде", "penalty": 0}, {"team": "Новая Зеландия", "penalty": 0},
            {"team": "Панама", "penalty": 0}, {"team": "Ирак", "penalty": 0},
        ],
        "p": [
            {"team": "Тунис", "penalty": 0}, {"team": "Чехия", "penalty": 0},
            {"team": "Саудовская Аравия", "penalty": 0}, {"team": "Гана", "penalty": 0},
            {"team": "Босния и Герцеговина", "penalty": 0}, {"team": "ДР Конго", "penalty": 0},
            {"team": "Австралия", "penalty": 0}, {"team": "Катар", "penalty": 0},
            {"team": "Иордания", "penalty": 0}, {"team": "Гаити", "penalty": 0},
            {"team": "Кюрасао", "penalty": 0}, {"team": "Узбекистан", "penalty": 0},
        ],
    },
}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_STATE))

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Логика очков ───────────────────────────────────────────────────────────────

def parse_score(s):
    if not s:
        return None
    m = re.match(r'^(\d+)[:\-](\d+)$', str(s).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def calc_pts(pred, result):
    p = parse_score(pred)
    r = parse_score(result)
    if not p or not r:
        return 0
    if p == r:
        return 5
    pd = p[0] - p[1]
    rd = r[0] - r[1]
    if pd == rd:
        return 3
    if (p[0] > p[1] and r[0] > r[1]) or (p[0] < p[1] and r[0] < r[1]):
        return 1
    if p[0] == p[1] and r[0] == r[1]:
        return 3
    return 0

def get_totals(data):
    m_match = sum(m["m_pts"] or 0 for m in data["matches"])
    p_match = sum(m["p_pts"] or 0 for m in data["matches"])
    m_fav   = sum(f["pts"] for f in data["favorites"]["m"])
    p_fav   = sum(f["pts"] for f in data["favorites"]["p"])
    m_out   = sum(o["penalty"] for o in data["outsiders"]["m"])
    p_out   = sum(o["penalty"] for o in data["outsiders"]["p"])
    return {
        "m_match": m_match, "p_match": p_match,
        "m_fav": m_fav,     "p_fav": p_fav,
        "m_out": m_out,     "p_out": p_out,
        "m_total": m_match + m_fav + m_out,
        "p_total": p_match + p_fav + p_out,
    }

# ── Хелперы названий команд ────────────────────────────────────────────────────

def split_match_name(match_name: str):
    """'Мексика – ЮАР' → ('Мексика', 'ЮАР')"""
    for sep in [" – ", " - ", " vs ", " — "]:
        if sep in match_name:
            parts = match_name.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return None, None

# ── Клавиатуры ─────────────────────────────────────────────────────────────────

def main_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📊 Счёт")
    kb.button(text="⚽ Матчи")
    kb.button(text="🌟 Фавориты")
    kb.button(text="💀 Аутсайдеры")
    kb.button(text="➕ Добавить матч")
    kb.button(text="✅ Ввести результат")
    kb.button(text="🔍 Обновить результаты")
    kb.button(text="📈 Аналитика")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup(resize_keyboard=True)

STAGE_LABELS = {
    "group": "Группа",
    "r32": "1/16 финала",
    "r16": "1/8 финала",
    "qf":  "1/4 финала",
    "sf":  "1/2 финала",
    "3rd": "Матч за 3-е место",
    "f":   "Финал",
}

FAV_STAGE_OPTIONS = [
    ("0",  "Не вышел из группы (0)"),
    ("5",  "1/16 финала (+5)"),
    ("10", "1/8 финала (+10)"),
    ("15", "1/4 финала (+15)"),
    ("25", "4-е место (+25)"),
    ("30", "3-е место (+30)"),
    ("40", "2-е место (+40)"),
    ("50", "🏆 Чемпион (+50)"),
]

OUT_STAGE_OPTIONS = [
    ("0",    "Не вышел из группы (0)"),
    ("-10",  "1/16 финала (–10)"),
    ("-20",  "1/8 финала (–20)"),
    ("-30",  "1/4 финала (–30)"),
    ("-40",  "4-е место (–40)"),
    ("-60",  "3-е место (–60)"),
    ("-80",  "2-е место (–80)"),
    ("-100", "🏆 Чемпион (–100)"),
]

def stages_keyboard(options):
    kb = InlineKeyboardBuilder()
    for val, label in options:
        kb.button(text=label, callback_data=f"stage:{val}")
    kb.adjust(1)
    return kb.as_markup()

def stage_keyboard_reply():
    kb = ReplyKeyboardBuilder()
    for key, label in STAGE_LABELS.items():
        kb.button(text=label)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)

# ── Форматирование ─────────────────────────────────────────────────────────────

def fmt_pts(pts):
    if pts == 5: return "🎯 5"
    if pts == 3: return "✅ 3"
    if pts == 1: return "👍 1"
    if pts == 0: return "❌ 0"
    return "–"

def score_message(data):
    t = get_totals(data)
    if t["m_total"] > t["p_total"]:
        leader = f"🟦 Мукаку ведёт +{t['m_total'] - t['p_total']} очков"
    elif t["p_total"] > t["m_total"]:
        leader = f"🟥 Пеналдо ведёт +{t['p_total'] - t['m_total']} очков"
    else:
        leader = "🤝 Счёт равный"
    return (
        f"🏆 <b>ЧМ-2026 — Текущий счёт</b>\n\n"
        f"{leader}\n\n"
        f"<pre>"
        f"{'':22} {'Мукаку':>8} {'Пеналдо':>8}\n"
        f"{'─'*38}\n"
        f"{'Очки за матчи':<22} {t['m_match']:>8} {t['p_match']:>8}\n"
        f"{'Фавориты':<22} {'+'+str(t['m_fav']):>8} {'+'+str(t['p_fav']):>8}\n"
        f"{'Штраф (аутсайдеры)':<22} {t['m_out']:>8} {t['p_out']:>8}\n"
        f"{'─'*38}\n"
        f"{'ИТОГО':<22} {t['m_total']:>8} {t['p_total']:>8}\n"
        f"</pre>"
    )

def matches_message(data):
    played  = [m for m in data["matches"] if m["result"]]
    pending = [m for m in data["matches"] if not m["result"]]
    lines = [f"⚽ <b>Матчи</b> (всего: {len(data['matches'])})\n"]
    if played:
        lines.append("✅ <b>Сыграны:</b>")
        for m in played[-10:]:
            lines.append(
                f"  <b>{m['id']}. {m['match']}</b>\n"
                f"  Мукаку: {m['m_pred']} → {fmt_pts(m['m_pts'])} | "
                f"Пеналдо: {m['p_pred']} → {fmt_pts(m['p_pts'])}\n"
                f"  Счёт: <b>{m['result']}</b>"
            )
    if pending:
        lines.append(f"\n⏳ <b>Ожидают результата ({len(pending)}):</b>")
        for m in pending[:10]:
            lines.append(
                f"  <b>{m['id']}. {m['match']}</b> [{STAGE_LABELS.get(m['stage'], m['stage'])}]\n"
                f"  Мукаку: {m['m_pred'] or '—'} | Пеналдо: {m['p_pred'] or '—'}"
            )
        if len(pending) > 10:
            lines.append(f"  ... и ещё {len(pending) - 10} матчей")
    return "\n".join(lines)

def favorites_message(data):
    lines = ["🌟 <b>Фавориты</b>\n"]
    lines.append(f"<pre>{'Конт.':<14} {'Мукаку':<18} {'Очки':>5} {'Пеналдо':<18} {'Очки':>5}")
    lines.append("─" * 60)
    for fm, fp in zip(data["favorites"]["m"], data["favorites"]["p"]):
        lines.append(f"{fm['cont']:<14} {fm['team']:<18} {fm['pts']:>5} {fp['team']:<18} {fp['pts']:>5}")
    m_sum = sum(f["pts"] for f in data["favorites"]["m"])
    p_sum = sum(f["pts"] for f in data["favorites"]["p"])
    lines.append("─" * 60)
    lines.append(f"{'ИТОГО':<14} {' ':18} {m_sum:>5} {' ':18} {p_sum:>5}")
    lines.append("</pre>")
    return "\n".join(lines)

def outsiders_message(data):
    lines = ["💀 <b>Аутсайдеры</b>\n<pre>"]
    lines.append(f"{'Мукаку':<22} {'Штраф':>6}  {'Пеналдо':<22} {'Штраф':>6}")
    lines.append("─" * 58)
    for om, op in zip(data["outsiders"]["m"], data["outsiders"]["p"]):
        lines.append(f"{om['team']:<22} {om['penalty']:>6}  {op['team']:<22} {op['penalty']:>6}")
    m_sum = sum(o["penalty"] for o in data["outsiders"]["m"])
    p_sum = sum(o["penalty"] for o in data["outsiders"]["p"])
    lines.append("─" * 58)
    lines.append(f"{'ИТОГО':<22} {m_sum:>6}  {'ИТОГО':<22} {p_sum:>6}")
    lines.append("</pre>")
    return "\n".join(lines)

def analytics_message(data):
    played = [m for m in data["matches"] if m["result"]]
    mE=mD=mW=mZ=pE=pD=pW=pZ = 0
    for m in played:
        if m["m_pts"]==5: mE+=1
        elif m["m_pts"]==3: mD+=1
        elif m["m_pts"]==1: mW+=1
        else: mZ+=1
        if m["p_pts"]==5: pE+=1
        elif m["p_pts"]==3: pD+=1
        elif m["p_pts"]==1: pW+=1
        else: pZ+=1
    t = get_totals(data)
    diff = abs(t["m_total"] - t["p_total"])
    leader = "🟦 Мукаку" if t["m_total"] >= t["p_total"] else "🟥 Пеналдо"
    text = (
        f"📈 <b>Аналитика</b>\n\n"
        f"Сыграно матчей: <b>{len(played)}</b> из {len(data['matches'])}\n"
        f"Лидер: <b>{leader}</b> (разрыв: {diff} очков)\n\n"
        f"<pre>{'':26} {'Мукаку':>7} {'Пеналдо':>7}\n{'─'*40}\n"
        f"{'🎯 Точный счёт':<26} {mE:>7} {pE:>7}\n"
        f"{'✅ Угадана разница':<26} {mD:>7} {pD:>7}\n"
        f"{'👍 Угадан победитель':<26} {mW:>7} {pW:>7}\n"
        f"{'❌ Промахи':<26} {mZ:>7} {pZ:>7}\n{'─'*40}\n"
    )
    if played:
        mAcc = round((mE*5+mD*3+mW)/ len(played) *100/5)
        pAcc = round((pE*5+pD*3+pW)/ len(played) *100/5)
        text += f"{'Эффективность %':<26} {mAcc:>6}% {pAcc:>6}%\n"
    text += "</pre>"
    return text

# ── apply_result: записать счёт и пересчитать очки ────────────────────────────

def apply_result(match: dict, result: str, pen_winner: str | None = None):
    match["result"] = result
    match["m_pts"] = calc_pts(match["m_pred"], result)
    match["p_pts"] = calc_pts(match["p_pred"], result)
    if pen_winner:
        match["pen_winner"] = pen_winner
        # +1 за угаданную ничью в основное время (плей-офф)
        for key in ("m_pred", "p_pred"):
            sc = parse_score(match[key])
            pts_key = "m_pts" if key == "m_pred" else "p_pts"
            if sc and sc[0] == sc[1]:
                match[pts_key] += 1

# ── Хэндлеры ──────────────────────────────────────────────────────────────────

from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer(
        "🏆 <b>Прогноз ЧМ-2026</b>\n\n"
        "Трекер игры между 🟦 Мукаку и 🟥 Пеналдо.\n\n"
        "Кнопка <b>🔍 Обновить результаты</b> автоматически подтянет "
        "счета сыгранных матчей из открытой базы данных ЧМ-2026.",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "📊 Счёт")
async def show_score(msg: types.Message):
    await msg.answer(score_message(load_data()))

@dp.message(F.text == "⚽ Матчи")
async def show_matches(msg: types.Message):
    await msg.answer(matches_message(load_data()))

@dp.message(F.text == "🌟 Фавориты")
async def show_favorites(msg: types.Message):
    await msg.answer(favorites_message(load_data()))

@dp.message(F.text == "💀 Аутсайдеры")
async def show_outsiders(msg: types.Message):
    await msg.answer(outsiders_message(load_data()))

@dp.message(F.text == "📈 Аналитика")
async def show_analytics(msg: types.Message):
    await msg.answer(analytics_message(load_data()))

# ── 🔍 Авто-обновление результатов ────────────────────────────────────────────

@dp.message(F.text == "🔍 Обновить результаты")
async def auto_update_results(msg: types.Message):
    wait = await msg.answer("⏳ Запрашиваю данные о матчах ЧМ-2026...")
    data = load_data()
    pending = [m for m in data["matches"] if not m["result"]]

    if not pending:
        await wait.edit_text("✅ Все матчи уже имеют результаты.")
        return

    all_results = await get_todays_results()
    if not all_results:
        await wait.edit_text(
            "⚠️ Не удалось получить данные.\n"
            "Источник: github.com/openfootball/worldcup.json\n"
            "Попробуйте позже или введите счёт вручную."
        )
        return

    updated = []
    needs_pen = []  # плей-офф с ничьей — нужен победитель пенальти

    for m in pending:
        t1, t2 = split_match_name(m["match"])
        if not t1:
            continue
        found = None
        # Сначала ищем по названию из нашей БД
        for r in all_results:
            r1 = r["team1_ru"].lower()
            r2 = r["team2_ru"].lower()
            if (r1 == t1.lower() and r2 == t2.lower()) or \
               (r1 == t2.lower() and r2 == t1.lower()):
                found = r
                break
        if not found:
            continue

        result = found["score_ft"]
        is_playoff = m["stage"] != "group"
        sc = parse_score(result)

        if is_playoff and sc and sc[0] == sc[1]:
            # Есть ли данные о пенальти?
            if found.get("score_p"):
                p = parse_score(found["score_p"])
                pen_winner = found["team1_ru"] if p and p[0] > p[1] else found["team2_ru"]
                apply_result(m, result, pen_winner)
                updated.append(f"  <b>{m['match']}</b>: {result} (пен. → {pen_winner})")
            else:
                # Ничья в плей-офф, пенальти неизвестны — пометим для ручного ввода
                needs_pen.append(m["id"])
                apply_result(m, result)
                updated.append(f"  <b>{m['match']}</b>: {result} ⚠️ нужен победитель пенальти")
        else:
            apply_result(m, result)
            updated.append(
                f"  <b>{m['match']}</b>: {result} "
                f"[М: {fmt_pts(m['m_pts'])} / П: {fmt_pts(m['p_pts'])}]"
            )

    if updated:
        save_data(data)
        text = "✅ <b>Результаты обновлены:</b>\n\n" + "\n".join(updated)
        if needs_pen:
            ids = ", ".join(str(i) for i in needs_pen)
            text += f"\n\n⚠️ Для матчей <b>{ids}</b> введите победителя по пенальти вручную через «✅ Ввести результат»."
        text += f"\n\n{score_message(data)}"
        await wait.edit_text(text)
    else:
        await wait.edit_text(
            "ℹ️ Новых результатов не найдено.\n\n"
            f"Матчей без результата: {len(pending)}\n"
            "Данные обновляются автором ~раз в день после окончания матчей.\n"
            "Источник: <a href='https://github.com/openfootball/worldcup.json'>openfootball/worldcup.json</a>"
        )

# ── Добавление матча ───────────────────────────────────────────────────────────

@dp.message(F.text == "➕ Добавить матч")
async def add_match_start(msg: types.Message, state: FSMContext):
    await state.set_state(AddMatch.waiting_match_name)
    await msg.answer(
        "Введите название матча.\n"
        "Формат: <b>Команда1 – Команда2</b>\n"
        "Пример: <b>Испания – Германия</b>",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(AddMatch.waiting_match_name)
async def add_match_name(msg: types.Message, state: FSMContext):
    await state.update_data(match=msg.text.strip())
    await state.set_state(AddMatch.waiting_stage)
    await msg.answer("Выберите этап турнира:", reply_markup=stage_keyboard_reply())

@dp.message(AddMatch.waiting_stage)
async def add_match_stage(msg: types.Message, state: FSMContext):
    stage_map = {v: k for k, v in STAGE_LABELS.items()}
    stage = stage_map.get(msg.text, "group")
    await state.update_data(stage=stage)
    await state.set_state(AddMatch.waiting_pred_m)
    await msg.answer("Прогноз <b>🟦 Мукаку</b> (например: 2:1):", reply_markup=types.ReplyKeyboardRemove())

@dp.message(AddMatch.waiting_pred_m)
async def add_match_pred_m(msg: types.Message, state: FSMContext):
    if not parse_score(msg.text.strip()):
        await msg.answer("❌ Формат: 2:1. Попробуйте снова:"); return
    await state.update_data(m_pred=msg.text.strip())
    await state.set_state(AddMatch.waiting_pred_p)
    await msg.answer("Прогноз <b>🟥 Пеналдо</b> (например: 1:0):")

@dp.message(AddMatch.waiting_pred_p)
async def add_match_pred_p(msg: types.Message, state: FSMContext):
    pred = msg.text.strip()
    if not parse_score(pred):
        await msg.answer("❌ Формат: 2:1. Попробуйте снова:"); return
    d = await state.get_data()
    await state.clear()
    data = load_data()
    data["matches"].append({
        "id": data["next_id"], "match": d["match"], "stage": d["stage"],
        "m_pred": d["m_pred"], "p_pred": pred,
        "result": None, "m_pts": None, "p_pts": None, "pen_winner": None
    })
    data["next_id"] += 1
    save_data(data)
    await msg.answer(
        f"✅ Матч добавлен!\n\n"
        f"<b>{d['match']}</b> [{STAGE_LABELS.get(d['stage'])}]\n"
        f"🟦 Мукаку: {d['m_pred']} | 🟥 Пеналдо: {pred}\n\n"
        f"Нажмите <b>🔍 Обновить результаты</b> — бот сам найдёт счёт, "
        f"как только матч завершится.",
        reply_markup=main_keyboard()
    )

# ── Ручной ввод результата ─────────────────────────────────────────────────────

@dp.message(F.text == "✅ Ввести результат")
async def enter_result_start(msg: types.Message, state: FSMContext):
    data = load_data()
    pending = [m for m in data["matches"] if not m["result"]]
    if not pending:
        await msg.answer("Нет матчей без результата.", reply_markup=main_keyboard()); return
    lines = ["Введите <b>номер матча</b>:\n"]
    for m in pending:
        lines.append(f"  <b>{m['id']}.</b> {m['match']} [М: {m['m_pred'] or '—'} / П: {m['p_pred'] or '—'}]")
    await state.set_state(EnterResult.waiting_match_id)
    await msg.answer("\n".join(lines), reply_markup=types.ReplyKeyboardRemove())

@dp.message(EnterResult.waiting_match_id)
async def enter_result_id(msg: types.Message, state: FSMContext):
    try:
        mid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число:"); return
    data = load_data()
    match = next((m for m in data["matches"] if m["id"] == mid), None)
    if not match:
        await msg.answer("❌ Матч не найден:"); return
    if match["result"]:
        await msg.answer(f"Результат уже введён: {match['result']}")
        await state.clear(); return
    await state.update_data(match_id=mid)
    await state.set_state(EnterResult.waiting_result)
    await msg.answer(f"Введите счёт <b>{match['match']}</b> (например: 2:1):")

@dp.message(EnterResult.waiting_result)
async def enter_result_score(msg: types.Message, state: FSMContext):
    result = msg.text.strip()
    if not parse_score(result):
        await msg.answer("❌ Формат: 2:1. Попробуйте снова:"); return
    d = await state.get_data()
    data = load_data()
    match = next((m for m in data["matches"] if m["id"] == d["match_id"]), None)
    r = parse_score(result)
    match["result"] = result
    match["m_pts"] = calc_pts(match["m_pred"], result)
    match["p_pts"] = calc_pts(match["p_pred"], result)
    if match["stage"] != "group" and r and r[0] == r[1]:
        await state.update_data(result=result)
        await state.set_state(EnterResult.waiting_pen_winner)
        save_data(data)
        await msg.answer("Ничья! Кто прошёл дальше по пенальти? Введите название команды:")
        return
    save_data(data)
    await state.clear()
    await msg.answer(
        f"✅ Результат сохранён!\n\n"
        f"<b>{match['match']}</b>: {result}\n"
        f"🟦 Мукаку ({match['m_pred']}): {fmt_pts(match['m_pts'])}\n"
        f"🟥 Пеналдо ({match['p_pred']}): {fmt_pts(match['p_pts'])}",
        reply_markup=main_keyboard()
    )

@dp.message(EnterResult.waiting_pen_winner)
async def enter_pen_winner(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    data = load_data()
    match = next((m for m in data["matches"] if m["id"] == d["match_id"]), None)
    apply_result(match, match["result"], msg.text.strip())
    save_data(data)
    await state.clear()
    await msg.answer(
        f"✅ Готово!\n\n"
        f"<b>{match['match']}</b>: {match['result']} (пен. → {msg.text.strip()})\n"
        f"🟦 Мукаку ({match['m_pred']}): {fmt_pts(match['m_pts'])}\n"
        f"🟥 Пеналдо ({match['p_pred']}): {fmt_pts(match['p_pts'])}",
        reply_markup=main_keyboard()
    )

# ── Фавориты ───────────────────────────────────────────────────────────────────

@dp.message(Command("fav"))
async def fav_start(msg: types.Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🟦 Мукаку", callback_data="fav_player:m")
    kb.button(text="🟥 Пеналдо", callback_data="fav_player:p")
    await state.set_state(UpdateFav.waiting_player)
    await msg.answer("Чьего фаворита обновляем?", reply_markup=kb.as_markup())

@dp.callback_query(UpdateFav.waiting_player, F.data.startswith("fav_player:"))
async def fav_player(call: types.CallbackQuery, state: FSMContext):
    player = call.data.split(":")[1]
    await state.update_data(player=player)
    data = load_data()
    kb = InlineKeyboardBuilder()
    for f in data["favorites"][player]:
        kb.button(text=f["team"], callback_data=f"fav_team:{f['team']}")
    kb.adjust(2)
    await state.set_state(UpdateFav.waiting_team)
    await call.message.edit_text("Выберите команду:", reply_markup=kb.as_markup())

@dp.callback_query(UpdateFav.waiting_team, F.data.startswith("fav_team:"))
async def fav_team(call: types.CallbackQuery, state: FSMContext):
    team = call.data[9:]
    await state.update_data(team=team)
    await state.set_state(UpdateFav.waiting_stage)
    await call.message.edit_text(
        f"Стадия выхода <b>{team}</b>:",
        reply_markup=stages_keyboard(FAV_STAGE_OPTIONS)
    )

@dp.callback_query(UpdateFav.waiting_stage, F.data.startswith("stage:"))
async def fav_stage(call: types.CallbackQuery, state: FSMContext):
    pts = int(call.data.split(":")[1])
    d = await state.get_data()
    await state.clear()
    data = load_data()
    for f in data["favorites"][d["player"]]:
        if f["team"] == d["team"]:
            f["pts"] = pts; break
    save_data(data)
    pname = "Мукаку" if d["player"] == "m" else "Пеналдо"
    await call.message.edit_text(
        f"✅ {pname} → {d['team']}: <b>{'+' if pts >= 0 else ''}{pts}</b>"
    )
    await call.message.answer(score_message(data), reply_markup=main_keyboard())

# ── Аутсайдеры ─────────────────────────────────────────────────────────────────

@dp.message(Command("out"))
async def out_start(msg: types.Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🟦 Мукаку", callback_data="out_player:m")
    kb.button(text="🟥 Пеналдо", callback_data="out_player:p")
    await state.set_state(UpdateOut.waiting_player)
    await msg.answer("Чьего аутсайдера обновляем?", reply_markup=kb.as_markup())

@dp.callback_query(UpdateOut.waiting_player, F.data.startswith("out_player:"))
async def out_player(call: types.CallbackQuery, state: FSMContext):
    player = call.data.split(":")[1]
    await state.update_data(player=player)
    data = load_data()
    kb = InlineKeyboardBuilder()
    for o in data["outsiders"][player]:
        kb.button(text=o["team"], callback_data=f"out_team:{o['team']}")
    kb.adjust(2)
    await state.set_state(UpdateOut.waiting_team)
    await call.message.edit_text("Выберите команду:", reply_markup=kb.as_markup())

@dp.callback_query(UpdateOut.waiting_team, F.data.startswith("out_team:"))
async def out_team(call: types.CallbackQuery, state: FSMContext):
    team = call.data[9:]
    await state.update_data(team=team)
    await state.set_state(UpdateOut.waiting_penalty)
    await call.message.edit_text(
        f"Стадия выхода <b>{team}</b>:",
        reply_markup=stages_keyboard(OUT_STAGE_OPTIONS)
    )

@dp.callback_query(UpdateOut.waiting_penalty, F.data.startswith("stage:"))
async def out_stage(call: types.CallbackQuery, state: FSMContext):
    pen = int(call.data.split(":")[1])
    d = await state.get_data()
    await state.clear()
    data = load_data()
    for o in data["outsiders"][d["player"]]:
        if o["team"] == d["team"]:
            o["penalty"] = pen; break
    save_data(data)
    pname = "Мукаку" if d["player"] == "m" else "Пеналдо"
    await call.message.edit_text(f"✅ {pname} → {d['team']}: <b>{pen}</b> очков")
    await call.message.answer(score_message(data), reply_markup=main_keyboard())

# ── Запуск ─────────────────────────────────────────────────────────────────────

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
