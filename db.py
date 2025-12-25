# db.py
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import requests
from dotenv import load_dotenv

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
load_dotenv()

# --- НАСТРОЙКИ JSONBIN ---
JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY")
MASTER_BIN_ID = os.getenv("MASTER_BIN_ID")

if not JSONBIN_API_KEY:
    raise ValueError("JSONBIN_API_KEY не найден в переменных окружения")
if not MASTER_BIN_ID:
    raise ValueError("MASTER_BIN_ID не найден в переменных окружения")

JSONBIN_BASE_URL = "https://api.jsonbin.io/v3/b"

# Структура данных для хранения в JSON
INITIAL_DATA_STRUCTURE = {
    "users": {},
    "sessions": {},
    "transactions": {},
    "debts": {}
}


class JSONBinManager:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-Master-Key": JSONBIN_API_KEY,
        }
        self.master_bin_id = MASTER_BIN_ID

    def _load_data(self) -> Dict[str, Any]:
        """Загружает данные из JSONBin"""
        try:
            response = requests.get(f"{JSONBIN_BASE_URL}/{self.master_bin_id}/latest", headers=self.headers)
            if response.status_code == 200:
                return response.json()["record"]
            return INITIAL_DATA_STRUCTURE.copy()
        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")
            return INITIAL_DATA_STRUCTURE.copy()

    def _save_data(self, data: Dict[str, Any]) -> bool:
        """Сохраняет данные в JSONBin"""
        try:
            response = requests.put(f"{JSONBIN_BASE_URL}/{self.master_bin_id}", headers=self.headers, json=data)
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")
            return False

    def _get_next_id(self, data_type: str) -> int:
        """Генерирует следующий ID для указанного типа данных"""
        data = self._load_data()
        if data_type not in data:
            return 1
        existing_ids = [int(id_) for id_ in data[data_type].keys() if id_.isdigit()]
        return max(existing_ids, default=0) + 1


# Создаем глобальный экземпляр менеджера
db_manager = JSONBinManager()


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---

def ensure_user_exists(user_id: int) -> None:
    """Создает запись пользователя, если её нет"""
    data = db_manager._load_data()

    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "role": "user",
            "access_expiry": None,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        db_manager._save_data(data)


def update_user_activity(user_id: int) -> None:
    """Обновляет время последней активности пользователя"""
    data = db_manager._load_data()

    if str(user_id) in data["users"]:
        data["users"][str(user_id)]["last_active"] = datetime.now().isoformat()
        db_manager._save_data(data)


def get_user_role(user_id: int) -> str:
    """Возвращает роль пользователя"""
    data = db_manager._load_data()
    user = data["users"].get(str(user_id), {})
    return user.get("role", "user")


