"""
Retrieval side of the RAG pipeline: embedding model + ChromaDB collection.

The same embedding model must be used at ingest time and at query time,
otherwise the vectors live in different spaces and similarity is meaningless.
"""
from functools import lru_cache

import chromadb

import config


@lru_cache(maxsize=1)
def get_embedder():
    # imported lazily because loading torch takes a few seconds
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBED_MODEL, device="cpu")


def embed_passages(texts):
    # normalize -> dot product == cosine similarity
    return get_embedder().encode(texts, normalize_embeddings=True, batch_size=32,
                                 show_progress_bar=len(texts) > 64).tolist()


def embed_query(query):
    # bge-v1.5 works best when short queries carry the retrieval instruction
    return get_embedder().encode(config.BGE_QUERY_INSTRUCTION + query,
                                 normalize_embeddings=True).tolist()


def get_client():
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR))


def get_collection(create=False):
    client = get_client()
    if create:
        return client.get_or_create_collection(config.COLLECTION_NAME,
                                               metadata={"hnsw:space": "cosine"})
    return client.get_collection(config.COLLECTION_NAME)


def retrieve(query, k=None):
    """
    Return the top-k chunks for a query as a list of dicts:
    {text, source, page, similarity}. Sorted best first.
    """
    k = k or config.TOP_K
    try:
        collection = get_collection()
    except Exception:
        raise RuntimeError("Vector store not found. Run `python main.py ingest` first.")

    res = collection.query(query_embeddings=[embed_query(query)], n_results=k,
                           include=["documents", "metadatas", "distances"])
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({
            "text": doc,
            "source": meta.get("source"),
            "page": meta.get("page"),        # None for txt/csv
            "rows": meta.get("rows"),        # only for csv chunks
            "similarity": round(1 - dist, 3),  # chroma returns cosine *distance*
        })
    return hits
