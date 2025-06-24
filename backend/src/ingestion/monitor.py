import asyncio
import json
import os
import time
import sqlite3
from rq import Queue
from redis import Redis
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.rabbit_mq.base_publisher import RabbitPublisher
from src.repositories.i_database_manager import IDatabaseManager
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.processing.processor import process_image

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Generic")


class ImageHandler(FileSystemEventHandler):
    def __init__(self, db_path='pixquery.db', loop=None):
        self.db_path = db_path
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("ImageHandler")
        self.queue = RabbitPublisher(queue_name="image_task")
        sqlite_database = SQLiteHandler(db_path)
        self.database_manager = SQLDatabaseManager(sqlite_database)

    async def initialize(self):
        await self.queue.connect()

    def on_created(self, event):
        # Now this is a sync method, as required by watchdog
        if event.is_directory or not event.src_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            return

        # Schedule the actual async processing in the running loop
        asyncio.run_coroutine_threadsafe(
            self.handle_new_image(event.src_path),
            self.loop
        )

    async def handle_new_image(self, image_path):
        try:
            self.logger.info("[NEW IMAGE] Detected new file: %s", image_path)

            result = self.database_manager.get_image_by_path(image_path)

            if result is None:
                self.database_manager.add_image(image_path)
                payload = {'image_path': image_path}
                await self.queue.publish(json.dumps(payload))
                self.logger.info(f"[NEW IMAGE] Logged to DB and queued: {image_path}")
            else:
                if result['processed'] == 1:
                    self.logger.info(f"[SKIP] Already processed: {image_path}")
                else:
                    self.logger.info(f"[REQUEUE] Found but unprocessed: {image_path}")
                    # You could requeue it here if needed
        except Exception as e:
            logger.exception("Error pushing new image to queue: %s", str(e))

async def start_monitoring(folder_path='~/pixquery_photos', db_path='pixquery.db'):
    try:
        folder_path = os.path.expanduser(folder_path)
        os.makedirs(folder_path, exist_ok=True)

        loop = asyncio.get_running_loop()
        event_handler = ImageHandler(db_path=db_path, loop=loop)
        await event_handler.initialize()
        logger.info(f"Initialized event handler for: {folder_path}")

        observer = Observer()
        observer.schedule(event_handler, folder_path, recursive=False)
        observer.start()

        logger.info(f"Started watching: {folder_path}")
        try:
            while True:
                await asyncio.sleep(1)  # async-safe sleep
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except Exception as e:
        logger.error(f"Error in monitoring: {str(e)}")


if __name__ == "__main__":
    _folder_path = os.environ.get("MONITOR_PATH", "~/pixquery_photos")
    _db_path = os.environ.get("DB_PATH", "pixquery.db")
    asyncio.run(start_monitoring(folder_path=_folder_path, db_path=_db_path))

