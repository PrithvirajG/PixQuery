import asyncio

from src.consumer.ingestion import start_monitoring


if __name__ == "__main__":
    asyncio.run(start_monitoring())

