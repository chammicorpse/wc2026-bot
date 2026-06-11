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
    keyboard = [
        [InlineKeyboardButton("🐱 Познакомиться с котом", callback_data="new_cat")],
        [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🐾 Привет! Я бот «Кот покакал».\n\n"
        "Все данные сохраняются в Google Sheets!\n\n"
        "Выбери действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "new_cat":
            await query.edit_message_text("📝 Введите имя кота:")
            return NAME_INPUT
        
        elif query.data == "switch_cat":
            await query.edit_message_text("🔄 Введите имя кота, чей журнал хотите посмотреть:")
            return SWITCH_CAT_INPUT
        
        elif query.data.startswith("cat_"):
            cat_name = query.data[4:]
            context.user_data["current_cat"] = cat_name
            await show_cat_actions(query.message, cat_name)
        
        elif query.data == "poop":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            poop_time = db.add_poop(cat_name)
            await query.edit_message_text(
                f"💩 Кот {cat_name} покакал!\n"
                f"🕐 Время: {poop_time.strftime('%d.%m.%Y %H:%M:%S')}"
            )
            await show_cat_actions(query.message, cat_name)
        
        elif query.data == "when":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            result = db.get_time_since_last_poop(cat_name)
            await query.edit_message_text(result)
            await show_cat_actions(query.message, cat_name)
        
        elif query.data == "history":
            cat_name = context.user_data.get("current_cat")
            if not cat_name:
                await query.edit_message_text("❌ Ошибка: кот не выбран. Нажмите /start")
                return
            
            # Получаем историю и статистику
            logger.info(f"Запрос истории для кота: {cat_name}")
            history = db.get_history(cat_name)
            stats = db.get_stats_last_3_months(cat_name)
            
            # Формируем текст
            if history and len(history) > 0:
                history_text = "\n".join(history)
            else:
                history_text = "📭 История пуста"
            
            text = f"📜 **История кота {cat_name}:**\n\n{history_text}\n\n{stats}"
            
            # Отправляем новым сообщением, а не редактируем старое
            await query.message.reply_text(text, parse_mode="Markdown")
            # Показываем меню действий заново
            await show_cat_actions(query.message, cat_name)
        
        elif query.data == "switch_cat_from_menu":
            await query.edit_message_text("🔄 Введите имя кота, чей журнал хотите посмотреть:")
            return SWITCH_CAT_INPUT
    
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def show_cat_actions(message, cat_name: str):
    """Показывает меню действий с котом"""
    keyboard = [
        [InlineKeyboardButton("💩 Кот покакал", callback_data="poop")],
        [InlineKeyboardButton("⏰ Как давно покакал кот?", callback_data="when")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await message.edit_text(
            f"🐱 Кот: **{cat_name}**\n\nЧто он сделал?", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при показе меню: {e}")
        await message.reply_text(
            f"🐱 Кот: **{cat_name}**\n\nЧто он сделал?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    if not name:
        await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return NAME_INPUT
    
    if db.cat_exists(name):
        await update.message.reply_text(
            "😸 Круто! Тезка! Но давай другое имя?\n\n"
            "Введите другое имя кота:"
        )
        return NAME_INPUT
    
    try:
        # Добавляем кота
        db.add_cat(name)
        context.user_data["current_cat"] = name
        
        await update.message.reply_text(f"✅ Познакомились! Теперь у тебя есть кот {name}")
        
        keyboard = [
            [InlineKeyboardButton("💩 Кот покакал", callback_data="poop")],
            [InlineKeyboardButton("⏰ Как давно покакал кот?", callback_data="when")],
            [InlineKeyboardButton("📜 История", callback_data="history")],
            [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")]
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

async def switch_cat_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    if not name:
        await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return SWITCH_CAT_INPUT
    
    if not db.cat_exists(name):
        await update.message.reply_text(
            f"❌ Кот с именем '{name}' не найден.\n"
            "Сначала познакомьтесь с котом через /start → Познакомиться с котом"
        )
        await start(update, context)
        return ConversationHandler.END
    
    context.user_data["current_cat"] = name
    
    keyboard = [
        [InlineKeyboardButton("💩 Кот покакал", callback_data="poop")],
        [InlineKeyboardButton("⏰ Как давно покакал кот?", callback_data="when")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🐱 Переключились на кота: **{name}**\n\nЧто он сделал?",
        parse_mode="Markdown", 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено. Нажмите /start")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_new_cat = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^new_cat$")],
        states={
            NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_switch_cat = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^switch_cat$")],
        states={
            SWITCH_CAT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, switch_cat_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_new_cat)
    app.add_handler(conv_switch_cat)
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(cat_|poop|when|history|switch_cat_from_menu)"))
    
    logger.info("Бот с Google Sheets запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
