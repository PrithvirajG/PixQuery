from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import numpy as np

def init_qdrant(host="localhost", port=6333) -> QdrantClient:
    client = QdrantClient(host=host, port=port)

    collection_name = "image_embeddings"
    if not client.collection_exists(collection_name=collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=512,  # or 768, depending on your CLIP model
                distance=Distance.COSINE,
            ),
        )
    return client


def insert_text_embedding(client: QdrantClient, collection_name: str, item_id: int, text: str, embedding: list):
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=len(embedding), distance=Distance.COSINE)
        )
    client.upsert(
        collection_name=collection_name,
        points=[PointStruct(id=item_id, vector=embedding, payload={"text": text})],
    )

def insert_image_embedding(client: QdrantClient, collection_name: str, image_id: int, embedding: np.ndarray):
    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=image_id,
                    vector=embedding.tolist(),
                    payload={"image_id": image_id},
                )
            ],
        )
    except Exception as e:
        raise ValueError(f"Failed to insert embedding for image_id {image_id}: {e}")

def search_embedding(client: QdrantClient, collection_name: str, query_vector: np.ndarray, limit: int = 10):
    search_result = client.search(
        collection_name=collection_name,
        query_vector=query_vector.tolist(),
        limit=limit,
        with_payload=False,
        with_vectors=False
    )
    return [(hit.id, hit.score) for hit in search_result]

def search_text_embedding(client: QdrantClient, collection_name: str, query_vector: list, limit: int = 5):
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit
    )
    return [(hit.id, hit.score, hit.payload.get("text", "")) for hit in results]
