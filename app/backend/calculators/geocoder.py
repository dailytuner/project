# backend/calculators/geocoder.py

import aiosqlite
import aiohttp
import asyncio
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass, asdict
import time
import logging
import hashlib
from contextlib import asynccontextmanager
from aiolimiter import AsyncLimiter
import timezonefinder
import json

logger = logging.getLogger(__name__)

try:
    from transliterate import translit

    HAS_TRANSLIT = True
except ImportError:
    HAS_TRANSLIT = False
    logger.warning("transliterate not installed. Latin/Cyrillic support will be limited.")


@dataclass(frozen=True)
class CityCoordinates:
    lat: float
    lon: float
    timezone: str
    display_name: str
    country_code: str
    region: Optional[str] = None
    country: Optional[str] = None
    importance: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CityCoordinates':
        return cls(**data)


class AsyncCityGeocoder:
    """Production-ready асинхронный геокодер с кэшированием и поддержкой кириллицы/латиницы"""

    DEFAULT_RATE_LIMIT = 1.0
    MEMORY_CACHE_TTL = 3600
    DB_CACHE_TTL = 30 * 86400
    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_CONCURRENT = 3

    # Fallback координаты для известных городов
    FALLBACK_COORDINATES = {
        "moscow": (55.7558, 37.6173, "Europe/Moscow", "RU"),
        "москва": (55.7558, 37.6173, "Europe/Moscow", "RU"),
        "msk": (55.7558, 37.6173, "Europe/Moscow", "RU"),
        "мск": (55.7558, 37.6173, "Europe/Moscow", "RU"),
        "spb": (59.9343, 30.3351, "Europe/Moscow", "RU"),
        "санкт-петербург": (59.9343, 30.3351, "Europe/Moscow", "RU"),
        "st petersburg": (59.9343, 30.3351, "Europe/Moscow", "RU"),
        "питер": (59.9343, 30.3351, "Europe/Moscow", "RU"),
        "kaliningrad": (54.7104, 20.5070, "Europe/Kaliningrad", "RU"),
        "калининград": (54.7104, 20.5070, "Europe/Kaliningrad", "RU"),
        "ekaterinburg": (56.8389, 60.6057, "Asia/Yekaterinburg", "RU"),
        "екатеринбург": (56.8389, 60.6057, "Asia/Yekaterinburg", "RU"),
        "novosibirsk": (55.0084, 82.9357, "Asia/Novosibirsk", "RU"),
        "новосибирск": (55.0084, 82.9357, "Asia/Novosibirsk", "RU"),
        "kazan": (55.8304, 49.0661, "Europe/Moscow", "RU"),
        "казань": (55.8304, 49.0661, "Europe/Moscow", "RU"),
        "nnov": (56.3269, 44.0075, "Europe/Moscow", "RU"),
        "нижний новгород": (56.3269, 44.0075, "Europe/Moscow", "RU"),
        "chelyabinsk": (55.1644, 61.4368, "Asia/Yekaterinburg", "RU"),
        "челябинск": (55.1644, 61.4368, "Asia/Yekaterinburg", "RU"),
        "omsk": (54.9884, 73.3242, "Asia/Omsk", "RU"),
        "омск": (54.9884, 73.3242, "Asia/Omsk", "RU"),
        "samara": (53.2415, 50.2212, "Europe/Samara", "RU"),
        "самара": (53.2415, 50.2212, "Europe/Samara", "RU"),
        "rostov": (47.2225, 39.7187, "Europe/Moscow", "RU"),
        "ростов-на-дону": (47.2225, 39.7187, "Europe/Moscow", "RU"),
        "ufa": (54.7355, 55.9587, "Asia/Yekaterinburg", "RU"),
        "уфа": (54.7355, 55.9587, "Asia/Yekaterinburg", "RU"),
        "krasnoyarsk": (56.0153, 92.8932, "Asia/Krasnoyarsk", "RU"),
        "красноярск": (56.0153, 92.8932, "Asia/Krasnoyarsk", "RU"),
        "perm": (58.0105, 56.2502, "Asia/Yekaterinburg", "RU"),
        "пермь": (58.0105, 56.2502, "Asia/Yekaterinburg", "RU"),
        "voronezh": (51.6720, 39.1843, "Europe/Moscow", "RU"),
        "воронеж": (51.6720, 39.1843, "Europe/Moscow", "RU"),
        "volgograd": (48.7080, 44.5133, "Europe/Volgograd", "RU"),
        "волгоград": (48.7080, 44.5133, "Europe/Volgograd", "RU"),
        "krasnodar": (45.0355, 38.9750, "Europe/Moscow", "RU"),
        "краснодар": (45.0355, 38.9750, "Europe/Moscow", "RU"),
        "saratov": (51.5924, 45.9608, "Europe/Saratov", "RU"),
        "саратов": (51.5924, 45.9608, "Europe/Saratov", "RU"),
        "tyumen": (57.1613, 65.5250, "Asia/Yekaterinburg", "RU"),
        "тюмень": (57.1613, 65.5250, "Asia/Yekaterinburg", "RU"),
        "tolyatti": (53.5088, 49.4192, "Europe/Samara", "RU"),
        "тольятти": (53.5088, 49.4192, "Europe/Samara", "RU"),
        "izhevsk": (56.8527, 53.2115, "Europe/Samara", "RU"),
        "ижевск": (56.8527, 53.2115, "Europe/Samara", "RU"),
        "ulyanovsk": (54.3282, 48.3866, "Europe/Ulyanovsk", "RU"),
        "ульяновск": (54.3282, 48.3866, "Europe/Ulyanovsk", "RU"),
        "irkutsk": (52.2864, 104.2806, "Asia/Irkutsk", "RU"),
        "иркутск": (52.2864, 104.2806, "Asia/Irkutsk", "RU"),
        "khabarovsk": (48.4802, 135.0719, "Asia/Vladivostok", "RU"),
        "хабаровск": (48.4802, 135.0719, "Asia/Vladivostok", "RU"),
        "yaroslavl": (57.6261, 39.8845, "Europe/Moscow", "RU"),
        "ярославль": (57.6261, 39.8845, "Europe/Moscow", "RU"),
        "vladivostok": (43.1332, 131.9113, "Asia/Vladivostok", "RU"),
        "владивосток": (43.1332, 131.9113, "Asia/Vladivostok", "RU"),
        "mga": (59.7569, 31.0609, "Europe/Moscow", "RU"),
        "мга": (59.7569, 31.0609, "Europe/Moscow", "RU"),
    }

    def __init__(
            self,
            cache_db_path: str = "/data/geocoder_cache.db",
            user_agent: str = "geocoding-service/1.0",
            rate_limit: float = DEFAULT_RATE_LIMIT,
            enable_memory_cache: bool = True,
            enable_db_cache: bool = True
    ):
        self.user_agent = user_agent
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.db_path = cache_db_path

        self.tf = timezonefinder.TimezoneFinder()
        self._limiter = AsyncLimiter(rate_limit, 1)

        self._memory_cache: Dict[str, Tuple[CityCoordinates, float]] = {}
        self._memory_cache_lock = asyncio.Lock()
        self._enable_memory_cache = enable_memory_cache

        self._enable_db_cache = enable_db_cache
        self._conn: Optional[aiosqlite.Connection] = None

        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

        self._stats = {
            'hits_memory': 0,
            'hits_db': 0,
            'hits_api': 0,
            'hits_major_cities': 0,
            'hits_fallback': 0,
            'errors': 0,
            'total_requests': 0
        }
        self._stats_lock = asyncio.Lock()

        # Инициализация кэша major cities
        self._init_major_cities()

    def _init_major_cities(self):
        """Инициализация кэша major cities с поддержкой кириллицы и латиницы"""
        # Используем латиницу как основной ключ
        self._major_cities = {
            # Московское время (UTC+3)
            "moscow": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "msk": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "москва": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "мск": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),

            # СПБ
            "saint petersburg": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "st petersburg": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "spb": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "санкт-петербург": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "спб": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "питер": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),

            # Калининград
            "kaliningrad": (54.7104, 20.5070, "Europe/Kaliningrad", "RU", 0.8),
            "калининград": (54.7104, 20.5070, "Europe/Kaliningrad", "RU", 0.8),

            # Екатеринбург
            "ekaterinburg": (56.8389, 60.6057, "Asia/Yekaterinburg", "RU", 0.8),
            "екатеринбург": (56.8389, 60.6057, "Asia/Yekaterinburg", "RU", 0.8),

            # Новосибирск
            "novosibirsk": (55.0084, 82.9357, "Asia/Novosibirsk", "RU", 0.8),
            "новосибирск": (55.0084, 82.9357, "Asia/Novosibirsk", "RU", 0.8),

            # Казань
            "kazan": (55.8304, 49.0661, "Europe/Moscow", "RU", 0.7),
            "казань": (55.8304, 49.0661, "Europe/Moscow", "RU", 0.7),

            # Нижний Новгород
            "nnov": (56.3269, 44.0075, "Europe/Moscow", "RU", 0.7),
            "нижний новгород": (56.3269, 44.0075, "Europe/Moscow", "RU", 0.7),

            # Челябинск
            "chelyabinsk": (55.1644, 61.4368, "Asia/Yekaterinburg", "RU", 0.7),
            "челябинск": (55.1644, 61.4368, "Asia/Yekaterinburg", "RU", 0.7),

            # Омск
            "omsk": (54.9884, 73.3242, "Asia/Omsk", "RU", 0.7),
            "омск": (54.9884, 73.3242, "Asia/Omsk", "RU", 0.7),

            # Самара
            "samara": (53.2415, 50.2212, "Europe/Samara", "RU", 0.7),
            "самара": (53.2415, 50.2212, "Europe/Samara", "RU", 0.7),

            # Ростов-на-Дону
            "rostov": (47.2225, 39.7187, "Europe/Moscow", "RU", 0.7),
            "ростов-на-дону": (47.2225, 39.7187, "Europe/Moscow", "RU", 0.7),

            # Уфа
            "ufa": (54.7355, 55.9587, "Asia/Yekaterinburg", "RU", 0.7),
            "уфа": (54.7355, 55.9587, "Asia/Yekaterinburg", "RU", 0.7),

            # Красноярск
            "krasnoyarsk": (56.0153, 92.8932, "Asia/Krasnoyarsk", "RU", 0.7),
            "красноярск": (56.0153, 92.8932, "Asia/Krasnoyarsk", "RU", 0.7),

            # Пермь
            "perm": (58.0105, 56.2502, "Asia/Yekaterinburg", "RU", 0.7),
            "пермь": (58.0105, 56.2502, "Asia/Yekaterinburg", "RU", 0.7),

            # Воронеж
            "voronezh": (51.6720, 39.1843, "Europe/Moscow", "RU", 0.6),
            "воронеж": (51.6720, 39.1843, "Europe/Moscow", "RU", 0.6),

            # Волгоград
            "volgograd": (48.7080, 44.5133, "Europe/Volgograd", "RU", 0.6),
            "волгоград": (48.7080, 44.5133, "Europe/Volgograd", "RU", 0.6),

            # Краснодар
            "krasnodar": (45.0355, 38.9750, "Europe/Moscow", "RU", 0.6),
            "краснодар": (45.0355, 38.9750, "Europe/Moscow", "RU", 0.6),

            # Саратов
            "saratov": (51.5924, 45.9608, "Europe/Saratov", "RU", 0.6),
            "саратов": (51.5924, 45.9608, "Europe/Saratov", "RU", 0.6),

            # Тюмень
            "tyumen": (57.1613, 65.5250, "Asia/Yekaterinburg", "RU", 0.6),
            "тюмень": (57.1613, 65.5250, "Asia/Yekaterinburg", "RU", 0.6),

            # Тольятти
            "tolyatti": (53.5088, 49.4192, "Europe/Samara", "RU", 0.6),
            "тольятти": (53.5088, 49.4192, "Europe/Samara", "RU", 0.6),

            # Ижевск
            "izhevsk": (56.8527, 53.2115, "Europe/Samara", "RU", 0.6),
            "ижевск": (56.8527, 53.2115, "Europe/Samara", "RU", 0.6),

            # Ульяновск
            "ulyanovsk": (54.3282, 48.3866, "Europe/Ulyanovsk", "RU", 0.6),
            "ульяновск": (54.3282, 48.3866, "Europe/Ulyanovsk", "RU", 0.6),

            # Иркутск
            "irkutsk": (52.2864, 104.2806, "Asia/Irkutsk", "RU", 0.6),
            "иркутск": (52.2864, 104.2806, "Asia/Irkutsk", "RU", 0.6),

            # Хабаровск
            "khabarovsk": (48.4802, 135.0719, "Asia/Vladivostok", "RU", 0.6),
            "хабаровск": (48.4802, 135.0719, "Asia/Vladivostok", "RU", 0.6),

            # Ярославль
            "yaroslavl": (57.6261, 39.8845, "Europe/Moscow", "RU", 0.6),
            "ярославль": (57.6261, 39.8845, "Europe/Moscow", "RU", 0.6),

            # Владивосток
            "vladivostok": (43.1332, 131.9113, "Asia/Vladivostok", "RU", 0.6),
            "владивосток": (43.1332, 131.9113, "Asia/Vladivostok", "RU", 0.6),

            # Мга
            "mga": (59.7569, 31.0609, "Europe/Moscow", "RU", 0.5),
            "мга": (59.7569, 31.0609, "Europe/Moscow", "RU", 0.5),
        }

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        """Асинхронная инициализация всех ресурсов"""
        tasks = []

        if self._enable_db_cache:
            tasks.append(self._init_database())

        tasks.append(self._init_session())

        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Geocoder initialized")

    async def _ensure_session(self):
        """Гарантирует, что сессия инициализирована"""
        if self._session is None or self._session.closed:
            await self._init_session()
        return self._session

    async def _init_session(self):
        """Инициализация HTTP сессии"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    headers={'User-Agent': self.user_agent},
                    connector=aiohttp.TCPConnector(
                        limit=100,
                        ttl_dns_cache=300,
                        enable_cleanup_closed=True
                    )
                )

    async def _init_database(self):
        """Инициализация SQLite с правильной схемой"""
        try:
            self._conn = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )

            await self._conn.execute('PRAGMA journal_mode=WAL')
            await self._conn.execute('PRAGMA synchronous=NORMAL')
            await self._conn.execute('PRAGMA busy_timeout=5000')
            await self._conn.execute('PRAGMA cache_size=-20000')

            await self._conn.execute('''
                CREATE TABLE IF NOT EXISTS city_cache (
                    city_hash TEXT PRIMARY KEY,
                    city_name TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    timezone TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    region TEXT,
                    country TEXT,
                    importance REAL DEFAULT 0,
                    timestamp INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),

                    CHECK (lat BETWEEN -90 AND 90),
                    CHECK (lon BETWEEN -180 AND 180)
                )
            ''')

            await self._conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_city_name 
                ON city_cache(city_name COLLATE NOCASE)
            ''')

            await self._conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_expires 
                ON city_cache(expires_at)
            ''')

            await self._conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON city_cache(timestamp)
            ''')

            await self._conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_region 
                ON city_cache(region COLLATE NOCASE)
            ''')

            await self._conn.commit()

            logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            if self._conn:
                await self._conn.close()
            self._conn = None
            raise

    @staticmethod
    def _hash_city_name(
            city_name: str,
            country_code: Optional[str] = None,
            region: Optional[str] = None
    ) -> str:
        """Создание хэша для кэширования с учетом региона"""
        key = f"{city_name.lower().strip()}:{region or ''}:{country_code or ''}"
        return hashlib.sha256(key.encode()).hexdigest()

    async def _get_from_memory_cache(self, cache_key: str) -> Optional[CityCoordinates]:
        """Получение из кэша памяти с TTL"""
        if not self._enable_memory_cache:
            return None

        async with self._memory_cache_lock:
            if cache_key in self._memory_cache:
                coords, timestamp = self._memory_cache[cache_key]
                if time.time() - timestamp < self.MEMORY_CACHE_TTL:
                    async with self._stats_lock:
                        self._stats['hits_memory'] += 1
                    return coords
                else:
                    del self._memory_cache[cache_key]
        return None

    async def _save_to_memory_cache(self, cache_key: str, coords: CityCoordinates):
        """Атомарное сохранение в кэш памяти"""
        if not self._enable_memory_cache:
            return

        async with self._memory_cache_lock:
            self._memory_cache[cache_key] = (coords, time.time())

    async def _get_from_db_cache(self, cache_key: str) -> Optional[CityCoordinates]:
        """Получение из БД кэша"""
        if not self._enable_db_cache or not self._conn:
            return None

        try:
            async with self._conn.execute(
                    """SELECT lat, lon, timezone, display_name, country_code, region, country, importance
                       FROM city_cache 
                       WHERE city_hash = ? AND expires_at > ?""",
                    (cache_key, int(time.time()))
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    coords = CityCoordinates(*row)
                    async with self._stats_lock:
                        self._stats['hits_db'] += 1
                    return coords
        except Exception as e:
            logger.debug(f"DB cache read error: {e}")

        return None

    async def _save_to_db_cache(
            self,
            cache_key: str,
            city_name: str,
            coords: CityCoordinates
    ):
        """Асинхронное сохранение в БД кэша"""
        if not self._enable_db_cache or not self._conn:
            return

        try:
            expires_at = int(time.time()) + self.DB_CACHE_TTL

            await self._conn.execute(
                '''INSERT OR REPLACE INTO city_cache 
                   (city_hash, city_name, lat, lon, timezone, display_name, 
                    country_code, region, country, importance, timestamp, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    cache_key,
                    city_name.lower().strip(),
                    coords.lat,
                    coords.lon,
                    coords.timezone,
                    coords.display_name,
                    coords.country_code,
                    coords.region,
                    coords.country,
                    coords.importance,
                    int(time.time()),
                    expires_at
                )
            )
            await self._conn.commit()

        except Exception as e:
            logger.error(f"Failed to save to DB cache: {e}")

    def _normalize_city_name(self, name: str) -> str:
        """Только нормализация: регистр, пробелы, спецсимволы"""
        if not name:
            return ""
        return name.strip().lower().replace('ё', 'е')

    def _get_name_variants(self, name: Optional[str]) -> List[str]:
        """
        Генерация всех возможных вариантов названия.
        Упрощенная версия - только латиница и кириллица.
        """
        if not name:
            return []

        variants = [name]

        # Добавляем транслитерированные варианты
        if HAS_TRANSLIT:
            try:
                # Кириллица → Латиница (основной вариант)
                lat = translit(name, 'ru')
                if lat != name and lat:
                    variants.append(lat)

                # Латиница → Кириллица
                cyr = translit(name, 'ru', reversed=True)
                if cyr != name and cyr:
                    variants.append(cyr)
            except Exception as e:
                logger.debug(f"Transliteration failed for '{name}': {e}")

        # Убираем дубликаты и пустые строки
        clean_variants = []
        for v in variants:
            if v and v.strip():
                clean_variants.append(v.strip())

        return list(set(clean_variants))

    async def _cache_coords(
            self,
            cache_key: str,
            city_name: str,
            coords: CityCoordinates
    ):
        """Сохранение координат во все кэши"""
        await asyncio.gather(
            self._save_to_memory_cache(cache_key, coords),
            self._save_to_db_cache(cache_key, city_name, coords)
        )

    async def _get_fallback(self, city_name: str, country_code: Optional[str], region: Optional[str]) -> Optional[
        CityCoordinates]:
        """Получение fallback координат для известных городов"""
        city_lower = city_name.lower().strip()

        if city_lower in self.FALLBACK_COORDINATES:
            lat, lon, tz, country = self.FALLBACK_COORDINATES[city_lower]
            logger.info(f"📍 Использован fallback для {city_name} ({lat}, {lon})")

            async with self._stats_lock:
                self._stats['hits_fallback'] += 1

            return CityCoordinates(
                lat=lat,
                lon=lon,
                timezone=tz,
                display_name=city_name,
                country_code=country,
                region=region,
                country=country,
                importance=0.5
            )
        return None

    async def geocode(
            self,
            city_name: str,
            country_code: Optional[str] = None,
            region: Optional[str] = None,
            retry_attempts: int = 2,
            timeout: Optional[int] = None
    ) -> Optional[CityCoordinates]:
        """
        Основной метод геокодирования с поддержкой:
        - Кириллицы и латиницы (автоматическая транслитерация)
        - Региона/области
        - Страны
        - Многоуровневого кэширования
        """
        if not city_name or not city_name.strip():
            return None

        async with self._stats_lock:
            self._stats['total_requests'] += 1

        # 1. Проверяем major cities
        city_lower = city_name.lower().strip()
        if city_lower in self._major_cities:
            lat, lon, timezone, country, importance = self._major_cities[city_lower]
            coords = CityCoordinates(
                lat=lat,
                lon=lon,
                timezone=timezone,
                display_name=city_name,
                country_code=country,
                region=region,
                country=country,
                importance=importance
            )
            async with self._stats_lock:
                self._stats['hits_major_cities'] += 1
            logger.debug(f"Major city hit: {city_name} -> {timezone}")
            return coords

        # 2. Проверяем fallback
        fallback = await self._get_fallback(city_name, country_code, region)
        if fallback:
            return fallback

        # 3. Генерируем все варианты названий
        city_variants = self._get_name_variants(city_name)
        region_variants = self._get_name_variants(region) if region else [None]

        # Пробуем все комбинации
        for city_var in city_variants:
            for region_var in region_variants:
                result = await self._try_geocode_variant(
                    city_var,
                    country_code,
                    region_var,
                    retry_attempts,
                    timeout or self.DEFAULT_TIMEOUT
                )
                if result:
                    return result

        logger.info(f"No results found for '{city_name}' (tried {len(city_variants)} variants)")
        return None

    async def _try_geocode_variant(
            self,
            city_name: str,
            country_code: Optional[str],
            region: Optional[str],
            retry_attempts: int,
            timeout: int
    ) -> Optional[CityCoordinates]:
        """Попытка геокодирования с одним вариантом названия"""

        # Нормализация
        norm_city = self._normalize_city_name(city_name)
        norm_region = self._normalize_city_name(region) if region else None

        # 1. Проверяем major cities
        if norm_city in self._major_cities:
            lat, lon, timezone, country, importance = self._major_cities[norm_city]

            if country_code and country_code.upper() != country:
                logger.debug(f"Country mismatch for {city_name}: expected {country}, got {country_code}")
            else:
                coords = CityCoordinates(
                    lat=lat,
                    lon=lon,
                    timezone=timezone,
                    display_name=city_name,
                    country_code=country,
                    region=region,
                    country=country,
                    importance=importance
                )

                cache_key = self._hash_city_name(norm_city, country_code, norm_region)
                await self._cache_coords(cache_key, city_name, coords)

                async with self._stats_lock:
                    self._stats['hits_major_cities'] += 1

                logger.debug(f"Major city cache hit: {city_name} -> {timezone}")
                return coords

        # 2. Кэш памяти
        cache_key = self._hash_city_name(norm_city, country_code, norm_region)
        cached = await self._get_from_memory_cache(cache_key)
        if cached:
            logger.debug(f"Memory cache hit: {norm_city}")
            return cached

        # 3. Кэш БД
        cached = await self._get_from_db_cache(cache_key)
        if cached:
            logger.info(f"DB cache hit: {norm_city}")
            await self._save_to_memory_cache(cache_key, cached)
            return cached

        # 4. API запрос
        result = await self._geocode_with_retry(
            norm_city,
            country_code,
            norm_region,
            retry_attempts,
            timeout
        )

        if result:
            await self._cache_coords(cache_key, city_name, result)
            async with self._stats_lock:
                self._stats['hits_api'] += 1
            logger.info(f"API geocode: {norm_city} → {result.country_code} ({result.timezone})")

        return result

    async def _geocode_with_retry(
            self,
            city_name: str,
            country_code: Optional[str],
            region: Optional[str],
            max_attempts: int,
            timeout: int
    ) -> Optional[CityCoordinates]:
        """Геокодирование с повторными попытками"""
        for attempt in range(max_attempts + 1):
            try:
                async with self._limiter:
                    return await self._geocode_single(
                        city_name,
                        country_code,
                        region,
                        attempt,
                        timeout
                    )

            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {city_name} (attempt {attempt + 1})")
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"Error geocoding {city_name}: {e}")
                async with self._stats_lock:
                    self._stats['errors'] += 1

                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None

        return None

    async def _geocode_single(
            self,
            city_name: str,
            country_code: Optional[str],
            region: Optional[str],
            attempt: int,
            timeout: int
    ) -> Optional[CityCoordinates]:
        """Одиночный запрос к API"""
        if attempt > 0:
            logger.info(f"Retry {attempt} for {city_name}")

        # ✅ Гарантируем, что сессия инициализирована
        session = await self._ensure_session()
        if session is None:
            logger.error(f"Session is None for {city_name}")
            return None

        params = {
            'q': city_name,
            'format': 'json',
            'addressdetails': 1,
            'limit': 5,
            'accept-language': 'ru,en',
            'dedupe': 1
        }

        if country_code:
            params['countrycodes'] = country_code.lower()

        try:
            request_timeout = aiohttp.ClientTimeout(total=timeout)

            async with session.get(
                    self.base_url,
                    params=params,
                    timeout=request_timeout
            ) as response:

                if response.status != 200:
                    raise ValueError(f"API returned {response.status}")

                data = await response.json()

                if not isinstance(data, list):
                    logger.warning(f"Unexpected response type for {city_name}: {type(data)}")
                    return None

                if not data:
                    logger.info(f"No results for: {city_name}")
                    return None

                best_result = self._select_best_result(data, country_code, region)

                if not best_result or not isinstance(best_result, dict):
                    logger.warning(f"No valid result for: {city_name}")
                    return None

                if 'lat' not in best_result or 'lon' not in best_result:
                    logger.warning(f"Missing coordinates in result for: {city_name}")
                    return None

                try:
                    lat = float(best_result['lat'])
                    lon = float(best_result['lon'])
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid coordinate values for {city_name}: {e}")
                    return None

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f"Invalid coordinates: {lat}, {lon}")

                timezone = self.tf.timezone_at(lat=lat, lng=lon) or "UTC"

                address = best_result.get('address')
                if address is None or not isinstance(address, dict):
                    address = {}

                display_name = best_result.get('display_name')
                if not display_name or not isinstance(display_name, str):
                    display_name = city_name

                coords = CityCoordinates(
                    lat=lat,
                    lon=lon,
                    timezone=timezone,
                    display_name=display_name,
                    country_code=address.get('country_code', '').upper() if address else '',
                    region=address.get('state') or address.get('region') if address else None,
                    country=address.get('country') if address else None,
                    importance=float(best_result.get('importance', 0))
                )

                return coords

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for {city_name}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for {city_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {city_name}: {e}")

        return None

    @staticmethod
    def _select_best_result(
            results: List[dict],
            country_code: Optional[str],
            region: Optional[str] = None
    ) -> Optional[dict]:
        """Выбор наилучшего результата с учетом региона"""
        if not results or not isinstance(results, list):
            return None

        filtered = results

        if country_code:
            country_filtered = []
            for r in filtered:
                if not isinstance(r, dict):
                    continue
                address = r.get('address')
                if address and isinstance(address, dict):
                    cc = address.get('country_code', '').upper()
                    # ✅ Сравниваем с учетом регистра
                    if cc == country_code.upper():
                        country_filtered.append(r)
            if country_filtered:
                filtered = country_filtered
            else:
                # ✅ Если нет результатов в указанной стране - ищем все
                logger.warning(f"No results for country {country_code}, trying without filter")

        # Затем фильтр по региону
        if region and filtered:
            region_lower = region.lower()
            region_filtered = []
            for r in filtered:
                if not isinstance(r, dict):
                    continue
                address = r.get('address')
                display_name = r.get('display_name', '')
                if address and isinstance(address, dict):
                    state = address.get('state', '') or address.get('region', '')
                    if (state and region_lower in state.lower()) or \
                            (display_name and region_lower in display_name.lower()):
                        region_filtered.append(r)
            if region_filtered:
                filtered = region_filtered
            else:
                logger.warning(f"No results for region {region}, trying without filter")

        if not filtered:
            return None

        # Возвращаем наиболее важный результат
        try:
            return max(filtered, key=lambda x: float(x.get('importance', 0)) if isinstance(x, dict) else 0)
        except (ValueError, TypeError):
            return filtered[0] if filtered else None

    async def batch_geocode(
            self,
            cities: List[str],
            country_code: Optional[str] = None,
            region: Optional[str] = None,
            max_concurrent: int = DEFAULT_MAX_CONCURRENT,
            progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Optional[CityCoordinates]]:
        """Пакетное геокодирование с поддержкой региона"""
        from asyncio import Semaphore

        semaphore = Semaphore(max_concurrent)
        total = len(cities)
        completed = 0

        async def process_city(city: str) -> Tuple[str, Optional[CityCoordinates]]:
            nonlocal completed

            async with semaphore:
                result = await self.geocode(city, country_code, region)

                completed += 1
                if progress_callback:
                    asyncio.create_task(
                        asyncio.to_thread(progress_callback, completed, total)
                    )

                return city, result

        tasks = [process_city(city) for city in cities]

        results = {}
        for task in asyncio.as_completed(tasks):
            try:
                city, coords = await task
                results[city] = coords
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")

        return results

    async def get_stats(self) -> Dict[str, Any]:
        """Полная статистика использования"""
        db_stats = {}
        if self._enable_db_cache and self._conn:
            try:
                async with self._conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN expires_at > ? THEN 1 END) as valid,
                        COUNT(CASE WHEN timestamp > ? THEN 1 END) as recent_1h,
                        AVG(importance) as avg_importance,
                        COUNT(CASE WHEN region IS NOT NULL THEN 1 END) as with_region
                    FROM city_cache
                """, (int(time.time()), int(time.time()) - 3600)) as cursor:
                    row = await cursor.fetchone()
                    db_stats = {
                        'db_total': row[0],
                        'db_valid': row[1],
                        'db_recent_1h': row[2],
                        'db_avg_importance': row[3],
                        'db_with_region': row[4]
                    }
            except Exception as e:
                logger.error(f"Failed to get DB stats: {e}")

        async with self._stats_lock:
            stats = self._stats.copy()

        stats.update({
            'memory_cache_size': len(self._memory_cache),
            'major_cities_count': len(self._major_cities),
            'rate_limit': self._limiter.max_rate,
            'db_enabled': self._enable_db_cache,
            'memory_cache_enabled': self._enable_memory_cache,
            'db_path': self.db_path if self._enable_db_cache else None,
            'has_transliteration': HAS_TRANSLIT,
        })
        stats.update(db_stats)

        return stats

    async def cleanup_cache(
            self,
            max_age_days: int = 30,
            max_memory_items: int = 10000
    ) -> Dict[str, int]:
        """Очистка кэша"""
        results = {'memory_cleaned': 0, 'db_cleaned': 0}

        if self._enable_memory_cache:
            cutoff = time.time() - self.MEMORY_CACHE_TTL
            async with self._memory_cache_lock:
                initial_size = len(self._memory_cache)
                self._memory_cache = {
                    k: v for k, v in self._memory_cache.items()
                    if v[1] > cutoff
                }
                results['memory_cleaned'] = initial_size - len(self._memory_cache)

                if len(self._memory_cache) > max_memory_items:
                    items = sorted(self._memory_cache.items(), key=lambda x: x[1][1])
                    to_remove = items[:len(items) - max_memory_items]
                    for key, _ in to_remove:
                        del self._memory_cache[key]

        if self._enable_db_cache and self._conn:
            try:
                cutoff = int(time.time()) - (max_age_days * 86400)
                async with self._conn.execute(
                        "DELETE FROM city_cache WHERE expires_at < ?",
                        (cutoff,)
                ) as cursor:
                    results['db_cleaned'] = cursor.rowcount
                    await self._conn.commit()
                    logger.info(f"Cleaned {cursor.rowcount} expired DB entries")

                await self._conn.execute("VACUUM")

            except Exception as e:
                logger.error(f"DB cleanup failed: {e}")

        return results

    async def close(self):
        """Корректное закрытие ресурсов"""
        close_tasks = []

        if self._session and not self._session.closed:
            close_tasks.append(self._session.close())

        if self._conn:
            close_tasks.append(self._conn.close())

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        async with self._memory_cache_lock:
            self._memory_cache.clear()

        logger.info("Geocoder closed")