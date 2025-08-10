# Development Guidelines

## Code Style Standards

### Python Code Style

#### PEP 8 Compliance
- **Indentation**: 4 spaces (no tabs)
- **Line length**: 88 characters (Black formatter standard)
- **Import organization**: Standard library, third-party, local imports
- **Naming conventions**:
  - Variables and functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private methods: `_leading_underscore`

#### Example Code Style
```python
# Good: Clear imports, proper spacing, descriptive names
import os
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from PIL import Image

from src.repositories.i_database_manager import IDatabaseManager
from src.processing.models.interface import ModelInterface


class ImageProcessor:
    """Processes images using AI models for object detection and embedding generation."""
    
    def __init__(self, database_manager: IDatabaseManager):
        self.database_manager = database_manager
        self._model_cache: Dict[str, ModelInterface] = {}
    
    def process_image_batch(self, image_paths: List[str]) -> Dict[str, bool]:
        """Process multiple images and return success status for each."""
        results = {}
        
        for image_path in image_paths:
            try:
                success = self._process_single_image(image_path)
                results[image_path] = success
            except Exception as e:
                self.logger.error(f"Failed to process {image_path}: {e}")
                results[image_path] = False
                
        return results
```

#### Code Formatting Tools
```bash
# Install formatting tools
pip install black isort flake8

# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/ --max-line-length=88
```

### Documentation Strings

#### Function Documentation
```python
def search_images(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search for images using semantic similarity.
    
    Args:
        query: Natural language search query
        limit: Maximum number of results to return
        
    Returns:
        List of dictionaries containing image metadata and similarity scores
        
    Raises:
        ValueError: If query is empty or limit is invalid
        ConnectionError: If vector database is unavailable
    """
```

#### Class Documentation  
```python
class SQLDatabaseManager(IDatabaseManager):
    """SQLite implementation of the database manager interface.
    
    Handles all database operations for image metadata including CRUD operations,
    processing status tracking, and batch operations. Uses connection pooling
    and automatic retry logic for reliability.
    
    Attributes:
        db_manager: SQLiteHandler instance for database operations
        logger: Logger instance for operation tracking
    """
```

## Architecture Patterns

### Repository Pattern Implementation
All database operations must go through repository interfaces:

```python
# Good: Using repository pattern
class ImageService:
    def __init__(self, db_manager: IDatabaseManager):
        self.db_manager = db_manager
    
    def get_unprocessed_images(self) -> List[str]:
        return self.db_manager.get_unprocessed_images()

# Bad: Direct database access
def get_unprocessed_images():
    conn = sqlite3.connect('pixquery.db')
    cursor = conn.cursor()
    # ... direct SQL
```

### Dependency Injection
Inject dependencies rather than using global variables:

```python
# Good: Dependency injection
def process_image(image_path: str, database_manager: IDatabaseManager, 
                  qdrant_client: QdrantClient):
    # Process with injected dependencies

# Bad: Global dependencies  
def process_image(image_path: str):
    global database_manager, qdrant_client
    # Use globals
```

### Error Handling Patterns
```python
# Good: Specific exception handling with logging
try:
    embedding = clip_model.embed(image)
    if embedding is None:
        raise ValueError("CLIP model returned None embedding")
except Exception as e:
    self.logger.error(f"Embedding generation failed for {image_path}: {e}")
    raise ProcessingError(f"Could not generate embedding: {e}") from e

# Bad: Generic exception handling
try:
    embedding = clip_model.embed(image)
except:
    pass  # Silent failure
```

## Testing Standards

### Test File Organization
- Place tests in `tests/` directory mirroring `src/` structure
- Use descriptive test method names: `test_process_image_updates_database_status`
- Group related tests in classes: `TestImageProcessing`, `TestSearchFunctionality`

### Test Data Management
```python
class TestImageProcessing:
    @classmethod
    def setUpClass(cls):
        """Set up shared test resources."""
        cls.test_db_path = 'test_processing.db'
        cls.test_image_path = 'tests/sample_image.jpg'
        cls.db_manager = cls._create_test_db_manager()
    
    def setUp(self):
        """Set up fresh test state for each test."""
        self.db_manager.clear_all_images()
        
    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
```

