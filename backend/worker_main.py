import asyncio

from src.consumer.processing import start_worker


if __name__ == "__main__":
    asyncio.run(start_worker())

