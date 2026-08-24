"""
Database infrastructure module for Psychometry Service.

Provides:
- Async SQLAlchemy engine and session management
- Base model class for all psych schema tables
- Repository pattern implementations for each entity
- Connection pooling and retry logic
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import AsyncGenerator, Optional, List, Dict, Any, Union
from decimal import Decimal
from fastapi import Depends

from sqlalchemy import (
    Column, BigInteger, String, Float, Integer, Boolean,
    DateTime, Text, JSON, ForeignKey, CheckConstraint,
    Index, PrimaryKeyConstraint, UniqueConstraint,
    create_engine, event, select, update, delete, insert,
    and_, or_, func, desc, asc
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker,
    declared_attr, Mapped, mapped_column
)
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from ..settings import settings


logger = logging.getLogger(__name__)


# ============================================================
# BASE MODEL
# ============================================================

class PsychBase:
    """Base class for all psych schema models."""

    __table_args__ = {"schema": "psych"}

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


Base = declarative_base(cls=PsychBase)


# ============================================================
# DATABASE ENGINE & SESSION FACTORY
# ============================================================

class DatabaseManager:
    """
    Manages database connections and sessions for Psychometry Service.
    Implements connection pooling, retry logic, and health checks.
    """

    _instance = None
    _engine: Optional[AsyncEngine] = None
    _async_session_factory: Optional[async_sessionmaker] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Initialize database connection pool and session factory."""
        if self._engine is not None:
            return

        try:
            # Create async engine with connection pooling
            self._engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,  # Check connection before using
                poolclass=AsyncAdaptedQueuePool,
                connect_args={
                    "timeout": 10,
                    "command_timeout": 30,
                    "server_settings": {
                        "application_name": "psychometry_service",
                        "statement_timeout": "30000",  # 30 seconds
                        "idle_in_transaction_session_timeout": "60000"  # 60 seconds
                    }
                }
            )

            # Create session factory
            self._async_session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )

            # Set up connection event listeners
            @event.listens_for(self._engine.sync_engine, "connect")
            def on_connect(dbapi_connection, connection_record):
                """Set up connection-specific settings."""
                cursor = dbapi_connection.cursor()
                cursor.execute("SET statement_timeout = '30s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '60s'")
                cursor.execute("SET synchronous_commit = 'on'")
                cursor.close()

            logger.info("Database connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise

    async def close(self) -> None:
        """Close all database connections and dispose of the engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._async_session_factory = None
            logger.info("Database connection pool disposed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session with proper context management.

        Usage:
            async with db_manager.get_session() as session:
                result = await session.execute(select(...))
        """
        if not self._async_session_factory:
            await self.initialize()

        async with self._async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database connection.

        Returns:
            Dict with status and any error details.
        """
        try:
            async with self.get_session() as session:
                # Simple query to check connection
                result = await session.execute(
                    select(func.now()).execution_options(
                        timeout=5  # 5 second timeout for health check
                    )
                )
                await result.scalar()

            return {
                "status": "healthy",
                "error": None
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# ============================================================
# GLOBAL DATABASE MANAGER INSTANCE
# ============================================================

db_manager = DatabaseManager()


# ============================================================
# REPOSITORY PATTERN IMPLEMENTATIONS
# ============================================================

class MMPIRepository:
    """Repository for MMPI results operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> "MMPIResult":
        """Create a new MMPI result."""
        from ..core.models import MMPIResult

        result = MMPIResult(**kwargs)
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_by_id(self, result_id: int) -> Optional["MMPIResult"]:
        """Get MMPI result by ID."""
        from ..core.models import MMPIResult

        result = await self.session.execute(
            select(MMPIResult).where(MMPIResult.id == result_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional["MMPIResult"]:
        """Get MMPI result by idempotency key."""
        from ..core.models import MMPIResult

        result = await self.session.execute(
            select(MMPIResult).where(MMPIResult.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_user_history(
            self,
            user_id: int,
            limit: int = 10,
            offset: int = 0
    ) -> List["MMPIResult"]:
        """Get MMPI history for a user."""
        from ..core.models import MMPIResult

        results = await self.session.execute(
            select(MMPIResult)
            .where(MMPIResult.user_id == user_id)
            .order_by(desc(MMPIResult.taken_at))
            .limit(limit)
            .offset(offset)
        )
        return results.scalars().all()

    async def update_raw_data_uri(self, result_id: int, uri: str) -> bool:
        """Update the raw_data_uri field for a result."""
        from ..core.models import MMPIResult

        result = await self.session.execute(
            update(MMPIResult)
            .where(MMPIResult.id == result_id)
            .values(raw_data_uri=uri)
            .returning(MMPIResult.id)
        )
        await self.session.flush()
        return result.scalar() is not None

    async def get_latest_by_user(self, user_id: int) -> Optional["MMPIResult"]:
        """Get the most recent MMPI result for a user."""
        from ..core.models import MMPIResult

        result = await self.session.execute(
            select(MMPIResult)
            .where(MMPIResult.user_id == user_id)
            .order_by(desc(MMPIResult.taken_at))
            .limit(1)
        )
        return result.scalar_one_or_none()


class IATRepository:
    """Repository for IAT results operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> "IATResult":
        """Create a new IAT result."""
        from ..core.models import IATResult

        result = IATResult(**kwargs)
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_by_id(self, result_id: int) -> Optional["IATResult"]:
        """Get IAT result by ID."""
        from ..core.models import IATResult

        result = await self.session.execute(
            select(IATResult).where(IATResult.id == result_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional["IATResult"]:
        """Get IAT result by idempotency key."""
        from ..core.models import IATResult

        result = await self.session.execute(
            select(IATResult).where(IATResult.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_user_history(
            self,
            user_id: int,
            limit: int = 10,
            offset: int = 0
    ) -> List["IATResult"]:
        """Get IAT history for a user."""
        from ..core.models import IATResult

        results = await self.session.execute(
            select(IATResult)
            .where(IATResult.user_id == user_id)
            .order_by(desc(IATResult.taken_at))
            .limit(limit)
            .offset(offset)
        )
        return results.scalars().all()

    async def update_raw_data_uri(self, result_id: int, uri: str) -> bool:
        """Update the raw_data_uri field for a result."""
        from ..core.models import IATResult

        result = await self.session.execute(
            update(IATResult)
            .where(IATResult.id == result_id)
            .values(raw_data_uri=uri)
            .returning(IATResult.id)
        )
        await self.session.flush()
        return result.scalar() is not None

    async def get_latest_by_user(self, user_id: int) -> Optional["IATResult"]:
        """Get the most recent IAT result for a user."""
        from ..core.models import IATResult

        result = await self.session.execute(
            select(IATResult)
            .where(IATResult.user_id == user_id)
            .order_by(desc(IATResult.taken_at))
            .limit(1)
        )
        return result.scalar_one_or_none()


class TestScheduleRepository:
    """Repository for test schedule operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> "TestSchedule":
        """Get existing schedule or create a new one for a user."""
        from ..core.models import TestSchedule

        schedule = await self.session.execute(
            select(TestSchedule).where(TestSchedule.user_id == user_id)
        )
        existing = schedule.scalar_one_or_none()

        if existing:
            return existing

        # Create new schedule
        new_schedule = TestSchedule(user_id=user_id)
        self.session.add(new_schedule)
        await self.session.flush()
        return new_schedule

    async def update_schedule(
            self,
            user_id: int,
            mmpi_at: Optional[datetime] = None,
            iat_at: Optional[datetime] = None
    ) -> "TestSchedule":
        """Update test schedule after taking a test."""
        from ..core.models import TestSchedule

        update_values = {}

        if mmpi_at:
            update_values["last_mmpi_at"] = mmpi_at
            update_values["next_mmpi_due"] = mmpi_at.date() + timedelta(
                days=settings.MMPI_INTERVAL_DAYS
            )

        if iat_at:
            update_values["last_iat_at"] = iat_at
            update_values["next_iat_due"] = iat_at.date() + timedelta(
                days=settings.IAT_INTERVAL_DAYS
            )

        if not update_values:
            schedule = await self.get_or_create(user_id)
            return schedule

        # Use ON CONFLICT for upsert
        from ..core.models import TestSchedule

        # Try update first
        result = await self.session.execute(
            update(TestSchedule)
            .where(TestSchedule.user_id == user_id)
            .values(**update_values)
            .returning(TestSchedule)
        )
        schedule = result.scalar_one_or_none()

        if schedule:
            return schedule

        # If no existing, create new
        new_schedule = TestSchedule(
            user_id=user_id,
            **update_values
        )
        self.session.add(new_schedule)
        await self.session.flush()
        return new_schedule

    async def can_take_mmpi(self, user_id: int) -> bool:
        """Check if user can take MMPI test."""
        schedule = await self.get_or_create(user_id)

        if not schedule.is_active:
            return False

        if schedule.next_mmpi_due is None:
            return True

        return schedule.next_mmpi_due <= date.today()

    async def can_take_iat(self, user_id: int) -> bool:
        """Check if user can take IAT test."""
        schedule = await self.get_or_create(user_id)

        if not schedule.is_active:
            return False

        if schedule.next_iat_due is None:
            return True

        return schedule.next_iat_due <= date.today()

    async def get_next_due_dates(self, user_id: int) -> Dict[str, Optional[date]]:
        """Get next due dates for both tests."""
        schedule = await self.get_or_create(user_id)

        return {
            "next_mmpi_due": schedule.next_mmpi_due,
            "next_iat_due": schedule.next_iat_due
        }


class OutboxRepository:
    """Repository for outbox operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
            self,
            event_type: str,
            payload: Dict[str, Any],
            idempotency_key: Optional[str] = None
    ) -> "Outbox":
        """Create a new outbox event."""
        from ..core.models import Outbox

        event = Outbox(
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
            status="pending"
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_pending_events(
            self,
            limit: int = 100,
            stale_minutes: int = 5
    ) -> List["Outbox"]:
        """
        Get pending or stale processing events.

        Args:
            limit: Maximum number of events to return
            stale_minutes: Minutes after which processing is considered stale

        Returns:
            List of events ready for processing
        """
        from ..core.models import Outbox

        stale_threshold = datetime.now() - timedelta(minutes=stale_minutes)

        events = await self.session.execute(
            select(Outbox)
            .where(
                or_(
                    Outbox.status == "pending",
                    and_(
                        Outbox.status == "processing",
                        Outbox.processing_started_at < stale_threshold
                    )
                )
            )
            .order_by(asc(Outbox.created_at))
            .limit(limit)
            .with_for_update(skip_locked=True)  # Skip rows locked by other workers
        )
        return events.scalars().all()

    async def mark_processing(self, event_id: int) -> bool:
        """Mark an event as being processed."""
        from ..core.models import Outbox

        result = await self.session.execute(
            update(Outbox)
            .where(Outbox.id == event_id)
            .where(Outbox.status == "pending")
            .values(
                status="processing",
                processing_started_at=datetime.now()
            )
            .returning(Outbox.id)
        )
        await self.session.flush()
        return result.scalar() is not None

    async def mark_sent(self, event_id: int) -> bool:
        """Mark an event as successfully sent."""
        from ..core.models import Outbox

        result = await self.session.execute(
            update(Outbox)
            .where(Outbox.id == event_id)
            .values(
                status="sent",
                processed_at=datetime.now()
            )
            .returning(Outbox.id)
        )
        await self.session.flush()
        return result.scalar() is not None

    async def mark_failed(
            self,
            event_id: int,
            error: str,
            max_retries: int = 5
    ) -> bool:
        """Mark an event as failed. Move to dead_letter if max retries exceeded."""
        from ..core.models import Outbox

        # Get current retry count
        event = await self.session.execute(
            select(Outbox).where(Outbox.id == event_id)
        )
        event_obj = event.scalar_one_or_none()

        if not event_obj:
            return False

        new_retry_count = event_obj.retry_count + 1

        if new_retry_count >= max_retries:
            # Move to dead_letter
            result = await self.session.execute(
                update(Outbox)
                .where(Outbox.id == event_id)
                .values(
                    status="dead_letter",
                    retry_count=new_retry_count,
                    last_error=error,
                    processing_started_at=None
                )
                .returning(Outbox.id)
            )
            logger.critical(
                f"Outbox event {event_id} moved to dead_letter after {new_retry_count} attempts",
                extra={"event_id": event_id, "error": error}
            )
        else:
            # Reset to pending for retry
            result = await self.session.execute(
                update(Outbox)
                .where(Outbox.id == event_id)
                .values(
                    status="pending",
                    retry_count=new_retry_count,
                    last_error=error,
                    processing_started_at=None
                )
                .returning(Outbox.id)
            )
            logger.warning(
                f"Outbox event {event_id} failed, will retry (attempt {new_retry_count}/{max_retries})",
                extra={"event_id": event_id, "error": error}
            )

        await self.session.flush()
        return result.scalar() is not None

    async def get_dead_letter_events(
            self,
            limit: int = 100
    ) -> List["Outbox"]:
        """Get dead_letter events for monitoring."""
        from ..core.models import Outbox

        events = await self.session.execute(
            select(Outbox)
            .where(Outbox.status == "dead_letter")
            .order_by(desc(Outbox.created_at))
            .limit(limit)
        )
        return events.scalars().all()

    async def count_pending(self) -> int:
        """Get count of pending events (for monitoring)."""
        from ..core.models import Outbox

        result = await self.session.execute(
            select(func.count(Outbox.id))
            .where(Outbox.status == "pending")
        )
        return result.scalar() or 0


# ============================================================
# DEPENDENCY INJECTION FOR FASTAPI
# ============================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database session.

    Usage:
        @app.get("/some-endpoint")
        async def endpoint(session: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with db_manager.get_session() as session:
        yield session


async def get_mmpi_repository(
        session: AsyncSession = Depends(get_db_session)
) -> MMPIRepository:
    """FastAPI dependency for MMPI repository."""
    return MMPIRepository(session)


async def get_iat_repository(
        session: AsyncSession = Depends(get_db_session)
) -> IATRepository:
    """FastAPI dependency for IAT repository."""
    return IATRepository(session)


async def get_schedule_repository(
        session: AsyncSession = Depends(get_db_session)
) -> TestScheduleRepository:
    """FastAPI dependency for test schedule repository."""
    return TestScheduleRepository(session)


async def get_outbox_repository(
        session: AsyncSession = Depends(get_db_session)
) -> OutboxRepository:
    """FastAPI dependency for outbox repository."""
    return OutboxRepository(session)


# ============================================================
# DATABASE INITIALIZATION FUNCTIONS
# ============================================================

async def init_database() -> None:
    """
    Initialize database connection pool.
    Should be called during application startup.
    """
    await db_manager.initialize()
    logger.info("Database initialization complete")


async def close_database() -> None:
    """
    Close database connection pool.
    Should be called during application shutdown.
    """
    await db_manager.close()
    logger.info("Database closed")


async def create_tables() -> None:
    """
    Create all database tables if they don't exist.
    For development/testing only.
    In production, use Alembic migrations.
    """
    if not db_manager._engine:
        await db_manager.initialize()

    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def drop_tables() -> None:
    """
    Drop all database tables.
    For testing only - USE WITH EXTREME CAUTION in production.
    """
    if not db_manager._engine:
        await db_manager.initialize()

    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.warning("Database tables dropped")


# ============================================================
# TRANSACTION UTILITIES
# ============================================================

class TransactionManager:
    """
    Utility for managing database transactions with retry logic.
    """

    def __init__(self, session: AsyncSession, max_retries: int = 3):
        self.session = session
        self.max_retries = max_retries

    async def execute(self, func, *args, **kwargs):
        """
        Execute a function within a transaction with retry logic.

        Usage:
            result = await TransactionManager(session).execute(
                some_async_function, arg1, arg2
            )
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with self.session.begin():
                    return await func(*args, **kwargs, session=self.session)
            except IntegrityError as e:
                # Unique constraint violation - likely idempotency duplicate
                logger.warning(f"Integrity error in transaction (attempt {attempt + 1}): {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    await self.session.rollback()
                    continue
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error in transaction (attempt {attempt + 1}): {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    await self.session.rollback()
                    continue
                raise
            except Exception as e:
                # Non-database error - don't retry
                logger.error(f"Unexpected error in transaction: {e}")
                raise

        raise last_error


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Base
    "Base",
    "PsychBase",

    # Database Manager
    "db_manager",
    "DatabaseManager",

    # Session
    "get_db_session",
    "AsyncSession",

    # Repositories
    "MMPIRepository",
    "IATRepository",
    "TestScheduleRepository",
    "OutboxRepository",
    "get_mmpi_repository",
    "get_iat_repository",
    "get_schedule_repository",
    "get_outbox_repository",

    # Initialization
    "init_database",
    "close_database",
    "create_tables",
    "drop_tables",

    # Utilities
    "TransactionManager",
]