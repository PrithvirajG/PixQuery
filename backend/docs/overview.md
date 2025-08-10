# PixQuery Backend Overview

## Purpose and Vision

PixQuery is an AI-powered local photo organizer that provides semantic search capabilities for personal image collections. The system runs entirely locally to ensure privacy while leveraging state-of-the-art computer vision models for automatic image analysis and natural language querying.

## Key Stakeholders

- **End Users**: Individuals wanting to organize and search their personal photo collections
- **Privacy-Conscious Users**: Those requiring local-only processing without cloud dependencies  
- **Developers**: Contributors extending AI model integrations or search capabilities
- **System Administrators**: Those deploying and maintaining the service

## Technical Stack

### Core Technologies
- **Backend Framework**: FastAPI (Python 3.8+)
- **Database**: SQLite for metadata, Qdrant for vector embeddings
- **Queue System**: Redis Queue (RQ) or RabbitMQ for async processing
- **AI Models**:
  - YOLO v8 for object detection
  - OpenAI CLIP for image embeddings and text-image matching
  - BLIP for scene description generation
- **File Monitoring**: Watchdog library for filesystem events

### Dependencies
- `torch==2.7.1` and `torchvision==0.22.1` - Deep learning framework
- `ultralytics==8.0.0` - YOLO implementation
- `transformers==4.52.4` - Hugging Face models (BLIP)
- `pillow==9.2.0` - Image processing
- `fastapi` and `uvicorn` - Web framework
- `redis==4.3.4` and `rq==1.11.0` - Queue management

## High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File System   │    │   FastAPI App   │    │  React Frontend │
│    Monitor      │────▶│   (main.py)     │◀───│   (Port 3000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ Redis/RabbitMQ  │    │   SQLite DB     │
│     Queue       │    │   (metadata)    │
└─────────────────┘    └─────────────────┘
         │                       
         ▼                       
┌─────────────────┐    ┌─────────────────┐
│  Worker Process │    │   Qdrant DB     │
│  (AI Models)    │────▶│  (embeddings)   │
└─────────────────┘    └─────────────────┘
```

## Core Components

### 1. API Layer (`src/api/`)
- **main.py**: FastAPI application with REST endpoints
- **sockets.py**: WebSocket support for real-time updates
- Handles image search, metadata retrieval, and processing triggers

### 2. Ingestion Layer (`src/ingestion/`)
- **monitor.py**: Filesystem watcher using `watchdog`
- Automatically detects new images in `~/pixquery_photos`
- Adds unprocessed images to database queue

### 3. Processing Layer (`src/processing/`)
- **processor.py**: Main image processing orchestrator
- **worker.py**: Redis/RabbitMQ worker for async processing
- **models/**: AI model abstractions (YOLO, CLIP, BLIP)
- Generates embeddings, descriptions, and object detections

### 4. Data Layer (`src/repositories/`)
- **Abstract interfaces**: `IDatabaseManager`, `IImageQueueManager`
- **SQLite implementation**: `sqlite_database_manager.py`
- Handles CRUD operations for image metadata

### 5. Storage Layer (`src/storage/`)
- **sqlite_db.py**: SQLite connection management
- **qdrant_db.py**: Vector database operations for embeddings
- **milvus_db.py**: Alternative vector database support

### 6. Query Layer (`src/query/`)
- **search.py**: Semantic search using CLIP embeddings
- Combines text queries with vector similarity search
- Returns ranked image results with metadata

## Key Design Patterns

### Repository Pattern
Database operations abstracted through `IDatabaseManager` interface, allowing easy swapping between SQLite, PostgreSQL, etc.

### Model Interface Pattern  
AI models implement `ModelInterface` abstract base class with standardized `detect()`, `embed()`, and `describe()` methods.

### Dependency Injection
Database managers and clients injected into processors and API handlers rather than global singletons.

### Event-Driven Processing
File system events trigger async processing pipeline through queue system.

## Data Flow

1. **Image Ingestion**: Watchdog monitors `~/pixquery_photos` directory
2. **Queueing**: New images added to SQLite with `processed=0` flag
3. **Processing Trigger**: API endpoint `/process` enqueues unprocessed images
4. **AI Processing**: Worker processes run YOLO, CLIP, and BLIP models
5. **Storage**: Metadata stored in SQLite, embeddings in Qdrant
6. **Search**: Frontend queries combine text search with vector similarity
7. **Results**: Ranked image results returned with metadata and paths

## Security Considerations

- **Local-Only Processing**: No external API calls or cloud dependencies
- **File System Access**: Limited to designated `~/pixquery_photos` directory
- **CORS Configuration**: Restricted to localhost:3000 for development
- **SQLite Security**: Direct file access, consider permissions for production

## Performance Characteristics

- **GPU Acceleration**: Automatic fallback from GPU to CPU for model inference
- **Async Processing**: Non-blocking image processing through worker queues
- **Vector Search**: Efficient similarity search using Qdrant indexes
- **Memory Management**: Models loaded once per worker process

## Scalability Limits

- **SQLite Limitations**: Single-writer database, not suitable for high concurrency
- **Local Storage**: Bounded by disk space for images and embeddings
- **Model Memory**: GPU VRAM requirements scale with batch size
- **Processing Speed**: CPU/GPU bound for AI model inference

## Integration Points

- **Frontend Communication**: REST API and optional WebSocket for real-time updates
- **External Services**: Docker containers for Redis, RabbitMQ, and Qdrant
- **File System**: Direct access to local photo directories
- **Model Files**: Downloads and caches YOLO, CLIP, and BLIP model weights