def check_user_access(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя доступ"""
    data = db_manager._load_data()
    user = data["users"].get(str(user_id), {})

    if user.get("role") == "admin":
        return True

    expiry_str = user.get("access_expiry")
    if not expiry_str:
        return False

    try:
        expiry = datetime.fromisoformat(expiry_str)
        return datetime.now() < expiry
    except:
        return False


def update_user_access(user_id: int, has_access: bool, days: int = 30) -> bool:
    """Обновляет доступ пользователя"""
    data = db_manager._load_data()

    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "role": "user",
            "access_expiry": None,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }

    if has_access:
        expiry = datetime.now() + timedelta(days=days)
        data["users"][str(user_id)]["access_expiry"] = expiry.isoformat()
    else:
        data["users"][str(user_id)]["access_expiry"] = None

    return db_manager._save_data(data)


def add_admin(user_id: int) -> bool:
    """Добавляет администратора"""
    data = db_manager._load_data()

    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "role": "admin",
            "access_expiry": None,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
    else:
        data["users"][str(user_id)]["role"] = "admin"

    return db_manager._save_data(data)


def remove_admin(user_id: int) -> bool:
    """Удаляет администратора"""
    data = db_manager._load_data()

    if str(user_id) in data["users"] and str(user_id) != "8382571809":
        data["users"][str(user_id)]["role"] = "user"
        data["users"][str(user_id)]["access_expiry"] = None
        return db_manager._save_data(data)

    return False


def get_all_users() -> List[Dict[str, Any]]:
    """Возвращает список всех пользователей"""
    data = db_manager._load_data()
    users = []

    for user_id_str, user_data in data["users"].items():
        users.append({
            "user_id": int(user_id_str),
            "role": user_data.get("role", "user"),
            "access_expiry": user_data.get("access_expiry"),
            "created_at": user_data.get("created_at"),
            "last_active": user_data.get("last_active")
        })

    return users


def grant_access_to_all() -> bool:
    """Открывает доступ всем пользователям на 30 дней"""
    data = db_manager._load_data()
    expiry = (datetime.now() + timedelta(days=30)).isoformat()

    try:
        for user_id_str, user_data in data["users"].items():
            if user_data.get("role") != "admin":
                data["users"][user_id_str]["access_expiry"] = expiry

        return db_manager._save_data(data)
    except Exception as e:
        print(f"Ошибка при открытии доступа всем: {e}")
        return False


def revoke_temporary_access() -> bool:
    """Закрывает доступ всем пользователям без админки"""
    data = db_manager._load_data()

    try:
        for user_id_str, user_data in data["users"].items():
            if user_data.get("role") != "admin":
                data["users"][user_id_str]["access_expiry"] = None

        return db_manager._save_data(data)
    except Exception as e:
        print(f"Ошибка при закрытии доступа всем: {e}")
        return False


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С СЕССИЯМИ ---

def add_session(user_id: int, name: str, budget: float, currency: str) -> int:
    """Создает новую сессию и возвращает её ID"""
    data = db_manager._load_data()
    session_id = db_manager._get_next_id("sessions")

    data["sessions"][str(session_id)] = {
        "user_id": user_id,
        "name": name[:50],
        "budget": float(budget),
        "currency": currency,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "closed_at": None,
        "last_updated": datetime.now().isoformat()
    }

    db_manager._save_data(data)
    return session_id


def get_user_sessions(user_id: int) -> List[tuple]:
    """Возвращает список сессий пользователя"""
    data = db_manager._load_data()
    sessions = []

    for session_id_str, session_data in data["sessions"].items():
        if session_data.get("user_id") == user_id:
            sessions.append((
                int(session_id_str),
                session_data["name"],
                session_data["budget"],
                session_data["currency"],
                session_data["is_active"]
            ))

    return sorted(sessions, key=lambda x: x[0], reverse=True)  # Новые сверху


def get_session_details(session_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает детали сессии с расчетами"""
    data = db_manager._load_data()
    session_data = data["sessions"].get(str(session_id))

    if not session_data:
        return None

    # Получаем все транзакции для сессии
    transactions = [
        t for t in data["transactions"].values()
        if t.get("session_id") == session_id
    ]

    # Получаем все долги для сессии
    debts = [
        d for d in data["debts"].values()
        if d.get("session_id") == session_id
    ]

    # Расчеты
    sales = [t for t in transactions if t.get("type") == "sale"]
    expenses = [t for t in transactions if t.get("type") == "expense"]

    total_sales = sum(t.get("amount", 0) for t in sales)
    total_expenses = sum(t.get("expense_amount", 0) for t in sales) + sum(t.get("amount", 0) for t in expenses)

    debts_owed_to_me = [d for d in debts if d.get("type") == "owed_to_me" and not d.get("is_repaid", False)]
    debts_i_owe = [d for d in debts if d.get("type") == "i_owe" and not d.get("is_repaid", False)]

    owed_to_me = sum(d.get("amount", 0) for d in debts_owed_to_me)
    i_owe = sum(d.get("amount", 0) for d in debts_i_owe)

    balance = total_sales - total_expenses

    # Рассчитываем средний чек
    avg_check = total_sales / len(sales) if sales else 0

    return {
        "name": session_data["name"],
        "currency": session_data["currency"],
        "budget": session_data["budget"],
        "is_active": session_data["is_active"],
        "balance": balance,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "sales_count": len(sales),
        "owed_to_me": owed_to_me,
        "i_owe": i_owe,
        "avg_check": avg_check,
        "created_at": session_data.get("created_at"),
        "last_updated": session_data.get("last_updated")
    }


def close_session(session_id: int) -> bool:
    """Закрывает сессию"""
    data = db_manager._load_data()

    if str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)]["is_active"] = False
        data["sessions"][str(session_id)]["closed_at"] = datetime.now().isoformat()
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()
        return db_manager._save_data(data)

    return False


