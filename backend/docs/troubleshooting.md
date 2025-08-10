# Troubleshooting Guide

## Quick Diagnostics

### System Health Check
Run these commands to verify system state:

```bash
# Check service status
docker-compose ps

# Test database connectivity
python -c "from src.storage.sqlite_db import SQLiteHandler; SQLiteHandler('pixquery.db').test_connection()"

# Verify AI model loading
python -c "from src.processing.models.yolo import YoloModel; YoloModel()"

# Check API response
curl -f http://localhost:8000/docs || echo "API server not responding"

# Verify queue system
redis-cli ping || echo "Redis not responding"
```

## Common Issues and Solutions

### 1. Service Connection Failures

#### Redis Connection Refused
**Symptoms**: 
- Worker fails with "Connection refused" on port 6379
- API `/process` endpoint returns 500 error

**Diagnosis**:
```bash
# Check if Redis is running
docker-compose ps redis
netstat -tulpn | grep 6379

# Test direct connection
redis-cli ping
```

**Solutions**:
```bash
# Restart Redis service
docker-compose restart redis

# Check Redis logs for issues
docker-compose logs redis

# Verify Redis configuration
docker exec -it pixquery-redis redis-cli CONFIG GET "*"

# Alternative: Use different Redis instance
export REDIS_URL=redis://different-host:6379
```

#### Qdrant Vector Database Issues
**Symptoms**:
- Embedding storage fails
- Search returns no results despite processed images

**Diagnosis**:
```bash
# Check Qdrant service
curl http://localhost:6333/collections

# Verify collections exist
curl http://localhost:6333/collections/image_embeddings

# Check collection status
curl http://localhost:6333/collections/image_embeddings | jq '.result.status'
```

**Solutions**:
```bash
# Recreate collections
curl -X DELETE http://localhost:6333/collections/image_embeddings
curl -X PUT "http://localhost:6333/collections/image_embeddings" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 512, "distance": "Cosine"}}'

# Check Qdrant logs
docker-compose logs qdrant

# Reset Qdrant data (destructive)
docker-compose down
rm -rf qdrant_data/
docker-compose up -d qdrant
```

### 2. AI Model Loading Issues

#### CUDA Out of Memory
**Symptoms**:
- "RuntimeError: CUDA out of memory" during processing
- Models fail to load on GPU

**Diagnosis**:
```bash
# Check GPU memory usage
nvidia-smi

# Test CUDA availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Memory: {torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0}')"
```

**Solutions**:
```bash
# Force CPU-only mode
export CUDA_VISIBLE_DEVICES=""
python src/processing/worker.py

# Reduce batch size in processing
# Edit src/processing/processor.py to process images individually

# Clear GPU memory
python -c "import torch; torch.cuda.empty_cache()" || echo "CUDA not available"

# Use smaller models (edit model configurations)
# YOLO: yolov8n.pt instead of yolov8l.pt
```

#### Model Download Failures
**Symptoms**:
- "Unable to load pretrained weights" errors
- Network timeouts during model initialization

**Diagnosis**:
```bash
# Check internet connectivity
ping huggingface.co
ping github.com

# Check model cache directories
ls -la ~/.cache/clip/
ls -la ~/.cache/huggingface/
ls yolov8n.pt 2>/dev/null || echo "YOLO model not found"
```

**Solutions**:
```bash
# Manual model downloads
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt

# Clear corrupted cache
rm -rf ~/.cache/clip/
rm -rf ~/.cache/huggingface/transformers/

# Use offline mode (if models already downloaded)
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

# Alternative mirror for Hugging Face
export HF_ENDPOINT=https://hf-mirror.com
```

### 3. Database and Storage Issues

#### SQLite Database Locked
**Symptoms**:
- "database is locked" errors
- Processing hangs indefinitely

**Diagnosis**:
```bash
# Check for hanging connections
lsof pixquery.db

# Look for WAL files (write-ahead logging)
ls -la pixquery.db*

# Check database integrity
sqlite3 pixquery.db "PRAGMA integrity_check;"
```

