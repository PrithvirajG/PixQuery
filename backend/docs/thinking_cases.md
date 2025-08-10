# Problem-Solving and Decision-Making Guide

## Thinking Framework for PixQuery

This guide provides structured approaches to common problems encountered when working with PixQuery's AI-powered image processing pipeline.

## Feature Development Decision Process

### Case Study: Adding New AI Model Integration

#### Problem Statement
"We want to add support for optical character recognition (OCR) to extract text from images containing documents or signs."

#### Decision Framework

**1. Requirements Analysis**
```python
# Questions to ask:
requirements = {
    "functional": [
        "What text accuracy is required?",
        "Should we detect multiple languages?", 
        "How to handle handwritten vs printed text?",
        "Integration with existing search functionality?"
    ],
    "non_functional": [
        "Performance impact on processing pipeline?",
        "Additional GPU memory requirements?",
        "Storage needs for OCR text data?",
        "Backwards compatibility with existing data?"
    ]
}
```

**2. Technical Evaluation**
```python
# Model comparison matrix
ocr_models = {
    "tesseract": {
        "pros": ["No GPU needed", "Mature", "Multi-language"],
        "cons": ["Slower", "Less accurate on natural scenes"],
        "memory": "50MB",
        "processing_time": "~2s per image"
    },
    "easyocr": {
        "pros": ["GPU accelerated", "Good accuracy", "Pre-trained"],
        "cons": ["Large model size", "GPU memory requirement"],
        "memory": "500MB GPU",
        "processing_time": "~0.5s per image"
    },
    "paddle_ocr": {
        "pros": ["Excellent accuracy", "Multiple scripts"],
        "cons": ["Complex setup", "Large memory footprint"],
        "memory": "1GB GPU", 
        "processing_time": "~0.8s per image"
    }
}
```

**3. Architecture Impact Assessment**
```python
# Implementation patterns to consider
class OCRModelInterface(ModelInterface):
    @abstractmethod
    def extract_text(self, image: Image.Image) -> Dict[str, Any]:
        """Extract text with bounding boxes and confidence scores."""
        pass

# Database schema changes needed
ocr_schema_changes = """
ALTER TABLE images ADD COLUMN ocr_text TEXT;
ALTER TABLE images ADD COLUMN ocr_data JSONB;  -- Bounding boxes, confidence
CREATE INDEX idx_images_ocr_text ON images USING gin(to_tsvector('english', ocr_text));
"""
```

**4. Testing Strategy**
```python
def test_ocr_integration():
    """Test plan for OCR feature."""
    test_cases = [
        "document_scan.jpg",        # Clean document text
        "street_sign.jpg",          # Natural scene text  
        "handwritten_note.jpg",     # Handwritten content
        "multi_language.jpg",       # Mixed languages
        "low_quality.jpg",          # Poor image quality
        "no_text.jpg"              # Images without text
    ]
    
    for test_image in test_cases:
        result = ocr_model.extract_text(Image.open(test_image))
        validate_ocr_result(result, expected_text[test_image])
```

#### Decision Outcome
Based on this analysis, choose EasyOCR for balanced performance/accuracy, implement as optional processing step, and add search integration.

### Case Study: Performance Optimization Decision

#### Problem Statement
"Image processing is taking too long (>30 seconds per image). Users are frustrated with wait times."

#### Diagnostic Process

**1. Performance Profiling**
```python
import time
import psutil
import GPUtil

def profile_processing_pipeline(image_path: str):
    """Profile each step of image processing."""
    
    profiling_results = {}
    
    # Memory before processing
    initial_memory = psutil.virtual_memory().used
    
    start_time = time.time()
    
    # YOLO detection profiling
    yolo_start = time.time()
    detections = yolo_model.detect(image)
    yolo_time = time.time() - yolo_start
    profiling_results['yolo'] = {
        'time': yolo_time,
        'memory_delta': psutil.virtual_memory().used - initial_memory
    }
    
    # CLIP embedding profiling  
    clip_start = time.time()
    embedding = clip_model.embed(image)
    clip_time = time.time() - clip_start
    profiling_results['clip'] = {
        'time': clip_time,
        'gpu_memory': GPUtil.getGPUs()[0].memoryUsed if GPUtil.getGPUs() else 0
    }
    
    # BLIP description profiling
    blip_start = time.time() 
    description = blip_model.describe(image)
    blip_time = time.time() - blip_start
    profiling_results['blip'] = {
        'time': blip_time
    }
    
    # Database operations profiling
    db_start = time.time()
    database_manager.update_image_metadata(image_id, detections, description)
    db_time = time.time() - db_start
    profiling_results['database'] = {
        'time': db_time
    }
    
    total_time = time.time() - start_time
    profiling_results['total'] = total_time
    
    return profiling_results
```

