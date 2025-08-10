# Setup Guide

## Prerequisites

### System Requirements
- **Python**: 3.8 or higher (3.12 recommended)
- **RAM**: Minimum 8GB (16GB+ recommended for GPU processing)
- **Storage**: 5GB for models and dependencies + image storage space
- **GPU** (optional): NVIDIA GPU with 4GB+ VRAM for faster inference

### Required Services
- **Docker**: For running Redis, RabbitMQ, and Qdrant containers
- **Git**: For cloning repositories and managing code

## Step-by-Step Installation

### 1. Clone and Navigate to Backend
```bash
git clone <repository-url>
cd PixQuery/backend
```

### 2. Create Photo Directory
```bash
mkdir -p ~/pixquery_photos
```
This directory will be monitored for new images to process.

### 3. Install Python Dependencies

#### Option A: Standard Installation
```bash
pip install -r requirements.txt
```

#### Option B: Separate Worker Dependencies (if using containers)
```bash
# For API server only
pip install fastapi uvicorn sqlite3

# For monitor service
pip install -r requirements.monitor.txt

# For worker service  
pip install -r requirements.worker.txt
```

### 4. Start External Services
```bash
# Start all required services
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected output:
```
pixquery-redis      redis:7            Up      6379/tcp
pixquery-rabbitmq   rabbitmq:3-mgmt    Up      5672/tcp, 15672/tcp  
qdrant             qdrant/qdrant       Up      6333/tcp, 6334/tcp
```

### 5. Initialize Database Schema
The SQLite database will be automatically created on first API startup, but you can verify:

```bash
# Check if database exists
ls -la pixquery.db

# View schema (after first run)
sqlite3 pixquery.db ".schema images"
```

### 6. Download AI Model Weights
Models will download automatically on first use, but you can pre-download:

```bash
# YOLO model (downloaded to project root)
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# CLIP model (cached in ~/.cache/clip/)
python -c "import clip; clip.load('ViT-B/32')"

# BLIP model (cached in ~/.cache/huggingface/)
python -c "from transformers import BlipProcessor, BlipForConditionalGeneration; \
BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base'); \
BlipForConditionalGeneration.from_pretrained('Salesforce/blip-image-captioning-base')"
```

## Environment Configuration

### Environment Variables (Optional)
Create `.env` file in backend directory:

```bash
# Image directory path (default: ~/pixquery_photos)
MONITOR_PATH=/path/to/your/photos

# Database path (default: pixquery.db)  
DB_PATH=./pixquery.db

# Qdrant connection
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Docker Compose Overrides (Optional)
For custom ports or volumes, create `docker-compose.override.yml`:

```yaml
version: "3.8"
services:
  qdrant:
    ports:
      - "6333:6333"
    volumes:
      - ./custom_qdrant_data:/qdrant/storage
```

## Verification Steps

### 1. Test API Server
```bash
# Start FastAPI development server
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Test health check (in another terminal)
curl http://localhost:8000/docs
```

### 2. Test Database Connection
```bash
# Python REPL test
python3 -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
sqlite_db = SQLiteHandler(db_path='pixquery.db')
db_manager = SQLDatabaseManager(sqlite_db)
print('Database connected successfully')
"
```

### 3. Test AI Models
```bash
# Quick model loading test
python3 -c "
from src.processing.models.yolo import YoloModel
from src.processing.models.clip import ClipModel
from PIL import Image
import numpy as np

print('Loading YOLO...')
yolo = YoloModel()

print('Loading CLIP...')
clip = ClipModel()

print('Testing with dummy image...')
dummy_img = Image.new('RGB', (224, 224), color='red')
detections = yolo.detect(dummy_img)
embedding = clip.embed(dummy_img)

print(f'YOLO detections: {len(detections) if detections else 0}')
print(f'CLIP embedding shape: {embedding.shape if embedding is not None else None}')
print('Models loaded successfully!')
"
```

### 4. Test External Services
```bash
# Test Redis connection
redis-cli ping
# Expected: PONG

# Test RabbitMQ (management UI)
open http://localhost:15672
# Login: guest/guest

# Test Qdrant API
curl http://localhost:6333/collections
# Expected: {"result":{"collections":[]}}
```

## Troubleshooting Common Issues

### CUDA/GPU Issues
```bash
# Check PyTorch CUDA support
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Force CPU-only mode if needed
export CUDA_VISIBLE_DEVICES=""
```

### Port Conflicts
```bash
# Check if ports are in use
netstat -tulpn | grep -E ':(6379|5672|6333|8000)'

# Kill existing services if needed
sudo lsof -ti:6379 | xargs kill -9
```

### Permission Errors
```bash
# Fix photo directory permissions
chmod 755 ~/pixquery_photos

# Fix database permissions
chmod 664 pixquery.db
```

### Import/Module Errors
```bash
# Ensure PYTHONPATH includes backend directory
export PYTHONPATH=/path/to/PixQuery/backend:$PYTHONPATH

# Or run from backend directory
cd /path/to/PixQuery/backend
python -m src.api.main
```

### Model Download Failures
```bash
# Clear cache and retry
rm -rf ~/.cache/clip/
rm -rf ~/.cache/huggingface/
rm -f yolov8n.pt

# Manual download with wget/curl
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
```

## Next Steps

After successful setup:

1. **Add test images**: Copy some photos to `~/pixquery_photos/`
2. **Start file monitor**: `python src/ingestion/monitor.py`
3. **Start worker**: `python src/processing/worker.py` or `rq worker photos`
4. **Trigger processing**: `curl -X POST http://localhost:8000/process`
5. **Test search**: `curl "http://localhost:8000/search?query=cat&top_k=5"`

See [running.md](./running.md) for detailed instructions on running the full system.