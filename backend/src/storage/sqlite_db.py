import sqlite3
import os
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

class SQLiteHandler:
    def __init__(self, db_path='pixquery.db'):
        self.db_path = db_path
        self.logger = logging.getLogger("SqliteManager")
        self.connection: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def initialize_connection(self, schema):
        try:
            self.logger.info("Initializing SQLite database connection...")
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.connection.cursor()
            self.cursor.execute(schema)
            self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Exception occurred while initializing database connection. Reason: {e}")
            self.connection.rollback()


    def execute_query(self, query, params=()) -> sqlite3.Cursor | None:
        try:
            if self.connection is None or self.cursor is None:
                self.logger.error("Database connection is not initialized.")
                return None
            self.cursor.execute(
                query,
                params
            )
            self.connection.commit()
            return self.cursor
        except Exception as e:
            self.logger.exception("Exception occurred while executing query. Reason: %s", str(e))
            self.connection.rollback()
            return None

    def update_query(self, query, params=()):
        try:
            if self.connection is None or self.cursor is None:
                self.logger.error("Database connection is not initialized.")
                return None
            self.cursor.execute(
                query,
                params
            )
            self.connection.commit()
        except Exception as e:
            self.logger.exception("Exception occurred while executing update query. Reason: %s", str(e))
            self.connection.rollback()

    def close_connection(self):
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
        except Exception as e:
            self.logger.exception("Exception occurred while closing database connection. Reason: %s", str(e))


    def get_image_id(self, path):
        self.cursor.execute('SELECT id FROM images WHERE path = ?', (path,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def update_image(self, path, detections, description):
        self.cursor.execute(
            'UPDATE images SET detections=?, description=?, processed=1 WHERE path=?',
            (detections, description, path)
        )
        self.connection.commit()

    def get_unprocessed_images(self):
        self.cursor.execute('SELECT path FROM images WHERE processed=0')
        paths = [row[0] for row in self.cursor.fetchall()]
        self.connection.commit()
        return paths

    def close(self):
        self.connection.close()

# Singleton per worker
sqlite_manager = SQLiteHandler()

def get_unprocessed_images(db_path='pixquery.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT path FROM images WHERE processed=0')
    paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    return paths

