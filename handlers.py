# handlers.py

import logging
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from db import *
from keyboards import *
from states import *
from analytics import *
from export import *

# --- НАСТРОЙКИ ---
ADMIN_ID = 8382571809
CONTACT_URL = "https://t.me/SalesFlowManager"
logger = logging.getLogger(__name__)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def safe_edit_message(chat_id: int, message_id: int, text: str, reply_markup=None, bot: Bot = None):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        if bot:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup
            )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return True
        logger.error(f"Ошибка редактирования сообщения: {e}")
        return False
    except Exception as e:
        logger.error(f"Неизвестная ошибка при редактировании: {e}")
        return False


async def show_main_menu(event: types.Message | types.CallbackQuery, state: FSMContext, text: str = None):
    """Показывает главное меню"""
    await state.clear()
    user_id = event.from_user.id
    is_admin = get_user_role(user_id) == 'admin'
    sessions = get_user_sessions(user_id)

    if not sessions:
        welcome_text = text or "Добро пожаловать! 🎉\n\nУ вас пока нет сессий. Создайте новую!"
    else:
        welcome_text = text or "Добро пожаловать! 🎉\n\nВыберите сессию:"

    kb = get_main_menu_inline(sessions, is_admin)

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(welcome_text, reply_markup=kb)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await event.bot.send_message(event.from_user.id, welcome_text, reply_markup=kb)
    else:
        await event.answer(welcome_text, reply_markup=kb)


async def show_session_menu(event: types.Message | types.CallbackQuery, state: FSMContext, session_id: int):
    """Показывает меню сессии"""
    await state.update_data(current_session_id=session_id)
    details = get_session_details(session_id)

    if not details:
        text = "Ошибка: сессия не найдена."
        reply_markup = get_main_menu_inline([], get_user_role(event.from_user.id) == 'admin')

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
        return

    status_text = "" if details['is_active'] else "\n\n<b>Сессия закрыта. Редактирование невозможно.</b>"
    menu_text = (
        f"📊 <b>Меню сессии: {details['name']}</b>{status_text}\n\n"
        f"💰 Баланс: <b>{details['balance']:.2f} {details['currency']}</b>\n"
        f"💸 Затраты: <b>{details['total_expenses']:.2f} {details['currency']}</b>\n"
        f"🔢 Продаж: <b>{details['sales_count']}</b>\n"
        f"💵 Мне должны: <b>{details['owed_to_me']:.2f} {details['currency']}</b>\n"
        f"🪙 Я должен: <b>{details['i_owe']:.2f} {details['currency']}</b>"
    )

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(menu_text, reply_markup=get_session_menu_inline(details['is_active']))
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await event.bot.send_message(event.from_user.id, menu_text,
                                         reply_markup=get_session_menu_inline(details['is_active']))
    else:
        await event.answer(menu_text, reply_markup=get_session_menu_inline(details['is_active']))


# --- MIDDLEWARE ---
class AccessMiddleware:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def __call__(self, handler, event: types.Message | types.CallbackQuery, data: dict) -> any:
        user_id = event.from_user.id
        update_user_activity(user_id)

        if isinstance(event, types.Message) and event.text == '/start':
            return await handler(event, data)

        if isinstance(event, types.CallbackQuery) and event.data in ['nav_start', 'cancel_action', 'session_menu']:
            return await handler(event, data)

        if isinstance(event, types.CallbackQuery) and event.data.startswith('admin_'):
            is_admin = get_user_role(user_id) == 'admin'
            if not is_admin:
                await event.answer("Доступ запрещен.", show_alert=True)
                return

        if not check_user_access(user_id):
            no_access_text = (
                f"👋 Привет! Это бот-бухгалтер.\n\n"
                f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
                f"Доступ к боту платный.\n\n"
                f"Для получения доступа, пожалуйста, свяжитесь с администратором."
            )
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Связаться с администратором", url=CONTACT_URL)]
            ])

            if isinstance(event, types.Message):
                await event.answer(no_access_text, reply_markup=reply_markup)
            elif isinstance(event, types.CallbackQuery):
                await event.answer("У вас нет доступа.", show_alert=True)
                await self.bot.send_message(chat_id=user_id, text=no_access_text, reply_markup=reply_markup)
            return

        return await handler(event, data)


class FSMTimeoutMiddleware:
    TIMEOUT_SECONDS = 300

    async def __call__(self, handler, event: types.Message | types.CallbackQuery, data: dict) -> any:
        state: FSMContext = data['state']
        current_state = await state.get_state()

        if current_state:
            state_data = await state.get_data()
            last_activity_ts = state_data.get('timestamp')

            if last_activity_ts and (datetime.now().timestamp() - last_activity_ts > self.TIMEOUT_SECONDS):
                await state.clear()
                text = "Сессия ввода данных истекла. Начните заново."
                reply_markup = get_main_menu_inline([], get_user_role(event.from_user.id) == 'admin')

                if isinstance(event, types.Message):
                    await event.answer(text, reply_markup=reply_markup)
                else:
                    try:
                        await event.message.edit_text(text, reply_markup=reply_markup)
                    except Exception as e:
                        logger.error(f"Ошибка при редактировании сообщения: {e}")
                        await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
                return

            await state.update_data(timestamp=datetime.now().timestamp())
        elif isinstance(event, types.Message):
            await state.update_data(timestamp=datetime.now().timestamp())

        return await handler(event, data)


# --- ГЛАВНЫЕ ОБРАБОТЧИКИ ---

async def handle_start_command(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    ensure_user_exists(message.from_user.id)

    is_admin = get_user_role(message.from_user.id) == 'admin'

    if not is_admin and not check_user_access(message.from_user.id):
        no_access_text = (
            f"👋 Привет! Это бот-бухгалтер.\n\n"
            f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n\n"
            f"Доступ к боту платный.\n\n"
            f"Для получения доступа, пожалуйста, свяжитесь с администратором."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Связаться с администратором", url=CONTACT_URL)]
        ])
        await message.answer(no_access_text, reply_markup=reply_markup)
        return

    await show_main_menu(message, state)


async def navigate(callback: CallbackQuery, state: FSMContext):
    """Обработчик навигационных callback"""
    action = callback.data.split('_', 1)[1]
    await state.clear()

    if action == "start":
        await show_main_menu(callback, state)
    elif action == "admin_panel":
        try:
            await callback.message.edit_text("Выберите действие в Админ-Панели:",
                                             reply_markup=get_admin_panel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Выберите действие в Админ-Панели:",
                                            reply_markup=get_admin_panel_inline())
    elif action == "create_session":
        try:
            await callback.message.edit_text("Введите название для новой сессии (макс. 50 символов):",
                                             reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id,
                                            "Введите название для новой сессии (макс. 50 символов):",
                                            reply_markup=get_cancel_inline())
        await state.set_state(CreateSession.name)
        await state.update_data(timestamp=datetime.now().timestamp())
    elif action.startswith("session_"):
        session_id = int(action.split('_', 1)[1])
        await show_session_menu(callback, state, session_id)

    await callback.answer()


