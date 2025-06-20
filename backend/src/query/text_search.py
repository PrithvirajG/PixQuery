import clip
import torch
from src.storage.qdrant_db import insert_text_embedding, search_text_embedding

device = "cuda" if torch.cuda.is_available() else "cpu"
model, _ = clip.load("ViT-B/32", device=device)

def embed_text(text: str):
    tokens = clip.tokenize([text]).to(device)
    with torch.no_grad():
        return model.encode_text(tokens).cpu().numpy().flatten()

# Insert examples
texts = [
    "a cat sitting on a couch",
    "a dog playing with a ball",
    "a tiger walking in the jungle",
    "a man riding a bicycle",
]

for idx, text in enumerate(texts):
    vector = embed_text(text)
    insert_text_embedding("text_search", idx, text, vector.tolist())

# Query
query = "tiger"
query_vec = embed_text(query)
results = search_text_embedding("text_search", query_vec)

print("\nSearch Results:")
for result_text, score in results:
    print(f"{score:.3f} -> {result_text}")
