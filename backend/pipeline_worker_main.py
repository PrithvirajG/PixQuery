import asyncio

from src.logging_config import configure_logging

configure_logging(process_name="pipeline-worker")

from src.consumer.processing import start_pipeline_worker


if __name__ == "__main__":
    asyncio.run(start_pipeline_worker())