**2. Bottleneck Analysis**
```python
# Example profiling results analysis
profiling_data = {
    'yolo': {'time': 15.2, 'memory_delta': 2048},    # Bottleneck identified!
    'clip': {'time': 0.3, 'gpu_memory': 4096},
    'blip': {'time': 2.1},
    'database': {'time': 0.1},
    'total': 17.7
}

def analyze_bottlenecks(profiling_data):
    """Identify performance bottlenecks and recommend solutions."""
    
    bottlenecks = []
    
    for component, metrics in profiling_data.items():
        if component == 'total':
            continue
            
        time_taken = metrics.get('time', 0)
        
        if time_taken > 5.0:  # >5 seconds is concerning
            bottlenecks.append({
                'component': component,
                'issue': f'Slow processing: {time_taken:.1f}s',
                'solutions': get_optimization_strategies(component, metrics)
            })
    
    return bottlenecks

def get_optimization_strategies(component: str, metrics: dict):
    """Get component-specific optimization strategies."""
    
    strategies = {
        'yolo': [
            "Use smaller model variant (yolov8n vs yolov8l)",
            "Enable GPU acceleration", 
            "Reduce input image resolution",
            "Use model quantization (FP16)",
            "Batch multiple images together"
        ],
        'clip': [
            "Use ViT-B/32 instead of ViT-L/14",
            "Enable mixed precision",
            "Pre-load model weights",
            "Use ONNX runtime for inference"
        ],
        'blip': [
            "Use BLIP-base instead of BLIP-large",
            "Cache model in GPU memory",
            "Reduce max generation length",
            "Use beam search optimization"
        ]
    }
    
    return strategies.get(component, ["No specific optimizations available"])
```

**3. Solution Implementation Priority**
```python
optimization_priorities = [
    {
        'priority': 1,
        'solution': 'Switch to yolov8n model',
        'expected_improvement': '10-15s reduction',
        'implementation_effort': 'Low',
        'risk': 'Slight accuracy decrease'
    },
    {
        'priority': 2, 
        'solution': 'Enable GPU acceleration for all models',
        'expected_improvement': '5-8s reduction',
        'implementation_effort': 'Medium',
        'risk': 'GPU memory constraints'
    },
    {
        'priority': 3,
        'solution': 'Implement model caching',
        'expected_improvement': '2-3s reduction for subsequent images',
        'implementation_effort': 'Medium', 
        'risk': 'Memory usage increase'
    }
]
```

## Edge Case Handling Strategies

### Corrupted or Invalid Images

#### Detection and Handling Pattern
```python
def robust_image_processing(image_path: str) -> Dict[str, Any]:
    """Process image with comprehensive error handling."""
    
    processing_result = {
        'success': False,
        'errors': [],
        'partial_results': {}
    }
    
    try:
        # Step 1: Validate image file
        if not validate_image_file(image_path):
            processing_result['errors'].append('Invalid image file format')
            return processing_result
            
        # Step 2: Load and validate image
        try:
            image = Image.open(image_path)
            
            # Check for common corruption patterns
            if image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Image has zero dimensions")
                
            if image.mode not in ['RGB', 'RGBA', 'L']:
                image = image.convert('RGB')
                
        except (IOError, OSError) as e:
            processing_result['errors'].append(f'Image loading failed: {e}')
            return processing_result
            
        # Step 3: Process with each model individually
        models_to_try = [
            ('yolo', lambda: yolo_model.detect(image)),
            ('clip', lambda: clip_model.embed(image)), 
            ('blip', lambda: blip_model.describe(image))
        ]
        
        for model_name, model_func in models_to_try:
            try:
                result = model_func()
                processing_result['partial_results'][model_name] = result
            except Exception as e:
                processing_result['errors'].append(f'{model_name} failed: {e}')
                
        # Step 4: Determine overall success
        if len(processing_result['partial_results']) > 0:
            processing_result['success'] = True
            
    except Exception as e:
        processing_result['errors'].append(f'Unexpected error: {e}')
        
    return processing_result

def validate_image_file(image_path: str) -> bool:
    """Comprehensive image file validation."""
    
    # Check file existence
    if not os.path.exists(image_path):
        return False
        
    # Check file size (not empty, not too large)
    file_size = os.path.getsize(image_path)
    if file_size == 0 or file_size > 100 * 1024 * 1024:  # 100MB limit
        return False
        
    # Check file extension
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    if Path(image_path).suffix.lower() not in valid_extensions:
        return False
        
    # Check image header magic numbers
    with open(image_path, 'rb') as f:
        header = f.read(16)
        
    # JPEG magic number
    if header.startswith(b'\xff\xd8\xff'):
        return True
    # PNG magic number  
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    # Add other format checks as needed
        
    return False
```