def update_session(session_id: int, field: str, value: Any) -> bool:
    """Обновляет поле сессии"""
    data = db_manager._load_data()

    if str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)][field] = value
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()
        return db_manager._save_data(data)

    return False


# --- ФУНКЦИИ ДЛЯ ТРАНЗАКЦИЙ ---

def add_transaction(session_id: int, trans_type: str, amount: float, expense_amount: float, description: str) -> int:
    """Добавляет транзакцию (продажу или затрату)"""
    data = db_manager._load_data()
    transaction_id = db_manager._get_next_id("transactions")

    data["transactions"][str(transaction_id)] = {
        "session_id": session_id,
        "type": trans_type,
        "amount": float(amount),
        "expense_amount": float(expense_amount),
        "description": description[:100],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Обновляем время последнего изменения сессии
    if str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

    db_manager._save_data(data)
    return transaction_id


def get_transactions_list(session_id: int, trans_type: str = None, search_query: str = None, limit: int = None) -> List[
    Dict[str, Any]]:
    """Возвращает список транзакций с фильтрацией"""
    data = db_manager._load_data()
    transactions = []

    for trans_id_str, trans_data in data["transactions"].items():
        if trans_data.get("session_id") != session_id:
            continue

        if trans_type and trans_data.get("type") != trans_type:
            continue

        if search_query:
            desc = trans_data.get("description", "").lower()
            if search_query.lower() not in desc:
                continue

        # Форматируем дату для отображения
        try:
            date_obj = datetime.fromisoformat(trans_data["created_at"])
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = trans_data.get("created_at", "")

        transactions.append({
            "id": int(trans_id_str),
            "type": trans_data.get("type"),
            "amount": trans_data.get("amount", 0),
            "expense_amount": trans_data.get("expense_amount", 0),
            "description": trans_data.get("description", ""),
            "date": formatted_date,
            "created_at": trans_data.get("created_at"),
            "profit": trans_data.get("amount", 0) - trans_data.get("expense_amount", 0)
        })

    # Сортируем по дате (новые сверху)
    transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    if limit:
        transactions = transactions[:limit]

    return transactions


def update_transaction(transaction_id: int, field: str, new_value: Any) -> bool:
    """Обновляет поле транзакции"""
    data = db_manager._load_data()

    if str(transaction_id) not in data["transactions"]:
        return False

    if field in ["amount", "expense_amount"]:
        new_value = float(new_value)

    data["transactions"][str(transaction_id)][field] = new_value
    data["transactions"][str(transaction_id)]["updated_at"] = datetime.now().isoformat()

    # Обновляем время сессии
    session_id = data["transactions"][str(transaction_id)].get("session_id")
    if session_id and str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

    return db_manager._save_data(data)


def delete_transaction(transaction_id: int) -> bool:
    """Удаляет транзакцию"""
    data = db_manager._load_data()

    if str(transaction_id) in data["transactions"]:
        # Получаем session_id перед удалением
        session_id = data["transactions"][str(transaction_id)].get("session_id")

        del data["transactions"][str(transaction_id)]

        # Обновляем время сессии
        if session_id and str(session_id) in data["sessions"]:
            data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

        return db_manager._save_data(data)

    return False


def get_transaction_type(transaction_id: int) -> Optional[str]:
    """Возвращает тип транзакции"""
    data = db_manager._load_data()
    trans_data = data["transactions"].get(str(transaction_id))
    return trans_data.get("type") if trans_data else None


# --- ФУНКЦИИ ДЛЯ ДОЛГОВ ---

def add_debt(session_id: int, debt_type: str, person_name: str, amount: float, description: str = "") -> int:
    """Добавляет запись о долге"""
    data = db_manager._load_data()
    debt_id = db_manager._get_next_id("debts")

    data["debts"][str(debt_id)] = {
        "session_id": session_id,
        "type": debt_type,
        "person_name": person_name[:50],
        "amount": float(amount),
        "description": description[:100],
        "is_repaid": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Обновляем время сессии
    if str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

    db_manager._save_data(data)
    return debt_id


def get_debts_list(session_id: int, debt_type: str = None, search_query: str = None, limit: int = None) -> List[
    Dict[str, Any]]:
    """Возвращает список долгов с фильтрацией"""
    data = db_manager._load_data()
    debts = []

    for debt_id_str, debt_data in data["debts"].items():
        if debt_data.get("session_id") != session_id:
            continue

        if debt_type and debt_data.get("type") != debt_type:
            continue

        if search_query:
            person = debt_data.get("person_name", "").lower()
            desc = debt_data.get("description", "").lower()
            if search_query.lower() not in person and search_query.lower() not in desc:
                continue

        # Форматируем дату
        try:
            date_obj = datetime.fromisoformat(debt_data["created_at"])
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = debt_data.get("created_at", "")

        debts.append({
            "id": int(debt_id_str),
            "type": debt_data.get("type"),
            "person_name": debt_data.get("person_name", ""),
            "amount": debt_data.get("amount", 0),
            "description": debt_data.get("description", ""),
            "is_repaid": debt_data.get("is_repaid", False),
            "date": formatted_date,
            "created_at": debt_data.get("created_at")
        })

    debts.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    if limit:
        debts = debts[:limit]

    return debts


def update_debt(debt_id: int, field: str, new_value: Any) -> bool:
    """Обновляет поле долга"""
    data = db_manager._load_data()

    if str(debt_id) not in data["debts"]:
        return False

    if field == "amount":
        new_value = float(new_value)
    elif field == "is_repaid":
        new_value = bool(int(new_value)) if isinstance(new_value, (int, str)) else bool(new_value)

    data["debts"][str(debt_id)][field] = new_value
    data["debts"][str(debt_id)]["updated_at"] = datetime.now().isoformat()

    # Обновляем время сессии
    session_id = data["debts"][str(debt_id)].get("session_id")
    if session_id and str(session_id) in data["sessions"]:
        data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

    return db_manager._save_data(data)


def delete_debt(debt_id: int) -> bool:
    """Удаляет запись о долге"""
    data = db_manager._load_data()

    if str(debt_id) in data["debts"]:
        # Получаем session_id перед удалением
        session_id = data["debts"][str(debt_id)].get("session_id")

        del data["debts"][str(debt_id)]

        # Обновляем время сессии
        if session_id and str(session_id) in data["sessions"]:
            data["sessions"][str(session_id)]["last_updated"] = datetime.now().isoformat()

        return db_manager._save_data(data)

    return False


# --- НОВЫЕ ФУНКЦИИ ДЛЯ АНАЛИТИКИ ИНТЕРНЕТ-ПРОДАЖ ---

def get_daily_statistics(session_id: int, days: int = 7) -> List[Dict[str, Any]]:
    """Возвращает статистику по дням за последние N дней"""
    data = db_manager._load_data()

    daily_stats = []
    today = datetime.now().date()

    for i in range(days):
        date = today - timedelta(days=i)
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())

        daily_sales = []
        daily_expenses = []

        for trans_id_str, trans_data in data["transactions"].items():
            if trans_data.get("session_id") != session_id:
                continue

            trans_date = datetime.fromisoformat(trans_data["created_at"])

            if date_start <= trans_date <= date_end:
                if trans_data.get("type") == "sale":
                    daily_sales.append(trans_data)
                elif trans_data.get("type") == "expense":
                    daily_expenses.append(trans_data)

        total_daily_sales = sum(s.get("amount", 0) for s in daily_sales)
        total_daily_expenses = sum(s.get("expense_amount", 0) for s in daily_sales) + \
                               sum(e.get("amount", 0) for e in daily_expenses)

        daily_stats.append({
            "date": date.isoformat(),
            "date_display": date.strftime("%d.%m.%Y"),
            "day_name": date.strftime("%A"),
            "sales_count": len(daily_sales),
            "expenses_count": len(daily_expenses),
            "total_sales": total_daily_sales,
            "total_expenses": total_daily_expenses,
            "net_profit": total_daily_sales - total_daily_expenses,
            "transactions": daily_sales + daily_expenses
        })

    return daily_stats


def get_sales_velocity(session_id: int) -> Dict[str, Any]:
    """Анализирует скорость продаж (сколько времени между продажами)"""
    transactions = get_transactions_list(session_id, 'sale', limit=50)

    if len(transactions) < 2:
        return {
            "avg_time_between_sales": 0,
            "sales_per_day": 0,
            "velocity_score": 0,
            "message": "Недостаточно данных для анализа"
        }

    # Сортируем по дате
    transactions.sort(key=lambda x: x.get("created_at"))

    time_diffs = []
    prev_date = None

    for trans in transactions:
        trans_date = datetime.fromisoformat(trans["created_at"])
        if prev_date:
            diff_hours = (trans_date - prev_date).total_seconds() / 3600
            if diff_hours > 0:
                time_diffs.append(diff_hours)
        prev_date = trans_date

    if not time_diffs:
        return {
            "avg_time_between_sales": 0,
            "sales_per_day": 0,
            "velocity_score": 0,
            "message": "Не удалось рассчитать скорость"
        }

    avg_time_hours = sum(time_diffs) / len(time_diffs)
    sales_per_day = 24 / avg_time_hours if avg_time_hours > 0 else 0

    # Оценка скорости (1-10)
    if sales_per_day >= 10:
        velocity_score = 10
    elif sales_per_day >= 5:
        velocity_score = 8
    elif sales_per_day >= 2:
        velocity_score = 6
    elif sales_per_day >= 1:
        velocity_score = 4
    elif sales_per_day >= 0.5:
        velocity_score = 2
    else:
        velocity_score = 1

    return {
        "avg_time_between_sales": avg_time_hours,
        "sales_per_day": sales_per_day,
        "velocity_score": velocity_score,
        "total_sales_analyzed": len(transactions),
        "message": f"Среднее время между продажами: {avg_time_hours:.1f} часов"
    }


def get_profitability_analysis(session_id: int) -> Dict[str, Any]:
    """Анализ прибыльности продаж"""
    sales = get_transactions_list(session_id, 'sale')

    if not sales:
        return {
            "total_profitable": 0,
            "total_unprofitable": 0,
            "profitability_percentage": 0,
            "avg_profit_margin": 0,
            "most_profitable": [],
            "least_profitable": []
        }

    profitable = []
    unprofitable = []

    for sale in sales:
        profit = sale.get("profit", 0)
        if profit > 0:
            profitable.append(sale)
        elif profit < 0:
            unprofitable.append(sale)

    # Расчет маржи прибыли для каждой продажи
    profit_margins = []
    for sale in sales:
        revenue = sale.get("amount", 0)
        cost = sale.get("expense_amount", 0)
        if revenue > 0:
            margin = ((revenue - cost) / revenue) * 100
            profit_margins.append(margin)

    avg_margin = sum(profit_margins) / len(profit_margins) if profit_margins else 0

    # Самые прибыльные продажи
    most_profitable = sorted(sales, key=lambda x: x.get("profit", 0), reverse=True)[:5]

    # Самые убыточные продажи
    least_profitable = sorted(sales, key=lambda x: x.get("profit", 0))[:5]

    return {
        "total_profitable": len(profitable),
        "total_unprofitable": len(unprofitable),
        "profitability_percentage": (len(profitable) / len(sales)) * 100 if sales else 0,
        "avg_profit_margin": avg_margin,
        "most_profitable": most_profitable,
        "least_profitable": least_profitable,
        "total_sales_analyzed": len(sales)
    }


def get_quick_expense_categories() -> List[str]:
    """Возвращает список категорий для быстрых затрат (интернет-продажи)"""
    return [
        "Реклама (таргет)",
        "Реклама (контекст)",
        "Креативы",
        "Доставка",
        "Упаковка",
        "Возвраты",
        "Обслуживание сайта",
        "Подписки (сервисы)",
        "Обмен/возврат",
        "Прочее"
    ]


def add_quick_expense(session_id: int, category: str, amount: float, description: str = "") -> int:
    """Добавляет быструю затрату по категории"""
    if not description:
        description = f"Быстрая затрата: {category}"

    return add_transaction(session_id, 'expense', amount, 0, description)


def get_expense_breakdown(session_id: int) -> Dict[str, float]:
    """Разбивает затраты по категориям"""
    expenses = get_transactions_list(session_id, 'expense')

    categories = {}

    for expense in expenses:
        desc = expense.get("description", "")
        amount = expense.get("amount", 0)

        # Определяем категорию из описания
        category = "Прочее"

        # Проверяем ключевые слова
        desc_lower = desc.lower()
        if any(word in desc_lower for word in ["таргет", "таргетирован", "социальн"]):
            category = "Реклама (таргет)"
        elif any(word in desc_lower for word in ["контекст", "яндекс", "google", "поиск"]):
            category = "Реклама (контекст)"
        elif any(word in desc_lower for word in ["креатив", "дизайн", "фото", "видео"]):
            category = "Креативы"
        elif any(word in desc_lower for word in ["доставк", "курьер", "почта", "тк"]):
            category = "Доставка"
        elif any(word in desc_lower for word in ["упаковк", "коробк", "пленк"]):
            category = "Упаковка"
        elif any(word in desc_lower for word in ["возврат", "отмен"]):
            category = "Возвраты"
        elif any(word in desc_lower for word in ["сайт", "хостинг", "домен"]):
            category = "Обслуживание сайта"
        elif any(word in desc_lower for word in ["подписк", "сервис", "приложен"]):
            category = "Подписки (сервисы)"
        elif "быстрая затрата:" in desc_lower:
            # Извлекаем категорию из быстрой затраты
            parts = desc.split(":")
            if len(parts) > 1:
                category = parts[1].strip()

        if category in categories:
            categories[category] += amount
        else:
            categories[category] = amount

    return dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))


