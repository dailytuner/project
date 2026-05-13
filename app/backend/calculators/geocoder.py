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

@dataclass(frozen=True)
class CityCoordinates:
    lat: float
    lon: float
    timezone: str
    display_name: str
    country_code: str
    importance: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CityCoordinates':
        return cls(**data)


class AsyncCityGeocoder:
    """Production-ready асинхронный геокодер с кэшированием"""
    
    DEFAULT_RATE_LIMIT = 1.0
    MEMORY_CACHE_TTL = 3600
    DB_CACHE_TTL = 30 * 86400
    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_CONCURRENT = 3
    
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
            'hits_major_cities': 0,  # Добавили статистику
            'errors': 0,
            'total_requests': 0
        }
        self._stats_lock = asyncio.Lock()

        # ИСПРАВЛЕННЫЙ кэш major_cities с правильными timezone
        self._major_cities = {
            # Московское время (UTC+3)
            "москва": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "мск": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "москва рф": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),
            "москва россия": (55.7558, 37.6173, "Europe/Moscow", "RU", 1.0),

            # СПБ (тоже Moscow time)
            "санкт-петербург": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "спб": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "питер": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),
            "петербург": (59.9343, 30.3351, "Europe/Moscow", "RU", 0.9),

            # Калининград (UTC+2)
            "калининград": (54.7104, 20.5070, "Europe/Kaliningrad", "RU", 0.8),

            # Екатеринбург (UTC+5)
            "екатеринбург": (56.8389, 60.6057, "Asia/Yekaterinburg", "RU", 0.8),

            # Новосибирск (UTC+7)
            "новосибирск": (55.0084, 82.9357, "Asia/Novosibirsk", "RU", 0.8),

            # Казань (Moscow time)
            "казань": (55.8304, 49.0661, "Europe/Moscow", "RU", 0.7),

            # Нижний Новгород (Moscow time)
            "нижний новгород": (56.3269, 44.0075, "Europe/Moscow", "RU", 0.7),

            # Челябинск (UTC+5)
            "челябинск": (55.1644, 61.4368, "Asia/Yekaterinburg", "RU", 0.7),

            # Омск (UTC+6)
            "омск": (54.9884, 73.3242, "Asia/Omsk", "RU", 0.7),

            # Самара (UTC+4)
            "самара": (53.2415, 50.2212, "Europe/Samara", "RU", 0.7),

            # Ростов-на-Дону (Moscow time)
            "ростов-на-дону": (47.2225, 39.7187, "Europe/Moscow", "RU", 0.7),

            # Уфа (UTC+5)
            "уфа": (54.7355, 55.9587, "Asia/Yekaterinburg", "RU", 0.7),

            # Красноярск (UTC+7)
            "красноярск": (56.0153, 92.8932, "Asia/Krasnoyarsk", "RU", 0.7),

            # Пермь (UTC+5)
            "пермь": (58.0105, 56.2502, "Asia/Yekaterinburg", "RU", 0.7),

            # Воронеж (Moscow time)
            "воронеж": (51.6720, 39.1843, "Europe/Moscow", "RU", 0.6),

            # Волгоград (UTC+3)
            "волгоград": (48.7080, 44.5133, "Europe/Volgograd", "RU", 0.6),

            # Краснодар (Moscow time)
            "краснодар": (45.0355, 38.9750, "Europe/Moscow", "RU", 0.6),

            # Саратов (UTC+4)
            "саратов": (51.5924, 45.9608, "Europe/Saratov", "RU", 0.6),

            # Тюмень (UTC+5)
            "тюмень": (57.1613, 65.5250, "Asia/Yekaterinburg", "RU", 0.6),

            # Тольятти (UTC+4)
            "тольятти": (53.5088, 49.4192, "Europe/Samara", "RU", 0.6),

            # Ижевск (UTC+4)
            "ижевск": (56.8527, 53.2115, "Europe/Samara", "RU", 0.6),

            # Ульяновск (UTC+4)
            "ульяновск": (54.3282, 48.3866, "Europe/Ulyanovsk", "RU", 0.6),

            # Иркутск (UTC+8)
            "иркутск": (52.2864, 104.2806, "Asia/Irkutsk", "RU", 0.6),

            # Хабаровск (UTC+10)
            "хабаровск": (48.4802, 135.0719, "Asia/Vladivostok", "RU", 0.6),

            # Ярославль (Moscow time)
            "ярославль": (57.6261, 39.8845, "Europe/Moscow", "RU", 0.6),

            # Владивосток (UTC+10)
            "владивосток": (43.1332, 131.9113, "Asia/Vladivostok", "RU", 0.6),

            # Мга (Moscow time)
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
            
            await self._conn.commit()
            
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            if self._conn:
                await self._conn.close()
            self._conn = None
            raise
    
    @staticmethod
    def _hash_city_name(city_name: str, country_code: Optional[str] = None) -> str:
        """Создание хэша для кэширования"""
        key = f"{city_name.lower().strip()}:{country_code or ''}"
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
                """SELECT lat, lon, timezone, display_name, country_code, importance
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
                    country_code, importance, timestamp, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    cache_key,
                    city_name.lower().strip(),
                    coords.lat,
                    coords.lon,
                    coords.timezone,
                    coords.display_name,
                    coords.country_code,
                    coords.importance,
                    int(time.time()),
                    expires_at
                )
            )
            await self._conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to save to DB cache: {e}")
    
    def _normalize_city_name(self, city_name: str) -> str:
        """Нормализация названия города для поиска в кэше"""
        return city_name.strip().lower().replace('ё', 'е')
    
    async def _cache_coords(
        self,
        city_name: str,
        country_code: Optional[str],
        coords: CityCoordinates
    ):
        """✅ ДОБАВЛЕННЫЙ МЕТОД: Сохранение координат во все кэши"""
        cache_key = self._hash_city_name(city_name, country_code)
        
        # Сохраняем в память и БД
        await asyncio.gather(
            self._save_to_memory_cache(cache_key, coords),
            self._save_to_db_cache(cache_key, city_name, coords)
        )
    
    async def geocode(
        self,
        city_name: str,
        country_code: Optional[str] = None,
        retry_attempts: int = 2,
        timeout: Optional[int] = None
    ) -> Optional[CityCoordinates]:
        """
        Основной метод геокодирования.
        """
        if not city_name or not city_name.strip():
            return None
        
        normalized_name = self._normalize_city_name(city_name)
        
        async with self._stats_lock:
            self._stats['total_requests'] += 1
        
        # 1. Проверяем кэш основных городов
        if normalized_name in self._major_cities:
            lat, lon, timezone, country, importance = self._major_cities[normalized_name]
            
            # Проверяем страну если указана
            if country_code and country_code.upper() != country:
                # Если страна не совпадает, продолжаем обычный поиск
                logger.debug(f"Country mismatch for {city_name}: expected {country}, got {country_code}")
            else:
                coords = CityCoordinates(
                    lat=lat,
                    lon=lon,
                    timezone=timezone,
                    display_name=city_name,
                    country_code=country,
                    importance=importance
                )
                
                # Сохраняем в обычные кэши
                await self._cache_coords(city_name, country_code, coords)
                
                async with self._stats_lock:
                    self._stats['hits_major_cities'] += 1
                
                logger.debug(f"Major city cache hit: {city_name} -> {timezone}")
                return coords
        
        cache_key = self._hash_city_name(normalized_name, country_code)
        
        # 2. Проверяем кэш памяти
        cached = await self._get_from_memory_cache(cache_key)
        if cached:
            logger.debug(f"Memory cache hit: {normalized_name}")
            return cached
        
        # 3. Проверяем кэш БД
        cached = await self._get_from_db_cache(cache_key)
        if cached:
            logger.info(f"DB cache hit: {normalized_name}")
            await self._save_to_memory_cache(cache_key, cached)
            return cached
        
        # 4. Запрашиваем у API
        result = await self._geocode_with_retry(
            normalized_name,
            country_code,
            retry_attempts,
            timeout or self.DEFAULT_TIMEOUT
        )
        
        if result:
            # Сохраняем в оба кэша
            await self._cache_coords(city_name, country_code, result)
            
            async with self._stats_lock:
                self._stats['hits_api'] += 1
            
            logger.info(f"API geocode: {normalized_name} → {result.country_code} ({result.timezone})")
        
        return result
    
    async def _geocode_with_retry(
        self,
        city_name: str,
        country_code: Optional[str],
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
        attempt: int,
        timeout: int
    ) -> Optional[CityCoordinates]:
        """Одиночный запрос к API"""
        if attempt > 0:
            logger.info(f"Retry {attempt} for {city_name}")
        
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
            
            async with self._session.get(
                self.base_url,
                params=params,
                timeout=request_timeout
            ) as response:
                
                if response.status != 200:
                    raise ValueError(f"API returned {response.status}")
                
                data = await response.json()
                if not data:
                    logger.info(f"No results for: {city_name}")
                    return None
                
                best_result = self._select_best_result(data, country_code)
                if not best_result:
                    return None
                
                lat = float(best_result['lat'])
                lon = float(best_result['lon'])
                
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f"Invalid coordinates: {lat}, {lon}")
                
                timezone = self.tf.timezone_at(lat=lat, lng=lon) or "UTC"
                address = best_result.get('address', {})
                
                coords = CityCoordinates(
                    lat=lat,
                    lon=lon,
                    timezone=timezone,
                    display_name=best_result.get('display_name', city_name),
                    country_code=address.get('country_code', '').upper(),
                    importance=float(best_result.get('importance', 0))
                )
                
                return coords
                
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP client error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
    
    @staticmethod
    def _select_best_result(
        results: List[dict],
        country_code: Optional[str]
    ) -> Optional[dict]:
        """Выбор наилучшего результата"""
        if not results:
            return None
        
        filtered = results
        
        if country_code:
            country_filtered = [
                r for r in results
                if r.get('address', {}).get('country_code', '').lower() == country_code.lower()
            ]
            if country_filtered:
                filtered = country_filtered
        
        return max(
            filtered,
            key=lambda x: float(x.get('importance', 0))
        )
    
    async def batch_geocode(
        self,
        cities: List[str],
        country_code: Optional[str] = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Optional[CityCoordinates]]:
        """Пакетное геокодирование"""
        from asyncio import Semaphore
        
        semaphore = Semaphore(max_concurrent)
        total = len(cities)
        completed = 0
        
        async def process_city(city: str) -> Tuple[str, Optional[CityCoordinates]]:
            nonlocal completed
            
            async with semaphore:
                result = await self.geocode(city, country_code)
                
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
                        AVG(importance) as avg_importance
                    FROM city_cache
                """, (int(time.time()), int(time.time()) - 3600)) as cursor:
                    row = await cursor.fetchone()
                    db_stats = {
                        'db_total': row[0],
                        'db_valid': row[1],
                        'db_recent_1h': row[2],
                        'db_avg_importance': row[3]
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
