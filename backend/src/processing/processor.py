import sqlite3
import json
import numpy as np
from PIL import Image
from .models.yolo import YoloModel
from .models.clip import ClipModel
from .models.blip import BlipModel
from src.storage.qdrant_db import init_qdrant, insert_image_embedding, insert_text_embedding
from src.processing.models.model_registry import model_registry
import logging

from ..repositories.i_database_manager import IDatabaseManager
from ..repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from ..storage.sqlite_db import SQLiteHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Generic")
# sql_database = SQLiteHandler(db_path='pixquery.db')
# database_manager: IDatabaseManager = SQLDatabaseManager(sql_database)
# qdrant_client = init_qdrant()

_yolo = None
_clip = None
_blip = None
_database_manager = None
_qdrant_client = None

def get_resources():
    global _yolo, _clip, _blip, _database_manager, _qdrant_client

    if _yolo is None:
        _yolo = model_registry.yolo
    if _clip is None:
        _clip = model_registry.clip
    if _blip is None:
        _blip = model_registry.blip
    if _database_manager is None:
        sql_database = SQLiteHandler(db_path='pixquery.db')
        _database_manager = SQLDatabaseManager(sql_database)
    if _qdrant_client is None:
        _qdrant_client = init_qdrant()

    return _yolo, _clip, _blip, _database_manager, _qdrant_client

def process_image(image_path: str, db_path='pixquery.db', collection_name='image_embeddings'):
    try:
        logger.info(f"Processing image at path {image_path}")
        image = Image.open(image_path).convert('RGB')

        yolo, clip, blip, database_manager, qdrant_client = get_resources()

        detections = yolo.detect(image=image, write_image=True)
        description = blip.describe(image)
        image_embedding = clip.embed(image)
        image_embedding = image_embedding / np.linalg.norm(image_embedding)
        text_embedding = clip.embed_text(description)
        text_embedding = text_embedding / np.linalg.norm(text_embedding)

        if image_embedding is None:
            logger.error(f"Error while creating image embeddings. Embedding: {image_embedding}")

        if description is None:
            logger.error(f"Error while generating description. Description: {description}")

        if detections is None:
            logger.error(f"Error while performing object detection. Detections: {detections}")

        if text_embedding is None:
            logger.error(f"Error while creating text embeddings. Text embedding: {text_embedding}")

        # global database_manager, qdrant_client
        cursor: sqlite3.Cursor = database_manager.get_cursor_by_path(image_path)

        result = cursor.fetchone()

        if result is None:
            raise ValueError(f"No record found in DB for image: {image_path}")
        image_id = result[0]

        # Store description & detections
        database_manager.update_metadata_by_cursor(
            cursor=cursor,
            detections=json.dumps(detections),
            description=description
        )

        # Store embedding in Qdrant
        insert_image_embedding(qdrant_client, collection_name, image_id, image_embedding)
        insert_text_embedding(
            client=qdrant_client,
            collection_name="text_embeddings",
            item_id=image_id,
            embedding=text_embedding,
            text=description
        )
        logger.info(f"Successfully processed and stored embedding for image at path {image_path}")

    except Exception as e:
        logger.error(f"Error processing {image_path}: {str(e)}")
