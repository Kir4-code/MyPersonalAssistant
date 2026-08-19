# 🤖 MyPersonalAssistant

**Персональный AI-ассистент в Telegram** на базе DeepSeek V4 Pro.  
Работает в Docker, запоминает имя пользователя и сохраняет историю диалогов.

---

## ✨ Возможности

- 🧠 **DeepSeek V4 Pro** — мощная языковая модель
- 💾 **Память диалогов** — история сохраняется между сессиями
- 👤 **Запоминание имени** — обращается к вам по имени
- 📦 **Готов к деплою** — работает в Docker
- ⚙️ **Гибкая настройка** — системный промпт в отдельном файле
- 🔒 **Безопасность** — ключи в `.env`, не попадают в репозиторий

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/Kir4-code/MyPersonalAssistant.git
cd MyPersonalAssistant
cp .env.example .env
# Отредактируйте .env
docker-compose up -d --build
