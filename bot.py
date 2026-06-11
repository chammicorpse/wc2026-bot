import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import BOT_TOKEN
from google_sheets_db import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

NAME_INPUT = 1
SWITCH_CAT_INPUT = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [
            InlineKeyboardButton("🐱 Познакомиться с котом", callback_data="new_cat"),
            InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data.pop("current_cat", None)
    
    await update.message.reply_text(
        "🐾 Привет! Я бот «Кот покакал».\n"
        "Все данные сохраняются в Google Sheets у Кати!\n"
        "Выбери действие:",
        reply_markup=reply_markup
    )

async def show_cat_menu(update: Update, cat_name: str):
    """Показывает меню действий с котом в виде сетки 2x2"""
    keyboard = [
        [
            InlineKeyboardButton("💩 Кот покакал", callback_data="poop"),
            InlineKeyboardButton("⏰ Как давно?", callback_data="when")
        ],
        [
            InlineKeyboardButton("📜 История", callback_data="history"),
            InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"Что сделал 🐱 Кот: **{cat_name}**?"
    
    if isinstance(update, Update) and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "new_cat":
            await query.edit_message_text("📝 Введите имя кота:")
            return NAME_INPUT
        
        elif query.data == "switch_cat":
            await query.edit_message_text("🔄 Введите имя кота, чей журнал хотите посмотреть:")
            return SWITCH_CAT_INPUT
        
        elif query.data == "switch_cat_from_menu":
            await query.edit_message_text("🔄 Введите имя кота, чей журнал хотите посмотреть:")
            return SWITCH_CAT_INPUT
        
        elif query.data == "poop":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            
            try:
                poop_time = db.add_poop(cat_name)
                await query.edit_message_text(
                    f"💩 Кот {cat_name} покакал! 💩\n"
                    f"Время: {poop_time.strftime('%d.%m.%y %H:%M')}"
                )
                await show_cat_menu(update, cat_name)
            except Exception as e:
                logger.error(f"Ошибка при добавлении какашки: {e}")
                await query.edit_message_text(f"❌ Ошибка: {str(e)}")
        
        elif query.data == "when":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            
            result = db.get_time_since_last_poop(cat_name)
            await query.edit_message_text(result, parse_mode="Markdown")
            await show_cat_menu(update, cat_name)
        
        elif query.data == "history":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            
            history = db.get_history(cat_name)
            stats = db.get_stats_last_3_months(cat_name)
            
            if history and len(history) > 0:
                history_text = "\n".join(history)
            else:
                history_text = "📭 История пуста"
            
            text = f"📜 **История кота {cat_name}:**\n{history_text}\n{stats}"
            
            await query.message.reply_text(text, parse_mode="Markdown")
            await show_cat_menu(update, cat_name)
    
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени нового кота"""
    name = update.message.text.strip()
    
    # Очищаем имя от лишних пробелов и приводим к нормальному виду
    name = ' '.join(name.split())
    
    logger.info(f"Пользователь ввёл имя: '{name}'")
    
    if not name:
        await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return NAME_INPUT
    
    # Проверяем существование кота (с нормализацией)
    cat_exists = db.cat_exists(name)
    logger.info(f"Проверка существования кота '{name}': {cat_exists}")
    
    if cat_exists:
        await update.message.reply_text(
            f"😸 Круто! Тезка! Кот с именем '{name}' уже существует.\n\n"
            "Пожалуйста, введите другое имя кота:"
        )
        # Важно: просто возвращаем NAME_INPUT, НЕ завершая ConversationHandler
        return NAME_INPUT
    
    try:
        # Добавляем кота
        db.add_cat(name)
        context.user_data["current_cat"] = name
        
        await update.message.reply_text(f"✅ Познакомились! Теперь у тебя есть кот {name}")
        
        # Показываем меню с сеткой 2x2
        keyboard = [
            [
                InlineKeyboardButton("💩 Кот покакал", callback_data="poop"),
                InlineKeyboardButton("⏰ Как давно?", callback_data="when")
            ],
            [
                InlineKeyboardButton("📜 История", callback_data="history"),
                InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🐱 Кот: **{name}**\n\nЧто он сделал?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении кота: {e}")
        await update.message.reply_text("❌ Произошла ошибка при создании кота. Попробуйте позже.")
        return ConversationHandler.END
    
    return ConversationHandler.END

async def switch_cat_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода имени существующего кота для переключения"""
    name = update.message.text.strip()
    
    if not name:
        await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return SWITCH_CAT_INPUT
    
    if not db.cat_exists(name):
        await update.message.reply_text(
            f"❌ Кот с именем '{name}' не найден.\n\n"
            "Сначала познакомьтесь с котом через /start → Познакомиться с котом"
        )
        keyboard = [
            [
                InlineKeyboardButton("🐱 Познакомиться с котом", callback_data="new_cat"),
                InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🐾 Выберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    context.user_data["current_cat"] = name
    await show_cat_menu(update, name)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text("❌ Действие отменено. Нажмите /start")
    return ConversationHandler.END

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_new_cat = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^new_cat$")],
        states={
            NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_switch_cat = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^switch_cat$"),
            CallbackQueryHandler(button_handler, pattern="^switch_cat_from_menu$")
        ],
        states={
            SWITCH_CAT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, switch_cat_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_new_cat)
    app.add_handler(conv_switch_cat)
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(poop|when|history)$"))
    
    logger.info("🚀 Бот с Google Sheets запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