### Mocking External Dependencies
```python
@patch('src.processing.processor.init_qdrant')
@patch('src.processing.models.clip.ClipModel')
def test_process_image_with_mocked_dependencies(self, mock_clip, mock_qdrant):
    """Test image processing with mocked AI models."""
    # Configure mocks
    mock_clip.return_value.embed.return_value = np.random.rand(512)
    
    # Run test
    result = process_image('test.jpg', database_manager=self.db_manager)
    
    # Verify behavior
    self.assertTrue(result)
    mock_clip.return_value.embed.assert_called_once()
```

## Git Workflow

### Branch Naming Conventions
- **Feature branches**: `feature/add-blip-model-integration`
- **Bug fixes**: `fix/database-connection-timeout`  
- **Documentation**: `docs/update-api-reference`
- **Refactoring**: `refactor/extract-search-service`

### Commit Message Structure

Use this comprehensive format for all commits to ensure clear communication and proper attribution:

```
<type>: <what was done> - <specific impact>

<detailed explanation of what was changed>
<rationale for the change and business/technical impact>
<testing status and coverage>

Impact: <Low|Medium|High> - <brief impact description>
Testing: <dev tested status and key test cases>

<any additional context or considerations>

Co-authored-by: <Human Developer Name> <email@domain.com>

aided by Claude
```

#### Commit Type Prefixes
- **feat**: New features or significant enhancements
- **fix**: Bug fixes and error corrections
- **refactor**: Code restructuring without functional changes
- **docs**: Documentation updates
- **test**: Test additions or modifications
- **perf**: Performance improvements
- **style**: Code formatting and style changes
- **chore**: Maintenance tasks, dependency updates

#### Example Comprehensive Commit

```
feat: add comprehensive model interface architecture - enables unified AI model management

Implemented abstract ModelInterface base class with detect(), embed(), and describe() methods.
Created concrete implementations for YOLO (object detection), CLIP (embeddings), and BLIP (descriptions).
Added model manager with lazy loading and caching to optimize memory usage and startup performance.

This change standardizes how AI models are integrated, making it easier to swap models,
add new capabilities, and maintain consistent error handling across the processing pipeline.
Reduces memory footprint by 40% through intelligent model caching.

Impact: High - Establishes foundation for scalable AI model integration
Testing: Dev tested with sample images, verified model loading and inference performance

Added comprehensive unit tests for ModelInterface implementations.
Verified backward compatibility with existing processing pipeline.
Tested memory usage under load with 100+ concurrent image processing requests.

Co-authored-by: [Developer Name] <developer@email.com>

aided by Claude
```

#### Good Commit Message Examples
```bash
feat: add BLIP model integration for automated scene descriptions - improves search accuracy

Integrated BLIP-2 model to generate detailed natural language descriptions for images.
Enhances semantic search capability by providing rich textual context for each processed image.
Implements efficient batching to process multiple images while managing GPU memory usage.

Impact: Medium - Significantly improves search result relevance for complex queries
Testing: Dev tested with 50+ diverse images, verified description quality and processing speed

fix: resolve database connection timeout in worker processes - prevents job failures

Updated SQLite connection handling to use connection pooling with 30-second timeout.
Added automatic retry logic with exponential backoff for failed database operations.
Implemented proper connection cleanup to prevent resource leaks under high load.

Impact: High - Eliminates ~15% of processing failures due to database timeouts
Testing: Dev tested under simulated high load, verified connection stability over 2-hour runtime

refactor: extract search functionality into SearchService class - improves code maintainability

Moved all search-related logic from main API handlers into dedicated SearchService class.
Implemented dependency injection pattern for database and vector store dependencies.
Added comprehensive logging and error handling for search operations.

Impact: Low - No functional changes, improves code organization for future enhancements
Testing: Dev tested all search endpoints, verified identical behavior with existing functionality

docs: update model integration guide with GPU optimization tips - helps deployment

Added section on CUDA memory management and model quantization options.
Documented performance benchmarks for different hardware configurations.
Included troubleshooting guide for common GPU-related issues.

Impact: Low - Improves developer onboarding and reduces support burden
Testing: Verified all code examples compile and run correctly
```

