"""
daily_forecast_service.py - Сервис дневных прогнозов на основе 9 осей Magic Profile
Версия 2.0 - Расширенный вывод с категоризацией сигналов
"""

import logging
import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, Index

from ..database.models import (
    User, MagicProfile, DailyForecastCache,
    ForecastFeedback, Biorhythm, NatalChart
)
from ..database.core import async_session
from .transit_calculator import TransitCalculator, get_transit_calculator
from .axis_modulator import AxisModulator, AxisName, get_axis_modulator
from .biorhythm_calculator import get_biorhythm_calculator
from .dasha_calculator import get_dasha_calculator
from .panchanga_calculator import get_panchanga_calculator
from ..users.user_services import user_service

logger = logging.getLogger(__name__)


# ============================================================
# ДАТАКЛАССЫ ДЛЯ ОТВЕТОВ API
# ============================================================

@dataclass
class AxisForecast:
    """Прогноз для одной оси"""
    name: str
    static_value: float
    delta: float
    daily_value: float
    trend: str  # rising, falling, stable
    advice: str

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'static_value': round(self.static_value, 3),
            'delta': round(self.delta, 3),
            'daily_value': round(self.daily_value, 3),
            'trend': self.trend,
            'advice': self.advice
        }


@dataclass
class DailyForecastResult:
    """Полный результат дневного прогноза"""
    user_id: int
    forecast_date: date
    axes: List[AxisForecast]
    summary: str
    top_advice: str
    caution_advice: str
    best_time: Optional[str]
    moon_info: Dict[str, Any]
    planetary_hour: Dict[str, Any]
    dasha_info: Dict[str, Any]
    calculated_at: datetime
    background_risks: List[str] = field(default_factory=list)
    subtle_signals: Dict[str, Any] = field(default_factory=dict)
    signal_categories: Dict[str, List[Dict]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'forecast_date': self.forecast_date.isoformat(),
            'axes': [a.to_dict() for a in self.axes],
            'summary': self.summary,
            'top_advice': self.top_advice,
            'caution_advice': self.caution_advice,
            'best_time': self.best_time,
            'moon_info': self.moon_info,
            'planetary_hour': self.planetary_hour,
            'dasha_info': self.dasha_info,
            'calculated_at': self.calculated_at.isoformat(),
            'background_risks': self.background_risks,
            'subtle_signals': self.subtle_signals,
            'signal_categories': self.signal_categories
        }


# ============================================================
# ОСНОВНОЙ СЕРВИС
# ============================================================

