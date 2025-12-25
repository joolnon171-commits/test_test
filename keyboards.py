# keyboards.py
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from db import get_quick_expense_categories


# --- ГЛАВНОЕ МЕНЮ И НАВИГАЦИЯ ---

def get_main_menu_inline(sessions: list, is_admin: bool) -> InlineKeyboardMarkup:
    """
    Генерирует главное меню.
    :param sessions: Список сессий пользователя в формате (id, name, budget, currency, is_active)
    :param is_admin: Является ли пользователь администратором
    """
    builder = InlineKeyboardBuilder()

    if is_admin:
        builder.add(InlineKeyboardButton(text="🛠️ Админ-Панель", callback_data="nav_admin_panel"))

    if sessions:
        for session in sessions:
            session_id, name, budget, currency, is_active = session
            # Обрезаем длинное название
            short_name = (name[:15] + '...') if len(name) > 15 else name
            status_icon = "✅" if is_active else "⏸️"
            builder.add(InlineKeyboardButton(
                text=f"{status_icon} {short_name}",
                callback_data=f"nav_session_{session_id}"
            ))

    builder.add(InlineKeyboardButton(text="➕ Создать новую сессию", callback_data="nav_create_session"))
    builder.adjust(1)
    return builder.as_markup()


def get_cancel_inline() -> InlineKeyboardMarkup:
    """Клавиатура для отмены действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="nav_start")]
    ])


# --- АДМИН-ПАНЕЛЬ ---

def get_admin_panel_inline() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👤 Управление доступом", callback_data="admin_access"))
    builder.add(InlineKeyboardButton(text="👑 Управление админами", callback_data="admin_admins"))
    builder.add(InlineKeyboardButton(text="📢 Массовая рассылка", callback_data="admin_broadcast"))
    builder.add(InlineKeyboardButton(text="📊 Статистика системы", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="nav_start"))
    builder.adjust(2)
    return builder.as_markup()


def get_access_management_inline() -> InlineKeyboardMarkup:
    """Клавиатура управления доступом"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Открыть доступ пользователю", callback_data="admin_open_user"))
    builder.add(InlineKeyboardButton(text="Закрыть доступ пользователю", callback_data="admin_close_user"))
    builder.add(InlineKeyboardButton(text="Открыть доступ всем", callback_data="admin_open_all"))
    builder.add(InlineKeyboardButton(text="Закрыть доступ всем", callback_data="admin_close_all"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="nav_admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


def get_admin_management_inline() -> InlineKeyboardMarkup:
    """Клавиатура управления администраторами"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Добавить админа", callback_data="admin_add_admin"))
    builder.add(InlineKeyboardButton(text="Удалить админа", callback_data="admin_remove_admin"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="nav_admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


def get_broadcast_audience_inline() -> InlineKeyboardMarkup:
    """Клавиатура выбора аудитории для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Для пользователей с доступом", callback_data="admin_broadcast_access"))
    builder.add(InlineKeyboardButton(text="Для пользователей без доступа", callback_data="admin_broadcast_no_access"))
    builder.add(InlineKeyboardButton(text="Для всех пользователей", callback_data="admin_broadcast_all"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="nav_admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


def get_admin_stats_inline() -> InlineKeyboardMarkup:
    """Клавиатура статистики системы"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📈 Статистика пользователей", callback_data="admin_stats_users"))
    builder.add(InlineKeyboardButton(text="📊 Статистика сессий", callback_data="admin_stats_sessions"))
    builder.add(InlineKeyboardButton(text="💾 Очистка данных", callback_data="admin_stats_cleanup"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="nav_admin_panel"))
    builder.adjust(2)
    return builder.as_markup()


# --- МЕНЮ СЕССИИ ---

def get_session_menu_inline(is_active: bool) -> InlineKeyboardMarkup:
    """
    Генерирует меню сессии.
    :param is_active: Активна ли сессия
    """
    builder = InlineKeyboardBuilder()

    if is_active:
        # Основные операции
        builder.add(InlineKeyboardButton(text="💰 Добавить продажу", callback_data="session_add_sale"))
        builder.add(InlineKeyboardButton(text="💸 Добавить затраты", callback_data="session_add_expense"))
        builder.add(InlineKeyboardButton(text="🪙 Управление долгами", callback_data="session_manage_debts"))
        builder.add(InlineKeyboardButton(text="📈 Мои продажи", callback_data="session_list_sales"))
        builder.add(InlineKeyboardButton(text="📉 Мои затраты", callback_data="session_list_expenses"))

        # Расширенные функции
        builder.add(InlineKeyboardButton(text="🎯 Расширенная аналитика", callback_data="advanced_features"))
        builder.add(InlineKeyboardButton(text="📊 Быстрый отчет", callback_data="session_report"))
        builder.add(InlineKeyboardButton(text="⚡ Быстрые затраты", callback_data="advanced_quick_expenses"))
        builder.add(InlineKeyboardButton(text="✅ Завершение сессии", callback_data="session_close_confirm"))
    else:
        # Только просмотр для закрытых сессий
        builder.add(InlineKeyboardButton(text="📈 Мои продажи", callback_data="session_list_sales"))
        builder.add(InlineKeyboardButton(text="📉 Мои затраты", callback_data="session_list_expenses"))
        builder.add(InlineKeyboardButton(text="🪙 Долги", callback_data="session_manage_debts"))
        builder.add(InlineKeyboardButton(text="📊 Полный отчет", callback_data="session_report"))
        builder.add(InlineKeyboardButton(text="🎯 Расширенная аналитика", callback_data="advanced_features"))

    builder.add(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="nav_start"))
    builder.adjust(2)
    return builder.as_markup()


# --- УПРАВЛЕНИЕ ДОЛГАМИ ---

def get_debt_management_inline() -> InlineKeyboardMarkup:
    """Меню для выбора действия с долгами: просмотр или добавление."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💵 Посмотреть долги мне", callback_data="list_debts_owed_to_me"))
    builder.add(InlineKeyboardButton(text="🪙 Посмотреть мои долги", callback_data="list_debts_i_owe"))
    builder.add(InlineKeyboardButton(text="➕ Добавить долг мне", callback_data="debt_owed_to_me"))
    builder.add(InlineKeyboardButton(text="➕ Добавить мой долг", callback_data="debt_i_owe"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="session_menu"))
    builder.adjust(2)
    return builder.as_markup()


# --- СПИСКИ И ДЕЙСТВИЯ ---

def get_items_list_inline(items: list, item_type: str, session_id: int,
                          search_query: str = None) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для списков (транзакции, долги).
    :param items: Список объектов из БД
    :param item_type: 'transaction' или 'debt'
    :param session_id: ID текущей сессии
    :param search_query: Текущий поисковый запрос
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        item_id = item['id']

        # Формируем текст для кнопки
        if item_type == 'transaction':
            # Для транзакций показываем описание
            desc = item.get('description', 'Без названия')
            short_desc = (desc[:20] + '...') if len(desc) > 20 else desc

            # Добавляем значки для типа транзакции
            icon = "💰" if item.get('type') == 'sale' else "💸"
            button_text = f"{icon} {short_desc}"

        elif item_type == 'debt':
            # Для долгов показываем имя и статус
            person_name = item.get('person_name', 'Без имени')
            short_name = (person_name[:20] + '...') if len(person_name) > 20 else person_name

            # Добавляем иконку в зависимости от типа долга и статуса
            if item.get('type') == 'owed_to_me':
                icon = "💵"
            else:
                icon = "🪙"

            # Отмечаем погашенные долги
            if item.get('is_repaid', False):
                icon = "✅"

            button_text = f"{icon} {short_name}"

        # Добавляем кнопки редактирования и удаления
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"edit_{item_type}_{item_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="🗑️",
            callback_data=f"del_{item_type}_{item_id}_confirm"
        ))

    builder.adjust(2)

    # Кнопки навигации
    nav_buttons = []

    # Кнопка поиска
    if search_query:
        nav_buttons.append(InlineKeyboardButton(
            text="🔍 Новый поиск",
            callback_data=f"search_{'debt' if item_type == 'debt' else 'transaction'}"
        ))

    # Кнопка возврата в меню
    nav_buttons.append(InlineKeyboardButton(
        text="⬅️ Назад в меню",
        callback_data="session_menu"
    ))

    builder.row(*nav_buttons)
    return builder.as_markup()