async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await show_main_menu(callback, state)


# --- СОЗДАНИЕ СЕССИИ ---

async def process_session_name(message: Message, state: FSMContext):
    """Обработчик названия сессии"""
    session_name = message.text.strip()

    if len(session_name) > 50 or len(session_name) < 3:
        return await message.answer("Название должно быть от 3 до 50 символов. Попробуйте еще раз:",
                                    reply_markup=get_cancel_inline())

    user_sessions = get_user_sessions(message.from_user.id)
    existing_names = [session[1] for session in user_sessions]

    if session_name in existing_names:
        return await message.answer("У вас уже есть сессия с таким названием. Введите другое название:",
                                    reply_markup=get_cancel_inline())

    await state.update_data(name=session_name)
    await message.answer("Выберите валюту:", reply_markup=get_currency_inline())
    await state.set_state(CreateSession.currency)


async def process_currency_choice(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора валюты"""
    currency_map = {"currency_USDT": "USDT", "currency_RUB": "Рубль ПМР"}
    currency_name = currency_map[callback.data]
    await state.update_data(currency=currency_name)

    try:
        await callback.message.edit_text(f"Валюта: <b>{currency_name}</b>.\n\nВведите бюджет на сессию:")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id,
                                        f"Валюта: <b>{currency_name}</b>.\n\nВведите бюджет на сессию:")

    await state.set_state(CreateSession.budget)
    await callback.answer()


async def process_budget(message: Message, state: FSMContext):
    """Обработчик ввода бюджета"""
    try:
        budget = float(message.text.replace(',', '.'))
        if budget <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректное положительное число.", reply_markup=get_cancel_inline())

    data = await state.get_data()
    session_id = add_session(message.from_user.id, data['name'], budget, data['currency'])

    await show_main_menu(message, state, f"✅ Сессия <b>'{data['name']}'</b> создана!")


# --- ОСНОВНЫЕ ДЕЙСТВИЯ В СЕССИИ ---

async def session_action_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик действий в меню сессии"""
    action = callback.data.split('_', 1)[1]

    if action == "add_sale":
        try:
            await callback.message.edit_text("Введите сумму продажи:", reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Введите сумму продажи:",
                                            reply_markup=get_cancel_inline())
        await state.set_state(AddSale.amount)

    elif action == "add_expense":
        try:
            await callback.message.edit_text("Введите сумму затраты:", reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Введите сумму затраты:",
                                            reply_markup=get_cancel_inline())
        await state.set_state(AddExpense.amount)

    elif action == "manage_debts":
        try:
            await callback.message.edit_text("Управление долгами:", reply_markup=get_debt_management_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Управление долгами:",
                                            reply_markup=get_debt_management_inline())

    elif action == "list_sales":
        await show_transactions_list(callback, state, 'sale')

    elif action == "list_expenses":
        await show_transactions_list(callback, state, 'expense')

    elif action == "report":
        await show_report(callback, state)

    elif action == "close_confirm":
        session_id = (await state.get_data()).get('current_session_id')
        try:
            await callback.message.edit_text("Вы уверены, что хотите завершить сессию? Это действие необратимо.",
                                             reply_markup=get_confirmation_inline('close_session', session_id))
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id,
                                            "Вы уверены, что хотите завершить сессию? Это действие необратимо.",
                                            reply_markup=get_confirmation_inline('close_session', session_id))

    elif action == "menu":
        session_id = (await state.get_data()).get('current_session_id')
        if session_id:
            await show_session_menu(callback, state, session_id)
        else:
            await show_main_menu(callback, state)

    await callback.answer()


async def handle_list_debts(callback: CallbackQuery, state: FSMContext):
    """Обработчик списка долгов"""
    debt_type_map = {
        "list_debts_owed_to_me": "owed_to_me",
        "list_debts_i_owe": "i_owe"
    }

    if callback.data in debt_type_map:
        debt_type = debt_type_map[callback.data]
        await state.update_data(debt_type=debt_type)
        await show_debts_list(callback, state, debt_type)

    await callback.answer()


async def debt_category_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора категории долга"""
    debt_type_map = {
        "debt_owed_to_me": "owed_to_me",
        "debt_i_owe": "i_owe"
    }

    if callback.data in debt_type_map:
        await state.update_data(debt_type=debt_type_map[callback.data])

        try:
            await callback.message.edit_text("Введите сумму долга:", reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Введите сумму долга:",
                                            reply_markup=get_cancel_inline())

        await state.set_state(AddDebt.amount)

    await callback.answer()


# --- FSM ДЛЯ ТРАНЗАКЦИЙ И ДОЛГОВ ---

async def process_sale_amount(message: Message, state: FSMContext):
    """Обработчик суммы продажи"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректную сумму.", reply_markup=get_cancel_inline())

    await state.update_data(amount=amount)
    await message.answer("Введите сумму затрат на эту продажу (если нет, введите 0):",
                         reply_markup=get_cancel_inline())
    await state.set_state(AddSale.expense)


async def process_sale_expense(message: Message, state: FSMContext):
    """Обработчик затрат на продажу"""
    try:
        expense = float(message.text.replace(',', '.'))
        if expense < 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректную сумму (0 или больше).", reply_markup=get_cancel_inline())

    await state.update_data(expense=expense)
    await message.answer("Введите название продажи (например, 'Звезды Телеграм'):",
                         reply_markup=get_cancel_inline())
    await state.set_state(AddSale.description)


async def process_sale_description(message: Message, state: FSMContext):
    """Обработчик описания продажи"""
    data = await state.get_data()
    session_id = data.get('current_session_id')

    if not session_id:
        await message.answer("Ошибка: сессия не найдена.", reply_markup=get_cancel_inline())
        return

    details = get_session_details(session_id)
    if not details['is_active']:
        await message.answer("Сессия закрыта. Добавление невозможно.",
                             reply_markup=get_session_menu_inline(False))
        return

    description = message.text.strip()[:100]
    if not description:
        description = "Продажа"

    add_transaction(session_id, 'sale', data['amount'], data['expense'], description)
    await show_session_menu(message, state, session_id)


async def process_expense_amount(message: Message, state: FSMContext):
    """Обработчик суммы затрат"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректную сумму.", reply_markup=get_cancel_inline())

    await state.update_data(amount=amount)
    await message.answer("На что была затрата (например, 'Реклама'):", reply_markup=get_cancel_inline())
    await state.set_state(AddExpense.description)


async def process_expense_description(message: Message, state: FSMContext):
    """Обработчик описания затрат"""
    data = await state.get_data()
    session_id = data.get('current_session_id')

    if not session_id:
        await message.answer("Ошибка: сессия не найдена.", reply_markup=get_cancel_inline())
        return

    details = get_session_details(session_id)
    if not details['is_active']:
        await message.answer("Сессия закрыта. Добавление невозможно.",
                             reply_markup=get_session_menu_inline(False))
        return

    description = message.text.strip()[:100]
    if not description:
        description = "Затраты"

    add_transaction(session_id, 'expense', data['amount'], 0, description)
    await show_session_menu(message, state, session_id)


async def process_debt_amount(message: Message, state: FSMContext):
    """Обработчик суммы долга"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректную сумму.", reply_markup=get_cancel_inline())

    await state.update_data(amount=amount)
    await message.answer("Введите имя человека или организации:", reply_markup=get_cancel_inline())
    await state.set_state(AddDebt.person_name)


