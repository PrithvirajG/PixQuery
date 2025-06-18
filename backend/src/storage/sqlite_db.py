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
