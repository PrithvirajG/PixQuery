# Testing Guide

## Test Structure Overview

The testing strategy covers unit tests, integration tests, and end-to-end pipeline testing with a focus on AI model reliability and data consistency.

### Test Organization
```
tests/
├── __init__.py
├── test.jpg                    # Sample test image
├── test_processing.py          # Core processing pipeline tests
├── unit/                       # Unit tests (planned)
│   ├── test_models.py         # AI model tests
│   ├── test_database.py       # Database operation tests
│   └── test_api.py            # API endpoint tests
└── integration/               # Integration tests (planned)
    ├── test_search.py         # Search functionality
    └── test_pipeline.py       # End-to-end pipeline
```

## Running Tests

### Quick Test Commands
```bash
# Run all tests
cd backend
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_processing.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run single test method
python -m pytest tests/test_processing.py::TestProcessing::test_processing -v
```

### Test Environment Setup
```bash
# Install test dependencies (if separated)
pip install pytest pytest-cov pytest-asyncio

# Start required services for integration tests
docker-compose up -d redis rabbitmq qdrant

# Create test database (separate from production)
export DB_PATH=test.db
```

## Current Test Coverage

### test_processing.py
**File**: `tests/test_processing.py`  
**Purpose**: End-to-end processing pipeline validation

```python
class TestProcessing(unittest.TestCase):
    def test_processing(self):
        # Tests complete image processing workflow
        # 1. Database initialization with test.db
        # 2. Image insertion with processed=0
        # 3. Processing via process_image()
        # 4. Validation of results and processed=1 flag
```

**What It Tests**:
- SQLite database initialization and schema creation
- Image record insertion and retrieval
- AI model processing (YOLO, CLIP, BLIP integration)
- Database updates after processing
- Cleanup and teardown

**Test Data**:
- Uses `tests/test.jpg` as sample image
- Creates temporary `test.db` for isolation

### Running Individual Tests
```bash
# Run processing test with verbose output
python tests/test_processing.py

# Run with Python unittest discovery
python -m unittest tests.test_processing.TestProcessing.test_processing -v
```

## Test Data Management

### Sample Images
- **test.jpg**: Primary test image in `tests/` directory
- Recommended: Add diverse test images for different scenarios
  ```bash
  # Add more test images
  cp ~/sample_photos/portrait.jpg tests/
  cp ~/sample_photos/landscape.jpg tests/
  cp ~/sample_photos/document.jpg tests/
  ```

### Test Database
- **test.db**: Separate SQLite database created during tests
- Automatically cleaned up after each test run
- Schema identical to production `pixquery.db`

### Test Collections
For Qdrant integration tests:
```bash
# Create test collections
curl -X PUT "http://localhost:6333/collections/test_image_embeddings" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 512, "distance": "Cosine"}}'

curl -X PUT "http://localhost:6333/collections/test_text_embeddings" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 512, "distance": "Cosine"}}'
```

## Adding New Tests

### Unit Test Template
Create `tests/unit/test_models.py`:
```python
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
import numpy as np

from src.processing.models.yolo import YoloModel
from src.processing.models.clip import ClipModel
from src.processing.models.blip import BlipModel

class TestModels(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_image = Image.new('RGB', (224, 224), color='red')
        
    def test_yolo_detection(self):
        """Test YOLO object detection functionality."""
        yolo = YoloModel()
        detections = yolo.detect(self.test_image)
        
        self.assertIsInstance(detections, list)
        # Add specific assertions for detection format
        
    def test_clip_embedding(self):
        """Test CLIP image embedding generation."""
        clip = ClipModel()
        embedding = clip.embed(self.test_image)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(embedding.shape[-1], 512)  # CLIP embedding dimension
        
    def test_blip_description(self):
        """Test BLIP image description generation."""
        blip = BlipModel()
        description = blip.describe(self.test_image)
        
        self.assertIsInstance(description, str)
        self.assertGreater(len(description), 0)
```

