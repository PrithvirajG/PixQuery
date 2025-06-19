import sqlite3
import os

def init_db(db_path='pixquery.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            detections TEXT,
            description TEXT,
            processed BOOLEAN DEFAULT 0,
            corrected_detections TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_unprocessed_images(db_path='pixquery.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT path FROM images WHERE processed=0')
    paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    return paths

