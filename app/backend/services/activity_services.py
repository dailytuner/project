# activity_services
from __future__ import annotations
import logging
import json
import math
from datetime import datetime, date, timezone, timedelta
from datetime import date as date_type
from typing import Dict, List, Optional, Any
from sqlalchemy.future import select
from sqlalchemy import and_, delete

from ..database.core import async_session
from ..database.models import OptimalActivity, ActivityType, MagicProfile, parse_json_field

logger = logging.getLogger(__name__)


def _normalize_date(date_input: Any) -> date_type:
    """
    Единая функция нормализации даты.
    Принимает: date объект, строку YYYY-MM-DD, None
    Возвращает: date объект
    """
    if date_input is None:
        return date_type.today()

    if isinstance(date_input, date_type):
        return date_input

    if isinstance(date_input, str):
        try:
            # Поддерживаем YYYY-MM-DD
            return date_type.fromisoformat(date_input)
        except ValueError:
            # Попробуем DD.MM.YYYY
            try:
                from datetime import datetime
                return datetime.strptime(date_input, '%d.%m.%Y').date()
            except ValueError:
                logger.warning(f"Invalid date format: {date_input}, using today")
                return date_type.today()

    # Fallback
    logger.warning(f"Unknown date type: {type(date_input)}, using today")
    return date_type.today()

