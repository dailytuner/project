"""
Outbox worker for guaranteed event delivery.
"""
import asyncio
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main worker loop."""
    logger.info("🚀 Outbox worker started")

    while True:
        try:
            # Здесь будет логика обработки outbox
            logger.info("⏳ Processing outbox events...")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error processing outbox: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())