### Integration Test Template  
Create `tests/integration/test_search.py`:
```python
import unittest
from src.repositories.sqlite.sqlite_database_manager import SQLDatabaseManager
from src.storage.sqlite_db import SQLiteHandler
from src.query.search import ImageSearchManager
from src.processing.processor import process_image

class TestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database and process test images."""
        cls.db_path = 'integration_test.db'
        cls.sqlite_db = SQLiteHandler(db_path=cls.db_path)
        cls.database_manager = SQLDatabaseManager(cls.sqlite_db)
        cls.search_manager = ImageSearchManager(cls.database_manager)
        
        # Add and process test images
        test_images = ['tests/test.jpg', 'tests/portrait.jpg']
        for img_path in test_images:
            cls.database_manager.add_image(img_path)
            process_image(img_path, cls.db_path)
    
    def test_text_search(self):
        """Test semantic text search functionality."""
        results = self.search_manager.search_images("red color", limit=5)
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Verify result structure
        
    def test_description_search(self):
        """Test description-based search."""
        results = self.search_manager.search_image_descriptions("portrait", limit=5)
        
        self.assertIsInstance(results, list)
        # Add specific assertions for description search
```

### API Test Template
Create `tests/unit/test_api.py`:
```python
import unittest
from fastapi.testclient import TestClient
from src.api.main import app

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
    
    def test_search_endpoint(self):
        """Test /search API endpoint."""
        response = self.client.get("/search?query=test&top_k=5")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        
    def test_process_endpoint(self):
        """Test /process API endpoint."""
        response = self.client.post("/process")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('count', data)
```

## Test Data Validation

### Expected Test Results
When running `test_processing.py`, verify:

1. **Database Operations**:
   ```sql
   SELECT COUNT(*) FROM images WHERE processed = 1;
   -- Should return 1 after processing
   ```

2. **AI Model Outputs**:
   - YOLO detections: List of bounding boxes and class labels
   - BLIP description: Non-empty string describing the image
   - CLIP embeddings: 512-dimensional normalized vector

3. **Qdrant Storage**:
   ```bash
   curl "http://localhost:6333/collections/image_embeddings/points/1"
   # Should return point data with embedding vector
   ```

### Test Assertions Checklist
- [ ] Database record created with correct path
- [ ] `processed` flag updated to `1` after processing
- [ ] `detections` field contains valid JSON
- [ ] `description` field contains non-empty string
- [ ] Embedding stored in Qdrant with correct dimensions
- [ ] No exceptions raised during processing
- [ ] Temporary files cleaned up

## Performance Testing

### Load Testing Setup
```python
def test_processing_performance():
    """Test processing speed for batch images."""
    import time
    
    start_time = time.time()
    for i in range(10):
        process_image(f'tests/test{i}.jpg')
    end_time = time.time()
    
    avg_time = (end_time - start_time) / 10
    print(f"Average processing time: {avg_time:.2f}s per image")
    
    # Assert reasonable performance thresholds
    assert avg_time < 30.0  # 30 seconds per image max
```

### Memory Usage Testing
```python
def test_memory_usage():
    """Monitor memory usage during processing."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Process multiple images
    for i in range(5):
        process_image('tests/test.jpg')
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    # Assert memory doesn't grow excessively
    assert memory_increase < 1024 * 1024 * 1024  # 1GB limit
```

## Continuous Integration

### GitHub Actions Workflow (Recommended)
Create `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis
        ports:
          - 6379:6379
      qdrant:
        image: qdrant/qdrant
        ports:
          - 6333:6333
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
        
    - name: Run tests
      run: |
        cd backend
        pytest tests/ --cov=src --cov-report=xml
        
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## Test Debugging

### Common Issues and Solutions

**Model Loading Failures**:
```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Force CPU mode for consistent testing
export CUDA_VISIBLE_DEVICES=""
pytest tests/
```

**Database Locking Issues**:
```bash
# Ensure test database cleanup
rm -f test.db test.db-wal test.db-shm

# Check for hanging connections
lsof test.db
```

**Service Connection Failures**:
```bash
# Verify services before testing
docker-compose ps
curl http://localhost:6333/collections
redis-cli ping
```

### Debug Test Execution
```bash
# Run tests with debug output
pytest tests/ -v -s --tb=short

# Run specific failing test
pytest tests/test_processing.py::TestProcessing::test_processing -vvv

# Drop into debugger on failure
pytest tests/ --pdb
```

## Coverage Requirements

### Target Coverage Levels
- **Overall**: 80%+ line coverage
- **Critical paths**: 95%+ (processing, search, database operations)
- **AI models**: 70%+ (harder to test deterministically)

### Coverage Commands
```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Generate terminal coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Check coverage thresholds
pytest tests/ --cov=src --cov-fail-under=80
```