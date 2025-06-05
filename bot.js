const TelegramBot = require('node-telegram-bot-api');
const express = require('express');
const fs = require('fs');
const path = require('path');

// === Configuration ===
const TOKEN = "TOKEN";
const MANAGER_USERNAME = "@ms_manager_by";
const CHANNEL_USERNAME = "@maxssell";
const CHANNEL_LINK = "https://t.me/maxssell";
const REVIEWS_GROUP = "https://t.me/maxssell_feedback";

const CALCULATION_SETTINGS = {
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
};

// === Keep-alive server ===
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
    res.send("I'm alive!");
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`[keep_alive] → запускаю сервер на 0.0.0.0:${PORT}`);
});

// === Bot initialization ===
const bot = new TelegramBot(TOKEN, {polling: true});

// Helper functions
function createMainKeyboard() {
    return {
        inline_keyboard: [
            [{text: "💰 Рассчитать заказ", callback_data: 'calculate'}],
            [{text: "⭐️ Отзывы", url: REVIEWS_GROUP}],
            [{text: "🛒 Оформить заказ", url: `https://t.me/${MANAGER_USERNAME.substring(1)}`}]
        ]
    };
}

async function checkSubscription(userId, chatId) {
    try {
        const member = await bot.getChatMember(CHANNEL_USERNAME, userId);
        if (member.status === "member" || member.status === "creator" || member.status === "administrator") {
            return true;
        }
    } catch (e) {
        console.error(`Не удалось проверить подписку: ${e}`);
    }

    await bot.sendMessage(
        chatId,
        `🚨 <b>Перед началом работы, пожалуйста, подпишитесь на наш канал:</b>\n${CHANNEL_LINK}`,
        {parse_mode: "HTML"}
    );
    return false;
}

async function sendCalculationRequest(chatId) {
    const imgDir = path.join(__dirname, 'img');
    const mediaGroup = [];
    
    try {
        for (let i = 1; i <= 3; i++) {
            const imgPath = path.join(imgDir, `${i}.jpg`);
            if (fs.existsSync(imgPath)) {
                const caption = i === 1 ? 
                    "🛍 <b>Пожалуйста, введите цену в ¥(Юань), чтобы я мог рассчитать стоимость.</b>\n\n" : 
                    undefined;
                
                mediaGroup.push({
                    type: 'photo',
                    media: fs.createReadStream(imgPath),
                    caption: caption,
                    parse_mode: i === 1 ? "HTML" : undefined
                });
            }
        }
        
        if (mediaGroup.length > 0) {
            await bot.sendMediaGroup(chatId, mediaGroup);
        } else {
            await bot.sendMessage(
                chatId,
                "🛍 <b>Пожалуйста, введите цену в ¥(Юань), чтобы я мог рассчитать стоимость.</b>",
                {parse_mode: "HTML"}
            );
        }
    } catch (e) {
        console.error(`Ошибка при отправке медиа: ${e}`);
        await bot.sendMessage(
            chatId,
            "🛍 <b>Пожалуйста, введите цену в ¥(Юань), чтобы я мог рассчитать стоимость.</b>",
            {parse_mode: "HTML"}
        );
    }
}

// Bot handlers
bot.onText(/\/start/, async (msg) => {
    const user = msg.from;
    const welcomeText = `
👋 <b>Привет, ${user.first_name}!</b>\n
📌 С помощью этого бота ты можешь:\n
   <i>• Рассчитать стоимость заказа
   • Получить консультацию
   • Оформить заказ</i>\n
✉️ <b>Ваш менеджер:</b> ${MANAGER_USERNAME}\n\n
🌟 <b>ЖЕЛАЕМ ПРИЯТНЫХ ПОКУПОК!</b>
    `;
    
    try {
        const imgPath = path.join(__dirname, 'img', 'welcome.jpg');
        if (fs.existsSync(imgPath)) {
            await bot.sendPhoto(msg.chat.id, fs.createReadStream(imgPath), {
                caption: welcomeText,
                parse_mode: "HTML",
                reply_markup: createMainKeyboard()
            });
        } else {
            await bot.sendMessage(msg.chat.id, welcomeText, {
                parse_mode: "HTML",
                reply_markup: createMainKeyboard()
            });
        }
    } catch (e) {
        console.error(`Ошибка при отправке приветствия: ${e}`);
        await bot.sendMessage(msg.chat.id, welcomeText, {
            parse_mode: "HTML",
            reply_markup: createMainKeyboard()
        });
    }
});

bot.on('callback_query', async (callbackQuery) => {
    const msg = callbackQuery.message;
    const chatId = msg.chat.id;
    const userId = callbackQuery.from.id;
    
    await bot.answerCallbackQuery(callbackQuery.id);
    
    if (callbackQuery.data === 'calculate') {
        if (!await checkSubscription(userId, chatId)) return;
        
        bot.once('message', handleAmountInput.bind(null, chatId, userId));
        await sendCalculationRequest(chatId);
    }
});

async function handleAmountInput(chatId, userId, msg) {
    if (msg.chat.id !== chatId) return;
    
    const amount = parseFloat(msg.text);
    if (isNaN(amount)) {
        await bot.sendMessage(
            chatId,
            "❌ Пожалуйста, введите число (например: 1500)",
            {reply_markup: createMainKeyboard()}
        );
        return;
    }
    
    const settings = CALCULATION_SETTINGS;
    let response;
    
    if (amount < settings.min_amount) {
        response = `❌ Сумма заказа должна быть не менее ${settings.min_amount} ¥\n\n`;
    } else if (amount > settings.max_amount) {
        response = `⚠️ Для заказа свыше ${settings.max_amount} ¥\n\n👨‍💼 Обратитесь к менеджеру: ${MANAGER_USERNAME}`;
    } else {
        const range = settings.ranges.find(r => r.min <= amount && amount < r.max);
        if (range) {
            const total = amount * range.multiplier;
            response = `
💰 Итоговая стоимость товара: <b>${Math.round(total)}.00 BYN</b>\n\n
🚛 Итоговая стоимость - это конечная стоимость товара без учета доставки. Доставка оплачивается отдельно, когда пара/вещь приедет к нам в Гродно, идет строго по весу, 7$/кг.\n\n
👉 Для оформления заказа отправь скриншот товара, ссылку и свой размер: ${MANAGER_USERNAME}
            `;
        } else {
            response = `❌ Ошибка расчета\n\n✍️ Свяжитесь с менеджером: ${MANAGER_USERNAME}`;
        }
    }
    
    await bot.sendMessage(
        chatId,
        response,
        {parse_mode: "HTML", reply_markup: createMainKeyboard()}
    );
}

// Create img directory if not exists
const imgDir = path.join(__dirname, 'img');
if (!fs.existsSync(imgDir)) {
    fs.mkdirSync(imgDir);
    console.log("Создана папка 'img'.");
}

console.log("Бот успешно запущен!");