# Running PixQuery Backend

## Quick Start (Development Mode)

### 1. Start External Services
```bash
# From project root
docker-compose up -d

# Verify services
docker-compose logs -f qdrant
```

### 2. Start API Server
```bash
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
API will be available at `http://localhost:8000` with docs at `/docs`

### 3. Start File Monitor (Optional)
```bash
# In separate terminal
cd backend
python src/ingestion/monitor.py
```
Monitors `~/pixquery_photos/` for new images

### 4. Start Processing Worker
```bash
# In separate terminal
cd backend

# Option A: Redis Queue worker
rq worker photos --logging_level INFO

# Option B: RabbitMQ worker  
python src/processing/worker.py
```

## Running Modes

### Development Mode
**Use Case**: Local development, debugging, hot-reload  
**Resources**: Minimal, single-process components

```bash
# Terminal 1: External services
docker-compose up -d

# Terminal 2: API with auto-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Monitor (if testing file ingestion)
python src/ingestion/monitor.py

# Terminal 4: Worker (if testing processing)  
rq worker photos
```

**Testing the Pipeline**:
```bash
# Add test image
cp /path/to/test.jpg ~/pixquery_photos/

# Trigger processing
curl -X POST http://localhost:8000/process

# Search
curl "http://localhost:8000/search?query=test&top_k=5"
```

### Staging Mode
**Use Case**: Performance testing, integration testing  
**Resources**: Production-like setup, multiple workers

```bash
# Use production requirements
pip install -r requirements.txt

# Start services with resource limits
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Start API with multiple workers
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Start multiple processing workers
rq worker photos &
rq worker photos &
rq worker photos &
```

### Production Mode
**Use Case**: Deployment, high availability  
**Resources**: Optimized containers, monitoring, logging

```bash
# Build production images
docker-compose build

# Start with production configuration
docker-compose -f docker-compose.prod.yml up -d

# Health checks
curl http://localhost:8000/health
curl http://localhost:6333/collections
```

## Service Management

### Individual Components

#### FastAPI Server
```bash
# Basic startup
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Development (auto-reload)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production (multiple workers)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Custom configuration
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --log-level info
```

#### File System Monitor
```bash
# Default path (~/pixquery_photos)
python src/ingestion/monitor.py

# Custom path
MONITOR_PATH=/custom/photo/path python src/ingestion/monitor.py

# With debug logging
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from src.ingestion.monitor import main
main()
"
```

#### Processing Worker

**Redis Queue (RQ)**:
```bash
# Single worker
rq worker photos

# Multiple workers
rq worker photos &
rq worker photos &

# With custom settings
rq worker photos --url redis://localhost:6379/0 --logging_level DEBUG

# Worker dashboard
rq-dashboard --redis-url redis://localhost:6379
```

**RabbitMQ Worker**:
```bash
# Start consumer
python src/processing/worker.py

# Custom RabbitMQ URL
RABBITMQ_URL=amqp://guest:guest@localhost:5672/ python src/processing/worker.py
```

### Docker Containers

#### Full Stack
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose build && docker-compose up -d
```

#### Individual Services
```bash
# Just Redis
docker-compose up -d redis

# Just Qdrant  
docker-compose up -d qdrant

# Scale workers
docker-compose up -d --scale worker=3
```

## CLI Operations

### Direct Database Operations
```bash
# Add image manually
python -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
db.add_image('/path/to/image.jpg')
"

# Check processing status
python -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
print('Unprocessed:', len(db.get_unprocessed_images()))
print('Processed:', len(db.get_processed_images()))
"
```

### Direct Processing
```bash
# Process single image
python -c "
from src.processing.processor import process_image
process_image('/path/to/image.jpg')
"

# Batch process
python -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.processing.processor import process_image

db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
for path in db.get_unprocessed_images()[:5]:  # Process first 5
    process_image(path)
"
```

### Search Operations
```bash
# CLI search
python -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.query.search import ImageSearchManager

db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
search = ImageSearchManager(db)
results = search.search_images('cat', limit=5)
print(results)
"
```

## API Endpoints

### Core Endpoints
```bash
# Trigger processing
curl -X POST http://localhost:8000/process

# Search images
curl "http://localhost:8000/search?query=sunset&top_k=10"

# Search descriptions  
curl "http://localhost:8000/search_descriptions?query=beach&top_k=5"

# Get image metadata
curl http://localhost:8000/images/123

# Update image metadata
curl -X POST http://localhost:8000/correct/123 \
  -H "Content-Type: application/json" \
  -d '{"detections": [...], "description": "Updated description"}'
```

### Static Files
```bash
# Access images directly
curl http://localhost:8000/images_source/photo.jpg

# List directory (if enabled)
ls ~/pixquery_photos/
```

## Monitoring and Debugging

### Logs and Status
```bash
# API server logs
tail -f errors.log

# Worker queue status
rq info --url redis://localhost:6379

# Database statistics
sqlite3 pixquery.db "SELECT COUNT(*) as total, SUM(processed) as processed FROM images;"

# Qdrant collections
curl http://localhost:6333/collections | jq
```

### Performance Monitoring
```bash
# Resource usage
docker stats

# Queue metrics
rq info --url redis://localhost:6379

# Database size
ls -lh pixquery.db
du -sh qdrant_data/
```

### Health Checks
```bash
# Service availability
curl -f http://localhost:8000/docs
curl -f http://localhost:6333/collections  
redis-cli ping

# Model loading test
python -c "
from src.processing.models.yolo import YoloModel
from src.processing.models.clip import ClipModel
print('Models load successfully:', YoloModel() is not None and ClipModel() is not None)
"
```

## Shutdown Procedures

### Graceful Shutdown
```bash
# Stop workers first (finish current jobs)
pkill -f "rq worker"
pkill -f "python src/processing/worker.py"

# Stop API server
pkill -f uvicorn

# Stop external services
docker-compose down --timeout 30
```

### Emergency Shutdown
```bash
# Force kill all processes
pkill -9 -f pixquery
pkill -9 -f uvicorn
pkill -9 -f "rq worker"

# Force stop containers
docker-compose kill
```

### Cleanup
```bash
# Clear queue
rq empty photos --url redis://localhost:6379

# Reset processing status  
sqlite3 pixquery.db "UPDATE images SET processed = 0;"

# Clear vector database
curl -X DELETE http://localhost:6333/collections/image_embeddings
curl -X DELETE http://localhost:6333/collections/text_embeddings
```

## Environment-Specific Notes

### Development Environment
- Use `--reload` for API server hot-reload
- Enable debug logging for all components
- Single worker sufficient for testing

### Staging Environment  
- Multiple workers to test concurrency
- Production-like resource limits
- Performance profiling enabled

### Production Environment
- Process management (systemd/supervisor)
- Log rotation and monitoring
- Backup procedures for database and embeddings
- SSL/TLS termination at load balancer
- Health check endpoints for orchestration