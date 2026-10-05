from dotenv import load_dotenv
load_dotenv()
import telebot
from openai import OpenAI
import os
import json
import re
import html
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ATRIA_API_KEY = os.getenv("ATRIA_API_KEY")

if not TELEGRAM_TOKEN or not ATRIA_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и ATRIA_API_KEY должны быть установлены")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(
    base_url="https://api.atria-asi.ai/v1",
    api_key=ATRIA_API_KEY,
    http_client=None
)

def escape_html(text: str) -> str:
    """Экранирует спецсимволы HTML, кроме уже расставленных тегов модели."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def safe_send(chat_id, text, reply_to=None, parse_mode="HTML"):
    """Отправка с автоматическим откатом на plain text при ошибке парсинга."""
    try:
        if reply_to:
            bot.reply_to(reply_to, text, parse_mode=parse_mode)
        else:
            bot.send_message(chat_id, text, parse_mode=parse_mode)
    except Exception as e:
        print(f"HTML parse error, fallback to plain: {e}")
        plain = re.sub(r"<[^>]+>", "", text)
        plain = html.unescape(plain)
        if reply_to:
            bot.reply_to(reply_to, plain)
        else:
            bot.send_message(chat_id, plain)

# Prompt
def load_system_prompt():
    prompt_file = "system_prompt.txt"
    if os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return "Вы профессиональный ассистент. Отвечайте на русском языке, деловым стилем."

SYSTEM_PROMPT = load_system_prompt()
print(f"Загружен системный промпт: {len(SYSTEM_PROMPT)} символов")

# data storage
DATA_FILE = "user_data.json"

def load_user_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_user_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_user_data()

def get_user_name(user_id):
    user_id = str(user_id)
    return user_data.get(user_id, {}).get("name", None)

def set_user_name(user_id, name):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["name"] = name
    save_user_data(user_data)

def get_user_context(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {"name": None, "history": []}
    if "history" not in user_data[user_id]:
        user_data[user_id]["history"] = []
    if "name" not in user_data[user_id]:
        user_data[user_id]["name"] = None
    return user_data[user_id]

def save_chat_history(user_id, role, content):
    context = get_user_context(user_id)
    context["history"].append({
        "role": role,
        "content": content,
        "time": datetime.now().isoformat()
    })
    if len(context["history"]) > 50:
        context["history"] = context["history"][-50:]
    save_user_data(user_data)

def get_chat_history(user_id, limit=10):
    context = get_user_context(user_id)
    return context["history"][-limit:]

# Commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    name = get_user_name(user_id)

    if name:
        welcome = f"Здравствуйте, <b>{escape_html(name)}</b>. Чем могу помочь?"
    else:
        welcome = "Здравствуйте. Представьтесь, пожалуйста. Как мне к Вам обращаться?"

    safe_send(message.chat.id, welcome, reply_to=message)

@bot.message_handler(commands=['clear'])
def clear_history(message):
    user_id = str(message.from_user.id)
    context = get_user_context(user_id)
    context["history"] = []
    save_user_data(user_data)
    safe_send(message.chat.id, "История очищена.", reply_to=message)

@bot.message_handler(commands=['name'])
def change_name(message):
    user_id = str(message.from_user.id)
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        safe_send(message.chat.id, "Укажите имя после команды. Пример: /name Александр", reply_to=message)
        return

    new_name = parts[1].strip()
    set_user_name(user_id, new_name)
    safe_send(message.chat.id, f"Имя сохранено. Здравствуйте, <b>{escape_html(new_name)}</b>.", reply_to=message)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.from_user.id)

    if not message.text:
        safe_send(message.chat.id, "Принимаю только текстовые сообщения.", reply_to=message)
        return

    user_text = message.text

    bot.send_chat_action(message.chat.id, 'typing')

    try:
        context = get_user_context(user_id)
        name = context.get("name")

        # Name checking
        if not name:
            name_match = re.search(r'(?:меня зовут|зовут|я\s+)([А-Яа-яёЁA-Za-z\-]+)', user_text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).capitalize()
                set_user_name(user_id, name)
                safe_send(
                    message.chat.id,
                    f"Принял. <b>{escape_html(name)}</b>, чем могу Вам помочь?",
                    reply_to=message
                )
                return
            else:
                safe_send(
                    message.chat.id,
                    "Представьтесь, пожалуйста. Напишите 'Меня зовут [имя]' или используйте команду /name [имя]",
                    reply_to=message
                )
                return

        save_chat_history(user_id, "user", user_text)
        system_prompt_with_name = SYSTEM_PROMPT + f"\n\nИМЯ ПОЛЬЗОВАТЕЛЯ: {name}"

        messages = [{"role": "system", "content": system_prompt_with_name}]

        history = get_chat_history(user_id, 3)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_text})

        response = client.chat.completions.create(
            model="Atria-Dawn-Preview",
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        if response.usage:
            print(f"TOKENS: prompt={response.usage.prompt_tokens} "
                  f"completion={response.usage.completion_tokens} "
                  f"total={response.usage.total_tokens}")
        else:
            print("TOKENS: usage не вернулся провайдером")

        bot_reply = response.choices[0].message.content
        save_chat_history(user_id, "assistant", bot_reply)
        safe_send(message.chat.id, bot_reply, reply_to=message)

    except Exception as e:
        print(f"Ошибка: {e}")
        safe_send(message.chat.id, f"Ошибка: {escape_html(str(e)[:100])}", reply_to=message)

print("Деловой ассистент запущен.")
bot.infinity_polling()