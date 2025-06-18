import os
import time
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.storage.sqlite_db import init_db
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

    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT processed FROM images WHERE path = ?', (event.src_path,))
        result = cursor.fetchone()
        if result is None:
            cursor.execute('INSERT INTO images (path, processed) VALUES (?, 0)', (event.src_path,))
            conn.commit()
            self.logger.info(f"[NEW IMAGE] Logged to DB: {event.src_path}")
        else:
            self.logger.warning(f"[SKIP] Duplicate detected: {event.src_path}")
        conn.close()

def start_monitoring(folder_path='~/pixquery_photos', db_path='pixquery.db'):
    folder_path = os.path.expanduser(folder_path)
    logger.info(f"Folder Path: {folder_path}")
    os.makedirs(folder_path, exist_ok=True)
    db_path = os.path.join(folder_path, 'pixquery.db')
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

if __name__ == "__main__":
    folder_path = os.environ.get("MONITOR_PATH", "~/pixquery_photos")
    start_monitoring(folder_path=folder_path)
