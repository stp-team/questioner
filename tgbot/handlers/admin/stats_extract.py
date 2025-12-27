import logging
from io import BytesIO

import pandas as pd
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from numpy.random.mtrand import Sequence
from stp_database.repo.Questions import QuestionsRequestsRepo
from stp_database.repo.STP import MainRequestsRepo

from tgbot.filters.admin import AdminFilter
from tgbot.keyboards.admin.main import AdminMenu
from tgbot.keyboards.admin.stats_extract import (
    DivisionStatsExtract,
    MonthStatsExtract,
    division_selection_kb,
    extract_kb,
)

stats_router = Router()
stats_router.message.filter(AdminFilter())
stats_router.callback_query.filter(AdminFilter())

logger = logging.getLogger(__name__)


@stats_router.callback_query(AdminMenu.filter(F.menu == "stats_extract"))
async def extract_stats(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        """<b>📥 Выгрузка статистики</b>

Универсальная выгрузка для обоих направлений

<i>Выбери период выгрузки используя меню</i>""",
        reply_markup=extract_kb(),
    )
    await callback.answer()


@stats_router.callback_query(MonthStatsExtract.filter(F.menu == "month"))
async def admin_extract_month_select_division(
    callback: CallbackQuery,
    callback_data: MonthStatsExtract,
) -> None:
    """После выбора месяца показываем выбор направления"""
    month = callback_data.month
    year = callback_data.year

    # Названия месяцев на русском
    month_names = {
        1: "январь",
        2: "февраль",
        3: "март",
        4: "апрель",
        5: "май",
        6: "июнь",
        7: "июль",
        8: "август",
        9: "сентябрь",
        10: "октябрь",
        11: "ноябрь",
        12: "декабрь",
    }

    await callback.message.edit_text(
        f"""<b>📥 Выгрузка статистики</b>

Выбран период: <b>{month_names[month]} {year}</b>

<i>Теперь выбери направление для выгрузки:</i>""",
        reply_markup=division_selection_kb(month=month, year=year),
    )
    await callback.answer()


@stats_router.callback_query(DivisionStatsExtract.filter(F.menu == "division"))
async def admin_extract_division(
    callback: CallbackQuery,
    callback_data: DivisionStatsExtract,
    questions_repo: QuestionsRequestsRepo,
    stp_repo: MainRequestsRepo,
) -> None:
    """Выгрузка статистики по выбранному месяцу и направлению"""
    month = callback_data.month
    year = callback_data.year
    division = callback_data.division

    # Названия месяцев на русском
    month_names = {
        1: "январь",
        2: "февраль",
        3: "март",
        4: "апрель",
        5: "май",
        6: "июнь",
        7: "июль",
        8: "август",
        9: "сентябрь",
        10: "октябрь",
        11: "ноябрь",
        12: "декабрь",
    }

    # Отправляем сообщение о начале обработки
    await callback.message.edit_text(
        f"""<b>📥 Выгрузка статистики</b>

Период: <b>{month_names[month]} {year}</b>
Направление: <b>{division}</b>

⏳ Обрабатываю данные, это может занять некоторое время..."""
    )

    # Получаем все вопросы за месяц
    questions: Sequence = await questions_repo.questions.get_questions_by_month(
        month=month, year=year
    )

    # Собираем все уникальные user_id для батчевого запроса
    employee_ids = set()
    duty_ids = set()
    for question in questions:
        employee_ids.add(question.employee_userid)
        if question.duty_userid:
            duty_ids.add(question.duty_userid)

    # Батчево получаем всех сотрудников и дежурных
    logger.info(
        f"Fetching employee data for {len(employee_ids)} employees and {len(duty_ids)} duty users"
    )
    all_employees = await stp_repo.employee.get_users()
    logger.info(f"Retrieved {len(all_employees)} total employees from database")

    # Создаем словари для быстрого поиска
    employees_dict = {emp.user_id: emp for emp in all_employees if emp.user_id}
    logger.info(f"Created lookup dictionary with {len(employees_dict)} employees")

    # Подготавливаем данные для Excel
    data = []
    processed_count = 0
    for question in questions:
        processed_count += 1
        if processed_count % 1000 == 0:
            logger.info(f"Processed {processed_count}/{len(questions)} questions")
        # Получаем данные из словарей
        employee = employees_dict.get(question.employee_userid)
        duty = (
            employees_dict.get(question.duty_userid) if question.duty_userid else None
        )

        # Применяем фильтр по направлению
        if division and division != "ВСЕ" and employee and employee.division:
            if division.upper() not in employee.division.upper():
                continue

        # Определяем статус чата
        if question.status == "open":
            status = "Открыт"
        elif question.status == "in_progress":
            status = "В работе"
        elif question.status == "closed":
            status = "Закрыт"
        else:
            status = question.status

        # Оценки качества
        quality_employee = (
            "Хорошо"
            if question.quality_employee
            else ("Плохо" if question.quality_employee is False else "")
        )
        quality_duty = (
            "Хорошо"
            if question.quality_duty
            else ("Плохо" if question.quality_duty is False else "")
        )

        # Возможность возврата
        allow_return = "Доступен" if question.allow_return else "Недоступен"

        data.append({
            "Токен": question.token,
            "Дежурный": duty.fullname if duty else "Не назначен",
            "Специалист": employee.fullname if employee else "Не найден",
            "Направление": employee.division if employee else "Не указано",
            "Вопрос": question.question_text,
            "Время вопроса": question.start_time,
            "Время завершения": question.end_time,
            "Ссылка на БЗ": question.clever_link,
            "Оценка специалиста": quality_employee,
            "Оценка дежурного": quality_duty,
            "Статус чата": status,
            "Возврат": allow_return,
        })

    if not data:
        await callback.message.edit_text(
            f"""<b>📥 Выгрузка статистики</b>

Не найдено вопросов для периода <b>{month_names[month]} {year}</b> и направления <b>{division}</b>

Всего обработано вопросов: {len(questions)}

Попробуй другой месяц или направление""",
            reply_markup=extract_kb(),
        )
        await callback.answer()
        return

    # Создаем файл excel в памяти
    df = pd.DataFrame(data)
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=f"{division} - {month}_{year}", index=False)

    excel_buffer.seek(0)

    # Создаем имя файла
    filename = f"История вопросов {division} - {month_names[month]} {year}.xlsx"

    # Сохраняем файл в буфер
    excel_file = BufferedInputFile(excel_buffer.getvalue(), filename=filename)

    await callback.message.answer_document(
        excel_file,
        caption=f"""📊 <b>Статистика {division}</b>

📅 Период: {month_names[month]} {year}
📋 Количество вопросов: {len(data)}""",
    )

    # Возвращаемся к главному меню статистики
    await callback.message.answer(
        """<b>📥 Выгрузка статистики</b>

Универсальная выгрузка для обоих направлений

<i>Выбери период выгрузки используя меню</i>""",
        reply_markup=extract_kb(),
    )

    await callback.answer()
