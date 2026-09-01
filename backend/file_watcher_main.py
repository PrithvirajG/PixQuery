import asyncio

from src.logging_config import configure_logging

configure_logging(process_name="file-watcher")

from src.consumer.ingestion import start_file_watcher


if __name__ == "__main__":
    asyncio.run(start_file_watcher())

