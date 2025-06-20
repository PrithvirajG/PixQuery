import sqlite3
import clip
import numpy as np
import torch
from src.storage.qdrant_db import search_embedding, init_qdrant, search_text_embedding


def search_images(query: str, db_path='pixquery.db', collection_name='image_embeddings', limit=10):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)

    text = clip.tokenize([query]).to(device)
    with torch.no_grad():
        query_embedding = model.encode_text(text).cpu().numpy().flatten()
        query_embedding = query_embedding / np.linalg.norm(query_embedding)  # Normalize!

    client = init_qdrant()
    image_ids_with_scores = search_embedding(client, collection_name, query_embedding, limit=limit)

    image_ids = [item[0] for item in image_ids_with_scores]
    scores = {item[0]: item[1] for item in image_ids_with_scores}

    if not image_ids:
        return []

    placeholders = ','.join('?' * len(image_ids))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id, path, detections, description FROM images WHERE id IN ({placeholders})",
        image_ids
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "path": row[1],
            "detections": row[2],
            "description": row[3],
            "score": scores.get(row[0])
        })
    return results

def search_image_descriptions(query: str, db_path='pixquery.db', collection_name='text_embeddings', limit=5):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _ = clip.load("ViT-B/32", device=device)

    text = clip.tokenize([query]).to(device)
    with torch.no_grad():
        query_embedding = model.encode_text(text).cpu().numpy().flatten()
        query_embedding = query_embedding / np.linalg.norm(query_embedding)  # Normalize!

    client = init_qdrant()
    image_ids_with_scores = search_text_embedding(client, collection_name, query_embedding, limit=limit)

    image_ids = [item[0] for item in image_ids_with_scores]
    scores = {item[0]: item[1] for item in image_ids_with_scores}


    if not image_ids:
        return []

    placeholders = ','.join('?' * len(image_ids))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id, path, detections, description FROM images WHERE id IN ({placeholders})",
        image_ids
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "path": row[1],
            "detections": row[2],
            "description": row[3],
            "score": scores.get(row[0])
        })
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python search.py 'your query here'")
    else:
        query = " ".join(sys.argv[1:])
        res = search_image_descriptions(query)
        for r in res:
            print(r)