#### Attribution Guidelines

**Always follow this attribution pattern:**

1. **Primary Author**: List the human developer as the main contributor
   ```
   Co-authored-by: [Human Developer Name] <email@domain.com>
   ```

2. **AI Assistance**: Only mention AI assistance at the very bottom
   ```
   aided by Claude
   ```

3. **Never mention AI in the main commit message** - keep the focus on the technical change and human decision-making

4. **Multiple contributors example:**
   ```
   Co-authored-by: Alice Developer <alice@company.com>
   Co-authored-by: Bob Reviewer <bob@company.com>
   
   aided by Claude
   ```

#### Testing Status Guidelines

Include specific testing information:

- **"Dev tested with [specific scenarios]"** - What you actually tested
- **"Verified [specific behaviors]"** - What you confirmed works
- **"Test cases: [list key scenarios]"** - Important test cases for others to verify

Examples:
- `Testing: Dev tested with 25 sample images, verified YOLO detection accuracy > 85%`
- `Testing: Dev tested API endpoints, verified response times under 200ms for text search`
- `Testing: Dev tested worker restart scenarios, confirmed queue processing resumes correctly`

#### Impact Assessment Levels

**High Impact**: 
- Breaking changes or major feature additions
- Performance improvements > 25%
- Security fixes
- Database schema changes

**Medium Impact**:
- New features that extend existing functionality
- Bug fixes affecting user experience
- Configuration changes
- Performance improvements 10-25%

**Low Impact**:
- Code refactoring without functional changes
- Documentation updates
- Minor bug fixes
- Style/formatting changes

#### Bad Commit Message Examples (Avoid These)
```bash
# Too vague
update code
fix bug
changes
improvements

# Missing context
add BLIP model
fix timeout
update docs

# No impact assessment
feat: new search feature

# Missing testing information
fix: database connection issue

# AI mentioned in main message (incorrect)
feat: add model interface with Claude's help
```

### Pull Request Process

#### PR Title Format
- `[Feature] Add semantic search with CLIP embeddings`
- `[Fix] Database connection timeout in processing worker`
- `[Docs] Update setup guide with GPU requirements`

#### PR Description Template
```markdown
## Summary
Brief description of changes and motivation

## Changes Made
- List of specific changes
- Focus on what, not how

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass  
- [ ] Manual testing completed

## Deployment Notes
Any special deployment considerations

## Related Issues
Fixes #123, addresses #456
```

### Code Review Checklist

#### For Reviewers
- [ ] **Functionality**: Code does what PR claims
- [ ] **Tests**: Adequate test coverage for new code
- [ ] **Style**: Follows project coding standards
- [ ] **Performance**: No obvious performance regressions
- [ ] **Security**: No exposed credentials or unsafe operations
- [ ] **Documentation**: Public APIs documented
- [ ] **Backwards compatibility**: No breaking changes without migration plan

#### For Authors
- [ ] **Self-review**: Read through own code changes
- [ ] **Tests run**: All tests pass locally
- [ ] **Linting**: Code passes style checks
- [ ] **Documentation**: Updated relevant docs
- [ ] **Dependencies**: New dependencies justified and documented

## Environment Management

### Development Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If separated

# Pre-commit hooks (recommended)
pip install pre-commit
pre-commit install
```

### Environment Variables
Store configuration in environment variables, not code:

```python
# Good: Environment-based configuration
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///pixquery.db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
MODEL_CACHE_DIR = os.getenv('MODEL_CACHE_DIR', '~/.cache/pixquery')

