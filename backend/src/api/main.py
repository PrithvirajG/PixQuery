# src/api/main.py
import os

from fastapi import FastAPI
# from src.query.search import search_images, search_image_descriptions
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import get_unprocessed_images
from src.processing.processor import process_image
import sqlite3
import json
from rq import Queue
from redis import Redis
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.repositories.i_database_manager import IDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.query.search import ImageSearchManager

sqlite_db = SQLiteHandler(db_path='pixquery.db')
database_manager: IDatabaseManager = SQLDatabaseManager(sqlite_db)
search_manager = ImageSearchManager(database_manager)

app = FastAPI()
photo_dir = os.path.expanduser("~/pixquery_photos")
app.mount("/images_source", StaticFiles(directory=photo_dir), name="images_source")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # <-- your React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post('/process')
async def process():
    paths = database_manager.get_unprocessed_images()
    queue = Queue('photos', connection=Redis())
    for path in paths:
        queue.enqueue(process_image, path)
    return {'status': 'queued', 'count': len(paths)}

@app.get('/search')
async def search(query: str, top_k: int = 10):
    results = search_manager.search_images(query=query, limit=top_k)
    return results

@app.get('/search_descriptions')
async def search(query: str, top_k: int = 10):
    results = search_manager.search_image_descriptions(query=query, limit=top_k)
    return results

@app.get('/images/{id}')
async def get_image(id: int):
    response = database_manager.get_image_by_id(image_id=id)
    if response:
        return response
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