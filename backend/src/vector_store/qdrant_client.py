from qdrant_client import QdrantClient

def get_client():
    return QdrantClient(host="localhost", port=6333)