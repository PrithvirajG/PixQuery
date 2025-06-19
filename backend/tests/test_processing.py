import unittest
import sqlite3
import os

from PIL import Image

from src.processing.processor import process_image
from src.storage.sqlite_db import init_db

class TestProcessing(unittest.TestCase):
    def test_processing(self):
        # Setup
        db_path = 'test.db'
        os.remove(db_path)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Image.new('RGB', (224, 224), color='white').save("tests/test3.jpg")
        cursor.execute('INSERT INTO images (path, processed) VALUES (?, 0)', ('tests/test.jpg',))
        conn.commit()

        # Process
        process_image('tests/test.jpg', db_path)

        # Validate
        cursor.execute('SELECT detections, description, processed FROM images WHERE path = ?', ('test.jpg',))
        result = cursor.fetchone()
        self.assertEqual(result[2], 1)
        self.assertIsNotNone(result[0])
        self.assertIsNotNone(result[1])

        # Cleanup
        conn.close()
        os.remove(db_path)

if __name__ == '__main__':
    unittest.main()
