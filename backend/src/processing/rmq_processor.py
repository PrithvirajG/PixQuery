import json
import sqlite3

from src.processing.models.blip import BlipModel
from src.processing.models.clip import ClipModel
from src.processing.models.yolo import YoloModel
from src.rabbit_mq.base_consumer import RabbitConsumer
import aio_pika
import logging
import numpy as np
from PIL import Image

from src.repositories.i_database_manager import IDatabaseManager
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.qdrant_db import insert_image_embedding, insert_text_embedding, init_qdrant
from src.storage.sqlite_db import SQLiteHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

class ImageProcessorConsumer(RabbitConsumer):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ImageProcessorConsumer")
        self.yolo = None
        self.clip = None
        self.blip = None
        self.qdrant_client = init_qdrant()
        sql_database = SQLiteHandler(db_path='pixquery.db')
        self.database_manager: IDatabaseManager = SQLDatabaseManager(sql_database)
        self.load_models()

    def load_models(self):
        print("[ModelRegistry] Loading models...")
        self.yolo = YoloModel()
        self.clip = ClipModel()
        self.blip = BlipModel()
        print("[ModelRegistry] All models loaded.")


    async def on_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            image_path = message.body.decode()
            try:
                message_json = json.loads(image_path)
                self.logger.info(f"Processing: {image_path}")
                await self.process_image(message_json.get("image_path"))
                self.logger.info(f"Done: {image_path}")
            except Exception as e:
                self.logger.exception(f"Error processing {image_path}: {str(e)}")


    async def process_image(self, image_path: str):
        try:
            self.logger.info(f"Processing image at path {image_path}")
            image = Image.open(image_path).convert('RGB')

            detections = self.yolo.detect(image=image, write_image=True)
            description = self.blip.describe(image)
            image_embedding = self.clip.embed(image)
            image_embedding = image_embedding / np.linalg.norm(image_embedding)
            text_embedding = self.clip.embed_text(description)
            text_embedding = text_embedding / np.linalg.norm(text_embedding)

            if image_embedding is None:
                self.logger.error(f"Error while creating image embeddings. Embedding: {image_embedding}")

            if description is None:
                self.logger.error(f"Error while generating description. Description: {description}")

            if detections is None:
                self.logger.error(f"Error while performing object detection. Detections: {detections}")

            if text_embedding is None:
                self.logger.error(f"Error while creating text embeddings. Text embedding: {text_embedding}")

            # global database_manager, qdrant_client
            result = self.database_manager.get_image_by_path(image_path)
            self.logger.info("Fetched image record from DB: %s", result)
            if result is None:
                raise ValueError(f"No record found in DB for image: {image_path}")
            image_id = result["id"]

            self.logger.info(f"DETECTIONS: {detections}")
            self.logger.info(f"DESCRIPTION: {description}")
            # Store description & detections
            self.database_manager.update_image_metadata(
                image_id=image_id,
                detections=json.dumps(detections),
                description=description
            )

            # Store embedding in Qdrant
            insert_image_embedding(
                self.qdrant_client,
                "image_embeddings",
                image_id,
                image_embedding
            )
            insert_text_embedding(
                client=self.qdrant_client,
                collection_name="text_embeddings",
                item_id=image_id,
                embedding=text_embedding,
                text=description
            )
            self.logger.info(f"Successfully processed and stored embedding for image at path {image_path}")

        except Exception as e:
            self.logger.exception("Error processing image: %s", str(e))
