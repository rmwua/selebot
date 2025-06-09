import sqlite3
from rapidfuzz import fuzz
import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Память для заявок
pending_requests = {}

# Словарь сокращений категорий
category_synonyms = {
    "похуденка": "Похудение",
    "похудение": "Похудение",
    "снижение веса": "Похудение",
    "сех": "Похудение",
    "простик": "Простатит",
    "прост": "Простатит",
    "простатит": "Простатит",
    "потенция": "Потенция",
    "грибок": "Грибок",
    "паразит": "Паразиты",
    "чистка от паразитов": "Паразиты",
    "суставы": "Суставы",
    "артик": "Суставы",
    "кардио": "Кардио",
    "сахар": "Диабет",
    "диабет": "Диабет",
    "омоложение": "Омоложение",
    "венки": "Варикоз",
    "варикоз": "Варикоз",
    "глаз": "Зрение",
    "окулус": "Зрение",
    "футлярмозг": "Зрение",
    "мочевой пузырь": "Цистит",
    "цистит": "Цистит",
    "гастрит": "ЖКТ",
    "кишечник": "ЖКТ",
    "жкт": "ЖКТ",
    "геморрой": "Геморрой",
    "воспаление вен": "Геморрой",
    "прохождение": "Геморрой",
    "слух": "Слух"
}