**Solutions**:
```bash
# Kill processes using database
lsof pixquery.db | awk 'NR>1 {print $2}' | xargs kill -9

# Remove WAL files (ensure no active connections first)
rm -f pixquery.db-wal pixquery.db-shm

# Backup and recreate database
cp pixquery.db pixquery.db.backup
sqlite3 pixquery.db ".backup recovery.db"
mv recovery.db pixquery.db

# Switch to WAL mode for better concurrency
sqlite3 pixquery.db "PRAGMA journal_mode=WAL;"
```

#### Disk Space Issues
**Symptoms**:
- Processing fails with "No space left on device"
- Slow performance and timeouts

**Diagnosis**:
```bash
# Check disk usage
df -h .
du -sh pixquery.db qdrant_data/ ~/.cache/

# Find large files
find . -size +1G -type f 2>/dev/null
```

**Solutions**:
```bash
# Clean up model cache
rm -rf ~/.cache/huggingface/transformers/
rm -rf ~/.cache/clip/

# Vacuum SQLite database
sqlite3 pixquery.db "VACUUM;"

# Clean processed media dumps
rm -f src/processing/processed_media_dump/*

# Archive old embeddings (if recreatable)
tar -czf qdrant_backup.tar.gz qdrant_data/
rm -rf qdrant_data/collections/*/0/segments/*/vector_storage/
```

### 4. Processing Pipeline Issues

#### Images Not Being Processed
**Symptoms**:
- Images added but remain with `processed=0`
- Worker logs show no activity

**Diagnosis**:
```bash
# Check unprocessed image count
sqlite3 pixquery.db "SELECT COUNT(*) FROM images WHERE processed = 0;"

# Check queue status
rq info --url redis://localhost:6379

# Verify worker is running
ps aux | grep "rq worker"

# Check worker logs
rq worker photos --logging_level DEBUG
```

**Solutions**:
```bash
# Clear stuck queue
rq empty photos --url redis://localhost:6379

# Restart worker
pkill -f "rq worker"
rq worker photos &

# Manual processing test
python -c "
from src.processing.processor import process_image
process_image('path/to/test/image.jpg')
"

# Re-queue unprocessed images
curl -X POST http://localhost:8000/process
```

#### Search Returns No Results
**Symptoms**:
- Search queries return empty arrays
- Images are processed but not searchable

**Diagnosis**:
```bash
# Check processed images count
sqlite3 pixquery.db "SELECT COUNT(*) FROM images WHERE processed = 1;"

# Verify embeddings in Qdrant
curl "http://localhost:6333/collections/image_embeddings/points/1"

# Test CLIP model directly
python -c "
from src.processing.models.clip import ClipModel
clip = ClipModel()
embedding = clip.embed_text('cat')
print('Embedding shape:', embedding.shape if embedding is not None else None)
"
```

**Solutions**:
```bash
# Rebuild embeddings for existing images
python -c "
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.processing.processor import process_image

db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
for img in db.get_processed_images()[:10]:  # Test with first 10
    process_image(img['path'])
"

# Verify search manager initialization
python -c "
from src.query.search import ImageSearchManager
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler

db = SQLDatabaseManager(SQLiteHandler('pixquery.db'))
search = ImageSearchManager(db)
results = search.search_images('test', limit=1)
print('Search results:', len(results))
"
```

### 5. Performance Issues

#### Slow Processing Speed
**Symptoms**:
- Each image takes >30 seconds to process
- High CPU usage but no GPU utilization

**Diagnosis**:
```bash
# Check GPU utilization
nvidia-smi -l 1

# Monitor CPU usage
htop

# Check model loading time
python -c "
import time
start = time.time()
from src.processing.models.clip import ClipModel
clip = ClipModel()
print(f'CLIP loading time: {time.time() - start:.2f}s')
"
```

**Solutions**:
```bash
# Enable GPU acceleration
export CUDA_VISIBLE_DEVICES=0
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"

# Use smaller models
# Edit model configs to use yolov8n instead of yolov8l
# Use smaller CLIP variant if available

# Process in batches
python -c "
from src.processing.processor import process_image
import time

# Test batch processing vs individual
start = time.time()
for i in range(5):
    process_image('tests/test.jpg')
print(f'5 images processed in {time.time() - start:.2f}s')
"

# Increase worker count
rq worker photos &
rq worker photos &
```

#### High Memory Usage
**Symptoms**:
- System becomes unresponsive during processing
- Out of memory errors

