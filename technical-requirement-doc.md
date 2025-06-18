PixQuery - Technical Requirements and Architecture Document
1. Introduction
1.1 Purpose
This document outlines the technical requirements and architecture for PixQuery, a local, AI-powered personal photo organizer that automatically tags photos with objects, scenes, and people, and enables natural language search (e.g., “find photos of my dog at the beach”). Designed to run on a user’s home PC, PixQuery prioritizes privacy, flexibility, and extensibility for broader applications like CCTV monitoring or anomaly detection. It leverages state-of-the-art (SOTA) AI models, supports user-selected models via an abstraction layer, and includes human-in-the-loop feedback for correcting AI outputs.
1.2 Scope
PixQuery will:

Process images locally using SOTA models for object detection, embeddings, and detailed scene descriptions.
Store metadata in SQLite and embeddings in Milvus Lite.
Support natural language queries for image retrieval.
Allow users to correct AI-generated tags and descriptions.
Operate offline on a mid-range PC (e.g., 8GB RAM, optional NVIDIA GPU).
Be extensible for future use cases like video processing or anomaly detection.

1.3 Audience
This document is intended for developers and AI systems building PixQuery. It assumes familiarity with Python, databases, and AI model integration but provides detailed, step-by-step instructions (including "baby steps") for clarity. Alternatives are provided for potential failure points to ensure robustness.
1.4 Final Output
A fully functional Python application that:

Monitors a designated folder for new images.
Processes images with YOLO (object detection), CLIP (embeddings for search), and BLIP (detailed scene descriptions).
Stores metadata in SQLite and embeddings in Milvus Lite.
Enables natural language search (e.g., “find photos of my cat in the garden”) via a command-line interface (CLI) or basic GUI.
Supports user corrections for AI outputs.
Runs entirely on a local PC, ensuring data privacy.

2. System Overview
PixQuery is a modular, Python-based application designed for local execution. It processes images asynchronously, generates AI-driven tags and descriptions, and supports efficient search and feedback mechanisms.
2.1 Key Features

Image Ingestion: Automatically detects new images in a specified folder.
AI Processing:
Object detection: Identifies objects (e.g., “dog,” “car”).
Image embeddings: Enables natural language search.
Scene descriptions: Generates detailed text (e.g., “A dog playing on the beach at sunset”).


Storage: Uses SQLite for metadata and Milvus Lite for embeddings.
Search: Retrieves images based on natural language queries.
Feedback: Allows users to correct AI outputs and store corrections.
Model Flexibility: Supports user-selected AI models via an abstraction layer.

2.2 Use Cases

Personal photo organization (e.g., finding specific memories).
Potential extensions: CCTV monitoring (e.g., detecting unusual activity) or anomaly detection (e.g., identifying outliers in image datasets).

3. Architecture
3.1 High-Level Architecture
PixQuery is composed of the following modules:

Ingestion Layer: Monitors a folder and queues new images.
Queue Layer: Manages asynchronous processing tasks using Redis Queue (RQ).
Processing Layer: Runs AI models for detection, embedding, and description.
Storage Layer: Stores metadata (SQLite) and embeddings (Milvus Lite).
Query Layer: Processes natural language searches.
Interface Layer: Provides CLI or GUI for interaction and feedback.
Feedback Layer: Handles user corrections.

3.2 Component Diagram
[User] --> [Interface (CLI/GUI)] --> [Query Layer]
                        |
                        v
[Ingestion Layer] --> [Redis Queue] --> [Processing Layer (AI Models: YOLO, CLIP, BLIP)]
                        |                        |
                        v                        v
                 [SQLite (Metadata)]    [Milvus Lite (Embeddings)]
                        |                        |
                        v                        v
                 [Feedback Layer] <--- [Interface (Corrections)]

3.3 Tech Stack

Language: Python 3.9+
AI Framework: PyTorch (flexible for SOTA models, widely supported)
Models:
Object Detection: YOLOv7 (non-transformer, fast)
Image Embedding: CLIP-ViT-B/32 (transformer, optimized for text-image search)
Image-to-Text: BLIP (transformer, detailed scene descriptions)