# Словарь сокращений гео
geo_synonyms = {
    "it": "Италия", "italy": "Италия", "италия": "Италия",
    "es": "Испания", "spain": "Испания", "испания": "Испания",
    "pt": "Португалия", "portugal": "Португалия", "португалия": "Португалия",
    "de": "Германия", "germany": "Германия", "германия": "Германия",
    "at": "Австрия", "austria": "Австрия", "австрия": "Австрия",
    "fr": "Франция", "france": "Франция", "франция": "Франция",
    "be": "Бельгия", "belgium": "Бельгия", "бельгия": "Бельгия",
    "ro": "Румыния", "romania": "Румыния", "румыния": "Румыния",
    "bg": "Болгария", "bulgaria": "Болгария", "болгария": "Болгария",
    "hu": "Венгрия", "hungary": "Венгрия", "венгрия": "Венгрия",
    "gr": "Греция", "greece": "Греция", "греция": "Греция",
    "cz": "Чехия", "czech": "Чехия", "чехия": "Чехия",
    "pl": "Польша", "poland": "Польша", "польша": "Польша",
    "si": "Словения", "slovenia": "Словения", "словения": "Словения",
    "sk": "Словакия", "slovakia": "Словакия", "словакия": "Словакия",
    "hr": "Хорватия", "croatia": "Хорватия", "хорватия": "Хорватия",
    "mx": "Мексика", "mexico": "Мексика", "мексика": "Мексика",
    "pe": "Перу", "peru": "Перу", "перу": "Перу",
    "co": "Колумбия", "colombia": "Колумбия", "колумбия": "Колумбия"
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS celebrities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            geo TEXT,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geo_list (geo TEXT UNIQUE)
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_list (category TEXT UNIQUE)
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_geo_requests (
            user_id INTEGER,
            user_name TEXT,
            geo TEXT,
            timestamp TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_category_requests (
            user_id INTEGER,
            user_name TEXT,
            category TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Нормализация текста
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'\W+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Поиск знаменитости
def search_celebrity(name):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, status FROM celebrities')
    celebrities = cursor.fetchall()
    conn.close()

    name_norm = normalize_text(name)
    best_match = None
    highest_score = 0

    for celeb_name, status in celebrities:
        celeb_norm = normalize_text(celeb_name)
        score = fuzz.partial_ratio(name_norm, celeb_norm)
        if score > highest_score:
            highest_score = score
            best_match = (celeb_name, status)

    if highest_score >= 80:
        return best_match
    else:
        return None

# Нормализация гео и категорий
def normalize_geo(geo):
    geo_norm = geo.lower()
    return geo_synonyms.get(geo_norm, geo.title())

def normalize_category(category):
    category_norm = category.lower()
    return category_synonyms.get(category_norm, category.title())

# Проверка существования гео/категории в базе
def geo_exists(geo):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM geo_list WHERE lower(geo) = ?', (geo.lower(),))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def category_exists(category):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM category_list WHERE lower(category) = ?', (category.lower(),))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

# Сохранение новых запросов
def save_new_geo(user_id, user_name, geo):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO new_geo_requests (user_id, user_name, geo, timestamp) VALUES (?, ?, ?, ?)',
                   (user_id, user_name, geo, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def save_new_category(user_id, user_name, category):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO new_category_requests (user_id, user_name, category, timestamp) VALUES (?, ?, ?, ?)',
                   (user_id, user_name, category, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# Обработчики команд и сообщений
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\nЯ бот для проверки статуса знаменитостей.\n\n"
        "Напишите имя знаменитости, категорию оффера и гео в формате:\n<Имя>, <Категория>, <Гео>"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user = update.effective_user
    try:
        name, category, geo = map(str.strip, text.split(','))
    except ValueError:
        await update.message.reply_text("Пожалуйста, используйте формат: Имя, Категория, Гео")
        return

    category = normalize_category(category)
    geo = normalize_geo(geo)

    if not geo_exists(geo):
        await update.message.reply_text("Знаменитость не согласована. Данного гео пока нет.")
        save_new_geo(user.id, user.username or user.full_name, geo)
        return

    if not category_exists(category):
        await update.message.reply_text("Знаменитость не согласована. Данной категории пока нет.")
        save_new_category(user.id, user.username or user.full_name, category)
        return

    result = search_celebrity(name)
    if result:
        celeb_name, status = result
        await update.message.reply_text(f"Найдено: {celeb_name}\nСтатус: {status}")
    else:
        await update.message.reply_text("Имя не найдено. Ваш запрос направлен модератору, ожидайте...")

        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{update.message.chat_id}"),
                InlineKeyboardButton("❌ Забанить", callback_data=f"ban_{update.message.chat_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        moderator_chat_id = 415682886

        await context.bot.send_message(
            chat_id=moderator_chat_id,
            text=f"Новый запрос:\nИмя: {name}\nКатегория: {category}\nГео: {geo}",
            reply_markup=reply_markup
        )
        pending_requests[update.message.chat_id] = {
            'name': name,
            'category': category,
            'geo': geo
        }

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action, user_chat_id = data[0], int(data[1])
    req = pending_requests.get(user_chat_id)

    if req:
        status = 'Согласована' if action == 'approve' else 'Черный список'
        conn = sqlite3.connect('celebrities.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO celebrities (name, category, geo, status) VALUES (?, ?, ?, ?)',
                       (req['name'], req['category'], req['geo'], status))
        conn.commit()
        conn.close()

        await context.bot.send_message(chat_id=user_chat_id, text=f"Ваш запрос обработан. Статус: {status}")
        await query.edit_message_text(text=f"Запрос обработан: {status}")
        del pending_requests[user_chat_id]

# Команды для отображения списка Гео и Категорий
async def geo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('SELECT geo FROM geo_list')
    rows = cursor.fetchall()
    conn.close()

    if rows:
        geo_items = [row[0] for row in rows]
        await update.message.reply_text("Список доступных Гео:\n" + "\n".join(geo_items))
    else:
        await update.message.reply_text("Пока нет доступных Гео.")

async def category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('celebrities.db')
    cursor = conn.cursor()
    cursor.execute('SELECT category FROM category_list')
    rows = cursor.fetchall()
    conn.close()

    if rows:
        category_items = [row[0] for row in rows]
        await update.message.reply_text("Список доступных Категорий:\n" + "\n".join(category_items))
    else:
        await update.message.reply_text("Пока нет доступных Категорий.")

# Запуск бота
def main():
    init_db()
    application = Application.builder().token('8089924412:AAHq9V-Qz6p54jChGqT7E3Lc3qy4KfT6PvE').build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('geo', geo_list))
    application.add_handler(CommandHandler('categories', category_list))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
