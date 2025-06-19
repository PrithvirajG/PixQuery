import os
import time
import sqlite3
from rq import Queue
from redis import Redis
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.storage.sqlite_db import init_db
from src.processing.processor import process_image

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Generic")


class ImageHandler(FileSystemEventHandler):
    def __init__(self, db_path='pixquery.db'):
        self.db_path = db_path
        self.logger = logging.getLogger("ImageHandler")
        self.queue = Queue('photos', connection=Redis(host='localhost', port=6379))

    def on_created(self, event):
        try:
            self.logger.info("[NEW IMAGE] Detected new file: %s", event.src_path)
            if event.is_directory or not event.src_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT processed FROM images WHERE path = ?', (event.src_path,))
            result = cursor.fetchone()
            if result is None:
                self.queue.enqueue(process_image, event.src_path, self.db_path)
                cursor.execute('INSERT INTO images (path, processed) VALUES (?, 0)', (event.src_path,))
                conn.commit()
                self.logger.info(f"[NEW IMAGE] Logged to DB: {event.src_path}")
            else:
                self.logger.warning(f"[SKIP] Duplicate detected: {event.src_path}")
            conn.close()
        except Exception as e:
            logger.exception("Error pushing the new image in Queue: %s", str(e))

def start_monitoring(folder_path='~/pixquery_photos', db_path='pixquery.db'):
    try:
        folder_path = os.path.expanduser(folder_path)
        logger.info(f"Folder Path: {folder_path}")
        os.makedirs(folder_path, exist_ok=True)
        # db_path = os.path.join(folder_path, 'pixquery.db')
        logger.info(f"Initializing SQL database at path: {db_path}")

        init_db(db_path)

        event_handler = ImageHandler(db_path)
        observer = Observer()
        observer.schedule(event_handler, folder_path, recursive=False)
        observer.start()

        logger.info(f"Started watching: {folder_path}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except Exception as e:
        logger.error(f"Error in monitoring: {str(e)}")

if __name__ == "__main__":
    _folder_path = os.environ.get("MONITOR_PATH", "~/pixquery_photos")
    _db_path = os.environ.get("DB_PATH", "pixquery.db")
    start_monitoring(folder_path=_folder_path, db_path=_db_path)