async def process_debt_person_name(message: Message, state: FSMContext):
    """Обработчик имени для долга"""
    person_name = message.text.strip()[:50]
    if not person_name:
        return await message.answer("Введите корректное имя:", reply_markup=get_cancel_inline())

    await state.update_data(person_name=person_name)
    await message.answer("Введите описание долга (необязательно) или /skip:",
                         reply_markup=get_cancel_inline())
    await state.set_state(AddDebt.description)


async def process_debt_description(message: Message, state: FSMContext):
    """Обработчик описания долга"""
    data = await state.get_data()
    session_id = data.get('current_session_id')

    if not session_id:
        await message.answer("Ошибка: сессия не найдена.", reply_markup=get_cancel_inline())
        return

    details = get_session_details(session_id)
    if not details['is_active']:
        await message.answer("Сессия закрыта. Добавление невозможно.",
                             reply_markup=get_session_menu_inline(False))
        return

    description = "" if message.text == "/skip" else message.text.strip()[:100]

    add_debt(session_id, data['debt_type'], data['person_name'], data['amount'], description)
    await show_session_menu(message, state, session_id)


# --- СПИСКИ И ПОИСК ---

async def show_transactions_list(event: types.Message | types.CallbackQuery, state: FSMContext, t_type: str,
                                 search_query: str = None):
    """Показывает список транзакций"""
    session_id = (await state.get_data()).get('current_session_id')

    if not session_id:
        text = "Ошибка: сессия не найдена."
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="nav_start")]
        ])

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
        return

    items = get_transactions_list(session_id, t_type, search_query, limit=20)

    if not items:
        type_name = "Продаж" if t_type == 'sale' else "Затрат"
        text = f"{type_name} пока нет."
        if search_query:
            text = f"По запросу '{search_query}' ничего не найдено."

        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data=f"search_{t_type}")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="session_menu")]
        ])

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
        return

    type_name = "📈 Мои продажи" if t_type == 'sale' else "📉 Мои затраты"
    text = f"{type_name}:\n\n"

    for item in items:
        expense_text = f" / -{item['expense_amount']:.2f}" if item['expense_amount'] > 0 else ""
        profit_text = f" (💰{item['profit']:.2f})" if t_type == 'sale' and item['profit'] != 0 else ""
        text += f"• {item['description'] or 'Без описания'} | +{item['amount']:.2f}{expense_text} | {item['date']}{profit_text}\n"

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(
                text,
                reply_markup=get_items_list_inline(items, 'transaction', session_id, search_query)
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await event.bot.send_message(
                event.from_user.id,
                text,
                reply_markup=get_items_list_inline(items, 'transaction', session_id, search_query)
            )
    else:
        await event.answer(text, reply_markup=get_items_list_inline(items, 'transaction', session_id, search_query))


async def show_debts_list(event: types.Message | types.CallbackQuery, state: FSMContext, debt_type: str,
                          search_query: str = None):
    """Показывает список долгов"""
    session_id = (await state.get_data()).get('current_session_id')

    if not session_id:
        text = "Ошибка: сессия не найдена."
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="nav_start")]
        ])

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
        return

    items = get_debts_list(session_id, debt_type, search_query, limit=20)

    if not items:
        type_name = "Долгов вам" if debt_type == 'owed_to_me' else "Ваших долгов"
        text = f"{type_name} пока нет."
        if search_query:
            text = f"По запросу '{search_query}' ничего не найдено."

        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="search_debt")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="session_menu")]
        ])

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        else:
            await event.answer(text, reply_markup=reply_markup)
        return

    type_name = "💵 Мне должны" if debt_type == 'owed_to_me' else "🪙 Я должен"
    text = f"{type_name}:\n\n"

    for item in items:
        repaid_marker = " ✅" if item['is_repaid'] else ""
        text += f"• {item['person_name']} - {item['amount']:.2f} | {item['date']}{repaid_marker}\n"

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(
                text,
                reply_markup=get_items_list_inline(items, 'debt', session_id, search_query)
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await event.bot.send_message(
                event.from_user.id,
                text,
                reply_markup=get_items_list_inline(items, 'debt', session_id, search_query)
            )
    else:
        await event.answer(text, reply_markup=get_items_list_inline(items, 'debt', session_id, search_query))


async def handle_search(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала поиска"""
    item_type = callback.data.split('_', 1)[1]

    if item_type == "debt":
        await state.update_data(
            waiting_for_search=True,
            search_type="debt"
        )
    else:
        await state.update_data(
            waiting_for_search=True,
            search_type="transaction",
            transaction_type=item_type
        )

    try:
        await callback.message.edit_text("Введите текст для поиска:",
                                         reply_markup=get_search_inline(item_type))
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, "Введите текст для поиска:",
                                        reply_markup=get_search_inline(item_type))

    await callback.answer()


# --- РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ---

async def handle_edit_init(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала редактирования"""
    parts = callback.data.split('_')

    if len(parts) < 3:
        await callback.answer("Ошибка формата.", show_alert=True)
        return

    item_type = parts[1]

    try:
        item_id = int(parts[2])
    except ValueError:
        await callback.answer("Неверный ID элемента.", show_alert=True)
        return

    await state.update_data(edit_item_id=item_id, edit_item_type=item_type)

    try:
        await callback.message.edit_text("Что вы хотите изменить?",
                                         reply_markup=get_edit_item_inline(item_type, item_id))
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, "Что вы хотите изменить?",
                                        reply_markup=get_edit_item_inline(item_type, item_id))

    await callback.answer()


async def handle_edit_field(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора поля для редактирования"""
    parts = callback.data.split('_')

    if len(parts) < 5:
        logger.error(f"Неверный формат callback_data в handle_edit_field: {callback.data}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)
        return

    item_type = parts[2]
    try:
        item_id = int(parts[3])
    except ValueError:
        logger.error(f"Неверный ID элемента в callback_data: {parts[3]}")
        await callback.answer("Произошла ошибка. Неверный ID.", show_alert=True)
        return

    field = parts[4]

    await state.update_data(
        edit_item_id=item_id,
        edit_item_type=item_type,
        edit_field=field
    )

    if item_type == 'transaction':
        await state.set_state(EditTransaction.field)
    elif item_type == 'debt':
        await state.set_state(EditDebt.field)

    prompt_map = {
        'amount': "Введите новую сумму:",
        'expense_amount': "Введите новую сумму затрат:",
        'description': "Введите новое описание:",
        'person_name': "Введите новое имя:"
    }

    prompt_text = prompt_map.get(field, "Введите новое значение:")

    try:
        await callback.message.edit_text(prompt_text, reply_markup=get_cancel_inline())
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, prompt_text,
                                        reply_markup=get_cancel_inline())

    await callback.answer()


async def process_edit_field(message: Message, state: FSMContext):
    """Обработчик ввода нового значения для редактирования"""
    data = await state.get_data()

    item_type = data.get('edit_item_type')
    item_id = data.get('edit_item_id')
    field = data.get('edit_field')

    if not all([item_type, item_id, field]):
        await message.answer("Ошибка: данные не найдены.", reply_markup=get_cancel_inline())
        return

    new_value = message.text.strip()

    if field in ['amount', 'expense_amount']:
        try:
            new_value = float(new_value.replace(',', '.'))
            if new_value < 0:
                raise ValueError
        except ValueError:
            return await message.answer("Введите корректное неотрицательное число.",
                                        reply_markup=get_cancel_inline())

    success = False
    if item_type == 'transaction':
        success = update_transaction(item_id, field, new_value)
    elif item_type == 'debt':
        success = update_debt(item_id, field, new_value)

    if success:
        await message.answer("✅ Изменения сохранены.")
    else:
        await message.answer("❌ Ошибка при сохранении изменений.")

    session_id = data.get('current_session_id')
    if session_id:
        await show_session_menu(message, state, session_id)
    else:
        await show_main_menu(message, state)


async def handle_repay_debt(callback: CallbackQuery, state: FSMContext):
    """Обработчик отметки долга как погашенного"""
    try:
        debt_id = int(callback.data.split('_')[2])
    except (ValueError, IndexError):
        await callback.answer("Неверный ID долга.", show_alert=True)
        return

    success = update_debt(debt_id, 'is_repaid', 1)

    if success:
        await callback.answer("✅ Долг отмечен как погашенный.", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при обновлении долга.", show_alert=True)

    session_id = (await state.get_data()).get('current_session_id')
    if session_id:
        await show_session_menu(callback, state, session_id)


async def handle_delete_confirm(callback: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения удаления"""
    parts = callback.data.split('_')

    if len(parts) < 3:
        await callback.answer("Неверный формат команды.", show_alert=True)
        return

    item_type = parts[1]

    try:
        item_id = int(parts[2])
    except ValueError:
        await callback.answer("Неверный ID элемента.", show_alert=True)
        return

    await state.update_data(delete_item_type=item_type, delete_item_id=item_id)

    try:
        await callback.message.edit_text("Вы уверены, что хотите удалить эту запись?",
                                         reply_markup=get_confirmation_inline(f'del_{item_type}', item_id))
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id,
                                        "Вы уверены, что хотите удалить эту запись?",
                                        reply_markup=get_confirmation_inline(f'del_{item_type}', item_id))

    await callback.answer()


async def process_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения действий"""
    parts = callback.data.split('_')

    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data в process_confirmation: {callback.data}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)
        return

    action_type = f"{parts[1]}_{parts[2]}"

    try:
        item_id = int(parts[3])
    except ValueError:
        await callback.answer("Неверный ID элемента.", show_alert=True)
        return

    success = False

    if action_type == 'del_transaction':
        success = delete_transaction(item_id)
        if success:
            await callback.answer("✅ Транзакция удалена.", show_alert=True)
        else:
            await callback.answer("❌ Ошибка при удалении транзакции.", show_alert=True)

    elif action_type == 'del_debt':
        success = delete_debt(item_id)
        if success:
            await callback.answer("✅ Долг удален.", show_alert=True)
        else:
            await callback.answer("❌ Ошибка при удалении долга.", show_alert=True)

    elif action_type == 'close_session':
        close_session(item_id)
        details = get_session_details(item_id)

        if details:
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data=f"nav_session_{item_id}")]]
            )
            try:
                await callback.message.edit_text(
                    f"🏁 Сессия '{details['name']}' завершена.\n"
                    f"Итоговая прибыль: {details['balance']:.2f} {details['currency']}",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await callback.bot.send_message(
                    callback.from_user.id,
                    f"🏁 Сессия '{details['name']}' завершена.\n"
                    f"Итоговая прибыль: {details['balance']:.2f} {details['currency']}",
                    reply_markup=reply_markup
                )
            return
        else:
            await callback.answer("❌ Ошибка при закрытии сессии.", show_alert=True)
            return

    session_id = (await state.get_data()).get('current_session_id')
    if session_id and success:
        await show_session_menu(callback, state, session_id)


async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования"""
    parts = callback.data.split('_')

    if len(parts) < 3:
        await callback.answer("Ошибка формата.", show_alert=True)
        return

    item_type = parts[2]

    if item_type == 'transaction':
        await show_transactions_list(callback, state, 'sale')
    elif item_type == 'debt':
        debt_type = (await state.get_data()).get('debt_type', 'owed_to_me')
        await show_debts_list(callback, state, debt_type)

    await callback.answer()


async def show_report(callback: CallbackQuery, state: FSMContext):
    """Показывает отчет по сессии"""
    session_id = (await state.get_data()).get('current_session_id')

    if not session_id:
        await callback.answer("Ошибка: сессия не найдена.", show_alert=True)
        return

    details = get_session_details(session_id)

    if not details:
        await callback.answer("Ошибка получения данных.", show_alert=True)
        return

    report_text = (
        f"📊 <b>Отчет по сессии: {details['name']}</b>\n\n"
        f"💰 Общий доход: <b>{details['total_sales']:.2f} {details['currency']}</b>\n"
        f"💸 Общие затраты: <b>{details['total_expenses']:.2f} {details['currency']}</b>\n"
        f"💵 Мне должны: <b>{details['owed_to_me']:.2f} {details['currency']}</b>\n"
        f"🪙 Я должен: <b>{details['i_owe']:.2f} {details['currency']}</b>\n\n"
        f"🟢 Чистая прибыль (без учета долгов): <b>{details['balance']:.2f} {details['currency']}</b>\n"
        f"📈 Средний чек: <b>{details['avg_check']:.2f} {details['currency']}</b>"
    )

    reply_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Детальная аналитика", callback_data="advanced_detailed_analytics")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=f"nav_session_{session_id}")]
        ]
    )

    try:
        await callback.message.edit_text(report_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, report_text, reply_markup=reply_markup)


