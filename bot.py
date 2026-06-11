import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import BOT_TOKEN
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
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
        "Выбери действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
        history = db.get_history(cat_name)
        stats = db.get_stats_last_3_months(cat_name)
        
        text = "📜 **Последние 10 записей:**\n" + "\n".join(history) + "\n\n" + stats
        await query.edit_message_text(text, parse_mode="Markdown")
        await show_cat_actions(query.message, cat_name)
    
    elif query.data == "switch_cat_from_menu":
        await query.edit_message_text("🔄 Введите имя кота, чей журнал хотите посмотреть:")
        return SWITCH_CAT_INPUT

async def show_cat_actions(message, cat_name: str):
    keyboard = [
        [InlineKeyboardButton("💩 Кот покакал", callback_data="poop")],
        [InlineKeyboardButton("⏰ Как давно покакал кот?", callback_data="when")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.edit_text(f"🐱 Кот: **{cat_name}**\n\nЧто он сделал?", 
                            parse_mode="Markdown", reply_markup=reply_markup)

async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
    if db.cat_exists(name):
        await update.message.reply_text(
            "😸 Круто! Тезка! Но давай другое имя?\n\n"
            "Введите другое имя кота:"
        )
        return NAME_INPUT
    
    # Сохраняем кота
    context.user_data["current_cat"] = name
    # Создаём пустой файл, если не существует
    db.load_cat_data(name)
    
    await update.message.reply_text(f"✅ Познакомились! Теперь у тебя есть кот {name}")
    
    # Показываем меню действий (через новое сообщение с кнопками)
    keyboard = [
        [InlineKeyboardButton("💩 Кот покакал", callback_data="poop")],
        [InlineKeyboardButton("⏰ Как давно покакал кот?", callback_data="when")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("🔄 Сменить кота", callback_data="switch_cat_from_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🐱 Кот: **{name}**\n\nЧто он сделал?", 
                                    parse_mode="Markdown", reply_markup=reply_markup)
    return ConversationHandler.END

async def switch_cat_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    
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
    await update.message.reply_text(f"🐱 Переключились на кота: **{name}**\n\nЧто он сделал?",
                                    parse_mode="Markdown", reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено. Нажмите /start")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation для знакомства с новым котом
    conv_new_cat = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^new_cat$")],
        states={
            NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Conversation для смены кота
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
    
    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
