# main.py
import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Добавляем путь для импортов
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import init_db
from handlers import register_handlers, AccessMiddleware, FSMTimeoutMiddleware

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
load_dotenv()

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения. Проверьте настройки Railway.")

# Получаем порт от Railway (если запускается как веб-сервис)
PORT = int(os.environ.get("PORT", 8080))

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Используем stdout для Railway
    ]
)

logger = logging.getLogger(__name__)


# --- ЗАПУСК ---
async def main():
    # Инициализация БД
    init_db()

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Регистрация всех обработчиков
    register_handlers(dp)

    # Подключение middleware
    dp.message.middleware(AccessMiddleware(bot))
    dp.callback_query.middleware(AccessMiddleware(bot))
    dp.message.middleware(FSMTimeoutMiddleware())
    dp.callback_query.middleware(FSMTimeoutMiddleware())

    # Удаление вебхука и запуск поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен и ожидает сообщений...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    # Проверяем переменные окружения
    required_vars = ["BOT_TOKEN", "JSONBIN_API_KEY", "MASTER_BIN_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Отсутствуют переменные окружения: {missing_vars}")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)