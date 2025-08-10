# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PixQuery is an AI-powered local photo organizer backend that automatically processes images using computer vision models, generates embeddings for semantic search, and enables natural language queries. The system runs entirely locally for privacy, using YOLO for object detection, CLIP for embeddings, and BLIP for detailed scene descriptions.

## Documentation Structure

This backend contains comprehensive documentation in the `docs/` folder. Use this decision tree to know which documentation to consult:

### Quick Reference Guide

**For Setup & Installation Tasks:**
- First time setup → `docs/setup.md`
- Environment configuration → `docs/setup.md` + `docs/running.md`
- Dependencies issues → `docs/setup.md` + `docs/troubleshooting.md`

**For Development Tasks:**
- Code style questions → `docs/guidelines.md`
- Architecture understanding → `docs/overview.md`
- Testing approach → `docs/testing.md`
- Problem-solving patterns → `docs/thinking_cases.md`

**For Operations & Deployment:**
- Running the application → `docs/running.md`
- Performance issues → `docs/troubleshooting.md`
- Production deployment → `docs/running.md` + `docs/future.md`

**For Maintenance & Updates:**
- Documentation updates → `docs/update_docs.md`
- Future planning → `docs/future.md`
- Known limitations → `docs/future.md`

### Documentation Workflow for Claude Code

When working on PixQuery backend tasks, follow this workflow:

1. **Always start with** `docs/README.md` for navigation and current status
2. **For specific tasks, read in this order:**
   - Primary doc (see Quick Reference above)
   - `docs/overview.md` for context if needed
   - `docs/troubleshooting.md` for known issues
3. **When making changes:**
   - Check `docs/guidelines.md` for code standards
   - Reference `docs/thinking_cases.md` for decision patterns
   - Update relevant docs using `docs/update_docs.md` guidance

### Key Documentation Files

- **`docs/README.md`** - Master navigation and documentation status
- **`docs/overview.md`** - Architecture, tech stack, system design
- **`docs/setup.md`** - Installation, environment setup, dependencies
- **`docs/running.md`** - Operations, deployment, service management
- **`docs/testing.md`** - Test strategies, coverage, execution
- **`docs/guidelines.md`** - Code style, best practices, patterns
- **`docs/troubleshooting.md`** - Common issues, debug procedures
- **`docs/future.md`** - Limitations, roadmap, technical debt
- **`docs/thinking_cases.md`** - Problem-solving frameworks, decision trees
- **`docs/update_docs.md`** - Documentation maintenance procedures

## Architecture

The backend is a Python FastAPI application with the following layers:

- **API Layer**: FastAPI server (`src/api/main.py`) with REST endpoints
- **Processing Layer**: Asynchronous image processing using Redis Queue (RQ) or RabbitMQ
- **Model Layer**: AI model abstraction with YOLO, CLIP, and BLIP implementations
- **Data Layer**: SQLite for metadata, Qdrant for vector embeddings
- **Monitoring**: File system monitoring for automatic image ingestion

## Key Components

### Core Structure
- `src/api/main.py` - FastAPI application with CORS-enabled endpoints
- `src/ingestion/monitor.py` - File system watcher using watchdog library
- `src/processing/` - AI model implementations and worker processes
- `src/repositories/` - Database abstraction layer with SQLite implementation
- `src/storage/` - Vector database handlers for Qdrant/Milvus
- `src/query/search.py` - Search functionality combining metadata and embeddings

### Model Implementations
- `src/processing/models/interface.py` - Abstract base class defining model interface
- `src/processing/models/yolo.py` - YOLO object detection implementation
- `src/processing/models/clip.py` - CLIP embedding model implementation
- `src/processing/models/blip.py` - BLIP scene description model

## Development Commands

### Basic Setup
```bash
# Install dependencies
pip install -r requirements.txt

# For worker-specific dependencies
pip install -r requirements.worker.txt

# For monitor-specific dependencies
pip install -r requirements.monitor.txt
```

### Running the Application
```bash
# Start FastAPI server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Run image processing worker (Redis/RQ)
rq worker photos

# Run image processing worker (RabbitMQ)
python src/processing/worker.py

# Start file system monitor
python src/ingestion/monitor.py
```

### Testing
```bash
# Run tests
python -m pytest tests/

# Run specific test
python -m unittest tests.test_processing

# Run with verbose output
python -m pytest tests/ -v
```

### Docker Services
```bash
# Start required services (from parent directory)
cd .. && docker-compose up -d

# View service logs
docker-compose logs -f [redis|rabbitmq|qdrant]
```

## Database Schema

### SQLite Schema (images table)
```sql
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE,
    detections TEXT,          -- JSON: YOLO detection results
    description TEXT,         -- BLIP-generated scene description
    processed BOOLEAN DEFAULT 0,
    corrected_detections TEXT -- JSON: user-corrected detections
);
```

### Vector Database Collections
- `image_embeddings` - CLIP image embeddings (512-dimensional)
- `text_embeddings` - Text embeddings for descriptions
- `clip_embeddings` - Combined image-text embeddings