class ActivityOptimizer:
    """
    Оптимизатор активностей для ML моделей.
    Генерирует чистые числовые данные без текстовых описаний.
    """

    def __init__(self):
        # Веса для расчета оценок активностей на основе ML-признаков
        self.ml_feature_weights = {
            "physical": {
                'willpower_determination': 0.25,
                'willpower_persistence': 0.20,
                'emotional_stability': 0.15,
                'willpower_adaptability': 0.40
            },
            "spiritual": {
                'creative_imagination': 0.30,
                'creative_intuition': 0.25,
                'emotional_joy': 0.20,
                'ethical_honesty': 0.25
            },
            "learning": {
                'intellectual_curiosity': 0.30,
                'intellectual_learning': 0.25,
                'thinking_critical': 0.20,
                #'willpower_focus': 0.25
                'execution_focus': 0.25
            },
            "psychological": {
                'emotional_stability': 0.25,
                'emotional_self_awareness': 0.20,
                'psychological_authenticity': 0.30,
                'social_empathy': 0.25
            },
            "career": {
                'willpower_determination': 0.20,
                'intellectual_learning': 0.20,
                'ethical_responsibility': 0.25,
                'social_diplomacy': 0.35
            },
            "self_realization": {
                'creative_imagination': 0.35,
                'creative_innovation': 0.25,
                'psychological_authenticity': 0.20,
                'intellectual_curiosity': 0.20
            },
            "finances": {
                'ethical_honesty': 0.25,
                'ethical_responsibility': 0.25,
                'intellectual_learning': 0.20,
                'willpower_persistence': 0.30
            }
        }

        # Балансировочные коэффициенты для каждого типа активности
        self.balancing_factors = {
            "physical": 1.0,
            "spiritual": 1.1,
            "learning": 1.0,
            "psychological": 1.2,
            "career": 0.9,
            "self_realization": 1.1,
            "finances": 0.8
        }

    async def calculate_optimal_activities(self, user_id: int,
                                           magic_profile_data: Dict[str, Any],
                                           target_date: date = None) -> Dict[str, Any]:
        """Расчет оптимальных активностей для ML моделей."""
        # ✅ НОРМАЛИЗУЕМ ДАТУ В САМОМ НАЧАЛЕ
        calc_date = _normalize_date(target_date)

        logger.info(f"🔄 Расчет ML-активностей для {user_id} на {calc_date}")

        if magic_profile_data is None:
            logger.error("❌ magic_profile_data = None!")
            return self._get_default_ml_activities(user_id, calc_date)

        if isinstance(magic_profile_data, str):
            logger.warning("⚠️ magic_profile_data = STRING, десериализуем...")
            magic_profile_data = json.loads(magic_profile_data)

        try:
            # Проверка наличия данных magic profile
            if not magic_profile_data:
                raise ValueError("Не переданы данные magic profile")

            # Валидация критичных данных
            if not self._validate_magic_profile(magic_profile_data):
                logger.warning(f"⚠️ Magic profile невалиден для {user_id}, используем дефолт")
                return self._get_default_ml_activities(user_id, calc_date)

            logger.info(f"✅ Magic profile получен для расчета активностей {user_id}")

            # Расчет ML-признаков и оценок
            ml_features = self._extract_ml_features(magic_profile_data)
            activity_scores = self._calculate_activity_scores(ml_features)
            optimal_indices = self._select_optimal_activities(activity_scores)

            # Расчет энергетического уровня
            energy_level = sum(activity_scores.values()) / len(activity_scores)

            # ✅ Используем calc_date
            result = {
                'user_id': user_id,
                'calculation_date': calc_date.isoformat(),
                'ml_features': ml_features,
                'activity_scores': activity_scores,
                'optimal_activities': optimal_indices,
                'energy_level': round(energy_level, 4),
                'feature_vector': self._create_feature_vector(ml_features, activity_scores, optimal_indices),
                'metadata': {
                    'calculated_at': datetime.now().isoformat(),
                    'algorithm_version': 'ml_1.0',
                    'data_source': 'magic_profile',
                    'magic_profile_source': 'passed_directly'
                }
            }

            logger.info(f"✅ ML-активности рассчитаны для {user_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка расчета ML-активностей для {user_id}: {e}")
            return self._get_default_ml_activities(user_id, calc_date)

    def _validate_magic_profile(self, magic_profile: Dict) -> bool:
        """Валидация magic profile v2.0 для расчета ML-активностей"""
        try:
            # v2.0 обязательные секции
            required_sections = ['axes', 'psychological_blueprint', 'ml_features']

            for section in required_sections:
                if section not in magic_profile or not magic_profile[section]:
                    logger.warning(f"⚠️ Отсутствует обязательная секция v2.0: {section}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации magic profile: {e}")
            return False

    def _extract_ml_features(self, magic_profile: Dict) -> Dict[str, float]:
        """
        Извлечение чистых ML-признаков из magic profile v2.0.
        """
        try:
            features = {}

            # ✅ Извлекаем ml_features из v2.0 структуры
            ml_features_data = {}
            if isinstance(magic_profile, dict):
                ml_features_data = magic_profile.get('ml_features', {})
                if isinstance(ml_features_data, str):
                    ml_features_data = json.loads(ml_features_data)

            # ✅ Берем raw_features из ml_features
            raw_features = ml_features_data.get('raw_features', {})

            # ✅ Добавляем все raw_features напрямую
            for key, value in raw_features.items():
                features[key] = float(value)

            # ✅ Добавляем big_five как отдельные признаки
            big_five = ml_features_data.get('big_five', {})
            for key, value in big_five.items():
                features[f'big5_{key}'] = float(value)

            # ✅ Добавляем специальные индикаторы
            special = ml_features_data.get('special_indicators', {})
            features['has_spica'] = 1.0 if special.get('has_spica') else 0.0
            features['has_yod'] = 1.0 if special.get('has_yod') else 0.0
            features['destiny_intensity'] = float(special.get('destiny_intensity', 0.5))

            # ✅ Добавляем признаки из psychological_blueprint
            blueprint = magic_profile.get('psychological_blueprint', {})
            if isinstance(blueprint, dict):
                for section in ['core_personality', 'emotional_architecture',
                                'cognitive_style', 'social_dynamics']:
                    section_data = blueprint.get(section, {})
                    for key, value in section_data.items():
                        if isinstance(value, (int, float)):
                            features[f'blueprint_{key}'] = float(value)

            # Нормализация
            normalized_features = {}
            for key, value in features.items():
                try:
                    normalized_features[key] = round(float(value), 6)
                except:
                    normalized_features[key] = 0.5

            return normalized_features

        except Exception as e:
            logger.error(f"❌ Ошибка извлечения ML-признаков: {e}")
            return self._get_default_ml_features()

    def _calculate_activity_scores(self, ml_features: Dict[str, float]) -> Dict[str, float]:
        """
        Расчет оценок активностей на основе ML-признаков.
        Чисто математические вычисления.
        """
        try:
            activity_scores = {}

            for activity_type in ActivityType:
                weights = self.ml_feature_weights.get(activity_type.value, {})
                balancing_factor = self.balancing_factors.get(activity_type.value, 1.0)

                total_score = 0.0
                total_weight = 0.0

                for feature_name, weight in weights.items():
                    if feature_name in ml_features:
                        feature_value = ml_features[feature_name]
                        total_score += feature_value * weight
                        total_weight += weight

                if total_weight > 0:
                    base_score = total_score / total_weight
                    # Применяем балансировочный коэффициент и сигмоиду для нормализации
                    final_score = self._sigmoid(base_score * balancing_factor * 2 - 1)
                    activity_scores[activity_type.value] = round(final_score, 6)
                else:
                    activity_scores[activity_type.value] = 0.5  # Нейтральное значение

            return activity_scores

        except Exception as e:
            logger.error(f"❌ Ошибка расчета оценок активностей: {e}")
            return self._get_default_activity_scores()

    def _select_optimal_activities(self, activity_scores: Dict[str, float]) -> List[int]:
        """
        Выбор оптимальных активностей для ML модели.
        Возвращает индексы топ-3 активностей + финансы.
        """
        try:
            # Получаем список всех типов активностей в правильном порядке
            activity_names = [activity.value for activity in ActivityType]
            
            # Сортируем активности по оценкам
            non_finance_scores = {k: v for k, v in activity_scores.items() if k != 'finances'}
            #non_finance_scores = {k: v for k, v in activity_scores.items() if k != ActivityType.FINANCES.value}
            sorted_activities = sorted(non_finance_scores.items(), key=lambda x: x[1], reverse=True)

            # Выбираем топ-3
            top_3_indices = []
            for activity_name, score in sorted_activities[:3]:
                index = activity_names.index(activity_name)
                top_3_indices.append(index)

            # Добавляем финансы как отдельную активность
            #finance_index = activity_names.index(ActivityType.FINANCES.value)
            finance_index = activity_names.index('finances') 
            top_3_indices.append(finance_index)

            return top_3_indices

        except Exception as e:
            logger.error(f"❌ Ошибка выбора оптимальных активностей: {e}")
            return [0, 1, 2, 6]  # Дефолтные индексы

    def _create_feature_vector(self, ml_features: Dict[str, float],
                               activity_scores: Dict[str, float],
                               optimal_indices: List[int]) -> List[float]:
        """
        Создание единого вектора признаков для ML модели.
        Включает все признаки, оценки и оптимальные индексы.
        """
        try:
            feature_vector = []

            # 1. Добавляем все ML-признаки (в алфавитном порядке для стабильности)
            for feature_name in sorted(ml_features.keys()):
                feature_vector.append(ml_features[feature_name])

            # 2. Добавляем оценки активностей (в порядке ActivityType)
            activity_names = [activity.value for activity in ActivityType]
            for activity_name in activity_names:
                feature_vector.append(activity_scores.get(activity_name, 0.5))

            # 3. Добавляем оптимальные индексы как one-hot encoding
            activity_count = len(ActivityType)
            for i in range(activity_count):
                feature_vector.append(1.0 if i in optimal_indices else 0.0)

            # 4. Добавляем мета-признаки
            feature_vector.append(len(ml_features))  # Количество признаков
            feature_vector.append(sum(activity_scores.values()) / len(activity_scores))  # Средняя оценка
            feature_vector.append(max(activity_scores.values()))  # Максимальная оценка
            feature_vector.append(min(activity_scores.values()))  # Минимальная оценка

            # Округляем все значения
            feature_vector = [round(float(x), 6) for x in feature_vector]

            return feature_vector

        except Exception as e:
            logger.error(f"❌ Ошибка создания вектора признаков: {e}")
            return [0.5] * 100  # Дефолтный вектор

    def _sigmoid(self, x: float) -> float:
        """Сигмоидальная функция для нормализации значений 0-1"""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except:
            return 0.5

    def _get_default_ml_features(self) -> Dict[str, float]:
        """Возвращает дефолтные ML-признаки"""
        return {f'feature_{i}': 0.5 for i in range(50)}

    def _get_default_activity_scores(self) -> Dict[str, float]:
        """Возвращает дефолтные оценки активностей"""
        return {activity.value: 0.5 for activity in ActivityType}

    def _get_default_ml_activities(self, user_id: int, target_date: date = None) -> Dict[str, Any]:
        """Возвращает дефолтную структуру ML-активностей"""
        # ✅ Защита от None
        calc_date = _normalize_date(target_date)

        default_features = self._get_default_ml_features()
        default_scores = self._get_default_activity_scores()

        return {
            'user_id': user_id,
            'calculation_date': calc_date.isoformat(),
            'ml_features': default_features,
            'activity_scores': default_scores,
            'optimal_activities': [0, 1, 2, 6],
            'energy_level': 0.5,
            'feature_vector': [0.5] * 100,
            'metadata': {
                'calculated_at': datetime.now().isoformat(),
                'algorithm_version': 'ml_1.0_default',
                'data_source': 'default'
            }
        }


