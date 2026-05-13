"""
psyho_matrix_service.py - Сервис для работы с психоматрицей
Соответствует psyho_matrix.py v3.1
"""

import logging
from datetime import date, datetime
from sqlalchemy.future import select
from sqlalchemy import update, func, and_
from sqlalchemy.exc import IntegrityError
from ..database.core import async_session
from ..database.models import PsyhoMatrix  # Убран неиспользуемый EnergyLevel
from ..calculators.psyho_matrix import (
    PsyhoMatrixCalculator, 
    prepare_for_db_insert, 
    validate_for_database
)
from ..users.user_services import user_service

logger = logging.getLogger(__name__)

# Константы для валидации
REQUIRED_MATRIX_FIELDS = [
    'first_number', 'second_number', 'third_number', 'fourth_number',
    'matrix_digits', 'characteristics', 'talent_codes', 'strength_codes',
    'energy_level', 'life_purpose', 'compatibility_hints',
    'additional', 'karmic_analysis', 'forecasting'
]

async def calculate_and_save_psyho_matrix(user_id: int) -> dict:
    """
    Calculate and save psychomatrix - v3.1 (соответствует модулю)
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Dict с данными психоматрицы
        
    Raises:
        ValueError: Если пользователь не найден, дата некорректна или валидация не пройдена
        TypeError: Если передан неверный тип данных
    """
    try:
        # 1. Получаем профиль пользователя
        user_profile = await user_service.get_user_profile_by_id(
            user_id=user_id, 
            include_extended=True
        )
        if not user_profile:
            raise ValueError(f"User {user_id} not found")
        
        # 2. Валидация и преобразование даты
        birth_date_raw = user_profile.get('birth_date')
        if not birth_date_raw:
            raise ValueError(f"No birth_date in user profile for user {user_id}")
        
        # Преобразование строки в date если необходимо
        if isinstance(birth_date_raw, str):
            try:
                birth_date = datetime.strptime(birth_date_raw, '%Y-%m-%d').date()
            except ValueError as e:
                raise ValueError(f"Invalid birth_date format for user {user_id}: {e}")
        elif isinstance(birth_date_raw, date):
            birth_date = birth_date_raw
        else:
            raise TypeError(f"birth_date must be date or str, got {type(birth_date_raw)}")
        
        # 3. Расчет психоматрицы
        logger.info(f"🧮 Calculating psychomatrix for user {user_id}, birth_date: {birth_date}")
        #matrix_data = PsyhoMatrixCalculator.calculate_matrix(birth_date)
        calculator = PsyhoMatrixCalculator()
        matrix_data = calculator.calculate_matrix(birth_date)
        #matrix_data = PsyhoMatrixCalculator.calculate_matrix_static(birth_date)
        
        # Проверка результата расчета
        if not matrix_data or not isinstance(matrix_data, dict):
            raise RuntimeError(f"Invalid calculation result for user {user_id}")
        
        # Проверка наличия обязательных полей
        missing_fields = [f for f in REQUIRED_MATRIX_FIELDS if f not in matrix_data]
        if missing_fields:
            raise ValueError(f"Missing required fields in calculation: {missing_fields}")
        
        # 4. Валидация данных перед сохранением
        is_valid, errors = validate_for_database(matrix_data)
        if not is_valid:
            error_msg = f"Matrix validation failed for user {user_id}: {errors}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 5. Подготовка данных для БД
        prepared = prepare_for_db_insert(matrix_data)
        
        # Дополнительная проверка после подготовки
        if 'user_id' in prepared:
            logger.warning(f"Removing unexpected user_id from prepared data for user {user_id}")
            del prepared['user_id']  # На всякий случай, если вдруг появится
        
        # 6. Сохранение в БД с обработкой конкурентного доступа
        async with async_session() as session:
            # ✅ ИСПРАВЛЕНО: Явно блокируем ТОЛЬКО строку PsyhoMatrix без JOIN
            stmt = select(PsyhoMatrix).where(PsyhoMatrix.user_id == user_id)
            result = await session.execute(
                stmt.execution_options(populate_existing=True).with_for_update()
            )
            existing = result.scalar_one_or_none()

            try:
                if existing:
                    # Обновление - ТОЛЬКО нужные поля
                    for key in ['first_number', 'second_number', 'third_number', 'fourth_number',
                                'matrix_digits', 'matrix_3x3', 'characteristics', 'talent_codes',
                                'strength_codes', 'energy_level', 'life_purpose', 'compatibility_hints',
                                'additional', 'karmic_analysis', 'forecasting', 'calculation_version']:
                        if key in prepared:
                            setattr(existing, key, prepared[key])
                    action = "updated"
                else:
                    # ✅ НОВАЯ ЗАПИСЬ - ТОЧНЫЙ список полей
                    psyho_matrix = PsyhoMatrix.from_calculator_result(user_id, prepared)
                    session.add(psyho_matrix)
                    action = "created"

                await session.commit()
                logger.info(
                    f"✅ Psychomatrix {action} for user {user_id} (v{matrix_data.get('calculation_version', 'unknown')})")

            except IntegrityError as e:
                await session.rollback()
                logger.error(f"Integrity error for user {user_id}: {e}")
                raise ValueError(f"Database integrity error: {e}")

        # 7. Возвращаем результат с метаданными
        return {
            **matrix_data,
            #'saved_at': datetime.now().isoformat(),
            'saved_at': datetime.now().isoformat(),
            'user_id': user_id
        }
        
    except ValueError as e:
        logger.error(f"❌ Validation error for user {user_id}: {e}")
        raise
    except TypeError as e:
        logger.error(f"❌ Type error for user {user_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error for user {user_id}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to calculate psychomatrix: {e}")