Queue: Redis Queue (RQ)
Databases:
SQLite (metadata: file paths, tags, descriptions)
Milvus Lite (embeddings for search)


File Monitoring: Watchdog (Python library for folder monitoring)
Interface: Click (CLI) or Tkinter (GUI)
API: FastAPI (RESTful endpoints)
Dependencies: torchvision, ultralytics, openai-clip, transformers, pymilvus, redis, fastapi, uvicorn

4. Detailed Workflow
Below is a step-by-step flow of how PixQuery processes images, from ingestion to querying, with baby steps for complex tasks, alternatives for potential failures, and gap-filling details.
4.1 Image Ingestion
Purpose: Detect new images and queue them for processing without duplicates.
Steps:

Folder Monitoring:
Use the watchdog library to monitor a user-specified folder (e.g., ~/pixquery_photos).
Trigger an event when a new image (JPEG, PNG) is added or modified.
Example formats: .jpg, .jpeg, .png.


Uniqueness Check:
Query the SQLite images table to check if the image’s path exists and processed=1.
If not in the table or processed=0, proceed to queueing.


Queueing:
Add the image path to a Redis Queue (RQ) for asynchronous processing.
Example: queue.enqueue(process_image, image_path).



Baby Steps:

Install watchdog: pip install watchdog.
Create a script (monitor.py):from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sqlite3
from rq import Queue
from redis import Redis

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(('.jpg', '.jpeg', '.png')):
            return
        conn = sqlite3.connect('pixquery.db')
        cursor = conn.cursor()
        cursor.execute('SELECT processed FROM images WHERE path = ?', (event.src_path,))
        result = cursor.fetchone()
        if result is None or result[0] == 0:
            queue = Queue('photos', connection=Redis())
            queue.enqueue(process_image, event.src_path)
        conn.close()

observer = Observer()
observer.schedule(ImageHandler(), path='~/pixquery_photos', recursive=False)
observer.start()


Test: Add 10 images to the folder, verify they’re queued, and check SQLite for duplicates.

Alternative (if watchdog fails):

Use a manual CLI command to scan the folder: pixquery scan ~/pixquery_photos.
Pros: Simpler, no real-time monitoring overhead.
Cons: Requires user initiation, less automated.
Implementation: glob.glob('~/pixquery_photos/*.jpg') to list files.

Gap Filled: Explicitly checks for supported file formats and handles duplicates via SQLite.
4.2 Queue Management
Purpose: Manage asynchronous processing to prevent system overload, especially with resource-intensive transformer models like BLIP.
Why Redis Queue (RQ)?:

Lightweight: Runs on a local Redis instance, minimal setup (redis-server).
Python-Friendly: Integrates seamlessly with Python via rq (pip install rq).
Local Suitability: Unlike RabbitMQ (complex setup for distributed systems) or Kafka (designed for high-throughput clusters), RQ is ideal for a single-PC setup.
Features: Supports retries, task prioritization, and monitoring.

Steps:

Start a local Redis server: redis-server (default port 6379).
Create a queue: Queue('photos', connection=Redis()).
Enqueue image paths from the ingestion layer.
Run workers: rq worker photos to process queued tasks.

Baby Steps:

Install Redis: On Ubuntu, sudo apt-get install redis; on macOS, brew install redis.
Test RQ:from rq import Queue
from redis import Redis
queue = Queue('photos', connection=Redis())
queue.enqueue(lambda x: print(f"Processing {x}"), "test.jpg")


Start a worker in a separate terminal: rq worker photos.
Verify the test job runs.

Alternative (if Redis fails):

Use Python’s multiprocessing.Pool:from multiprocessing import Pool
def process_image(image_path):
    # Process image
    pass
with Pool(processes=4) as pool:
    pool.map(process_image, image_paths)


Pros: No external server needed, simpler for small datasets.
Cons: Lacks RQ’s retry and monitoring features, harder to scale.

