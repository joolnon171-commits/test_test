# export.py (упрощенная версия без pandas)

import io
from datetime import datetime
from typing import List, Dict, Any
from db import get_transactions_list, get_debts_list, get_session_details, get_session_summary
from analytics import generate_analytics_report


def generate_text_report(session_id: int) -> str:
    """Генерирует текстовый отчет по сессии"""
    summary = get_session_summary(session_id)
    if not summary:
        return "Ошибка: не удалось получить данные сессии"

    return generate_analytics_report(summary)


def generate_excel_report(session_id: int) -> Optional[io.BytesIO]:
    """Заглушка для Excel отчета (Excel временно отключен)"""
    return None


def generate_csv_report(session_id: int, data_type: str = 'sales') -> Optional[io.BytesIO]:
    """Заглушка для CSV отчета (CSV временно отключен)"""
    return None


def format_date_for_export(date_str: str) -> str:
    """Форматирует дату для экспорта"""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return date_str