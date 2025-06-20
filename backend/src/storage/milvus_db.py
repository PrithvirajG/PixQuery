from pymilvus import (
    connections, FieldSchema, CollectionSchema, DataType,
    Collection, utility
)
import numpy as np

def init_milvus(collection_name='image_embeddings', dim=512):
    connections.connect()

    if utility.has_collection(collection_name):
        return Collection(name=collection_name)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields=fields, description="Image CLIP Embeddings")
    collection = Collection(name=collection_name, schema=schema)

    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    return collection

def insert_embedding(collection, image_id: int, embedding: np.ndarray):
    if embedding.shape != (512,):
        raise ValueError(f"Embedding shape mismatch: expected (512,), got {embedding.shape}")
    data = [[image_id], [embedding.tolist()]]
    collection.insert(data)

def search_embedding(collection, query_embedding: np.ndarray, limit=10):
    if query_embedding.shape != (512,):
        raise ValueError(f"Query embedding shape mismatch: expected (512,), got {query_embedding.shape}")
    search_params = {
        "metric_type": "L2",
        "params": {"nprobe": 10}
    }
    results = collection.search(
        data=[query_embedding.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=limit,
        output_fields=["id"]
    )
    return [hit.id for hit in results[0]]
