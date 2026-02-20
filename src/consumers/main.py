import asyncio
from src.common.utils import setup_signal_handlers
from src.consumers.db_consumer import DatabaseConsumer
from src.consumers.redis_consumer import RedisConsumer
from loguru import logger

async def main():
    redisConsumer = RedisConsumer()
    dbConsumer = DatabaseConsumer()

    setup_signal_handlers(redisConsumer)
    setup_signal_handlers(dbConsumer, )

    async def log_health():
        while dbConsumer._running:
            await asyncio.sleep(60)
            health = redisConsumer.get_stats()
            logger.info(f'RedisConsumer Status: {health}')
            dbHealth = dbConsumer.get_stats()
            logger.info(f'DatabaseConsumer Status: {dbHealth}')

    try:
        await asyncio.gather(
            redisConsumer.start(),
            dbConsumer.start(),
            log_health()
        )
    
    except Exception as e:
        logger.error(f'Error with consumers: {e}')
        await asyncio.gather(
            redisConsumer.stop(),
            dbConsumer.stop()
        )
        

if __name__ == '__main__':
    asyncio.run(main())
