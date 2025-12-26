# analytics.py
import io
import matplotlib

matplotlib.use('Agg')  # ДОЛЖНО БЫТЬ В САМОМ НАЧАЛЕ, перед импортом pyplot
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
from db import get_daily_statistics, get_expense_breakdown


def generate_profit_chart(daily_stats: List[Dict[str, Any]], currency: str) -> io.BytesIO:
    """Генерирует график прибыли по дням"""
    if not daily_stats or len(daily_stats) < 2:
        return None

    dates = [stat.get("date_display", "") for stat in daily_stats[::-1]]
    profits = [stat.get("net_profit", 0) for stat in daily_stats[::-1]]

    plt.figure(figsize=(12, 6))

    # Создаем столбчатую диаграмму
    bars = plt.bar(dates, profits, color=['#4CAF50' if p >= 0 else '#F44336' for p in profits],
                   edgecolor='black', linewidth=0.5)

    plt.title(f'📈 Прибыль по дням ({currency})', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Дата', fontsize=12)
    plt.ylabel(f'Прибыль ({currency})', fontsize=12)
    plt.xticks(rotation=45, fontsize=10)
    plt.yticks(fontsize=10)

    # Добавляем сетку
    plt.grid(axis='y', alpha=0.3, linestyle='--')

    # Добавляем значения на столбцы
    for bar, profit in zip(bars, profits):
        height = bar.get_height()
        if height != 0:  # Не показываем 0
            va = 'bottom' if height >= 0 else 'top'
            y_offset = 3 if height >= 0 else -3
            plt.text(bar.get_x() + bar.get_width() / 2., height + y_offset,
                     f'{profit:.0f}',
                     ha='center', va=va,
                     fontsize=9, fontweight='bold',
                     color='green' if height >= 0 else 'red')

    # Добавляем линию тренда если достаточно данных
    if len(profits) > 2:
        x_indices = range(len(profits))
        try:
            z = np.polyfit(x_indices, profits, 1)
            p = np.poly1d(z)
            plt.plot(dates, p(x_indices), "b--", alpha=0.5, linewidth=2, label='Тренд')
            plt.legend()
        except:
            pass

    plt.tight_layout()

    # Сохраняем в байты
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


def generate_expense_pie_chart(expense_breakdown: Dict[str, float], currency: str) -> io.BytesIO:
    """Генерирует круговую диаграмму затрат по категориям"""
    if not expense_breakdown:
        return None

    # Объединяем мелкие категории в "Другое"
    total = sum(expense_breakdown.values())
    threshold = total * 0.05  # 5% порог

    main_categories = {}
    other_sum = 0

    for category, amount in expense_breakdown.items():
        if amount >= threshold:
            main_categories[category] = amount
        else:
            other_sum += amount

    if other_sum > 0:
        main_categories['Другое'] = other_sum

    if not main_categories:
        return None

    # Создаем красивые цвета
    colors = plt.cm.Set3(np.linspace(0, 1, len(main_categories)))

    plt.figure(figsize=(10, 8))

    # Взрываем первый сегмент для акцента
    explode = [0.05] + [0] * (len(main_categories) - 1)

    wedges, texts, autotexts = plt.pie(
        main_categories.values(),
        labels=main_categories.keys(),
        autopct=lambda pct: f'{pct:.1f}%\n({pct * sum(main_categories.values()) / 100:.0f})',
        startangle=90,
        colors=colors,
        explode=explode,
        shadow=True,
        textprops={'fontsize': 10}
    )

    # Делаем проценты жирными
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontweight('bold')

    plt.title(f'🥧 Структура затрат ({currency})', fontsize=16, fontweight='bold', pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


def generate_sales_velocity_chart(daily_stats: List[Dict[str, Any]], currency: str) -> io.BytesIO:
    """Генерирует график продаж по дням"""
    if not daily_stats:
        return None

    dates = [stat.get("date_display", "") for stat in daily_stats[::-1]]
    sales_counts = [stat.get("sales_count", 0) for stat in daily_stats[::-1]]
    revenues = [stat.get("total_sales", 0) for stat in daily_stats[::-1]]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # График количества продаж
    bars1 = ax1.bar(dates, sales_counts, color='#2196F3', edgecolor='black', linewidth=0.5)
    ax1.set_title('🛒 Количество продаж по дням', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Количество', fontsize=12)
    ax1.set_xticklabels(dates, rotation=45, fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Добавляем значения на столбцы
    for bar, count in zip(bars1, sales_counts):
        if count > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.1,
                     f'{count}',
                     ha='center', va='bottom',
                     fontsize=9, fontweight='bold')

    # График выручки
    bars2 = ax2.bar(dates, revenues, color='#FF9800', edgecolor='black', linewidth=0.5)
    ax2.set_title(f'💰 Выручка по дням ({currency})', fontsize=14, fontweight='bold')
    ax2.set_ylabel(f'Выручка ({currency})', fontsize=12)
    ax2.set_xlabel('Дата', fontsize=12)
    ax2.set_xticklabels(dates, rotation=45, fontsize=10)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    # Добавляем значения на столбцы
    for bar, revenue in zip(bars2, revenues):
        if revenue > 0:
            ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + max(revenues) * 0.01,
                     f'{revenue:.0f}',
                     ha='center', va='bottom',
                     fontsize=9, fontweight='bold')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


def generate_combined_chart(daily_stats: List[Dict[str, Any]], currency: str) -> io.BytesIO:
    """Генерирует комбинированный график прибыли и продаж"""
    if not daily_stats or len(daily_stats) < 2:
        return None

    dates = [stat.get("date_display", "") for stat in daily_stats[::-1]]
    profits = [stat.get("net_profit", 0) for stat in daily_stats[::-1]]
    sales_counts = [stat.get("sales_count", 0) for stat in daily_stats[::-1]]

    fig, ax1 = plt.subplots(figsize=(14, 8))

    # Столбцы прибыли
    bars = ax1.bar(dates, profits, color=['#4CAF50' if p >= 0 else '#F44336' for p in profits],
                   alpha=0.7, label='Прибыль', edgecolor='black', linewidth=0.5)

    ax1.set_xlabel('Дата', fontsize=12)
    ax1.set_ylabel(f'Прибыль ({currency})', fontsize=12, color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.set_xticklabels(dates, rotation=45, fontsize=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Добавляем значения прибыли
    for bar, profit in zip(bars, profits):
        if profit != 0:
            va = 'bottom' if profit >= 0 else 'top'
            y_offset = max(profits) * 0.02 if profit >= 0 else -max(profits) * 0.02
            ax1.text(bar.get_x() + bar.get_width() / 2., profit + y_offset,
                     f'{profit:.0f}',
                     ha='center', va=va,
                     fontsize=9, fontweight='bold',
                     color='green' if profit >= 0 else 'red')

    # Линия количества продаж
    ax2 = ax1.twinx()
    line = ax2.plot(dates, sales_counts, 'b-', marker='o', linewidth=3,
                    markersize=8, label='Кол-во продаж', alpha=0.7)

    ax2.set_ylabel('Количество продаж', fontsize=12, color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')

    # Добавляем значения количества продаж
    for i, count in enumerate(sales_counts):
        if count > 0:
            ax2.text(i, count + max(sales_counts) * 0.02, f'{count}',
                     ha='center', va='bottom',
                     fontsize=9, fontweight='bold', color='blue')

    # Объединяем легенды
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

    plt.title(f'📊 Комбинированный анализ: Прибыль и количество продаж ({currency})',
              fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


def generate_analytics_report(session_summary: Dict[str, Any]) -> str:
    """Генерирует текстовый аналитический отчет"""
    if not session_summary:
        return "Ошибка: не удалось получить данные для отчета"

    # Получаем данные с безопасным доступом
    details = session_summary.get("details", {})
    velocity = session_summary.get("velocity", {})
    profitability = session_summary.get("profitability", {})
    roi = session_summary.get("roi", {})
    forecast = session_summary.get("forecast", {})
    daily_stats = session_summary.get("daily_stats", [])
    expense_breakdown = session_summary.get("expense_breakdown", {})

    # Безопасный доступ к дате создания
    created_at = details.get('created_at')
    if created_at:
        try:
            created_date = datetime.fromisoformat(created_at).strftime('%d.%m.%Y %H:%M')
        except:
            created_date = 'N/A'
    else:
        created_date = 'N/A'

    report = f"""
📊 ПОДРОБНЫЙ АНАЛИТИЧЕСКИЙ ОТЧЕТ
────────────────────────────
Сессия: <b>{details.get('name', 'Нет данных')}</b>
Валюта: <b>{details.get('currency', 'Нет данных')}</b>
Статус: <b>{'🟢 Активна' if details.get('is_active', False) else '🔴 Закрыта'}</b>
Создана: <b>{created_date}</b>

📈 ОСНОВНЫЕ МЕТРИКИ:
────────────────────────────
• Общая выручка: <b>{details.get('total_sales', 0):.2f} {details.get('currency', '')}</b>
• Общие затраты: <b>{details.get('total_expenses', 0):.2f} {details.get('currency', '')}</b>
• Чистая прибыль: <b>{details.get('balance', 0):.2f} {details.get('currency', '')}</b>
• Количество продаж: <b>{details.get('sales_count', 0)}</b>
• Средний чек: <b>{details.get('avg_check', 0):.2f} {details.get('currency', '')}</b>
• Рентабельность: <b>{profitability.get('profitability_percentage', 0):.1f}%</b> ({profitability.get('total_profitable', 0)}/{profitability.get('total_sales_analyzed', 0)} прибыльных)

🚀 СКОРОСТЬ ПРОДАЖ:
────────────────────────────
• Среднее время между продажами: <b>{velocity.get('avg_time_between_sales', 0):.1f} часов</b>
• Продаж в день: <b>{velocity.get('sales_per_day', 0):.1f}</b>
• Оценка скорости: <b>{'🔥' * min(5, velocity.get('velocity_score', 0) // 2)}</b> ({velocity.get('velocity_score', 0)}/10)

💰 АНАЛИЗ ПРИБЫЛЬНОСТИ:
────────────────────────────
• Средняя маржа: <b>{profitability.get('avg_profit_margin', 0):.1f}%</b>
• Прибыльных сделок: <b>{profitability.get('total_profitable', 0)}</b>
• Убыточных сделок: <b>{profitability.get('total_unprofitable', 0)}</b>

🎯 ROI АНАЛИЗ:
────────────────────────────
• Общий ROI: <b>{roi.get('roi_percentage', 0):.1f}%</b>
• ROMI (возврат на маркетинг): <b>{roi.get('romi', 0):.1f}%</b>
• Расходы на рекламу: <b>{roi.get('ad_spend', 0):.2f} {details.get('currency', '')}</b>
• CAC (стоимость привлечения): <b>{roi.get('cac', 0):.2f} {details.get('currency', '')}</b>
• LTV/CAC соотношение: <b>{roi.get('ltv_cac_ratio', 0):.2f}</b>

📊 ЗАТРАТЫ ПО КАТЕГОРИЯМ:
────────────────────────────
"""

    if expense_breakdown:
        total_expenses = sum(expense_breakdown.values())
        for category, amount in expense_breakdown.items():
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
            report += f"• {category}: <b>{amount:.2f} {details.get('currency', '')}</b> ({percentage:.1f}%)\n"
    else:
        report += "• Нет данных о затратах\n"

    if daily_stats:
        report += f"""
📅 ПОСЛЕДНИЕ {len(daily_stats)} ДНЕЙ:
────────────────────────────
"""
        total_profit_week = sum(day.get("net_profit", 0) for day in daily_stats)
        total_sales_week = sum(day.get("sales_count", 0) for day in daily_stats)

        for day in daily_stats[:7]:  # Показываем только последние 7 дней
            profit = day.get("net_profit", 0)
            sales_count = day.get("sales_count", 0)
            day_name = day.get("day_name", "День")
            profit_emoji = "🟢" if profit >= 0 else "🔴"
            report += f"• {day_name[:3]}: {profit_emoji} {profit:.0f} ({sales_count} продаж)\n"

        report += f"• Итого за {len(daily_stats)} дней: <b>{total_profit_week:.0f} {details.get('currency', '')}</b> ({total_sales_week} продаж)\n"

    report += f"""
🔮 ПРОГНОЗ НА 30 ДНЕЙ:
────────────────────────────
• Ожидаемая прибыль: <b>{forecast.get('forecast_profit', 0):.0f} {details.get('currency', '')}</b>
• Ожидаемая выручка: <b>{forecast.get('forecast_revenue', 0):.0f} {details.get('currency', '')}</b>
• Тренд: <b>{forecast.get('trend_emoji', '➡️')} {forecast.get('trend', 'stable')}</b>
• Уверенность в прогнозе: <b>{forecast.get('confidence', 0):.0f}%</b>
• Среднедневная прибыль: <b>{forecast.get('avg_daily_profit', 0):.0f} {details.get('currency', '')}</b>
• Проанализировано дней: <b>{forecast.get('days_analyzed', 0)}</b>

💡 РЕКОМЕНДАЦИИ:
────────────────────────────
"""

    # Генерируем рекомендации на основе данных
    recommendations = []

    if profitability.get('profitability_percentage', 0) < 70:
        recommendations.append("• Увеличить долю прибыльных сделок - анализируйте убыточные продажи")

    if roi.get('romi', 0) < 100:
        recommendations.append("• Оптимизировать рекламные расходы - проверьте эффективность каналов")

    if velocity.get('sales_per_day', 0) < 1:
        recommendations.append("• Увеличить частоту продаж - рассмотрите акции или дополнительные каналы сбыта")

    if roi.get('ltv_cac_ratio', 0) < 3:
        recommendations.append("• Улучшить удержание клиентов - работайте с повторными продажами")

    if len(recommendations) > 0:
        report += "\n".join(recommendations)
    else:
        report += "• Показатели в норме, продолжайте в том же духе! 🎯"

    report += f"\n\n📅 Отчет сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    return report