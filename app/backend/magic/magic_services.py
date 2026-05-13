"""
Сервис для работы с magic profile.
Адаптирован для MagicProfileCalculator v2.0.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy import select, update, Float
from sqlalchemy.dialects.postgresql import insert, array
import asyncio

from ..database.core import async_session
from ..database.models import (
    User, NatalChart, PsyhoMatrix, Biorhythm,
    MagicProfile  # ✅ Новая модель v2.0
)
from ..users.user_services import user_service
from .calculator import MagicProfileCalculator  # ✅ v2.0

logger = logging.getLogger(__name__)


class MagicProfileService:
    """
    Сервис для расчета и управления magic profile.
    Версия 2.0 - интеграция с 9 осями.
    """

    def __init__(self):
        self.calculator = MagicProfileCalculator()
        # ✅ v2.0 JSON поля для сериализации
        self.JSON_FIELDS = [
            'axes', 'psychological_blueprint', 'ml_features',
            'calculation_metadata'
        ]
        # feature_vector не JSON, а ARRAY

    def _orm_to_dict(self, obj) -> Dict:
        """Преобразование ORM объекта в словарь"""
        if obj is None:
            return {}
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    def _ensure_dict(self, data) -> Dict:
        """Гарантированное преобразование в словарь"""
        if data is None:
            return {}
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.error(f"Не удалось распарсить JSON: {data[:100]}...")
                return {}
        if isinstance(data, dict):
            return data
        if hasattr(data, '__dict__'):
            return self._orm_to_dict(data)
        return {}

    async def get_required_data(self, user_id: int) -> Dict:
        logger.info(f"📦 Получение данных для пользователя {user_id}")

        user_profile = await user_service.get_user_profile_by_id(user_id=user_id, include_extended=True)
        if not user_profile:
            raise ValueError(f"Профиль пользователя {user_id} не найден")

        async with async_session() as session:
            # ✅ ПРАВИЛЬНЫЙ СИНТАКСИС:
            natal_result = await session.execute(
                select(NatalChart)
                .where(NatalChart.user_id == user_id)
                .order_by(NatalChart.calculation_date.desc())
                .limit(1)
            )
            natal_chart = natal_result.scalars().first()

            if not natal_chart:
                raise ValueError(f"Натальная карта не найдена")

            matrix_result = await session.execute(
                select(PsyhoMatrix).where(PsyhoMatrix.user_id == user_id)
            )
            psyho_matrix = matrix_result.scalars().first()

            if not psyho_matrix:
                raise ValueError(f"Психоматрица не найдена")

            biorhythm_result = await session.execute(
                select(Biorhythm)
                .where(Biorhythm.user_id == user_id)
                .order_by(Biorhythm.calculation_date.desc())
                .limit(1)
            )
            biorhythms = biorhythm_result.scalars().first()

            if not biorhythms:
                raise ValueError(f"Биоритмы не найдены")

            return {
                'user_profile': user_profile,
                'natal_chart': self._orm_to_dict(natal_chart),
                'psyho_matrix': self._orm_to_dict(psyho_matrix),
                'biorhythms': self._orm_to_dict(biorhythms)
            }

    async def calculate_and_save_magic_profile(self, user_id: int) -> Dict:
        """
        Основной метод: расчет v2.0 и сохранение в БД.
        """
        logger.info(f"🔄 Расчет magic profile v2.0 для пользователя {user_id}")

        try:
            # 1. Получаем все данные
            data = await self.get_required_data(user_id)

            # 2. Преобразуем в нужный формат
            natal_chart_dict = self._ensure_dict(data['natal_chart'])
            psyho_matrix_dict = self._ensure_dict(data['psyho_matrix'])
            biorhythms_dict = self._ensure_dict(data['biorhythms'])
            user_profile_dict = self._ensure_dict(data['user_profile'])

            # Для биоритмов нужны статические данные
            biorhythms_static = biorhythms_dict.get('profile_data', {})
            if isinstance(biorhythms_static, str):
                biorhythms_static = json.loads(biorhythms_static)

            # 3. Запускаем расчет v2.0
            profile_data = await self.calculator.calculate_magic_profile_v2(
                user_id=user_id,
                natal_chart=natal_chart_dict,
                psyho_matrix=psyho_matrix_dict,
                biorhythms_static=biorhythms_static,
                user_profile=user_profile_dict
            )

            # 4. Валидация результата
            required_keys = ['axes', 'ml_features', 'feature_vector']
            if not all(k in profile_data for k in required_keys):
                raise ValueError("Неполные данные от калькулятора")

            # 5. Сохраняем в БД
            await self._save_magic_profile_v2_to_db(user_id, profile_data)

            logger.info(f"✅ Magic profile v2.0 сохранен для пользователя {user_id}")
            return profile_data

        except Exception as e:
            logger.error(f"❌ Ошибка расчета magic profile для {user_id}: {e}")
            raise


    async def _save_magic_profile_v2_to_db(self, user_id: int, profile_data: Dict) -> bool:
        async with async_session() as session:
            try:
                now = datetime.now()
                metadata = profile_data.get('calculation_metadata', {})

                # 🔥 feature_vector → PostgreSQL ARRAY
                feature_vector_raw = profile_data.get('feature_vector', [])
                if isinstance(feature_vector_raw, str):
                    feature_vector = json.loads(feature_vector_raw)
                else:
                    feature_vector = feature_vector_raw

                feature_vector = [float(x) for x in feature_vector]
                feature_vector_array = array(feature_vector, type_=Float)

                logger.info(f"✅ feature_vector_array: len={len(feature_vector)} type={type(feature_vector_array)}")

                # ✅ Подготовка данных
                insert_values = {
                    'user_id': user_id,
                    'axes': profile_data.get('axes', {}),
                    'axis_count': metadata.get('axis_count', 9),
                    'psychological_blueprint': profile_data.get('psychological_blueprint', {}),
                    'ml_features': profile_data.get('ml_features', {}),
                    'feature_vector': feature_vector_array,
                    'cluster_id': profile_data.get('cluster_id'),
                    'anomaly_score': profile_data.get('anomaly_score', 0.0),
                    'profile_version': profile_data.get('profile_version', '2.0'),
                    'confidence_score': metadata.get('confidence_score', 0.85),
                    'calculation_metadata': metadata,
                    'data_sources': metadata.get('data_sources', []),
                    'is_valid': True,
                    'validation_errors': [],
                    'calculated_at': now,
                    'updated_at': now
                }

                # ✅ Создаем insert_stmt для использования в excluded
                insert_stmt = insert(MagicProfile).values(insert_values)

                # ✅ Правильный UPSERT с on_conflict_do_update
                await session.execute(
                    insert_stmt.on_conflict_do_update(
                        index_elements=['user_id'],
                        set_={
                            col.name: getattr(insert_stmt.excluded, col.name)
                            for col in MagicProfile.__table__.c
                            if col.name not in ['id', 'user_id', 'calculated_at']
                        }
                    )
                )

                await session.commit()
                logger.info(f"💾 MagicProfile v2 OK: user_id={user_id}, features={len(feature_vector)}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Save FAILED user_id={user_id}: {e}")
                raise

    async def get_magic_profile(self, user_id: int) -> Optional[Dict]:
        """
        Получение сохраненного magic profile из БД.
        """
        async with async_session() as session:
            result = await session.execute(
                select(MagicProfile).where(MagicProfile.user_id == user_id)
            )

            # ❌ НЕ ИСПОЛЬЗОВАТЬ scalar_one_or_none() для MagicProfile!
            # profile = result.scalar_one_or_none()

            # ✅ ИСПОЛЬЗОВАТЬ first() для получения строки
            row = result.first()
            profile = row[0] if row else None

            if not profile:
                return None

            # ✅ Безопасное преобразование feature_vector
            feature_vector = profile.feature_vector

            # Если это строка - парсим JSON
            if isinstance(feature_vector, str):
                try:
                    feature_vector = json.loads(feature_vector)
                    logger.info(f"✅ Преобразовали feature_vector из строки в список")
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга feature_vector: {e}")
                    feature_vector = []

            # Если это список - оставляем как есть
            elif isinstance(feature_vector, list):
                logger.info(f"✅ feature_vector уже список, длина={len(feature_vector)}")

            # Если это ARRAY из pgvector - преобразуем в список
            else:
                try:
                    # Попытка преобразовать в список
                    feature_vector = list(feature_vector)
                    logger.info(f"✅ Преобразовали ARRAY в список")
                except:
                    feature_vector = []

            return {
                'user_id': profile.user_id,
                'axes': profile.axes,
                'psychological_blueprint': profile.psychological_blueprint,
                'ml_features': profile.ml_features,
                'feature_vector': feature_vector,
                'profile_version': profile.profile_version,
                'confidence_score': profile.confidence_score,
                'cluster_id': profile.cluster_id,
                'anomaly_score': profile.anomaly_score,
                'data_sources': profile.data_sources,
                'calculated_at': profile.calculated_at.isoformat() if profile.calculated_at else None,
                'validation_errors': profile.validation_errors,
                'is_valid': profile.is_valid
            }