import os


DEFAULT_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

DEFAULT_PIPELINE_ID = os.getenv("PIPELINE_ID", "default_image_analysis")
DEFAULT_PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "v1")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pixquery")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "image_task")
SCAN_COMMAND_QUEUE = os.getenv("SCAN_COMMAND_QUEUE", "scan_commands")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WATCH_ROOT = os.path.abspath(os.path.expanduser(os.getenv("WATCH_ROOT", "~/pixquery_photos")))
# How often (seconds) the monitor re-reads workspace definitions from MongoDB
WORKSPACE_REFRESH_INTERVAL = int(os.getenv("WORKSPACE_REFRESH_INTERVAL", "60"))

