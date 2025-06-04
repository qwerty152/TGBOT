from flask import Flask
from threading import Thread
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# === Flask keep-alive server ===
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    print(f"[keep_alive] → запускаю Flask на 0.0.0.0:{port}")
    # отключаем reloader, иначе будет двойной старт
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()


# === Telegram Bot configuration ===
TOKEN = "7823804408:AAEZNxL5z6vfKNTBtYPoR30q2XnjeGjtZR0"
MANAGER_USERNAME = "@ms_manager_by"
CHANNEL_USERNAME = "@maxssell"
CHANNEL_LINK = "https://t.me/maxssell"
REVIEWS_GROUP = "https://t.me/maxssell_feedback"

CALCULATION_SETTINGS = {
    "min_amount": 100,
    "max_amount": 2500,
    "ranges": [
        {"min": 100, "max": 300,  "multiplier": 0.7},
        {"min": 300, "max": 350, "multiplier": 0.67},
        {"min": 350, "max": 400,"multiplier": 0.65},
        {"min": 400, "max": 500,  "multiplier": 0.63},
        {"min": 500, "max": 550, "multiplier": 0.61},
        {"min": 550, "max": 600,"multiplier": 0.60},
        {"min": 600, "max": 650,  "multiplier": 0.59},
        {"min": 650, "max": 700, "multiplier": 0.585},
        {"min": 700, "max": 800,"multiplier": 0.575},
        {"min": 800, "max": 900,  "multiplier": 0.565},
        {"min": 900, "max": 2500,"multiplier": 0.55},
    ]
}

def create_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Рассчитать заказ", callback_data='calculate')],
        [InlineKeyboardButton("⭐️ Отзывы", url=REVIEWS_GROUP)],
        [InlineKeyboardButton("🛒 Оформить заказ", url=f"https://t.me/{MANAGER_USERNAME[1:]}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def check_subscription(user_id: int, bot, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ("member", "creator", "administrator"):
            return True
    except Exception as e:
        logger.error(f"Не удалось проверить подписку: {e}")

    await bot.send_message(
        chat_id=chat_id,
        text=(
            "🚨 <b>Перед началом работы, пожалуйста, подпишитесь на наш канал:</b>\n"
            f"{CHANNEL_LINK}"
        ),
        parse_mode="HTML"
    )
    return False

async def send_calculation_request(chat_id, context):
    media_group = []
    for i, has_caption in [(1, True), (2, False), (3, False)]:
        img_path = f'img/{i}.jpg'
        if os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                caption = "🛍 <b>Пожалуйста, введите цену в ¥(Юань), чтобы я мог рассчитать стоимость.</b>\n\n" if has_caption else None
                media_group.append(InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"))
    if media_group:
        await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🛍 <b>Пожалуйста, введите цену в ¥(Юань), чтобы я мог рассчитать стоимость.</b>",
            parse_mode="HTML"
        )
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_text = (
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        "📌 С помощью этого бота ты можешь:\n"
        "   <i>• Рассчитать стоимость заказа\n"
        "   • Получить консультацию\n"
        "   • Оформить заказ</i>\n\n"
        f"✉️ <b>Ваш менеджер:</b> {MANAGER_USERNAME}\n\n"
        "🌟 <b>ЖЕЛАЕМ ПРИЯТНЫХ ПОКУПОК!</b>"
    )
    try:
        with open('img/welcome.jpg', 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=welcome_text, parse_mode="HTML", reply_markup=create_main_keyboard())
    except:
        await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=create_main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await check_subscription(query.from_user.id, context.bot, query.message.chat_id):
        return
    if query.data == 'calculate':
        context.user_data['awaiting_amount'] = True
        await send_calculation_request(query.message.chat_id, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.message.chat_id

    if not context.user_data.get('sub_checked'):
        if not await check_subscription(user_id, context.bot, chat_id):
            return
        context.user_data['sub_checked'] = True

    if not context.user_data.get('awaiting_amount'):
        return await update.message.reply_text("⚠️ Пожалуйста, используйте кнопки меню", reply_markup=create_main_keyboard())

    try:
        amount = float(update.message.text)
    except ValueError:
        return await update.message.reply_text("❌ Пожалуйста, введите число (например: 1500)", reply_markup=create_main_keyboard())

    settings = CALCULATION_SETTINGS
    if amount < settings['min_amount']:
        response = f"❌ Сумма заказа должна быть не менее {settings['min_amount']} ¥\n\n"
    elif amount > settings['max_amount']:
        response = f"⚠️ Для заказа свыше {settings['max_amount']} ¥\n\n👨‍💼 Обратитесь к менеджеру: {MANAGER_USERNAME}"
    else:
        m = next((r["multiplier"] for r in settings["ranges"] if r["min"] <= amount < r["max"]), None)
        if m:
            total = amount * m
            response = (
                f"💰 Итоговая стоимость товара: <b>{total:.0f}.00 BYN</b>\n\n"
                "🚛 Итоговая стоимость - это конечная стоимость товара без учета доставки. Доставка оплачивается отдельно, когда пара/вещь приедет к нам в Гродно, идет строго по весу, 7$/кг.\n\n"
                f"👉 Для оформления заказа отправь скриншот товара, ссылку и свой размер: {MANAGER_USERNAME}"
            )
        else:
            response = f"❌ Ошибка расчета\n\n✍️ Свяжитесь с менеджером: {MANAGER_USERNAME}"

    await update.message.reply_text(response, parse_mode="HTML", reply_markup=create_main_keyboard())
    context.user_data['awaiting_amount'] = False

def main() -> None:
    # Запускаем web-сервер для keep-alive
    keep_alive()

    # Создаём папку img, если нужно
    if not os.path.exists('img'):
        os.makedirs('img')
        logger.warning("Создана папка 'img'.")

    # Создаём и запускаем бота
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот успешно запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