Gap Filled: Clarified Redis setup and provided a fallback for single-threaded or small-scale processing.
4.3 AI Processing
Purpose: Generate tags, embeddings, and detailed descriptions for each image.
Models:

Object Detection: YOLOv7 (non-transformer):
Why: Fast, lightweight, suitable for local PCs.
Output: JSON list, e.g., [{"label": "dog", "confidence": 0.95, "bbox": [x, y, w, h]}].


Image Embedding: CLIP-ViT-B/32 (transformer):
Why: Optimized for text-image search, feasible on mid-range hardware (~1.5GB GPU memory).
Output: 512-dimensional vector.


Image-to-Text: BLIP (transformer):
Why: Generates detailed scene descriptions, supporting broader use cases like CCTV monitoring.
Output: Text, e.g., “A dog playing on the beach with waves in the background at sunset.”



Steps:

Worker Setup:
Run RQ workers to pull image paths from the queue.
Example: rq worker photos.


Processing Pipeline:
Load image using PIL.Image.open(image_path).
YOLO: Run detection: model(image).
CLIP: Generate embedding: model.encode_image(image).
BLIP: Generate description: model.generate(image).


Error Handling:
Catch memory errors (e.g., torch.cuda.OutOfMemoryError) and retry with smaller batch size.
Log errors to a file (errors.log) for debugging.



Baby Steps:

Install dependencies: pip install torch torchvision ultralytics openai-clip transformers.
Test YOLO:from ultralytics import YOLO
model = YOLO('yolov7.pt')
results = model('test.jpg')
detections = [{'label': r.names[r.cls], 'confidence': r.conf, 'bbox': r.xywh} for r in results]


Test CLIP:import clip
import torch
from PIL import Image
model, preprocess = clip.load('ViT-B/32', device='cpu')
image = preprocess(Image.open('test.jpg')).unsqueeze(0)
embedding = model.encode_image(image)


Test BLIP:from transformers import BlipProcessor, BlipForConditionalGeneration
processor = BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base')
model = BlipForConditionalGeneration.from_pretrained('Salesforce/blip-image-captioning-base')
image = Image.open('test.jpg')
inputs = processor(images=image, return_tensors='pt')
description = model.generate(**inputs)
description = processor.decode(description[0], skip_special_tokens=True)


Combine outputs and test on one image.

Alternative (if models fail):

YOLO: Use YOLOv5s (smaller, ~100MB memory).
CLIP: Use ResNet-50 (lighter, but needs custom text-image alignment).
BLIP: Skip descriptions or use CNN-LSTM (e.g., Show and Tell) for simpler captions.
Pros: Lower resource usage, faster processing.
Cons: Reduced accuracy or description quality.

Gap Filled: Detailed code snippets for each model and error handling to ensure robust processing.
4.4 Storage
Purpose: Store metadata and embeddings for efficient retrieval.
Databases:

SQLite: Stores metadata (file paths, detections, descriptions, corrections).
Milvus Lite: Stores embeddings for similarity search.

Steps:

SQLite:
Insert metadata after processing:INSERT INTO images (path, detections, description, processed) VALUES (?, ?, ?, 1);


Update corrected_detections for user feedback.


Milvus:
Create a collection: image_embeddings with fields id (int64) and embedding (float vector, 512 dimensions).
Insert embedding with SQLite id as key.



Schema:
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE,
    detections TEXT,          -- JSON: [{"label": "dog", "confidence": 0.95, "bbox": [x, y, w, h]}]
    description TEXT,        -- e.g., "A dog playing on the beach at sunset"
    processed BOOLEAN DEFAULT 0,
    corrected_detections TEXT -- JSON: user-corrected detections
);

Milvus Collection:

Name: image_embeddings
Fields:
id (int64, primary key)
embedding (float vector, 512 dimensions)



Baby Steps:

