from ultralytics import YOLO

from PIL import Image, ImageDraw, ImageFont
from .interface import ModelInterface
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class YoloModel(ModelInterface):
    def __init__(self, model_path='yolov8n.pt'):
        self.logger = logging.getLogger("YoloModel")
        self.model = YOLO(model_path)
        self.logger.info("YOLO model loaded from %s", model_path)

    def detect(self, image: Image.Image, write_image: bool = False) -> list | None:
        try:
            self.logger.info("Performing YOLO object detection...")
            results = self.model(image)
            boxes = results[0].boxes

            detections = [{
                'label': results[0].names[int(cls)],
                'confidence': float(score),
                'bbox': box.xywh.tolist()[0],
            } for box, cls, score in zip(boxes, boxes.cls, boxes.conf)]

            if write_image:
                self.write_image_with_detections(
                    image,
                    detections,
                    "src/pipelines/processing/processed_media_dump/yolo_out.jpg",
                )

            return detections
        except Exception:
            self.logger.exception("Exception during YOLO detection")
            return None

    def write_image_with_detections(self, image: Image.Image, detections: list, save_path: str):
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

        for det in detections:
            x_c, y_c, w, h = det['bbox']
            x0, y0 = x_c - w / 2, y_c - h / 2
            x1, y1 = x_c + w / 2, y_c + h / 2
            label = f"{det['label']} ({det['confidence']:.2f})"
            draw.rectangle([x0, y0, x1, y1], outline="red", width=2)
            draw.text((x0, y0 - 10), label, fill="red", font=font)

        image.save(save_path)

    def embed(self, image): raise NotImplementedError
    def describe(self, image): raise NotImplementedError
