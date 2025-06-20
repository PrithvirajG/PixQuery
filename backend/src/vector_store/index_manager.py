from qdrant_client.models import Distance, VectorParams, PointStruct
from .qdrant_client import get_client

COLLECTION_NAME = "clip_embeddings"
DIM = 512

def init_collection():
    client = get_client()
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE)
    )

def add_embeddings(embeddings_with_ids_and_paths):
    client = get_client()
    points = [
        PointStruct(id=pid, vector=vec, payload={"path": path})
        for pid, vec, path in embeddings_with_ids_and_paths
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
