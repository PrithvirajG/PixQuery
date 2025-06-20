import sqlite3
import json
import numpy as np
from PIL import Image
from .models.yolo import YoloModel
from .models.clip import ClipModel
from .models.blip import BlipModel
from src.storage.qdrant_db import init_qdrant, insert_image_embedding, insert_text_embedding

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Generic")

def process_image(image_path: str, db_path='pixquery.db', collection_name='image_embeddings'):
    try:
        logger.info(f"Processing image at path {image_path}")
        image = Image.open(image_path).convert('RGB')

        yolo = YoloModel()
        clip = ClipModel()
        blip = BlipModel()

        logger.info(f"Loaded all models ...")
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

        # Fetch image_id
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM images WHERE path = ?', (image_path,))
        result = cursor.fetchone()
        if result is None:
            raise ValueError(f"No record found in DB for image: {image_path}")
        image_id = result[0]

        # Store description & detections
        cursor.execute(
            'UPDATE images SET detections=?, description=?, processed=1 WHERE path=?',
            (json.dumps(detections), description, image_path)
        )
        conn.commit()
        conn.close()

        # Store embedding in Qdrant
        client = init_qdrant()
        insert_image_embedding(client, collection_name, image_id, image_embedding)
        insert_text_embedding(
            client=client,
            collection_name="text_embeddings",
            item_id=image_id,
            embedding=text_embedding,
            text=description
        )

        logger.info(f"Successfully processed and stored embedding for image at path {image_path}")

    except Exception as e:
        logger.error(f"Error processing {image_path}: {str(e)}")
