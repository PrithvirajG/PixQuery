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

# Folder the ``image_write`` node writes into by default (resolved relative to the
# source image's directory, i.e. inside the workspace). The reconciler skips any
# directory with this name so pipeline outputs are never re-ingested as new
# source images. Custom absolute output paths are the user's responsibility.
PIPELINE_OUTPUT_DIRNAME = os.getenv("PIPELINE_OUTPUT_DIRNAME", "pixquery_output")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pixquery")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "image_task")
# Wait this long (total seconds) for the broker to become ready before giving up.
RABBITMQ_CONNECT_TIMEOUT = float(os.getenv("RABBITMQ_CONNECT_TIMEOUT", "60"))
# Run pending DB migrations automatically when the API starts. Set to "false" to
# manage migrations explicitly via `python -m src.migrations` (e.g. as a deploy step).
RUN_MIGRATIONS_ON_STARTUP = os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").lower() in ("1", "true", "yes")
SCAN_COMMAND_QUEUE = os.getenv("SCAN_COMMAND_QUEUE", "scan_commands")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WATCH_ROOT = os.path.abspath(os.path.expanduser(os.getenv("WATCH_ROOT", "~/pixquery_photos")))
# How often (seconds) the monitor re-reads workspace definitions from MongoDB
WORKSPACE_REFRESH_INTERVAL = int(os.getenv("WORKSPACE_REFRESH_INTERVAL", "60"))

