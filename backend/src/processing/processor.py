import sqlite3
import json
from PIL import Image
from .models.yolo import YoloModel
from .models.clip import ClipModel
from .models.blip import BlipModel

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Generic")

def process_image(image_path: str, db_path='pixquery.db'):
    try:
        logger.info(f"Processing image at path {image_path}")
        image = Image.open(image_path).convert('RGB')

        yolo = YoloModel()
        clip = ClipModel()
        blip = BlipModel()

        logger.info(f"Loaded all models ...")
        detections = yolo.detect(image=image, write_image=True)
        description = blip.describe(image)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE images SET detections=?, description=?, processed=1 WHERE path=?',
            (json.dumps(detections), description, image_path)
        )
        conn.commit()
        conn.close()
        logger.info(f"Successfully processed the image at path {image_path}")
    except Exception as e:
        logger.error(f"Error processing {image_path}: {str(e)}")