class ActivityOptimizerService:
    """Сервис для работы с оптимизатором активностей"""

    def __init__(self):
        self.optimizer = ActivityOptimizer()
        # Время жизни кэша в днях
        self.CACHE_TTL_DAYS = 1

    async def _get_existing_magic_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение существующего magic_profile из БД БЕЗ расчета"""
        async with async_session() as session:
            try:
                if user_id is None or user_id <= 0:
                    logger.warning(f"⚠️ Пользователь с user_id {user_id} не найден")
                    return None

                # ✅ Правильный запрос с first()
                result = await session.execute(
                    select(MagicProfile).where(MagicProfile.user_id == user_id)
                )
                row = result.first()
                record = row[0] if row else None

                if record and record.is_valid:
                    # Проверяем актуальность (не старше 30 дней)
                    if record.updated_at and record.updated_at > datetime.now(timezone.utc) - timedelta(days=30):
                        # ✅ Возвращаем v2.0 структуру
                        return {
                            'axes': record.axes,
                            'psychological_blueprint': record.psychological_blueprint,
                            'ml_features': record.ml_features,
                            'feature_vector': record.feature_vector
                        }
                    else:
                        logger.info(f"🔄 Magic profile устарел для {user_id}")
                        return None
                return None

            except Exception as e:
                logger.error(f"❌ Ошибка получения magic profile из БД для {user_id}: {e}")
                return None

    async def _get_cached_ml_activities(self, user_id: int, target_date: date) -> Optional[Dict[str, Any]]:
        """Получение кэшированных ML-активностей из таблицы OptimalActivity"""
        # ✅ НОРМАЛИЗУЕМ ДАТУ
        calc_date = _normalize_date(target_date)

        async with async_session() as session:
            try:
                if user_id is None or user_id <= 0:
                    logger.warning(f"⚠️ Пользователь {user_id} не найден при проверке кэша")
                    return None

                # ✅ Используем calc_date
                result = await session.execute(
                    select(OptimalActivity).where(
                        and_(
                            OptimalActivity.user_id == user_id,
                            OptimalActivity.calculation_date == calc_date  # ← ТЕПЕРЬ date
                        )
                    )
                )
                row = result.first()
                record = row[0] if row else None

                if record:
                    cache_age = datetime.now(timezone.utc) - record.generated_at
                    if cache_age < timedelta(days=self.CACHE_TTL_DAYS):
                        # Преобразуем activity_scores из массива в словарь
                        activity_names = [a.value for a in ActivityType]
                        activity_scores_dict = {}
                        for i, score in enumerate(record.activity_scores):
                            if i < len(activity_names):
                                activity_scores_dict[activity_names[i]] = float(score)

                        # Преобразуем feature_vector в список
                        fv = record.feature_vector
                        feature_vector = list(fv) if hasattr(fv, '__iter__') else fv or []

                        return {
                            'user_id': user_id,
                            'calculation_date': record.calculation_date.isoformat(),
                            'ml_features': record.ml_features,
                            'activity_scores': activity_scores_dict,
                            'optimal_activities': record.activity_indices,
                            'energy_level': float(record.energy_level),
                            'feature_vector': feature_vector,
                            'metadata': {
                                'calculated_at': record.generated_at.isoformat(),
                                'algorithm_version': record.model_version,
                                'data_source': 'cache',
                                'cached': True
                            }
                        }
                    else:
                        logger.info(f"🔄 Кэш устарел для {user_id} на {calc_date}")
                        return None
                return None

            except Exception as e:
                logger.error(f"❌ Ошибка получения кэша для {user_id}: {e}")
                return None

    async def _save_to_db(self, user_id: int, target_date: date, result: Dict[str, Any]) -> bool:
        """Сохранение результатов расчета в таблицу OptimalActivity"""
        # ✅ НОРМАЛИЗУЕМ ДАТУ
        calc_date = _normalize_date(target_date)

        async with async_session() as session:
            try:
                if user_id is None or user_id <= 0:
                    logger.error(f"❌ Не удалось сохранить результат: пользователь {user_id} не найден")
                    return False

                # Проверяем, существует ли уже запись
                existing_query = select(OptimalActivity).where(
                    and_(
                        OptimalActivity.user_id == user_id,
                        OptimalActivity.calculation_date == calc_date  # ← ТЕПЕРЬ date
                    )
                )
                existing_result = await session.execute(existing_query)
                existing_record = existing_result.scalar_one_or_none()

                # Преобразуем activity_scores из словаря в массив
                activity_scores_array = []
                for activity_type in ActivityType:
                    activity_scores_array.append(result['activity_scores'].get(activity_type.value, 0.5))

                if existing_record:
                    # Обновляем существующую запись
                    existing_record.activity_indices = result['optimal_activities']
                    existing_record.activity_scores = activity_scores_array
                    existing_record.ml_features = result['ml_features']
                    existing_record.feature_vector = result['feature_vector']
                    existing_record.energy_level = result.get('energy_level', 0.5)
                    existing_record.updated_at = datetime.now(timezone.utc)
                    logger.info(f"📝 Обновлена запись OptimalActivity для user_id {user_id} на {calc_date}")
                else:
                    # Создаем новую запись
                    new_record = OptimalActivity(
                        user_id=user_id,
                        calculation_date=calc_date,  # ← ТЕПЕРЬ date, не строка!
                        activity_indices=result['optimal_activities'],
                        activity_scores=activity_scores_array,
                        ml_features=result['ml_features'],
                        feature_vector=result['feature_vector'],
                        energy_level=result.get('energy_level', 0.5),
                        model_version=result.get('metadata', {}).get('algorithm_version', 'ml_1.0')
                    )
                    session.add(new_record)
                    logger.info(f"🆕 Создана новая запись OptimalActivity для user_id {user_id} на {calc_date}")

                await session.commit()
                if existing_record:
                    await session.refresh(existing_record)
                return True

            except Exception as e:
                logger.error(f"❌ Ошибка сохранения в БД для {user_id}: {e}")
                await session.rollback()
                return False

    async def _delete_cached_activities(self, user_id: int, target_date: date) -> bool:
        """Удаление кэшированных активностей за указанную дату"""
        # ✅ НОРМАЛИЗУЕМ ДАТУ
        calc_date = _normalize_date(target_date)

        async with async_session() as session:
            try:
                if user_id is None or user_id <= 0:
                    logger.warning(f"⚠️ Пользователь {user_id} не найден при удалении кэша")
                    return False

                # Удаляем запись за указанную дату
                delete_stmt = delete(OptimalActivity).where(
                    and_(
                        OptimalActivity.user_id == user_id,
                        OptimalActivity.calculation_date == calc_date  # ← ИСПРАВЛЕНО
                    )
                )
                result = await session.execute(delete_stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"🗑️ Удален кэш для user_id {user_id} на {calc_date}")
                return True

            except Exception as e:
                logger.error(f"❌ Ошибка удаления кэша для {user_id}: {e}")
                await session.rollback()
                return False

    async def get_ml_activities(
            self,
            user_id: int,
            target_date: date = None,
            magic_profile_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Основной метод получения ML-активностей.
        """
        # ✅ НОРМАЛИЗУЕМ ДАТУ В САМОМ НАЧАЛЕ
        calc_date = _normalize_date(target_date)

        try:
            logger.info(f"🔄 Получение ML-активностей для {user_id} на {calc_date}")

            # 1. Если переданы данные magic_profile - используем их сразу
            if magic_profile_data is not None:
                logger.info(f"✅ Используем переданный magic_profile для {user_id}")
                result = await self.optimizer.calculate_optimal_activities(
                    user_id=user_id,
                    magic_profile_data=magic_profile_data,
                    target_date=calc_date  # ← передаем нормализованную дату
                )
                # Сохраняем результат в кэш
                await self._save_to_db(user_id, calc_date, result)
                return result

            # 2. Проверяем кэш в таблице OptimalActivity
            cached_data = await self._get_cached_ml_activities(user_id, calc_date)
            if cached_data:
                logger.info(f"✅ Кэш ML-активностей использован для {user_id}")
                return cached_data

            # 3. Получаем magic_profile из БД
            logger.info(f"🔄 Кэш не найден, ищем magic_profile в БД для {user_id}")
            magic_profile_from_db = await self._get_existing_magic_profile(user_id)

            if magic_profile_from_db:
                logger.info(f"✅ Используем существующий magic_profile из БД для {user_id}")
                result = await self.optimizer.calculate_optimal_activities(
                    user_id=user_id,
                    magic_profile_data=magic_profile_from_db,
                    target_date=calc_date  # ← передаем нормализованную дату
                )
                # Сохраняем результат в кэш
                await self._save_to_db(user_id, calc_date, result)
                return result

            # 4. Если ничего не найдено - возвращаем дефолт
            logger.warning(f"⚠️ Magic profile не найден в БД для {user_id}, используем дефолт")
            default_result = self.optimizer._get_default_ml_activities(user_id, calc_date)
            # Сохраняем дефолт в кэш
            await self._save_to_db(user_id, calc_date, default_result)
            return default_result

        except Exception as e:
            logger.error(f"❌ Ошибка ML-активностей {user_id}: {e}")
            return self.optimizer._get_default_ml_activities(user_id, calc_date)

    async def get_ml_activities_with_magic_profile(
            self,
            user_id: int,
            magic_profile_data: Dict[str, Any],
            target_date: date = None
    ) -> Dict[str, Any]:
        """
        Альтернативный метод для явной передачи magic_profile_data.
        Удобно для использования в цепочке расчетов.
        """
        try:
            # ✅ НОРМАЛИЗУЕМ ДАТУ
            calc_date = _normalize_date(target_date)

            logger.info(f"🔄 Расчет ML-активностей с явной передачей magic_profile для {user_id}")

            # Прямой вызов оптимизатора с переданными данными
            result = await self.optimizer.calculate_optimal_activities(
                user_id=user_id,
                magic_profile_data=magic_profile_data,
                target_date=calc_date  # ← передаем нормализованную дату
            )

            # Сохраняем результат в кэш
            await self._save_to_db(user_id, calc_date, result)

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка расчета ML-активностей с явными данными: {e}")
            return self.optimizer._get_default_ml_activities(user_id, calc_date)

    async def force_recalculate(
            self,
            user_id: int,
            magic_profile_data: Optional[Dict[str, Any]] = None,
            target_date: date = None
    ) -> Dict[str, Any]:
        """Принудительный перерасчет ML-активностей с возможностью передачи данных."""
        try:
            # ✅ НОРМАЛИЗУЕМ ДАТУ
            calc_date = _normalize_date(target_date)

            logger.info(f"🔄 Принудительный перерасчет ML-активностей для {user_id}")

            # Удаляем кэш если существует
            await self._delete_cached_activities(user_id, calc_date)  # ← передаем нормализованную дату

            # Определяем какие данные использовать
            if magic_profile_data is not None:
                logger.info(f"✅ Используем переданный magic_profile для перерасчета")
                result = await self.optimizer.calculate_optimal_activities(
                    user_id=user_id,
                    magic_profile_data=magic_profile_data,
                    target_date=calc_date  # ← передаем нормализованную дату
                )
            else:
                logger.info(f"🔄 Ищем magic_profile в БД для перерасчета")
                existing_profile = await self._get_existing_magic_profile(user_id)
                if existing_profile:
                    result = await self.optimizer.calculate_optimal_activities(
                        user_id=user_id,
                        magic_profile_data=existing_profile,
                        target_date=calc_date  # ← передаем нормализованную дату
                    )
                else:
                    logger.warning(f"⚠️ Нет magic profile для принудительного перерасчета {user_id}")
                    result = self.optimizer._get_default_ml_activities(user_id, calc_date)

            # Сохраняем результат в кэш
            await self._save_to_db(user_id, calc_date, result)

            logger.info(f"✅ Принудительный перерасчет завершен для {user_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка принудительного перерасчета для {user_id}: {e}")
            raise


# Глобальный экземпляр сервиса для использования в других модулях
activity_optimizer_service = ActivityOptimizerService()