async def get_psyho_matrix(user_id: int) -> dict:
    """
    Получение сохраненной психоматрицы пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Dict с данными психоматрицы или None если не найдена
    """
    async with async_session() as session:
        result = await session.execute(
            select(PsyhoMatrix).where(PsyhoMatrix.user_id == user_id)
        )
        matrix = result.scalar_one_or_none()
        
        if matrix:
            logger.info(f"📊 Retrieved psychomatrix for user {user_id}")
            # Преобразование SQLAlchemy модели в dict
            return {
                column.name: getattr(matrix, column.name)
                for column in matrix.__table__.columns
            }
        
        logger.info(f"📭 No psychomatrix found for user {user_id}")
        return None


async def delete_psyho_matrix(user_id: int) -> bool:
    """
    Удаление психоматрицы пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если удалена, False если не найдена
    """
    async with async_session() as session:
        result = await session.execute(
            select(PsyhoMatrix).where(PsyhoMatrix.user_id == user_id)
        )
        matrix = result.scalar_one_or_none()
        
        if matrix:
            await session.delete(matrix)
            await session.commit()
            logger.info(f"🗑️ Deleted psychomatrix for user {user_id}")
            return True
        
        logger.info(f"📭 No psychomatrix to delete for user {user_id}")
        return False


async def recalculate_psyho_matrix(user_id: int, force: bool = False) -> dict:
    """
    Принудительный пересчет психоматрицы
    
    Args:
        user_id: ID пользователя
        force: Принудительный пересчет даже если есть сохраненная
        
    Returns:
        Dict с новыми данными психоматрицы
    """
    if not force:
        # Проверяем существующую
        existing = await get_psyho_matrix(user_id)
        if existing:
            logger.info(f"⏭️ Using existing psychomatrix for user {user_id}")
            return existing
    
    # Пересчитываем
    logger.info(f"🔄 Recalculating psychomatrix for user {user_id}" + (" (forced)" if force else ""))
    return await calculate_and_save_psyho_matrix(user_id)
