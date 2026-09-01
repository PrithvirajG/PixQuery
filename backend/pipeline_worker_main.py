import asyncio

from src.consumer.processing import start_pipeline_worker


if __name__ == "__main__":
    asyncio.run(start_pipeline_worker())