# Bad: Hardcoded configuration
DATABASE_URL = 'sqlite:///pixquery.db'
REDIS_URL = 'redis://localhost:6379'
```

### Configuration Management
```python
# src/config.py - Centralized configuration
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class Config:
    """Application configuration settings."""
    
    # Database settings
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///pixquery.db')
    
    # Redis settings  
    redis_url: str = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Model settings
    model_cache_dir: str = os.getenv('MODEL_CACHE_DIR', '~/.cache/pixquery')
    use_gpu: bool = os.getenv('USE_GPU', 'true').lower() == 'true'
    
    # API settings
    api_host: str = os.getenv('API_HOST', '0.0.0.0')
    api_port: int = int(os.getenv('API_PORT', '8000'))
```

## Logging and Monitoring

### Logging Standards
```python
import logging

# Configure logging at module level
logger = logging.getLogger(__name__)

class ImageProcessor:
    def process_image(self, image_path: str) -> bool:
        """Process single image with comprehensive logging."""
        
        # Info level for normal operations
        logger.info(f"Starting processing for image: {image_path}")
        
        try:
            # Debug level for detailed flow
            logger.debug(f"Loading image from {image_path}")
            image = Image.open(image_path)
            
            # Info level for milestones
            logger.info(f"Successfully loaded image, size: {image.size}")
            
            return True
            
        except FileNotFoundError:
            # Error level for failures with context
            logger.error(f"Image file not found: {image_path}")
            return False
            
        except Exception as e:
            # Exception level for unexpected errors
            logger.exception(f"Unexpected error processing {image_path}: {e}")
            return False
```

### Error Monitoring
```python
# Custom exception types for better error tracking
class ProcessingError(Exception):
    """Raised when image processing fails."""
    pass

class ModelLoadingError(ProcessingError):
    """Raised when AI models fail to load."""
    pass

class DatabaseError(Exception):
    """Raised for database operation failures."""
    pass
```

## Performance Guidelines

### Database Operations
```python
# Good: Batch operations
def update_multiple_images(self, updates: List[Tuple[int, str, str]]):
    """Update multiple images in single transaction."""
    query = "UPDATE images SET detections=?, description=? WHERE id=?"
    self.db_manager.execute_batch(query, updates)

# Bad: Individual operations in loop
for image_id, detections, description in updates:
    self.update_image_metadata(image_id, detections, description)
```

### Memory Management
```python
# Good: Process images in batches to control memory
def process_image_batch(self, image_paths: List[str], batch_size: int = 5):
    """Process images in small batches to manage memory usage."""
    for i in range(0, len(image_paths), batch_size):
        batch = image_paths[i:i + batch_size]
        for image_path in batch:
            self.process_single_image(image_path)
        
        # Optional: Force garbage collection after batch
        import gc
        gc.collect()
```

### Caching Strategies
```python
from functools import lru_cache
from typing import Dict, Any

class ModelManager:
    def __init__(self):
        self._model_cache: Dict[str, Any] = {}
    
    @lru_cache(maxsize=128)
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Cache model configurations to avoid repeated loading."""
        # Load and return model config
        pass
```

## Security Best Practices

### Input Validation
```python
from pathlib import Path

def validate_image_path(image_path: str) -> bool:
    """Validate image path for security and existence."""
    
    # Convert to Path object for safe handling
    path = Path(image_path)
    
    # Check if path exists and is a file
    if not path.exists() or not path.is_file():
        return False
    
    # Ensure path is within allowed directories
    allowed_dirs = [Path('~/pixquery_photos').expanduser()]
    if not any(path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
        return False
    
    # Check file extension
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    if path.suffix.lower() not in allowed_extensions:
        return False
    
    return True
```

### Credential Management
```python
# Good: Environment variables for credentials
import os

QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Bad: Hardcoded credentials
QDRANT_API_KEY = 'abc123xyz'
```

### SQL Injection Prevention
```python
# Good: Parameterized queries
def get_images_by_description(self, description_pattern: str):
    query = "SELECT * FROM images WHERE description LIKE ?"
    return self.db_manager.execute_query(query, (f"%{description_pattern}%",))

# Bad: String formatting
def get_images_by_description(self, description_pattern: str):
    query = f"SELECT * FROM images WHERE description LIKE '%{description_pattern}%'"
    return self.db_manager.execute_query(query)
```