def get_search_inline(item_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для поиска"""
    cancel_action = f"cancel_search_{item_type}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_action)]
    ])


def get_confirmation_inline(action: str, item_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действий.
    :param action: 'del_transaction', 'del_debt', 'close_session'
    :param item_id: ID элемента
    """
    builder = InlineKeyboardBuilder()

    if action == 'close_session':
        confirm_text = "✅ Да, завершить сессию"
        confirm_icon = "✅"
    else:
        confirm_text = "✅ Да, удалить"
        confirm_icon = "🗑️"

    builder.add(InlineKeyboardButton(
        text=confirm_text,
        callback_data=f"confirm_{action}_{item_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Нет, отмена",
        callback_data="cancel_action"
    ))

    builder.adjust(2)
    return builder.as_markup()


def get_edit_item_inline(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора поля редактирования.
    :param item_type: 'transaction' или 'debt'
    :param item_id: ID элемента
    """
    builder = InlineKeyboardBuilder()

    if item_type == 'transaction':
        builder.add(InlineKeyboardButton(
            text="✏️ Сумма",
            callback_data=f"edit_field_{item_type}_{item_id}_amount"
        ))
        builder.add(InlineKeyboardButton(
            text="✏️ Описание",
            callback_data=f"edit_field_{item_type}_{item_id}_description"
        ))

    elif item_type == 'debt':
        builder.add(InlineKeyboardButton(
            text="✏️ Сумма",
            callback_data=f"edit_field_{item_type}_{item_id}_amount"
        ))
        builder.add(InlineKeyboardButton(
            text="✏️ Имя",
            callback_data=f"edit_field_{item_type}_{item_id}_person_name"
        ))
        builder.add(InlineKeyboardButton(
            text="✏️ Описание",
            callback_data=f"edit_field_{item_type}_{item_id}_description"
        ))
        builder.add(InlineKeyboardButton(
            text="✅ Погашен",
            callback_data=f"repay_debt_{item_id}"
        ))

    builder.add(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=f"cancel_edit_{item_type}"
    ))

    builder.adjust(2)
    return builder.as_markup()


def get_currency_inline() -> InlineKeyboardMarkup:
    """Клавиатура выбора валюты"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="USDT 💎", callback_data="currency_USDT"))
    builder.add(InlineKeyboardButton(text="Рубль ПМР 🇲🇩", callback_data="currency_RUB"))
    builder.adjust(2)
    return builder.as_markup()


# --- РАСШИРЕННЫЕ ФУНКЦИИ ---

def get_advanced_features_inline() -> InlineKeyboardMarkup:
    """Клавиатура расширенных функций для интернет-продаж"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="📊 Детальная аналитика", callback_data="advanced_detailed_analytics"))
    builder.add(InlineKeyboardButton(text="🚀 Скорость продаж", callback_data="advanced_sales_velocity"))
    builder.add(InlineKeyboardButton(text="💰 ROI анализ", callback_data="advanced_roi_analysis"))
    builder.add(InlineKeyboardButton(text="📈 Графики", callback_data="advanced_charts"))
    builder.add(InlineKeyboardButton(text="⚡ Быстрые затраты", callback_data="advanced_quick_expenses"))
    builder.add(InlineKeyboardButton(text="📋 Категории затрат", callback_data="advanced_expense_categories"))
    builder.add(InlineKeyboardButton(text="🔮 Прогноз продаж", callback_data="advanced_sales_forecast"))
    builder.add(InlineKeyboardButton(text="⚙️ Настройки сессии", callback_data="advanced_settings"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="session_menu"))

    builder.adjust(2)
    return builder.as_markup()


def get_quick_expense_categories_inline() -> InlineKeyboardMarkup:
    """Кнопки быстрых категорий затрат для интернет-продаж"""
    builder = InlineKeyboardBuilder()

    categories = get_quick_expense_categories()

    for category in categories:
        builder.add(InlineKeyboardButton(text=category, callback_data=f"quick_exp_{category}"))

    builder.add(InlineKeyboardButton(text="✏️ Своя категория", callback_data="quick_exp_custom"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features"))

    builder.adjust(2)
    return builder.as_markup()


def get_charts_inline() -> InlineKeyboardMarkup:
    """Кнопки графиков для интернет-продаж"""
    builder = InlineKeyboardBuilder()

    charts = [
        ("📈 Прибыль по дням", "chart_profit"),
        ("🥧 Структура затрат", "chart_expenses"),
        ("🚀 Скорость продаж", "chart_velocity"),
        ("📊 Комбинированный", "chart_combined")
    ]

    for text, chart_type in charts:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"chart_{chart_type}"))

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features"))

    builder.adjust(2)
    return builder.as_markup()


def get_forecast_period_inline() -> InlineKeyboardMarkup:
    """Кнопки для выбора периода прогноза"""
    builder = InlineKeyboardBuilder()

    periods = [
        ("📅 На неделю", "7"),
        ("📆 На месяц", "30"),
        ("📊 На квартал", "90"),
        ("🎯 На полгода", "180"),
        ("✏️ Свой период", "custom")
    ]

    for text, days in periods:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"forecast_{days}"))

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_sales_forecast"))

    builder.adjust(2)
    return builder.as_markup()


def get_date_range_inline() -> InlineKeyboardMarkup:
    """Кнопки для выбора периода анализа"""
    builder = InlineKeyboardBuilder()

    periods = [
        ("📅 Сегодня", "today"),
        ("📅 Вчера", "yesterday"),
        ("📅 Текущая неделя", "week"),
        ("📅 Текущий месяц", "month"),
        ("📅 Последние 7 дней", "last7"),
        ("📅 Последние 30 дней", "last30"),
        ("📅 За все время", "all"),
        ("✏️ Выбрать даты", "custom")
    ]

    for text, period in periods:
        builder.add(InlineKeyboardButton(text=text, callback_data=f"period_{period}"))

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features"))

    builder.adjust(3)
    return builder.as_markup()


def get_settings_inline() -> InlineKeyboardMarkup:
    """Кнопки настроек сессии"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data="settings_change_name"))
    builder.add(InlineKeyboardButton(text="💰 Изменить бюджет", callback_data="settings_change_budget"))
    builder.add(InlineKeyboardButton(text="📊 Сводка данных", callback_data="settings_summary"))
    builder.add(InlineKeyboardButton(text="🔄 Сбросить сессию", callback_data="settings_reset_confirm"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="advanced_features"))

    builder.adjust(2)
    return builder.as_markup()


def get_reset_confirmation_inline() -> InlineKeyboardMarkup:
    """Подтверждение сброса сессии"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="✅ Да, сбросить все данные", callback_data="settings_reset"))
    builder.add(InlineKeyboardButton(text="❌ Нет, отмена", callback_data="advanced_settings"))

    builder.adjust(2)
    return builder.as_markup()


def get_back_to_session_inline(session_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата в меню сессии"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню сессии", callback_data=f"nav_session_{session_id}")]
    ])


def get_back_to_advanced_inline() -> InlineKeyboardMarkup:
    """Кнопка возврата к расширенным функциям"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к аналитике", callback_data="advanced_features")]
    ])