def get_roi_analysis(session_id: int) -> Dict[str, Any]:
    """Анализ ROI (Return on Investment)"""
    sales = get_transactions_list(session_id, 'sale')
    expenses = get_transactions_list(session_id, 'expense')

    # Общие затраты на рекламу
    ad_expenses = 0
    for expense in expenses:
        desc = expense.get("description", "").lower()
        if any(word in desc for word in ["реклам", "таргет", "контекст", "продвижен"]):
            ad_expenses += expense.get("amount", 0)

    total_revenue = sum(sale.get("amount", 0) for sale in sales)
    total_expenses = sum(expense.get("amount", 0) for expense in expenses)

    if ad_expenses == 0:
        return {
            "roi_percentage": 0,
            "romi": 0,  # Return on Marketing Investment
            "ad_spend": 0,
            "revenue_from_ads": total_revenue,  # Предполагаем что весь доход от рекламы
            "cac": 0,  # Customer Acquisition Cost
            "ltv": 0,  # Lifetime Value (приблизительно)
            "message": "Затраты на рекламу не найдены"
        }

    # ROI = (Доход - Затраты) / Затраты * 100%
    roi_percentage = ((total_revenue - total_expenses) / total_expenses * 100) if total_expenses > 0 else 0

    # ROMI = (Доход от рекламы - Затраты на рекламу) / Затраты на рекламу * 100%
    romi = ((total_revenue - ad_expenses) / ad_expenses * 100) if ad_expenses > 0 else 0

    # CAC (Customer Acquisition Cost) = Затраты на рекламу / Количество продаж
    cac = ad_expenses / len(sales) if sales else 0

    # LTV (Lifetime Value) - приблизительный расчет
    avg_sale = total_revenue / len(sales) if sales else 0
    ltv = avg_sale * 3  # Предполагаем 3 повторных покупки

    return {
        "roi_percentage": roi_percentage,
        "romi": romi,
        "ad_spend": ad_expenses,
        "revenue": total_revenue,
        "total_expenses": total_expenses,
        "cac": cac,
        "ltv": ltv,
        "ltv_cac_ratio": ltv / cac if cac > 0 else 0,
        "message": f"ROI: {roi_percentage:.1f}%, ROMI: {romi:.1f}%"
    }