Install SQLite: Built into Python (sqlite3).
Install Milvus Lite: pip install pymilvus.
Test SQLite insert:import sqlite3
conn = sqlite3.connect('pixquery.db')
cursor = conn.cursor()
cursor.execute('INSERT INTO images (path, detections, description, processed) VALUES (?, ?, ?, ?)',
               ('test.jpg', '{"label": "dog"}', 'A dog on the beach', 1))
conn.commit()


Test Milvus insert:from pymilvus import Collection, connections
connections.connect()
collection = Collection('image_embeddings')
collection.insert([[1], [embedding.tolist()]])



Alternative (if Milvus fails):

Use FAISS for embeddings:import faiss
index = faiss.IndexFlatL2(512)
index.add(embedding.numpy())


Pros: CPU-only, simpler setup.
Cons: Less robust for large datasets, no built-in persistence.

Gap Filled: Explicit schema and insertion code, ensuring unique processing via processed flag.
4.5 Querying
Purpose: Retrieve images based on natural language queries (e.g., “find photos of my dog at the beach”).
Steps:

Query Input: User enters text via CLI/GUI.
Query Processing:
Convert query to embedding using CLIP’s text encoder: model.encode_text(clip.tokenize(query)).
Search Milvus for top-k similar embeddings: collection.search(data=[text_embedding], anns_field="embedding", limit=10).
Optionally filter SQLite for specific tags: SELECT * FROM images WHERE detections LIKE '%dog%' AND id IN (...);.


Output: Return a list of {id, path, detections, description, corrected_detections}.

Baby Steps:

Test CLIP text encoding:query = "dog at beach"
text = clip.tokenize([query]).to(device)
text_embedding = model.encode_text(text)


Test Milvus search:results = collection.search(data=[text_embedding.tolist()], anns_field="embedding", limit=10)
ids = [r.id for r in results[0]]


Join with SQLite:cursor.execute('SELECT * FROM images WHERE id IN ({})'.format(','.join('?' * len(ids))), ids)



Alternative (if Milvus search fails):

Use SQLite-only search: SELECT * FROM images WHERE description LIKE '%dog%' OR detections LIKE '%dog%';.
Pros: No vector database needed.
Cons: Less accurate for semantic queries.

Gap Filled: Detailed query pipeline with fallback for simpler search.
4.6 Human-in-the-Loop Feedback
Purpose: Allow users to correct AI outputs (e.g., change “cat” to “dog” or edit descriptions).
Steps:

Display Results: Show image, detections, and description in CLI/GUI.
Correction Interface:
CLI example: pixquery correct <id> --detections '{"label": "dog"}' --description "A dog on the beach".
GUI: Use Tkinter to display image and editable fields.


Store Corrections:
Update SQLite: UPDATE images SET corrected_detections=?, description=? WHERE id=?.


Apply Corrections: Use corrected_detections (if present) during search instead of detections.

Baby Steps:

Create a CLI command with click:import click
@click.command()
@click.argument('id', type=int)
@click.option('--detections', type=str)
@click.option('--description', type=str)
def correct(id, detections, description):
    conn = sqlite3.connect('pixquery.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE images SET corrected_detections=?, description=? WHERE id=?',
                   (detections, description, id))
    conn.commit()


Test: Correct one image’s detections and verify in SQLite.

Alternative (if feedback interface fails):

Log corrections to a JSON file: corrections.json.
Pros: Simpler storage, no database updates.
Cons: Harder to integrate with queries.

Gap Filled: Explicit correction storage and application logic.
4.7 Model Abstraction Layer
Purpose: Allow users to swap models (e.g., YOLO for Faster R-CNN, BLIP for LLaVA).
Implementation:

Define a Python interface:class ModelInterface:
    def detect(self, image):  # Returns JSON detections
        pass
    def embed(self, image):   # Returns vector
        pass
    def describe(self, image): # Returns text
        pass


Implement for each model (YOLO, CLIP, BLIP).
Load via config (YAML):models:
  detector: yolov7
  embedder: clip-vit-b32
  describer: blip



Baby Steps:

Create a base class and one implementation (e.g., YOLO).
Test swapping configs for a dummy model.

Alternative (if abstraction fails):

