import sqlite3
from typing import Union, Any, Dict, List
import logging

from src.repositories.i_database_manager import IDatabaseManager
from src.storage.sqlite_db import SQLiteHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class SQLDatabaseManager(IDatabaseManager):
    """
    SQLite implementation of the IEventRepository interface.
    Uses the SQLiteManager to perform database operations.
    """
    def __init__(self, db_manager: SQLiteHandler):
        self.db_manager = db_manager
        self.logger = logging.getLogger("SQLiteEventRepository")
        self._initialize_schema()

    def _initialize_schema(self):
        """Initializes the database schema for events."""

        schema_sql = '''
                        CREATE TABLE IF NOT EXISTS images (
                            id INTEGER PRIMARY KEY,
                            path TEXT UNIQUE,
                            detections TEXT,
                            description TEXT,
                            processed BOOLEAN DEFAULT 0,
                            other_metadata TEXT
                        )
                    '''
        self.db_manager.initialize_connection(schema_sql)


    def add_image(self, image_path: str):
        query = "INSERT INTO images (path, processed) VALUES (?, 0)"
        params = (image_path,)
        try:
            response = self.db_manager.update_query(query, params)
            self.logger.debug(f"Image from path {image_path} has been successfully added. Response: {response}")
            return response
        except Exception as e:
            self.logger.exception(f"Failed to add image {image_path}: {e}")

    def get_all_images_database(self) -> List[Dict[str, Any]]:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.exception(f"Failed to retrieve all images: {e}")

    def get_multiple_images_by_ids(self, image_ids: List[int]) -> List[Any]:
        if not image_ids:
            return []

        placeholders = ','.join('?' * len(image_ids))
        query = f"SELECT id, path, detections, description, processed, other_metadata FROM images WHERE id IN ({placeholders})"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query, image_ids)
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            self.logger.exception(f"Failed to retrieve images by IDs {image_ids}: {e}")
            return []

    def get_processed_images(self) -> List[Dict[str, Any]]:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images WHERE processed = 1"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.exception(f"Failed to retrieve processed images: {e}")

    def get_unprocessed_images(self) -> List[str]:
        query = "SELECT path FROM images WHERE processed = 0"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            self.logger.exception(f"Failed to retrieve unprocessed images: {e}")

    def get_image_by_id(self, image_id: int) -> Union[Dict[str, Any], None]:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images WHERE id = ?"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query, (image_id,))
            row = cursor.fetchone()
            response = {
                "id": row[0],
                "path": row[1],
                "detections": row[2],
                "description": row[3],
                "processed": row[4],
                "other_metadata": row[5]
            }
            return response
        except Exception as e:
            self.logger.exception(f"Failed to retrieve image by ID {image_id}: {e}")
            return None

    def get_image_by_path(self, image_path: str) -> Union[Dict[str, Any], None]:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images WHERE path = ?"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query, (image_path,))
            row = cursor.fetchone()

            response = {
                "id": row[0],
                "path": row[1],
                "detections": row[2],
                "description": row[3],
                "processed": row[4],
                "other_metadata": row[5]
            }
            return response
        except Exception as e:
            self.logger.exception(f"Failed to retrieve image by path {image_path}: {e}")
            return None

    def get_cursor_by_path(self, image_path: str) -> sqlite3.Cursor | None:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images WHERE path = ?"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query, (image_path,))
            return cursor
        except Exception as e:
            self.logger.exception(f"Failed to retrieve cursor for image by path {image_path}: {e}")
            return None

    def get_processed_image_by_path(self, image_path: str) -> Union[Dict[str, Any], None]:
        query = "SELECT id, path, detections, description, processed, other_metadata FROM images WHERE path = ? AND processed = 1"
        try:
            cursor: sqlite3.Cursor = self.db_manager.execute_query(query, (image_path,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            self.logger.exception(f"Failed to retrieve unprocessed image by path {image_path}: {e}")
            return None

    def delete_image_by_id(self, image_id: int) -> None:
        query = "DELETE FROM images WHERE id = ?"
        try:
            self.db_manager.execute_query(query, (image_id,))
            self.logger.debug(f"Image ID {image_id} deleted successfully.")
        except Exception as e:
            self.logger.exception(f"Failed to delete image by ID {image_id}: {e}")

    def update_image_metadata(self, image_id: int, detections: str, description: str) -> None:
        query = "UPDATE images SET detections = ?, description = ?, processed = 1 WHERE id = ?"
        params = (detections, description, image_id)
        try:
            self.db_manager.execute_query(query, params)
            self.logger.debug(f"Image ID {image_id} metadata updated successfully.")
        except Exception as e:
            self.logger.exception(f"Failed to update image metadata for ID {image_id}: {e}")

    def update_metadata_by_cursor(self, cursor: sqlite3.Cursor, detections: str, description: str) -> None:
        """
        Updates the metadata of an image using a cursor.
        :param cursor: sqlite3.Cursor object pointing to the image record.
        :param detections: JSON string of detections.
        :param description: Description of the image.
        """
        try:
            self.logger.info(f"Updating metadata using cursor: {detections} | {description}")
            cursor.execute(
                'UPDATE images SET detections=?, description=?, processed=1 WHERE id=?',
                (detections, description, cursor.lastrowid)
            )
            self.db_manager.connection.commit()
            self.logger.debug(f"Image metadata updated successfully for ID {cursor.lastrowid}.")
        except Exception as e:
            self.logger.exception(f"Failed to update image metadata: {e}")

    def delete_image_by_path(self, image_path: str) -> None:
        query = "DELETE FROM images WHERE path = ?"
        try:
            self.db_manager.execute_query(query, (image_path,))
            self.logger.debug(f"Image at path {image_path} deleted successfully.")
        except Exception as e:
            self.logger.exception(f"Failed to delete image by path {image_path}: {e}")