def get_sales_forecast(session_id: int, days: int = 30) -> Dict[str, Any]:
    """Прогноз продаж на основе исторических данных"""
    daily_stats = get_daily_statistics(session_id, min(30, days * 2))

    if len(daily_stats) < 7:
        return {
            "forecast_revenue": 0,
            "forecast_profit": 0,
            "confidence": 0,
            "trend": "stable",
            "message": "Недостаточно данных для прогноза (нужно минимум 7 дней)"
        }

    # Рассчитываем тренд
    recent_profits = [day["net_profit"] for day in daily_stats[:7]]
    avg_recent = sum(recent_profits) / len(recent_profits)

    older_profits = [day["net_profit"] for day in daily_stats[7:14] if len(daily_stats) > 7]
    avg_older = sum(older_profits) / len(older_profits) if older_profits else avg_recent

    # Определяем тренд
    if avg_recent > avg_older * 1.2:
        trend = "up"
        trend_factor = 1.1
    elif avg_recent < avg_older * 0.8:
        trend = "down"
        trend_factor = 0.9
    else:
        trend = "stable"
        trend_factor = 1.0

    # Прогноз
    avg_daily_profit = sum(day["net_profit"] for day in daily_stats) / len(daily_stats)
    avg_daily_revenue = sum(day["total_sales"] for day in daily_stats) / len(daily_stats)

    forecast_profit = avg_daily_profit * days * trend_factor
    forecast_revenue = avg_daily_revenue * days * trend_factor

    # Уверенность в прогнозе
    confidence = min(90, len(daily_stats) * 3)

    trend_emoji = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"

    return {
        "forecast_revenue": forecast_revenue,
        "forecast_profit": forecast_profit,
        "confidence": confidence,
        "trend": trend,
        "trend_emoji": trend_emoji,
        "avg_daily_profit": avg_daily_profit,
        "avg_daily_revenue": avg_daily_revenue,
        "days_analyzed": len(daily_stats),
        "message": f"Прогноз на {days} дней: {trend_emoji} {forecast_profit:.0f} прибыли"
    }


