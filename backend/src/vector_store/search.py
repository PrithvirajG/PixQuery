from .qdrant_client import get_client
from .index_manager import COLLECTION_NAME

def search_vector(query_vector, top_k=5):
    client = get_client()
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
    )
    return [(hit.payload["path"], hit.score) for hit in hits]
