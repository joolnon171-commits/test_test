# export.py
import io
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from db import get_transactions_list, get_debts_list, get_session_details, get_session_summary


def generate_text_report(session_id: int) -> str:
    """Генерирует текстовый отчет по сессии"""
    from analytics import generate_analytics_report

    summary = get_session_summary(session_id)
    if not summary:
        return "Ошибка: не удалось получить данные сессии"

    return generate_analytics_report(summary)


def generate_excel_report(session_id: int) -> io.BytesIO:
    """Генерирует Excel отчет по сессии"""
    # Получаем данные
    sales = get_transactions_list(session_id, 'sale')
    expenses = get_transactions_list(session_id, 'expense')
    debts_owed = get_debts_list(session_id, 'owed_to_me')
    debts_i_owe = get_debts_list(session_id, 'i_owe')
    session_details = get_session_details(session_id)

    if not session_details:
        return None

    # Создаем Excel файл в памяти
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Лист с продажами
        if sales:
            df_sales = pd.DataFrame([
                {
                    'ID': sale['id'],
                    'Дата': sale['date'],
                    'Сумма': sale['amount'],
                    'Затраты': sale['expense_amount'],
                    'Прибыль': sale['profit'],
                    'Описание': sale['description'],
                    'Маржа %': ((sale['amount'] - sale['expense_amount']) / sale['amount'] * 100) if sale[
                                                                                                         'amount'] > 0 else 0
                }
                for sale in sales
            ])
            df_sales.to_excel(writer, sheet_name='Продажи', index=False)

        # Лист с затратами
        if expenses:
            df_expenses = pd.DataFrame([
                {
                    'ID': exp['id'],
                    'Дата': exp['date'],
                    'Сумма': exp['amount'],
                    'Описание': exp['description']
                }
                for exp in expenses
            ])
            df_expenses.to_excel(writer, sheet_name='Затраты', index=False)

        # Лист с долгами
        if debts_owed or debts_i_owe:
            all_debts = []
            for debt in debts_owed:
                all_debts.append({
                    'Тип': 'Мне должны',
                    'Имя': debt['person_name'],
                    'Сумма': debt['amount'],
                    'Описание': debt['description'],
                    'Статус': 'Погашен' if debt['is_repaid'] else 'Ожидает',
                    'Дата': debt['date']
                })

            for debt in debts_i_owe:
                all_debts.append({
                    'Тип': 'Я должен',
                    'Имя': debt['person_name'],
                    'Сумма': debt['amount'],
                    'Описание': debt['description'],
                    'Статус': 'Погашен' if debt['is_repaid'] else 'Ожидает',
                    'Дата': debt['date']
                })

            df_debts = pd.DataFrame(all_debts)
            df_debts.to_excel(writer, sheet_name='Долги', index=False)

        # Лист с итогами
        summary_data = {
            'Показатель': [
                'Название сессии',
                'Валюта',
                'Статус',
                'Бюджет',
                'Общая выручка',
                'Общие затраты',
                'Чистая прибыль',
                'Количество продаж',
                'Средний чек',
                'Долги к получению',
                'Мои долги',
                'Дата создания',
                'Последнее обновление'
            ],
            'Значение': [
                session_details['name'],
                session_details['currency'],
                'Активна' if session_details['is_active'] else 'Закрыта',
                session_details['budget'],
                session_details['total_sales'],
                session_details['total_expenses'],
                session_details['balance'],
                session_details['sales_count'],
                session_details['avg_check'],
                session_details['owed_to_me'],
                session_details['i_owe'],
                datetime.fromisoformat(session_details['created_at']).strftime('%d.%m.%Y %H:%M') if session_details.get(
                    'created_at') else 'N/A',
                datetime.fromisoformat(session_details['last_updated']).strftime(
                    '%d.%m.%Y %H:%M') if session_details.get('last_updated') else 'N/A'
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Итоги', index=False)

        # Лист с аналитикой
        summary = get_session_summary(session_id)
        if summary:
            analytics_data = {
                'Метрика': [
                    'ROI (%)',
                    'ROMI (%)',
                    'Стоимость привлечения (CAC)',
                    'Средняя маржа (%)',
                    'Прибыльных сделок',
                    'Убыточных сделок',
                    'Скорость продаж (в день)',
                    'Прогноз на месяц',
                    'Тренд'
                ],
                'Значение': [
                    f"{summary['roi']['roi_percentage']:.1f}%",
                    f"{summary['roi']['romi']:.1f}%",
                    f"{summary['roi']['cac']:.2f} {session_details['currency']}",
                    f"{summary['profitability']['avg_profit_margin']:.1f}%",
                    summary['profitability']['total_profitable'],
                    summary['profitability']['total_unprofitable'],
                    f"{summary['velocity']['sales_per_day']:.1f}",
                    f"{summary['forecast']['forecast_profit']:.0f} {session_details['currency']}",
                    summary['forecast']['trend'].capitalize()
                ]
            }
            df_analytics = pd.DataFrame(analytics_data)
            df_analytics.to_excel(writer, sheet_name='Аналитика', index=False)

    output.seek(0)
    return output


def generate_csv_report(session_id: int, data_type: str = 'sales') -> io.BytesIO:
    """Генерирует CSV отчет"""
    if data_type == 'sales':
        data = get_transactions_list(session_id, 'sale')
        filename = 'sales'
    elif data_type == 'expenses':
        data = get_transactions_list(session_id, 'expense')
        filename = 'expenses'
    elif data_type == 'debts':
        data_owed = get_debts_list(session_id, 'owed_to_me')
        data_i_owe = get_debts_list(session_id, 'i_owe')
        data = data_owed + data_i_owe
        filename = 'debts'
    else:
        return None

    if not data:
        return None

    df = pd.DataFrame(data)
    output = io.BytesIO()

    if data_type == 'debts':
        # Для долгов добавляем тип
        df['type_display'] = df['type'].apply(lambda x: 'Мне должны' if x == 'owed_to_me' else 'Я должен')

    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)

    return output


def format_date_for_export(date_str: str) -> str:
    """Форматирует дату для экспорта"""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return date_str