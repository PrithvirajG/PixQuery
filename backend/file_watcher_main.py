import asyncio

from src.consumer.ingestion import start_file_watcher


if __name__ == "__main__":
    asyncio.run(start_file_watcher())