class DailyForecastService:
    """
    Сервис для расчёта дневных прогнозов с расширенной категоризацией сигналов
    """

    def __init__(self):
        self._transit_calculator: Optional[TransitCalculator] = None
        self._axis_modulator: Optional[AxisModulator] = None

    async def _get_transit_calculator(self) -> TransitCalculator:
        """Ленивая инициализация TransitCalculator"""
        if self._transit_calculator is None:
            self._transit_calculator = await get_transit_calculator()
        return self._transit_calculator

    async def _get_axis_modulator(self) -> AxisModulator:
        """Ленивая инициализация AxisModulator"""
        if self._axis_modulator is None:
            self._axis_modulator = get_axis_modulator()
        return self._axis_modulator

    # ============================================================
    # НОВЫЙ МЕТОД: КАТЕГОРИЗАЦИЯ СИГНАЛОВ
    # ============================================================

    def _categorize_signals(self, deltas: Dict[AxisName, float]) -> Dict[str, List[Tuple[AxisName, float]]]:
        """
        Категоризирует сигналы по силе изменений

        Returns:
            {
                'critical_positive': [(axis, delta), ...],  # >= 0.12
                'critical_negative': [(axis, delta), ...],  # <= -0.12
                'strong_positive': [(axis, delta), ...],    # >= 0.08
                'strong_negative': [(axis, delta), ...],    # <= -0.08
                'medium_positive': [(axis, delta), ...],    # >= 0.04
                'medium_negative': [(axis, delta), ...],    # <= -0.04
                'weak_positive': [(axis, delta), ...],      # >= 0.02
                'weak_negative': [(axis, delta), ...]       # <= -0.02
            }
        """
        result = {
            'critical_positive': [],
            'critical_negative': [],
            'strong_positive': [],
            'strong_negative': [],
            'medium_positive': [],
            'medium_negative': [],
            'weak_positive': [],
            'weak_negative': []
        }

        for axis, delta in deltas.items():
            if delta >= 0.12:
                result['critical_positive'].append((axis, delta))
            elif delta >= 0.08:
                result['strong_positive'].append((axis, delta))
            elif delta >= 0.04:
                result['medium_positive'].append((axis, delta))
            elif delta >= 0.02:
                result['weak_positive'].append((axis, delta))
            elif delta <= -0.12:
                result['critical_negative'].append((axis, delta))
            elif delta <= -0.08:
                result['strong_negative'].append((axis, delta))
            elif delta <= -0.04:
                result['medium_negative'].append((axis, delta))
            elif delta <= -0.02:
                result['weak_negative'].append((axis, delta))

        # Сортируем по абсолютной величине
        for key in result:
            result[key].sort(key=lambda x: abs(x[1]), reverse=True)

        return result

    def _analyze_background_risks(self, deltas: Dict[AxisName, float]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Анализирует фоновые риски от слабых сигналов

        Returns:
            (background_risks, subtle_signals)
        """
        background_risks = []
        subtle_signals = {}

        # Выявляем слабые сигналы
        weak_negative = [(axis, delta) for axis, delta in deltas.items() if -0.04 < delta < -0.02]
        weak_positive = [(axis, delta) for axis, delta in deltas.items() if 0.02 < delta < 0.04]

        if weak_negative:
            subtle_signals['weak_negative_axes'] = {
                self._axis_name_ru(a[0]): round(d, 3)
                for a, d in weak_negative
            }

            if len(weak_negative) >= 4:
                background_risks.append(f"📊 Фоновый спад на {len(weak_negative)} осях - будь внимателен")
            elif len(weak_negative) >= 2:
                axes_names = [self._axis_name_ru(a[0]) for a, _ in weak_negative]
                background_risks.append(f"📉 Легкий спад: {', '.join(axes_names)}")

        if weak_positive:
            subtle_signals['weak_positive_axes'] = {
                self._axis_name_ru(a[0]): round(d, 3)
                for a, d in weak_positive
            }

        # Проверяем комбинации слабых сигналов
        total_weak_negative = sum(d for _, d in weak_negative)
        if len(weak_negative) >= 3 and total_weak_negative < -0.1:
            background_risks.append("⚠️ Накопленный эффект слабых сигналов - снизь активность")

        # Проверяем отсутствие сильных сигналов при наличии слабых
        has_strong = any(
            d >= 0.08 or d <= -0.08
            for d in deltas.values()
        )

        if weak_negative and not has_strong:
            background_risks.append("🎯 Нет критических сигналов, но следи за деталями")

        return background_risks, subtle_signals

    # ============================================================
    # ПОЛУЧЕНИЕ СТАТИЧЕСКИХ ДАННЫХ
    # ============================================================

    async def _get_magic_profile(self, user_id: int, session: AsyncSession) -> Optional[MagicProfile]:
        """Получить Magic Profile пользователя"""
        result = await session.execute(
            select(MagicProfile).where(MagicProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_natal_chart(self, user_id: int, session: AsyncSession) -> Optional[NatalChart]:
        """Получить натальную карту пользователя"""
        result = await session.execute(
            select(NatalChart)
            .where(NatalChart.user_id == user_id)
            .order_by(NatalChart.calculation_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ============================================================
    # КЭШИРОВАНИЕ (ОБНОВЛЕНО)
    # ============================================================

    async def _get_cached_forecast(
            self,
            user_id: int,
            forecast_date: date,
            session: AsyncSession
    ) -> Optional[DailyForecastResult]:
        """Получить прогноз из кэша с расширенными данными"""
        result = await session.execute(
            select(DailyForecastCache)
            .where(
                and_(
                    DailyForecastCache.user_id == user_id,
                    DailyForecastCache.forecast_date == forecast_date,
                    DailyForecastCache.invalidated_at.is_(None)
                )
            )
        )
        cached = result.scalar_one_or_none()

        if cached and cached.expires_at and cached.expires_at > datetime.now(timezone.utc):
            logger.info(f"✅ Кэш прогноза для user={user_id} на {forecast_date}")

            # Восстанавливаем результат из кэша с новыми полями
            axes_data = cached.daily_axes
            axes_list = []

            for name, data in axes_data.items():
                axes_list.append(AxisForecast(
                    name=name,
                    static_value=data.get('static', 0.5),
                    delta=data.get('delta', 0.0),
                    daily_value=data.get('daily', 0.5),
                    trend=data.get('trend', 'stable'),
                    advice=data.get('advice', '')
                ))

            # Восстанавливаем новые поля
            background_risks = cached.background_risks if cached.background_risks else []
            subtle_signals = cached.subtle_signals if cached.subtle_signals else {}
            signal_categories = cached.signal_categories if cached.signal_categories else {}

            # Для обратной совместимости: если новых полей нет, генерируем из daily_axes
            if not signal_categories and axes_data:
                # Пересобираем дельты из кэша
                deltas = {}
                for axis_name, data in axes_data.items():
                    axis_enum = None
                    for a in AxisName:
                        if a.value == axis_name:
                            axis_enum = a
                            break
                    if axis_enum:
                        deltas[axis_enum] = data.get('delta', 0.0)

                # Генерируем расширенные данные
                signal_categories = self._categorize_signals(deltas)
                background_risks, subtle_signals = self._analyze_background_risks(deltas)

            return DailyForecastResult(
                user_id=user_id,
                forecast_date=forecast_date,
                axes=axes_list,
                summary=cached.recommendations.get('summary', '') if cached.recommendations else '',
                top_advice=cached.recommendations.get('top_advice', '') if cached.recommendations else '',
                caution_advice=cached.recommendations.get('caution_advice', '') if cached.recommendations else '',
                best_time=cached.recommendations.get('best_time') if cached.recommendations else None,
                moon_info=cached.recommendations.get('moon_info', {}) if cached.recommendations else {},
                planetary_hour=cached.recommendations.get('planetary_hour', {}) if cached.recommendations else {},
                dasha_info=cached.recommendations.get('dasha_info', {}) if cached.recommendations else {},
                calculated_at=cached.created_at or datetime.now(timezone.utc),
                background_risks=background_risks,
                subtle_signals=subtle_signals,
                signal_categories=signal_categories
            )

        return None

    async def _save_forecast_to_cache(
            self,
            user_id: int,
            forecast_date: date,
            forecast_result: DailyForecastResult,
            session: AsyncSession
    ) -> None:
        """Сохранить прогноз в кэш с расширенными данными"""
        from datetime import timedelta

        axes_data = {}
        for axis in forecast_result.axes:
            axes_data[axis.name] = {
                'static': axis.static_value,
                'delta': axis.delta,
                'daily': axis.daily_value,
                'trend': axis.trend,
                'advice': axis.advice
            }

        recommendations_data = {
            'summary': forecast_result.summary,
            'top_advice': forecast_result.top_advice,
            'caution_advice': forecast_result.caution_advice,
            'best_time': forecast_result.best_time,
            'moon_info': forecast_result.moon_info,
            'planetary_hour': forecast_result.planetary_hour,
            'dasha_info': forecast_result.dasha_info
        }

        existing = await session.execute(
            select(DailyForecastCache)
            .where(
                and_(
                    DailyForecastCache.user_id == user_id,
                    DailyForecastCache.forecast_date == forecast_date
                )
            )
        )
        existing_record = existing.scalar_one_or_none()

        expires_at = datetime.now(timezone.utc) + timedelta(days=31)

        if existing_record:
            existing_record.axes_deltas = axes_data
            existing_record.daily_axes = axes_data
            existing_record.recommendations = recommendations_data
            existing_record.invalidated_at = None
            existing_record.expires_at = expires_at
            # Новые поля
            existing_record.background_risks = forecast_result.background_risks
            existing_record.subtle_signals = forecast_result.subtle_signals
            existing_record.signal_categories = forecast_result.signal_categories
        else:
            cache_record = DailyForecastCache(
                user_id=user_id,
                forecast_date=forecast_date,
                axes_deltas={},
                daily_axes=axes_data,
                recommendations=recommendations_data,
                rules_version='v2.0',  # Обновляем версию
                expires_at=expires_at,
                # Новые поля
                background_risks=forecast_result.background_risks,
                subtle_signals=forecast_result.subtle_signals,
                signal_categories=forecast_result.signal_categories
            )
            session.add(cache_record)

        await session.commit()
        logger.info(f"💾 Прогноз для user={user_id} на {forecast_date} сохранён в кэш (v2.0)")

    # ============================================================
    # ГЕНЕРАЦИЯ ТЕКСТОВЫХ СОВЕТОВ (ОБНОВЛЕНО)
    # ============================================================

    def _generate_enhanced_summary(
            self,
            deltas: Dict[AxisName, float],
            signal_categories: Dict[str, List[Tuple[AxisName, float]]]
    ) -> Tuple[str, str, str]:
        """
        Сгенерировать расширенную текстовую сводку прогноза
        Возвращает: (summary, top_advice, caution_advice)
        """

        # Получаем категории
        critical_neg = signal_categories['critical_negative']
        critical_pos = signal_categories['critical_positive']
        strong_neg = signal_categories['strong_negative']
        strong_pos = signal_categories['strong_positive']
        medium_neg = signal_categories['medium_negative']
        medium_pos = signal_categories['medium_positive']
        weak_neg = signal_categories['weak_negative']
        weak_pos = signal_categories['weak_positive']

        # === ФОРМИРУЕМ SUMMARY ===
        summary_parts = []

        if critical_neg:
            axes_list = [self._axis_name_ru(a[0]) for a in critical_neg[:3]]
            if len(critical_neg) >= 3:
                summary_parts.append(f"🔴 КРИТИЧЕСКИ снижены: {', '.join(axes_list)}")
            else:
                summary_parts.append(f"🔴 Резко снижены: {', '.join(axes_list)}")

            total_other = len(strong_neg) + len(medium_neg) + len(weak_neg)
            if total_other > 0:
                summary_parts.append(f"(+{total_other} осей со спадом)")

        elif strong_neg:
            axes_list = [self._axis_name_ru(a[0]) for a in strong_neg[:2]]
            other_count = len(medium_neg) + len(weak_neg)
            if other_count > 0:
                summary_parts.append(f"⚠️ Сильно снижены: {', '.join(axes_list)} (ещё {other_count} оси со спадом)")
            else:
                summary_parts.append(f"⚠️ Снижены: {', '.join(axes_list)}")

        elif medium_neg:
            axes_list = [self._axis_name_ru(a[0]) for a in medium_neg[:3]]
            weak_count = len(weak_neg)
            if weak_count > 0:
                summary_parts.append(f"📉 Снижены: {', '.join(axes_list)} (фоновый спад ещё на {weak_count} осях)")
            else:
                summary_parts.append(f"📉 Снижены: {', '.join(axes_list)}")

        elif weak_neg:
            if len(weak_neg) >= 4:
                summary_parts.append(f"📊 Фоновый спад на {len(weak_neg)} осях (будь внимателен)")
            elif len(weak_neg) >= 2:
                axes_list = [self._axis_name_ru(a[0]) for a in weak_neg[:2]]
                summary_parts.append(f"📊 Легкое снижение: {', '.join(axes_list)}")
            else:
                summary_parts.append("📊 Незначительный спад активности")

        elif critical_pos or strong_pos or medium_pos:
            all_pos = critical_pos + strong_pos + medium_pos
            axes_list = [self._axis_name_ru(a[0]) for a in all_pos[:2]]
            if len(all_pos) > 2:
                summary_parts.append(f"✨ Повышены: {', '.join(axes_list)} и другие ({len(all_pos)} осей всего)")
            else:
                summary_parts.append(f"✨ Повышены: {', '.join(axes_list)}")

        else:
            summary_parts.append("➡️ Все оси в стабильном состоянии")

        summary = " ".join(summary_parts) if summary_parts else "➡️ Нейтральный день"

        # === ФОРМИРУЕМ СОВЕТЫ ===
        top_advice_parts = []
        caution_advice_parts = []

        # Критические негативные советы
        for axis, delta in critical_neg[:2]:
            caution_advice_parts.append(f"🔴 {self._axis_name_ru(axis)}: {self._get_caution_advice(axis)}")

        # Сильные негативные советы (если мало критических)
        if len(critical_neg) < 2:
            for axis, delta in strong_neg[:2]:
                level = "🟠" if len(critical_neg) > 0 else "⚠️"
                caution_advice_parts.append(f"{level} {self._axis_name_ru(axis)}: {self._get_caution_advice(axis)}")

        # Средние негативные (как дополнение)
        if len(caution_advice_parts) < 3 and medium_neg:
            for axis, delta in medium_neg[:1]:
                caution_advice_parts.append(f"📉 {self._axis_name_ru(axis)}: {self._get_caution_advice(axis)}")

        # Суммарное предупреждение при массовом спаде
        total_negative = len(critical_neg) + len(strong_neg) + len(medium_neg) + len(weak_neg)
        if total_negative >= 5:
            caution_advice_parts.append("\n📌 ОБЩЕЕ: снижена активность в большинстве сфер - отдохни сегодня")
        elif total_negative >= 3:
            caution_advice_parts.append("\n📌 Рекомендуется снизить активность и избегать рисков")

        # Позитивные советы
        for axis, delta in (critical_pos + strong_pos + medium_pos)[:2]:
            top_advice_parts.append(f"✅ {self._axis_name_ru(axis)}: {self._get_positive_advice(axis)}")

        # Если нет позитивных сигналов
        if not top_advice_parts and total_negative < 3:
            top_advice_parts.append("✨ Используй день для привычных дел в комфортном режиме")
        elif not top_advice_parts:
            top_advice_parts.append("🧘‍♂️ Сегодня лучше отдохнуть и набраться сил")

        top_advice = "\n".join(top_advice_parts[:3])
        caution_advice = "\n".join(caution_advice_parts[:5]) if caution_advice_parts else "✅ Особых предостережений нет"

        return summary, top_advice, caution_advice

    def _axis_name_ru(self, axis: AxisName) -> str:
        """Русское название оси"""
        names = {
            AxisName.ENERGY_WILL: "энергия",
            AxisName.HEALTH_PHYSICAL: "здоровье",
            AxisName.INTELLECT_LOGIC: "интеллект",
            AxisName.EMOTIONS_INTUITION: "эмоции",
            AxisName.WORK_DISCIPLINE: "дисциплина",
            AxisName.LUCK_TALENT: "удача",
            AxisName.SOCIAL_RELATIONS: "социум",
            AxisName.KARMA_CYCLES: "карма",
            AxisName.DESTINY_MISSION: "миссия",
        }
        return names.get(axis, axis.value)

    def _get_positive_advice(self, axis: AxisName) -> str:
        """Совет при повышенной оси"""
        advice_map = {
            AxisName.ENERGY_WILL: "Занимайся спортом, берись за сложные проекты",
            AxisName.HEALTH_PHYSICAL: "Удели внимание здоровью, закаляйся",
            AxisName.INTELLECT_LOGIC: "Учись, решай задачи, планируй",
            AxisName.EMOTIONS_INTUITION: "Твори, доверяй интуиции",
            AxisName.WORK_DISCIPLINE: "Делай рутину, закрывай долги",
            AxisName.LUCK_TALENT: "Рискуй, пробуй новое",
            AxisName.SOCIAL_RELATIONS: "Общайся, встречайся с друзьями",
            AxisName.KARMA_CYCLES: "Завершай старые дела",
            AxisName.DESTINY_MISSION: "Действуй по предназначению",
        }
        return advice_map.get(axis, "Используй этот день с пользой")

    def _get_caution_advice(self, axis: AxisName) -> str:
        """Совет при пониженной оси"""
        advice_map = {
            AxisName.ENERGY_WILL: "Отдыхай, не начинай конфликтов",
            AxisName.HEALTH_PHYSICAL: "Береги себя, избегай перегрузок",
            AxisName.INTELLECT_LOGIC: "Не берись за сложные задачи",
            AxisName.EMOTIONS_INTUITION: "Медитируй, избегай решений",
            AxisName.WORK_DISCIPLINE: "Не планируй много, отдыхай",
            AxisName.LUCK_TALENT: "Не рискуй, перепроверяй",
            AxisName.SOCIAL_RELATIONS: "Побудь один, избегай конфликтов",
            AxisName.KARMA_CYCLES: "Не начинай важное",
            AxisName.DESTINY_MISSION: "Анализируй, не форсируй",
        }
        return advice_map.get(axis, "Будь внимателен сегодня")

    def _get_best_time(self, planetary_hour: Dict) -> Optional[str]:
        """Определить лучшее время дня"""
        if not planetary_hour:
            return None

        hour_number = planetary_hour.get('hour_number', 0)
        is_day = planetary_hour.get('is_day', True)

        if is_day and hour_number in [1, 2, 3]:
            return "Утро (до 10:00) — лучшее время для важных дел"
        elif is_day and hour_number in [4, 5, 6]:
            return "Середина дня — хороша для активной работы"
        elif not is_day and hour_number in [1, 2]:
            return "Вечер — время для отдыха и общения"
        else:
            return None

    # ============================================================
    # ОСНОВНОЙ МЕТОД РАСЧЁТА ПРОГНОЗА (ОБНОВЛЕН)
    # ============================================================

    async def get_daily_forecast(
            self,
            user_id: int,
            forecast_date: Optional[date] = None,
            force_recalculate: bool = False
    ) -> DailyForecastResult:
        """
        Получить дневной прогноз для пользователя с расширенной категоризацией
        """
        if forecast_date is None:
            forecast_date = date.today()

        logger.info(f"🔮 Расчёт прогноза для user={user_id} на {forecast_date}")

        async with async_session() as session:
            # 1. Проверяем кэш
            if not force_recalculate:
                cached = await self._get_cached_forecast(user_id, forecast_date, session)
                if cached:
                    return cached

            # 2. Получаем пользователя
            user_profile = await user_service.get_user_profile_by_id(
                user_id=user_id,
                include_extended=True,
                session=session
            )

            if not user_profile:
                raise ValueError(f"Пользователь user_id={user_id} не найден")

            birth_date = user_profile.get('birth_date')
            if not birth_date:
                raise ValueError(f"Дата рождения для user_id={user_id} не указана")

            # 3. Получаем статический Magic Profile
            magic_profile = await self._get_magic_profile(user_id, session)
            if not magic_profile or not magic_profile.axes:
                raise ValueError(f"Magic profile для user={user_id} не найден")

            static_axes = {}
            for axis_name, axis_data in magic_profile.axes.items():
                static_potential = axis_data.get('static_potential', {})
                if static_potential:
                    first_key = list(static_potential.keys())[0] if static_potential else None
                    if first_key:
                        static_axes[axis_name] = static_potential.get(first_key, 0.5)
                    else:
                        static_axes[axis_name] = 0.5
                else:
                    static_axes[axis_name] = 0.5

            # 4. Получаем транзитные аспекты
            transit_calc = await self._get_transit_calculator()
            transits = await transit_calc.calculate_transit_aspects(user_id, forecast_date, session)

            aspects_for_modulator = []
            for aspect in transits.aspects_to_natal:
                aspects_for_modulator.append({
                    'transit_planet': aspect.transit_planet,
                    'natal_planet': aspect.natal_planet,
                    'aspect_type': aspect.aspect_type,
                    'orb': aspect.orb,
                    'strength': aspect.strength,
                    'applying': aspect.applying
                })

            # 5. Получаем биоритмы
            biorhythm_calc = get_biorhythm_calculator()
            biorhythms = biorhythm_calc.calculate_for_user(birth_date, forecast_date)

            # 6. Получаем даша-период (исправленный формат)
            natal_chart = await self._get_natal_chart(user_id, session)
            dasha_info_for_modulator = {'planet': 'unknown', 'progress': 0.5}
            dasha_info_for_response = {'mahadasha': 'unknown', 'mahadasha_progress': 0.5}

            if natal_chart and natal_chart.panchanga:
                nakshatra = natal_chart.panchanga.get('nakshatra_name', '')
                birth_datetime = natal_chart.birth_datetime_utc or natal_chart.birth_datetime_local

                if birth_datetime and nakshatra:
                    dasha_calc = get_dasha_calculator()
                    dasha_result = dasha_calc.calculate_for_user(birth_datetime, nakshatra, forecast_date)

                    # Для модулятора
                    dasha_info_for_modulator = {
                        'planet': dasha_result.get('mahadasha', 'unknown'),
                        'sub_planet': dasha_result.get('antardasha', ''),
                        'progress': dasha_result.get('mahadasha_progress', 0.5)
                    }

                    # Для ответа пользователю
                    dasha_info_for_response = dasha_result

            # 7. Получаем панчангу
            sun_long = transits.transit_positions.get('Sun', {}).get('longitude', 0)
            moon_long = transits.transit_positions.get('Moon', {}).get('longitude', 0)

            panchanga_calc = get_panchanga_calculator()
            panchanga = panchanga_calc.calculate(sun_long, moon_long, forecast_date)

            # 8. Рассчитываем модуляторы осей
            modulator = await self._get_axis_modulator()
            deltas = modulator.calculate_axis_modulators(
                transit_aspects=aspects_for_modulator,
                biorhythms=biorhythms,
                dasha_period=dasha_info_for_modulator,
                moon_phase=transits.planetary_hour_info.get('moon_phase', ''),
                void_of_course_moon=transits.void_of_course_moon
            )

            # 9. Категоризируем сигналы (НОВОЕ!)
            signal_categories = self._categorize_signals(deltas)

            # 10. Анализируем фоновые риски (НОВОЕ!)
            background_risks, subtle_signals = self._analyze_background_risks(deltas)

            # 11. Применяем дельты к статическим значениям
            axes_results = []

            for axis_name, static_value in static_axes.items():
                axis_enum = None
                for a in AxisName:
                    if a.value == axis_name:
                        axis_enum = a
                        break

                delta = deltas.get(axis_enum, 0.0) if axis_enum else 0.0
                daily_value = max(0.05, min(0.95, static_value + delta))

                if daily_value - static_value > 0.02:
                    trend = 'rising'
                elif static_value - daily_value > 0.02:
                    trend = 'falling'
                else:
                    trend = 'stable'

                if axis_enum:
                    advice = modulator.get_advice_for_axis(axis_enum, daily_value)
                else:
                    advice = "Рекомендаций нет"

                axes_results.append(AxisForecast(
                    name=axis_name,
                    static_value=static_value,
                    delta=delta,
                    daily_value=daily_value,
                    trend=trend,
                    advice=advice
                ))

            # 12. Генерируем расширенную текстовую сводку
            summary, top_advice, caution_advice = self._generate_enhanced_summary(deltas, signal_categories)

            # 13. Определяем лучшее время
            best_time = self._get_best_time(transits.planetary_hour_info)

            # 14. Собираем дополнительную информацию
            moon_info = {
                'phase': transits.planetary_hour_info.get('moon_phase', 'unknown'),
                'void_of_course': transits.void_of_course_moon,
                'sign': None,
                'nakshatra': panchanga.nakshatra_name_ru if panchanga else None
            }

            planetary_hour = {
                'planet': transits.planetary_hour_info.get('planet', ''),
                'is_day': transits.planetary_hour_info.get('is_day', True),
                'hour_number': transits.planetary_hour_info.get('hour_number', 0)
            }

            # 15. Формируем результат с новыми полями
            result = DailyForecastResult(
                user_id=user_id,
                forecast_date=forecast_date,
                axes=axes_results,
                summary=summary,
                top_advice=top_advice,
                caution_advice=caution_advice,
                best_time=best_time,
                moon_info=moon_info,
                planetary_hour=planetary_hour,
                dasha_info=dasha_info_for_response,
                calculated_at=datetime.now(timezone.utc),
                background_risks=background_risks,
                subtle_signals=subtle_signals,
                signal_categories={
                    'critical_negative': [(a.value, d) for a, d in signal_categories['critical_negative']],
                    'critical_positive': [(a.value, d) for a, d in signal_categories['critical_positive']],
                    'strong_negative': [(a.value, d) for a, d in signal_categories['strong_negative']],
                    'strong_positive': [(a.value, d) for a, d in signal_categories['strong_positive']],
                    'medium_negative': [(a.value, d) for a, d in signal_categories['medium_negative']],
                    'medium_positive': [(a.value, d) for a, d in signal_categories['medium_positive']],
                    'weak_negative': [(a.value, d) for a, d in signal_categories['weak_negative']],
                    'weak_positive': [(a.value, d) for a, d in signal_categories['weak_positive']]
                }
            )

            # 16. Сохраняем в кэш
            await self._save_forecast_to_cache(user_id, forecast_date, result, session)

            logger.info(f"✅ Прогноз для user={user_id} на {forecast_date} рассчитан (v2.0)")
            logger.info(f"📊 Категории: critical={len(signal_categories['critical_negative'])}, "
                        f"strong={len(signal_categories['strong_negative'])}, "
                        f"medium={len(signal_categories['medium_negative'])}, "
                        f"weak={len(signal_categories['weak_negative'])}")

            return result

    # ============================================================
    # ПОЛУЧЕНИЕ НЕДЕЛЬНОГО ПРОГНОЗА
    # ============================================================

    async def get_weekly_forecast(
            self,
            user_id: int,
            start_date: Optional[date] = None
    ) -> List[DailyForecastResult]:
        """
        Получить прогноз на неделю (7 дней)
        """
        if start_date is None:
            start_date = date.today()

        results = []

        for i in range(7):
            forecast_date = start_date + timedelta(days=i)
            try:
                forecast = await self.get_daily_forecast(user_id, forecast_date)
                results.append(forecast)
            except Exception as e:
                logger.error(f"Ошибка прогноза на {forecast_date}: {e}")
                empty_result = DailyForecastResult(
                    user_id=user_id,
                    forecast_date=forecast_date,
                    axes=[],
                    summary="Прогноз временно недоступен",
                    top_advice="",
                    caution_advice="",
                    best_time=None,
                    moon_info={},
                    planetary_hour={},
                    dasha_info={},
                    calculated_at=datetime.now(timezone.utc),
                    background_risks=[],
                    subtle_signals={},
                    signal_categories={}
                )
                results.append(empty_result)

        return results


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ СЕРВИСА
# ============================================================

_forecast_service: Optional[DailyForecastService] = None


def get_forecast_service() -> DailyForecastService:
    """Получить глобальный экземпляр DailyForecastService"""
    global _forecast_service
    if _forecast_service is None:
        _forecast_service = DailyForecastService()
    return _forecast_service