# --- РАСШИРЕННЫЕ ФУНКЦИИ ---

async def advanced_features_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик расширенных функций"""
    action = callback.data.split('_', 1)[1]

    if action == "features":
        try:
            await callback.message.edit_text("🎯 Расширенные функции и аналитика:",
                                             reply_markup=get_advanced_features_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "🎯 Расширенные функции и аналитика:",
                                            reply_markup=get_advanced_features_inline())

    elif action == "detailed_analytics":
        session_id = (await state.get_data()).get('current_session_id')
        await show_detailed_analytics(callback, state, session_id)

    elif action == "sales_velocity":
        session_id = (await state.get_data()).get('current_session_id')
        await show_sales_velocity(callback, state, session_id)

    elif action == "roi_analysis":
        session_id = (await state.get_data()).get('current_session_id')
        await show_roi_analysis(callback, state, session_id)

    elif action == "charts":
        try:
            await callback.message.edit_text("Выберите тип графика:",
                                             reply_markup=get_charts_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактирования сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Выберите тип графика:",
                                            reply_markup=get_charts_inline())

    elif action == "quick_expenses":
        try:
            await callback.message.edit_text("Выберите категорию быстрой затраты:",
                                             reply_markup=get_quick_expense_categories_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Выберите категорию быстрой затраты:",
                                            reply_markup=get_quick_expense_categories_inline())

    elif action == "expense_categories":
        session_id = (await state.get_data()).get('current_session_id')
        await show_expense_categories(callback, state, session_id)

    elif action == "sales_forecast":
        try:
            await callback.message.edit_text("Выберите период для прогноза:",
                                             reply_markup=get_forecast_period_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Выберите период для прогноза:",
                                            reply_markup=get_forecast_period_inline())

    elif action == "settings":
        try:
            await callback.message.edit_text("Настройки сессии:",
                                             reply_markup=get_settings_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Настройки сессии:",
                                            reply_markup=get_settings_inline())

    await callback.answer()

# В handlers.py найдите функцию show_detailed_analytics и замените её:

async def show_detailed_analytics(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Показывает детальную аналитику"""
    try:
        summary = get_session_summary(session_id)
        if not summary:
            await callback.answer("Ошибка: сессия не найдена.", show_alert=True)
            return

        report = generate_analytics_report(summary)

        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Графики", callback_data="advanced_charts")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features")]
        ])

        try:
            await callback.message.edit_text(report, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, report, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета: {e}")
        await callback.answer(f"Ошибка при генерации отчета: {str(e)[:100]}", show_alert=True)

    await callback.answer()
async def show_sales_velocity(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Показывает анализ скорости продаж"""
    velocity = get_sales_velocity(session_id)

    text = f"🚀 <b>АНАЛИЗ СКОРОСТИ ПРОДАЖ</b>\n\n"
    text += f"• Среднее время между продажами: <b>{velocity['avg_time_between_sales']:.1f} часов</b>\n"
    text += f"• Продаж в день: <b>{velocity['sales_per_day']:.1f}</b>\n"
    text += f"• Оценка скорости: <b>{velocity['velocity_score']}/10</b>\n"
    text += f"• Проанализировано продаж: <b>{velocity['total_sales_analyzed']}</b>\n\n"
    text += f"💡 <i>{velocity['message']}</i>"

    emoji_score = "🔥" * min(5, velocity['velocity_score'] // 2)
    if velocity['velocity_score'] >= 8:
        text += f"\n\n🎯 <b>Отличная скорость! {emoji_score}</b>"
    elif velocity['velocity_score'] >= 5:
        text += f"\n\n👍 <b>Хорошая скорость {emoji_score}</b>"
    else:
        text += f"\n\n⚠️ <b>Нужно увеличить скорость продаж {emoji_score}</b>"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная аналитика", callback_data="advanced_detailed_analytics")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)

    await callback.answer()


async def show_roi_analysis(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Показывает анализ ROI"""
    roi = get_roi_analysis(session_id)

    text = f"🎯 <b>АНАЛИЗ ROI (ОКУПАЕМОСТИ)</b>\n\n"
    text += f"• Общий ROI: <b>{roi['roi_percentage']:.1f}%</b>\n"
    text += f"• ROMI (возврат на маркетинг): <b>{roi['romi']:.1f}%</b>\n"
    text += f"• Расходы на рекламу: <b>{roi['ad_spend']:.2f}</b>\n"
    text += f"• CAC (стоимость привлечения): <b>{roi['cac']:.2f}</b>\n"
    text += f"• LTV/CAC соотношение: <b>{roi['ltv_cac_ratio']:.2f}</b>\n\n"

    # Оценка
    if roi['roi_percentage'] >= 100:
        text += "💰 <b>Отличная окупаемость! Бизнес очень прибыльный.</b>"
    elif roi['roi_percentage'] >= 50:
        text += "👍 <b>Хорошая окупаемость. Продолжайте в том же духе.</b>"
    elif roi['roi_percentage'] >= 0:
        text += "⚠️ <b>Окупаемость низкая. Рассмотрите оптимизацию затрат.</b>"
    else:
        text += "❌ <b>Убыточная деятельность. Нужно срочно менять стратегию.</b>"

    if roi['ltv_cac_ratio'] < 3:
        text += "\n\n💡 <i>Рекомендация: Улучшите удержание клиентов для повышения LTV</i>"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная аналитика", callback_data="advanced_detailed_analytics")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)

    await callback.answer()


async def handle_chart_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора графика"""
    chart_type = callback.data.split('_', 1)[1]
    session_id = (await state.get_data()).get('current_session_id')

    if not session_id:
        await callback.answer("Ошибка: сессия не найдена.", show_alert=True)
        return

    details = get_session_details(session_id)

    if chart_type == "profit":
        daily_stats = get_daily_statistics(session_id, 14)
        chart_bytes = generate_profit_chart(daily_stats, details['currency'])

        if chart_bytes:
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=types.BufferedInputFile(chart_bytes.getvalue(), filename="profit_chart.png"),
                caption=f"📈 График прибыли за 14 дней\nСессия: {details['name']}",
                reply_markup=get_back_to_advanced_inline()
            )
        else:
            await callback.answer("Недостаточно данных для графика.", show_alert=True)

    elif chart_type == "expenses":
        expense_breakdown = get_expense_breakdown(session_id)
        chart_bytes = generate_expense_pie_chart(expense_breakdown, details['currency'])

        if chart_bytes:
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=types.BufferedInputFile(chart_bytes.getvalue(), filename="expenses_chart.png"),
                caption=f"🥧 Структура затрат\nСессия: {details['name']}",
                reply_markup=get_back_to_advanced_inline()
            )
        else:
            await callback.answer("Нет данных о затратах.", show_alert=True)

    elif chart_type == "velocity":
        daily_stats = get_daily_statistics(session_id, 14)
        chart_bytes = generate_sales_velocity_chart(daily_stats, details['currency'])

        if chart_bytes:
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=types.BufferedInputFile(chart_bytes.getvalue(), filename="velocity_chart.png"),
                caption=f"🚀 Скорость продаж\nСессия: {details['name']}",
                reply_markup=get_back_to_advanced_inline()
            )
        else:
            await callback.answer("Недостаточно данных для графика.", show_alert=True)

    elif chart_type == "combined":
        daily_stats = get_daily_statistics(session_id, 14)
        chart_bytes = generate_combined_chart(daily_stats, details['currency'])

        if chart_bytes:
            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=types.BufferedInputFile(chart_bytes.getvalue(), filename="combined_chart.png"),
                caption=f"📊 Комбинированный анализ\nСессия: {details['name']}",
                reply_markup=get_back_to_advanced_inline()
            )
        else:
            await callback.answer("Недостаточно данных для графика.", show_alert=True)

    await callback.answer()


async def handle_quick_expense_category(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора категории быстрой затраты"""
    category = callback.data.split('_', 2)[2]

    if category == "custom":
        await callback.message.edit_text("Введите название категории:", reply_markup=get_cancel_inline())
        await state.set_state(AdvancedFeatures.custom_category)
    else:
        await state.update_data(quick_category=category)
        await callback.message.edit_text(f"Категория: {category}\n\nВведите сумму:",
                                         reply_markup=get_cancel_inline())
        await state.set_state(AdvancedFeatures.quick_expense_amount)

    await callback.answer()


async def process_custom_category(message: Message, state: FSMContext):
    """Обработчик ввода своей категории"""
    category = message.text.strip()[:30]
    if not category:
        return await message.answer("Введите корректное название категории:", reply_markup=get_cancel_inline())

    await state.update_data(quick_category=category)
    await message.answer(f"Категория: {category}\n\nВведите сумму:",
                         reply_markup=get_cancel_inline())
    await state.set_state(AdvancedFeatures.quick_expense_amount)


async def process_quick_expense_amount(message: Message, state: FSMContext):
    """Обработчик суммы быстрой затраты"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректную сумму.", reply_markup=get_cancel_inline())

    data = await state.get_data()
    session_id = data.get('current_session_id')
    category = data.get('quick_category', 'Прочее')

    add_quick_expense(session_id, category, amount)

    await message.answer(f"✅ Быстрая затрата добавлена:\n{category}: {amount:.2f}")
    await show_session_menu(message, state, session_id)


async def show_expense_categories(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Показывает категории затрат"""
    expense_breakdown = get_expense_breakdown(session_id)
    details = get_session_details(session_id)

    if not expense_breakdown:
        text = "Затрат пока нет. Добавьте первую затрату!"
    else:
        text = "📊 <b>Категории затрат:</b>\n\n"
        total = sum(expense_breakdown.values())

        for category, amount in expense_breakdown.items():
            percentage = (amount / total * 100) if total > 0 else 0
            text += f"• {category}: <b>{amount:.2f} {details['currency']}</b> ({percentage:.1f}%)\n"

        text += f"\n💰 <b>Всего затрат: {total:.2f} {details['currency']}</b>"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Быстрая затрата", callback_data="advanced_quick_expenses")],
        [InlineKeyboardButton(text="🥧 График затрат", callback_data="chart_expenses")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)

    await callback.answer()


async def handle_forecast_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора периода прогноза"""
    days_str = callback.data.split('_', 1)[1]

    if days_str == "custom":
        await callback.message.edit_text("Введите количество дней для прогноза:", reply_markup=get_cancel_inline())
        await state.set_state(Settings.custom_forecast_days)
    else:
        try:
            days = int(days_str)
            session_id = (await state.get_data()).get('current_session_id')
            await show_sales_forecast(callback, state, session_id, days)
        except ValueError:
            await callback.answer("Неверный формат дней.", show_alert=True)

    await callback.answer()


async def process_custom_forecast_days(message: Message, state: FSMContext):
    """Обработчик ввода своего периода прогноза"""
    try:
        days = int(message.text.strip())
        if days <= 0 or days > 365:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректное число дней (1-365):", reply_markup=get_cancel_inline())

    session_id = (await state.get_data()).get('current_session_id')
    await show_sales_forecast(message, state, session_id, days)


async def show_sales_forecast(event: types.Message | types.CallbackQuery, state: FSMContext, session_id: int,
                              days: int):
    """Показывает прогноз продаж"""
    forecast = get_sales_forecast(session_id, days)
    details = get_session_details(session_id)

    text = f"🔮 <b>ПРОГНОЗ ПРОДАЖ НА {days} ДНЕЙ</b>\n\n"
    text += f"• Ожидаемая прибыль: <b>{forecast['forecast_profit']:.0f} {details['currency']}</b>\n"
    text += f"• Ожидаемая выручка: <b>{forecast['forecast_revenue']:.0f} {details['currency']}</b>\n"
    text += f"• Тренд: <b>{forecast['trend_emoji']} {forecast['trend']}</b>\n"
    text += f"• Уверенность в прогнозе: <b>{forecast['confidence']:.0f}%</b>\n"
    text += f"• Среднедневная прибыль: <b>{forecast['avg_daily_profit']:.0f} {details['currency']}</b>\n"
    text += f"• Проанализировано дней: <b>{forecast['days_analyzed']}</b>\n\n"

    if forecast['trend'] == 'up':
        text += "📈 <b>Тренд восходящий! Отличные перспективы.</b>"
    elif forecast['trend'] == 'down':
        text += "📉 <b>Тренд нисходящий. Рекомендуется анализ причин.</b>"
    else:
        text += "➡️ <b>Тренд стабильный. Бизнес работает ровно.</b>"

    if forecast['confidence'] < 50:
        text += "\n\n⚠️ <i>Уверенность в прогнозе низкая из-за недостатка данных</i>"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная аналитика", callback_data="advanced_detailed_analytics")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features")]
    ])

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)


async def handle_settings_action(callback: CallbackQuery, state: FSMContext):
    """Обработчик действий настроек"""
    action = callback.data.split('_', 1)[1]

    if action == "change_name":
        await callback.message.edit_text("Введите новое название сессии:", reply_markup=get_cancel_inline())
        await state.set_state(Settings.change_name)

    elif action == "change_budget":
        await callback.message.edit_text("Введите новый бюджет сессии:", reply_markup=get_cancel_inline())
        await state.set_state(Settings.change_budget)

    elif action == "summary":
        session_id = (await state.get_data()).get('current_session_id')
        await show_settings_summary(callback, state, session_id)

    elif action == "reset_confirm":
        try:
            await callback.message.edit_text("⚠️ Вы уверены, что хотите сбросить все данные сессии?\n\n"
                                             "Это удалит все продажи, затраты и долги, но оставит сессию активной.",
                                             reply_markup=get_reset_confirmation_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id,
                                            "⚠️ Вы уверены, что хотите сбросить все данные сессии?\n\n"
                                            "Это удалит все продажи, затраты и долги, но оставит сессию активной.",
                                            reply_markup=get_reset_confirmation_inline())

    elif action == "reset":
        session_id = (await state.get_data()).get('current_session_id')
        await reset_session_data(callback, state, session_id)

    await callback.answer()


async def process_change_name(message: Message, state: FSMContext):
    """Обработчик изменения названия сессии"""
    new_name = message.text.strip()[:50]
    if len(new_name) < 3:
        return await message.answer("Название должно быть не менее 3 символов.", reply_markup=get_cancel_inline())

    session_id = (await state.get_data()).get('current_session_id')
    if session_id and update_session(session_id, 'name', new_name):
        await message.answer(f"✅ Название сессии изменено на: {new_name}")
        await show_session_menu(message, state, session_id)
    else:
        await message.answer("❌ Ошибка при изменении названия.", reply_markup=get_cancel_inline())


async def process_change_budget(message: Message, state: FSMContext):
    """Обработчик изменения бюджета сессии"""
    try:
        new_budget = float(message.text.replace(',', '.'))
        if new_budget <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите корректное положительное число.", reply_markup=get_cancel_inline())

    session_id = (await state.get_data()).get('current_session_id')
    if session_id and update_session(session_id, 'budget', new_budget):
        await message.answer(f"✅ Бюджет сессии изменен на: {new_budget:.2f}")
        await show_session_menu(message, state, session_id)
    else:
        await message.answer("❌ Ошибка при изменении бюджета.", reply_markup=get_cancel_inline())


async def show_settings_summary(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Показывает сводку настроек сессии"""
    details = get_session_details(session_id)
    if not details:
        await callback.answer("Ошибка: сессия не найдена.", show_alert=True)
        return

    text = f"⚙️ <b>СВОДКА СЕССИИ: {details['name']}</b>\n\n"
    text += f"• Валюта: <b>{details['currency']}</b>\n"
    text += f"• Бюджет: <b>{details['budget']:.2f}</b>\n"
    text += f"• Статус: <b>{'🟢 Активна' if details['is_active'] else '🔴 Закрыта'}</b>\n"
    text += f"• Создана: <b>{datetime.fromisoformat(details['created_at']).strftime('%d.%m.%Y %H:%M') if details.get('created_at') else 'N/A'}</b>\n"
    text += f"• Обновлена: <b>{datetime.fromisoformat(details['last_updated']).strftime('%d.%m.%Y %H:%M') if details.get('last_updated') else 'N/A'}</b>\n\n"

    text += f"📊 <b>СТАТИСТИКА:</b>\n"
    text += f"• Всего продаж: <b>{details['sales_count']}</b>\n"
    text += f"• Всего транзакций: <b>{details['sales_count'] + int(details['total_expenses'] > 0)}</b>\n"
    text += f"• Долгов: <b>{int(details['owed_to_me'] > 0) + int(details['i_owe'] > 0)}</b>"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data="settings_change_name")],
        [InlineKeyboardButton(text="💰 Изменить бюджет", callback_data="settings_change_budget")],
        [InlineKeyboardButton(text="🔄 Сбросить данные", callback_data="settings_reset_confirm")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_settings")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)

    await callback.answer()


async def reset_session_data(callback: CallbackQuery, state: FSMContext, session_id: int):
    """Сбрасывает данные сессии"""
    # В реальной реализации нужно добавить функцию сброса данных
    # Пока просто сообщаем об успехе
    await callback.answer("⚠️ Функция сброса данных временно недоступна", show_alert=True)
    await advanced_features_handler(callback, state)


# --- АДМИН-ПАНЕЛЬ ---

async def admin_panel_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик админ-панели"""
    action = callback.data.split('_', 1)[1]

    if action == "access":
        try:
            await callback.message.edit_text("Управление доступом:", reply_markup=get_access_management_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Управление доступом:",
                                            reply_markup=get_access_management_inline())

    elif action == "admins":
        try:
            await callback.message.edit_text("Управление админами:", reply_markup=get_admin_management_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Управление админами:",
                                            reply_markup=get_admin_management_inline())

    elif action == "broadcast":
        try:
            await callback.message.edit_text("Выберите аудиторию для рассылки:",
                                             reply_markup=get_broadcast_audience_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Выберите аудиторию для рассылки:",
                                            reply_markup=get_broadcast_audience_inline())

    elif action == "open_user":
        try:
            await callback.message.edit_text(
                "Введите Telegram ID и количество дней через пробел.\nПример: <code>987654321 30</code>",
                reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(
                callback.from_user.id,
                "Введите Telegram ID и количество дней через пробел.\nПример: <code>987654321 30</code>",
                reply_markup=get_cancel_inline())
        await state.set_state(AdminManageAccess.open_user)

    elif action == "close_user":
        try:
            await callback.message.edit_text("Введите Telegram ID пользователя, которому нужно закрыть доступ.",
                                             reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(
                callback.from_user.id,
                "Введите Telegram ID пользователя, которому нужно закрыть доступ.",
                reply_markup=get_cancel_inline())
        await state.set_state(AdminManageAccess.close_user)

    elif action == "open_all":
        success = grant_access_to_all()
        if success:
            reply_text = "✅ Доступ для всех пользователей открыт на 30 дней."
        else:
            reply_text = "❌ Ошибка при открытии доступа всем."

        try:
            await callback.message.edit_text(reply_text, reply_markup=get_access_management_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, reply_text,
                                            reply_markup=get_access_management_inline())

    elif action == "close_all":
        success = revoke_temporary_access()
        if success:
            reply_text = "✅ Доступ для неоплативших пользователей закрыт."
        else:
            reply_text = "❌ Ошибка при закрытии доступа."

        try:
            await callback.message.edit_text(reply_text, reply_markup=get_access_management_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, reply_text,
                                            reply_markup=get_access_management_inline())

    elif action == "add_admin":
        try:
            await callback.message.edit_text("Введите Telegram ID нового администратора.",
                                             reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(
                callback.from_user.id,
                "Введите Telegram ID нового администратора.",
                reply_markup=get_cancel_inline())
        await state.set_state(AdminManageAdmins.add)

    elif action == "remove_admin":
        try:
            await callback.message.edit_text("Введите Telegram ID администратора для удаления.",
                                             reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(
                callback.from_user.id,
                "Введите Telegram ID администратора для удаления.",
                reply_markup=get_cancel_inline())
        await state.set_state(AdminManageAdmins.remove)

    elif action.startswith("broadcast_"):
        audience = action.split('_', 1)[1]
        await state.update_data(audience=audience)

        try:
            await callback.message.edit_text("Введите текст для рассылки:", reply_markup=get_cancel_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(
                callback.from_user.id,
                "Введите текст для рассылки.",
                reply_markup=get_cancel_inline())

        await state.set_state(AdminBroadcast.text)

    elif action == "stats":
        try:
            await callback.message.edit_text("Статистика системы:", reply_markup=get_admin_stats_inline())
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.bot.send_message(callback.from_user.id, "Статистика системы:",
                                            reply_markup=get_admin_stats_inline())

    await callback.answer()


async def process_open_user_access(message: Message, state: FSMContext):
    """Обработчик открытия доступа пользователю"""
    logger.info(f"process_open_user_access вызван с текстом: {message.text}")

    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError

        user_id, days = int(parts[0]), int(parts[1])

        if days <= 0:
            await message.answer("Количество дней должно быть положительным числом.")
            return

        update_user_access(user_id, True, days)
        await message.answer(f"✅ Пользователю {user_id} открыт доступ на {days} дней.")

    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Используйте: <code>ID ДНИ</code>\nПример: <code>987654321 30</code>")

    await state.clear()
    await show_main_menu(message, state)


async def process_close_user_access(message: Message, state: FSMContext):
    """Обработчик закрытия доступа пользователю"""
    logger.info(f"process_close_user_access вызван с текстом: {message.text}")

    try:
        user_id = int(message.text)
        update_user_access(user_id, False)
        await message.answer(f"✅ Пользователю {user_id} закрыт доступ.")

    except ValueError:
        await message.answer("❌ Неверный формат. Введите только ID пользователя.")

    await state.clear()
    await show_main_menu(message, state)


async def process_add_admin(message: Message, state: FSMContext):
    """Обработчик добавления администратора"""
    try:
        user_id = int(message.text)

        if user_id == message.from_user.id:
            await message.answer("❌ Вы не можете добавить самого себя.")
            return

        add_admin(user_id)
        await message.answer(f"✅ Пользователь {user_id} теперь администратор.")

    except ValueError:
        await message.answer("❌ Неверный формат. Введите только ID пользователя.")

    await state.clear()
    await show_main_menu(message, state)


async def process_remove_admin(message: Message, state: FSMContext):
    """Обработчик удаления администратора"""
    try:
        user_id = int(message.text)

        if user_id == ADMIN_ID:
            return await message.answer("❌ Нельзя удалить главного администратора.")

        if user_id == message.from_user.id:
            return await message.answer("❌ Вы не можете удалить самого себя.")

        remove_admin(user_id)
        await message.answer(f"✅ Пользователь {user_id} больше не администратор.")

    except ValueError:
        await message.answer("❌ Неверный формат. Введите только ID пользователя.")

    await state.clear()
    await show_main_menu(message, state)


async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    """Обработчик массовой рассылки"""
    data = await state.get_data()
    audience = data.get('audience')

    if not audience:
        await message.answer("❌ Ошибка: аудитория не указана.")
        await state.clear()
        return

    all_users = get_all_users()
    users_to_send = []

    if audience == "all":
        users_to_send = [u['user_id'] for u in all_users]
    elif audience == "access":
        users_to_send = [u['user_id'] for u in all_users if check_user_access(u['user_id'])]
    elif audience == "no_access":
        users_to_send = [u['user_id'] for u in all_users if not check_user_access(u['user_id'])]

    success_count = 0
    failed_count = 0

    await message.answer(f"📤 Начинаю рассылку для {len(users_to_send)} пользователей...")

    for user_id in users_to_send:
        try:
            await bot.send_message(chat_id=user_id, text=message.text)
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            failed_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    result_text = (
        f"✅ Рассылка завершена.\n"
        f"Успешно отправлено: {success_count}\n"
        f"Не удалось отправить: {failed_count}\n"
        f"Всего пользователей: {len(users_to_send)}"
    )

    await message.answer(result_text)
    await state.clear()
    await show_main_menu(message, state)


# --- ОБЩИЙ ОБРАБОТЧИК ТЕКСТА ДЛЯ ПОИСКА ---

async def handle_search_text(message: Message, state: FSMContext):
    """Обработчик текста поиска"""
    current_state = await state.get_state()

    if current_state:
        return

    data = await state.get_data()
    if data.get('waiting_for_search'):
        search_type = data.get('search_type')
        search_query = message.text.strip()

        if search_type == "transaction":
            trans_type = data.get('transaction_type', 'sale')
            session_id = data.get('current_session_id')
            if session_id:
                await show_transactions_list(message, state, trans_type, search_query)
        elif search_type == "debt":
            debt_type = data.get('debt_type', 'owed_to_me')
            session_id = data.get('current_session_id')
            if session_id:
                await show_debts_list(message, state, debt_type, search_query)

        await state.clear()


# --- РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ---
def register_handlers(dp: Dispatcher):
    """Регистрирует все обработчики в диспетчере."""

    # Навигация и главные команды
    dp.message.register(handle_start_command, CommandStart())
    dp.callback_query.register(navigate, F.data.startswith("nav_"))
    dp.callback_query.register(cancel_action, F.data == "cancel_action")

    # Создание сессии
    dp.message.register(process_session_name, CreateSession.name)
    dp.callback_query.register(process_currency_choice, F.data.startswith("currency_"))
    dp.message.register(process_budget, CreateSession.budget)

    # Действия в сессии
    dp.callback_query.register(session_action_handler, F.data.startswith("session_"))
    dp.callback_query.register(debt_category_handler, F.data.startswith("debt_"))
    dp.callback_query.register(handle_list_debts, F.data.startswith("list_debts_"))

    # FSM для транзакций и долгов
    dp.message.register(process_sale_amount, AddSale.amount)
    dp.message.register(process_sale_expense, AddSale.expense)
    dp.message.register(process_sale_description, AddSale.description)
    dp.message.register(process_expense_amount, AddExpense.amount)
    dp.message.register(process_expense_description, AddExpense.description)
    dp.message.register(process_debt_amount, AddDebt.amount)
    dp.message.register(process_debt_person_name, AddDebt.person_name)
    dp.message.register(process_debt_description, AddDebt.description)

    # Редактирование
    dp.message.register(process_edit_field, EditTransaction.field)
    dp.message.register(process_edit_field, EditDebt.field)

    # Админские обработчики
    dp.message.register(process_open_user_access, AdminManageAccess.open_user)
    dp.message.register(process_close_user_access, AdminManageAccess.close_user)
    dp.message.register(process_add_admin, AdminManageAdmins.add)
    dp.message.register(process_remove_admin, AdminManageAdmins.remove)
    dp.message.register(process_broadcast, AdminBroadcast.text)

    # Поиск
    dp.callback_query.register(handle_search, F.data.startswith("search_"))
    dp.message.register(handle_search_text, F.text)

    # Списки, редактирование, удаление
    dp.callback_query.register(handle_edit_init,
                               F.data.startswith("edit_transaction_") | F.data.startswith("edit_debt_"))
    dp.callback_query.register(handle_edit_field, F.data.startswith("edit_field_"))

    dp.callback_query.register(handle_repay_debt, F.data.startswith("repay_debt_"))
    dp.callback_query.register(handle_delete_confirm,
                               F.data.startswith("del_transaction_") | F.data.startswith("del_debt_"))
    dp.callback_query.register(process_confirmation, F.data.startswith("confirm_"))
    dp.callback_query.register(cancel_edit, F.data.startswith("cancel_edit_"))

    # Расширенные функции
    dp.callback_query.register(advanced_features_handler, F.data.startswith("advanced_"))
    dp.callback_query.register(handle_chart_selection, F.data.startswith("chart_"))
    dp.callback_query.register(handle_quick_expense_category, F.data.startswith("quick_exp_"))
    dp.callback_query.register(handle_forecast_selection, F.data.startswith("forecast_"))
    dp.callback_query.register(handle_settings_action, F.data.startswith("settings_"))

    # Новые FSM состояния
    dp.message.register(process_custom_category, AdvancedFeatures.custom_category)
    dp.message.register(process_quick_expense_amount, AdvancedFeatures.quick_expense_amount)
    dp.message.register(process_custom_forecast_days, Settings.custom_forecast_days)
    dp.message.register(process_change_name, Settings.change_name)
    dp.message.register(process_change_budget, Settings.change_budget)

    # Админ-панель
    dp.callback_query.register(admin_panel_handler, F.data.startswith("admin_"))