Hardcode models initially and refactor later.
Pros: Faster prototyping.
Cons: Less flexible for users.

Gap Filled: Clear interface definition and config example.
5. Backend APIs
Expose REST APIs using FastAPI for programmatic interaction:

POST /process:
Input: None (scans folder).
Output: { "status": "queued", "count": N }.


GET /search?query={text}&top_k={int}:
Output: [{ "id": int, "path": str, "detections": json, "description": str, "corrected_detections": json }].


GET /images/{id}:
Output: { "id": int, "path": str, "detections": json, "description": str, "corrected_detections": json }.


POST /correct/{id}:
Input: { "detections": json, "description": str }.
Output: { "status": "updated" }.



Baby Steps:

Install FastAPI: pip install fastapi uvicorn.
Create a basic API:from fastapi import FastAPI
app = FastAPI()

@app.get("/search")
async def search(query: str, top_k: int = 10):
    # Implement search logic
    return {"results": []}


Run: uvicorn main:app --reload.

Alternative (if FastAPI fails):

Use Flask: Simpler but less modern.
Pros: Easier setup.
Cons: Fewer async features.

Gap Filled: Detailed API specs with example implementation.
6. Technical Requirements

Hardware:
Minimum: 8GB RAM, CPU (e.g., Intel i5).
Recommended: NVIDIA GPU (e.g., GTX 1060, 4GB VRAM) for faster processing.


Software:
Python 3.9+
Dependencies: torch, torchvision, ultralytics, openai-clip, transformers, pymilvus, redis, watchdog, click, fastapi, uvicorn


Performance:
Process 1 photo/sec (GPU) or 0.2 photo/sec (CPU).
Search returns results in <5 seconds for 10,000 photos.


Storage:
~1GB per 1,000 photos (images + embeddings).
SQLite: <10MB for metadata.
Milvus: ~100MB for 10,000 embeddings.



7. Alternatives for Failure Points

Slow Processing: Use lighter models (YOLOv5s, ResNet-50, CNN-LSTM).
Database Issues: Replace Milvus with FAISS or SQLite-only search.
Queue Overload: Process sequentially without RQ (multiprocessing).
Model Errors: Add retry logic (max 3 attempts) and log errors to errors.log.
Interface Failure: Default to CLI if GUI (Tkinter) is too complex.

8. Development Plan

Setup (Week 1):
Install Python, Redis, Milvus Lite, and dependencies.
Configure SQLite and Milvus.


Prototype (Weeks 2-3):
Implement folder monitoring and queueing.
Process 10 images with YOLO, CLIP, BLIP.
Store data in SQLite/Milvus.


Core Features (Weeks 4-6):
Add search functionality and APIs.
Implement CLI and basic GUI.


Feedback and Testing (Weeks 7-8):
Add correction interface.
Test with 1,000 photos, optimize performance.


Polish (Weeks 9-10):
Add error handling, logging, and documentation.
Test extensibility with a new model.



9. Final Output
A local Python application (pixquery) that:

Monitors ~/pixquery_photos for new images.
Processes images with:
YOLOv7: Object detections (e.g., [{"label": "dog", "confidence": 0.95}]).
CLIP: Embeddings for search (512-dimensional vector).
BLIP: Detailed descriptions (e.g., “A dog playing on the beach at sunset”).


Stores data in SQLite (metadata) and Milvus Lite (embeddings).
Supports natural language search via CLI (pixquery search "dog at beach") or GUI.
Allows corrections via CLI (pixquery correct 1 --detections '{"label": "dog"}') or GUI.
Runs offline, ensuring privacy.

10. Additional Notes

Extensibility: The abstraction layer supports future models (e.g., LLaVA for descriptions, Faster R-CNN for detection).
Scalability: Tested for 10,000 photos; for larger datasets, optimize Milvus or switch to FAISS.
Future Enhancements:
Add video support (extract keyframes, process as images).
Implement anomaly detection for CCTV use cases (e.g., flag unusual objects).


Documentation: Include a README.md with setup, usage, and model swapping instructions.