# --- ФУНКЦИИ ДЛЯ ЭКСПОРТА И ОТЧЕТОВ ---

def get_session_summary(session_id: int) -> Dict[str, Any]:
    """Возвращает полную сводку по сессии"""
    details = get_session_details(session_id)
    if not details:
        return {}

    velocity = get_sales_velocity(session_id)
    profitability = get_profitability_analysis(session_id)
    roi = get_roi_analysis(session_id)
    forecast = get_sales_forecast(session_id, 30)
    daily_stats = get_daily_statistics(session_id, 7)
    expense_breakdown = get_expense_breakdown(session_id)

    return {
        "details": details,
        "velocity": velocity,
        "profitability": profitability,
        "roi": roi,
        "forecast": forecast,
        "daily_stats": daily_stats,
        "expense_breakdown": expense_breakdown,
        "generated_at": datetime.now().isoformat()
    }


# --- ИНИЦИАЛИЗАЦИЯ ---

def init_db() -> None:
    """Инициализирует базу данных в JSONBin"""
    data = db_manager._load_data()

    # Проверяем структуру данных
    for key in INITIAL_DATA_STRUCTURE.keys():
        if key not in data:
            data[key] = INITIAL_DATA_STRUCTURE[key]

    # Добавляем главного администратора, если его нет
    if "8382571809" not in data["users"]:
        data["users"]["8382571809"] = {
            "role": "admin",
            "access_expiry": None,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }

    db_manager._save_data(data)
    print("База данных инициализирована в JSONBin")