### Memory Management for Large Image Collections

#### Batch Processing Strategy
```python
class BatchImageProcessor:
    """Process images in memory-efficient batches."""
    
    def __init__(self, batch_size: int = 5, max_memory_gb: float = 8.0):
        self.batch_size = batch_size
        self.max_memory_bytes = max_memory_gb * 1024 * 1024 * 1024
        self.current_memory_usage = 0
        
    def process_image_collection(self, image_paths: List[str]) -> Dict[str, Any]:
        """Process large image collection with memory management."""
        
        results = {
            'processed': 0,
            'failed': 0,
            'errors': []
        }
        
        for batch_start in range(0, len(image_paths), self.batch_size):
            batch = image_paths[batch_start:batch_start + self.batch_size]
            
            # Memory check before batch
            if self._check_memory_usage():
                self._cleanup_memory()
                
            batch_results = self._process_batch(batch)
            
            results['processed'] += batch_results['processed']
            results['failed'] += batch_results['failed'] 
            results['errors'].extend(batch_results['errors'])
            
            # Cleanup after batch
            self._cleanup_memory()
            
        return results
        
    def _check_memory_usage(self) -> bool:
        """Check if memory usage is approaching limits."""
        current_memory = psutil.virtual_memory().used
        return current_memory > self.max_memory_bytes * 0.8  # 80% threshold
        
    def _cleanup_memory(self):
        """Force garbage collection and GPU memory cleanup."""
        import gc
        gc.collect()
        
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
```

### Database Consistency Issues

#### Transaction Management Pattern
```python
class TransactionalImageProcessor:
    """Ensure database consistency during image processing."""
    
    def __init__(self, database_manager: IDatabaseManager):
        self.database_manager = database_manager
        
    def process_with_transaction(self, image_path: str) -> bool:
        """Process image with full transaction rollback on failure."""
        
        transaction_id = self._begin_transaction()
        
        try:
            # Step 1: Mark as processing
            image_record = self.database_manager.get_image_by_path(image_path)
            if not image_record:
                raise ValueError(f"Image record not found: {image_path}")
                
            self._update_processing_status(image_record['id'], 'processing')
            
            # Step 2: Process image
            processing_results = self._run_ai_models(image_path)
            
            # Step 3: Store results
            self._store_processing_results(image_record['id'], processing_results)
            
            # Step 4: Mark as complete
            self._update_processing_status(image_record['id'], 'completed')
            
            # Step 5: Commit transaction
            self._commit_transaction(transaction_id)
            return True
            
        except Exception as e:
            # Rollback all changes
            self._rollback_transaction(transaction_id)
            self._update_processing_status(image_record['id'], 'failed', str(e))
            return False
            
    def _begin_transaction(self) -> str:
        """Begin database transaction and return transaction ID."""
        # Implementation depends on database system
        pass
        
    def _commit_transaction(self, transaction_id: str):
        """Commit database transaction."""
        pass
        
    def _rollback_transaction(self, transaction_id: str):
        """Rollback database transaction.""" 
        pass
```

## Debugging Methodology

### Systematic Debugging Approach

