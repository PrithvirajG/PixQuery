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
# Fanout exchange carrying live UI events (job state changes, stage completions,
# output deletions) from the worker/monitor processes to the API's WebSockets.
EVENTS_EXCHANGE = os.getenv("EVENTS_EXCHANGE", "pixquery.events")
# Set to "false" to run without live updates; the UI then falls back to refetching
# on its own. Nothing else changes — events are advisory.
EVENTS_ENABLED = os.getenv("EVENTS_ENABLED", "true").lower() in ("1", "true", "yes")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WATCH_ROOT = os.path.abspath(os.path.expanduser(os.getenv("WATCH_ROOT", "~/pixquery_photos")))
# How often (seconds) the monitor re-reads workspace definitions from MongoDB
WORKSPACE_REFRESH_INTERVAL = int(os.getenv("WORKSPACE_REFRESH_INTERVAL", "60"))

# ---------------------------------------------------------------------------
# Logging — see src/logging_config.py for the setup this feeds.
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT", "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
)
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S")
# Console only — a color-coded level name. Auto-skipped on a non-TTY stream
# (redirected to a file, most container log drivers) regardless of this flag.
LOG_COLOR = os.getenv("LOG_COLOR", "true").lower() in ("1", "true", "yes")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() in ("1", "true", "yes")
LOG_DIR = os.getenv("LOG_DIR", "logs")
# Rollover cap: a new file starts once the current one reaches this size.
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
# Per-logger level overrides, applied on top of LOG_LEVEL — e.g.
# "pixquery.repositories=WARNING,pixquery.services.search_service=DEBUG".
LOG_LEVELS = os.getenv("LOG_LEVELS", "")