## API Endpoints

- `POST /process` - Trigger processing of unprocessed images
- `GET /search?query={text}&top_k={int}` - Search images by CLIP embeddings
- `GET /search_descriptions?query={text}&top_k={int}` - Search by text descriptions
- `GET /images/{id}` - Get image metadata by ID
- `POST /correct/{id}` - Update image metadata with corrections
- `GET /images_source/{filename}` - Serve images from ~/pixquery_photos

## Model Abstraction

The system uses a `ModelInterface` abstract base class in `src/processing/models/interface.py`:
```python
class ModelInterface(ABC):
    @abstractmethod
    def detect(self, image: Image.Image) -> list: pass
    
    @abstractmethod
    def embed(self, image: Image.Image) -> np.ndarray: pass
    
    @abstractmethod
    def describe(self, image: Image.Image) -> str: pass
```

Implementations are in their respective model files:
- `yolo.py` - Object detection using YOLOv8
- `clip.py` - Image embeddings using CLIP ViT-B/32
- `blip.py` - Scene descriptions (implementation needed)

## Configuration

### Environment Variables
- `MONITOR_PATH` - Directory to watch for new images (default: ~/pixquery_photos)
- `DB_PATH` - SQLite database path (default: pixquery.db)

### Required Services
- Redis (port 6379) or RabbitMQ (port 5672) for task queuing
- Qdrant (port 6333) for vector storage
- File system access to ~/pixquery_photos directory

## Processing Pipeline

1. **Ingestion**: `monitor.py` watches ~/pixquery_photos for new images
2. **Queuing**: New images added to Redis/RabbitMQ queue via publisher
3. **Processing**: Worker processes images with YOLO, CLIP, and BLIP models
4. **Storage**: Metadata stored in SQLite, embeddings in Qdrant via storage handlers
5. **Search**: API endpoints use `ImageSearchManager` for text and image queries

## Repository Pattern

The codebase uses repository pattern for database access:
- `src/repositories/i_database_manager.py` - Interface defining database operations
- `src/repositories/sqlite/sqlite_database_manager.py` - SQLite implementation
- Clean separation between business logic and data access

## Queue Management

Two queue implementations available:
- **Redis Queue (RQ)**: Simple, lightweight for single-machine setup
- **RabbitMQ**: More robust, supports advanced messaging patterns

Switch between them by using different worker implementations in `src/processing/`.

## Testing

- Tests in `tests/` directory
- Main test: `test_processing.py` - Tests the full image processing pipeline
- Uses separate `test.db` for isolation
- Mock dependencies (Redis, Qdrant) as needed

## Hardware Requirements

- Minimum: 8GB RAM for CPU processing
- Recommended: NVIDIA GPU (4GB+ VRAM) for faster model inference
- Storage: ~1GB per 1,000 processed images

## Code Style

**For comprehensive development guidelines, coding standards, and best practices, see `docs/guidelines.md`.**

### Essential Code Style
- Use 4-space indentation for Python
- Follow PEP 8 guidelines
- Include comprehensive logging with appropriate log levels
- Use type hints where possible
- Implement proper exception handling

## Git Integration

### Branch Structure
- `main` - Main development branch
- Feature branches: Create from main for new features
- Remote origin: `git@github.com:PrithvirajG/PixQuery.git`

### Development Workflow
```bash
# Check status before making changes
git status

# Stage changes (avoid staging generated files)
git add src/ tests/ requirements*.txt CLAUDE.md

# Commit with descriptive message
git commit -m "Add feature: descriptive message

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to remote
git push origin main
```

### Files to Avoid Committing
- `__pycache__/` directories and `.pyc` files
- `*.db` files (SQLite databases)
- `*.log` files
- Model files (`*.pt`, `*.pth`, `*.bin`)
- `processed_media_dump/` output files
- Virtual environments (`.venv/`, `venv/`)

### Git Commands for Development
```bash
# View recent commits and commit style
git log --oneline -10

# Check differences before committing
git diff
git diff --staged

# Restore accidentally modified files
git restore <file>
git restore --staged <file>

# View commit history
git log --graph --oneline --all
```

## Troubleshooting

**For comprehensive troubleshooting guidance, see `docs/troubleshooting.md`.**

### Common Issues
- **Models not loading**: Check GPU memory availability, models fallback to CPU
- **Queue not processing**: Verify Redis/RabbitMQ connection and service status
- **Search not working**: Check Qdrant service status and collection existence
- **Database errors**: Ensure SQLite database is initialized and accessible

### Debug Commands
```bash
# Check queue status (Redis)
rq worker photos --logging_level DEBUG

# Test image processing directly
python src/processing/processor.py

# Test search functionality
python src/query/search.py "your search query"

# Check API health
curl http://localhost:8000/search?query=test
```

**For detailed troubleshooting procedures, root cause analysis, and step-by-step debugging workflows, consult `docs/troubleshooting.md`.**