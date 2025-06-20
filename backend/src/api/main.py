# src/api/main.py
from fastapi import FastAPI
from src.query.search import search_images, search_image_descriptions
from src.storage.sqlite_db import get_unprocessed_images
from src.processing.processor import process_image
import sqlite3
import json
from rq import Queue
from redis import Redis

app = FastAPI()

@app.post('/process')
async def process():
    paths = get_unprocessed_images()
    queue = Queue('photos', connection=Redis())
    for path in paths:
        queue.enqueue(process_image, path)
    return {'status': 'queued', 'count': len(paths)}

@app.get('/search')
async def search(query: str, top_k: int = 10):
    results = search_images(query, limit=top_k)
    return results

@app.get('/search_descriptions')
async def search(query: str, top_k: int = 10):
    results = search_image_descriptions(query, limit=top_k)
    return results

@app.get('/images/{id}')
async def get_image(id: int):
    conn = sqlite3.connect('pixquery.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, path, detections, description, corrected_detections FROM images WHERE id = ?', (id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'path': row[1],
            'detections': row[2],
            'description': row[3],
            'corrected_detections': row[4]
        }
    return {'error': 'Image not found'}

@app.post('/correct/{id}')
async def correct(id: int, body: dict):
    conn = sqlite3.connect('pixquery.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE images SET corrected_detections=?, description=? WHERE id=?',
        (json.dumps(body.get('detections')), body.get('description'), id)
    )
    conn.commit()
    conn.close()
    return {'status': 'updated'}