**Diagnosis**:
```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head -10

# Check Python memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
```

**Solutions**:
```bash
# Limit worker processes
# Use only 1-2 workers instead of many

# Clear model cache between batches
python -c "
import gc
import torch
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
"

# Use model quantization (if supported)
# Enable mixed precision training for CLIP/BLIP models

# Process smaller batches
export BATCH_SIZE=1
python src/processing/worker.py
```

## Error Log Analysis

### Common Error Patterns

#### API Server Errors
```bash
# Find API errors in logs
grep -i "error\|exception" errors.log | tail -20

# Common patterns and solutions:
# "Connection refused" → Service not running
# "Permission denied" → File permissions issue  
# "No such file" → Missing model files or images
# "CUDA error" → GPU memory or driver issue
```

#### Worker Process Errors
```bash
# Monitor worker logs
rq worker photos --logging_level DEBUG 2>&1 | tee worker.log

# Analyze worker failures
grep -A 5 -B 5 "Failed\|Error" worker.log

# Common worker issues:
# Model loading failures → Check GPU/memory
# Database timeouts → Check SQLite locks
# Network errors → Check Qdrant/Redis connectivity
```

### Debug Mode Activation
```bash
# Enable debug logging for all components
export PYTHONPATH=/path/to/backend:$PYTHONPATH
export LOG_LEVEL=DEBUG

# Start API with debug logging
uvicorn src.api.main:app --reload --log-level debug

# Start worker with verbose output  
rq worker photos --logging_level DEBUG

# Enable SQLite query logging
sqlite3 pixquery.db ".trace stdout"
```

## Recovery Procedures

### Complete System Reset
If system is in unrecoverable state:

```bash
#!/bin/bash
# reset_system.sh

echo "Stopping all services..."
docker-compose down
pkill -f uvicorn
pkill -f "rq worker"

echo "Backing up data..."
cp pixquery.db pixquery.db.backup.$(date +%Y%m%d)
tar -czf qdrant_backup.$(date +%Y%m%d).tar.gz qdrant_data/

echo "Cleaning up..."
rm -f pixquery.db-wal pixquery.db-shm
rm -rf ~/.cache/clip/ ~/.cache/huggingface/
rm -f yolov8n.pt

echo "Restarting services..."
docker-compose up -d

echo "Waiting for services..."
sleep 10

echo "Testing system..."
curl -f http://localhost:8000/docs && echo "API: OK" || echo "API: FAILED"
redis-cli ping && echo "Redis: OK" || echo "Redis: FAILED"
curl -f http://localhost:6333/collections && echo "Qdrant: OK" || echo "Qdrant: FAILED"

echo "System reset complete. Re-run setup if needed."
```

### Data Recovery
```bash
# Recover from database corruption
sqlite3 pixquery.db.backup ".backup recovery.db"
mv recovery.db pixquery.db

# Rebuild embeddings from scratch
sqlite3 pixquery.db "UPDATE images SET processed = 0;"
curl -X POST http://localhost:8000/process

# Restore Qdrant from backup
docker-compose down
rm -rf qdrant_data/
tar -xzf qdrant_backup.20241201.tar.gz
docker-compose up -d qdrant
```

## Prevention Strategies

### Monitoring Setup
```bash
# Add health check endpoints to monitor
curl -f http://localhost:8000/health || alert_admin
curl -f http://localhost:6333/collections || alert_admin

# Monitor disk space
df -h / | awk 'NR==2 {if ($5+0 > 80) print "Disk usage high: " $5}'

# Monitor queue length
rq info --url redis://localhost:6379 | grep "queued"
```

### Regular Maintenance
```bash
# Weekly maintenance script
#!/bin/bash
# maintenance.sh

# Vacuum database
sqlite3 pixquery.db "VACUUM;"

# Clear old logs
find . -name "*.log" -mtime +7 -delete

# Restart services
docker-compose restart

# Health check
bash health_check.sh
```

### Backup Automation
```bash
# Daily backup script  
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d)
cp pixquery.db "backups/pixquery.db.$DATE"
tar -czf "backups/qdrant_data.$DATE.tar.gz" qdrant_data/

# Keep only 7 days of backups
find backups/ -mtime +7 -delete
```