#### 1. Problem Categorization
```python
def categorize_problem(error_description: str, logs: List[str]) -> str:
    """Categorize problem to apply appropriate debugging strategy."""
    
    categories = {
        'model_loading': ['model', 'load', 'cuda', 'memory', 'weight'],
        'database': ['database', 'sqlite', 'connection', 'lock', 'query'],
        'network': ['connection', 'timeout', 'redis', 'qdrant', 'refused'],
        'file_system': ['file', 'path', 'permission', 'not found', 'directory'],
        'processing': ['processing', 'image', 'embedding', 'detection', 'description']
    }
    
    error_text = error_description.lower()
    log_text = ' '.join(logs).lower()
    combined_text = error_text + ' ' + log_text
    
    scores = {}
    for category, keywords in categories.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        scores[category] = score
        
    return max(scores.items(), key=lambda x: x[1])[0]
```

#### 2. Debugging Decision Tree
```python
def debug_processing_failure(image_path: str, error_msg: str):
    """Systematic debugging approach for processing failures."""
    
    debug_steps = []
    
    # Step 1: Basic validation
    if not os.path.exists(image_path):
        debug_steps.append("CRITICAL: Image file does not exist")
        return debug_steps
        
    # Step 2: Image loading test
    try:
        image = Image.open(image_path)
        debug_steps.append(f"✓ Image loads successfully: {image.size}, {image.mode}")
    except Exception as e:
        debug_steps.append(f"✗ Image loading failed: {e}")
        debug_steps.append("SOLUTION: Check image file corruption or format")
        return debug_steps
        
    # Step 3: Model availability test
    for model_name in ['yolo', 'clip', 'blip']:
        try:
            model = get_model(model_name)
            debug_steps.append(f"✓ {model_name} model loaded")
        except Exception as e:
            debug_steps.append(f"✗ {model_name} model failed: {e}")
            debug_steps.append(f"SOLUTION: Check {model_name} model installation and GPU availability")
            
    # Step 4: Individual model testing
    test_results = test_individual_models(image)
    debug_steps.extend(test_results)
    
    # Step 5: Database connectivity test
    try:
        db_test = database_manager.get_image_by_path(image_path)
        debug_steps.append("✓ Database connection working")
    except Exception as e:
        debug_steps.append(f"✗ Database error: {e}")
        debug_steps.append("SOLUTION: Check database locks and connections")
        
    return debug_steps

def test_individual_models(image: Image.Image) -> List[str]:
    """Test each AI model individually to isolate issues."""
    
    results = []
    
    models = [
        ('YOLO', lambda: yolo_model.detect(image)),
        ('CLIP', lambda: clip_model.embed(image)),
        ('BLIP', lambda: blip_model.describe(image))
    ]
    
    for model_name, model_func in models:
        try:
            start_time = time.time()
            result = model_func()
            duration = time.time() - start_time
            
            if result is not None:
                results.append(f"✓ {model_name}: Success ({duration:.2f}s)")
            else:
                results.append(f"✗ {model_name}: Returned None")
                
        except Exception as e:
            results.append(f"✗ {model_name}: Exception - {e}")
            
    return results
```

### Root Cause Analysis Framework

#### Historical Error Pattern Analysis
```python
def analyze_error_patterns(log_files: List[str]) -> Dict[str, Any]:
    """Analyze historical errors to identify recurring patterns."""
    
    error_patterns = {}
    
    for log_file in log_files:
        with open(log_file, 'r') as f:
            for line in f:
                if 'ERROR' in line or 'EXCEPTION' in line:
                    # Extract error signature
                    error_signature = extract_error_signature(line)
                    
                    if error_signature not in error_patterns:
                        error_patterns[error_signature] = {
                            'count': 0,
                            'first_seen': None,
                            'last_seen': None,
                            'affected_files': set()
                        }
                    
                    error_patterns[error_signature]['count'] += 1
                    # Update timing and affected files
                    
    # Sort by frequency and recency
    sorted_patterns = sorted(
        error_patterns.items(),
        key=lambda x: (x[1]['count'], x[1]['last_seen']),
        reverse=True
    )
    
    return {
        'most_frequent_errors': sorted_patterns[:10],
        'recent_errors': [p for p in sorted_patterns if is_recent(p[1]['last_seen'])],
        'recurring_issues': [p for p in sorted_patterns if p[1]['count'] > 10]
    }
```

This systematic approach to problem-solving ensures consistent, thorough analysis of issues while building institutional knowledge about common failure patterns and their solutions.