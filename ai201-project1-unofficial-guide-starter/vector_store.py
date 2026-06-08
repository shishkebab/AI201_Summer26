from sentence_transformers import SentenceTransformer
import chromadb

from chunk import build_chunks


MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "professor_reviews"
DEFAULT_TOP_K = 5

_model = None


def get_model():
    """Load the embedding model once and reuse it."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client():
    """Create a persistent ChromaDB client."""
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_collection():
    """Get or create the professor review collection."""
    client = get_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def chunk_metadata(chunk):
    """Keep only simple scalar metadata values for ChromaDB."""
    return {
        "chunk_id": chunk["chunk_id"],
        "professor": chunk["professor"],
        "professor_id": chunk["professor_id"],
        "source_file": chunk["source_file"],
    }


def build_vector_store(chunks=None, reset=True):
    """
    Embed chunks and store them in ChromaDB.

    If reset is True, the existing collection is deleted first so the vector
    store does not keep stale chunks from previous runs.
    """
    if chunks is None:
        chunks = build_chunks()

    client = get_client()
    if reset:
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    if not chunks:
        return collection

    documents = [chunk["text"] for chunk in chunks]
    ids = [chunk["chunk_id"] for chunk in chunks]
    metadatas = [chunk_metadata(chunk) for chunk in chunks]
    embeddings = get_model().encode(documents).tolist()

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return collection


def retrieve(query, top_k=DEFAULT_TOP_K):
    """Return the top-k most relevant chunks with source metadata."""
    collection = get_collection()
    query_embedding = get_model().encode([query]).tolist()[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    retrieved_chunks = []
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        retrieved_chunks.append({
            "text": text,
            "chunk_id": metadata.get("chunk_id", chunk_id),
            "professor": metadata.get("professor", ""),
            "professor_id": metadata.get("professor_id", ""),
            "source_file": metadata.get("source_file", ""),
            "distance": distance,
        })

    return retrieved_chunks


def main():
    collection = build_vector_store()
    print(f"Stored {collection.count()} chunks in ChromaDB collection '{COLLECTION_NAME}'.")

    sample_query = "Which professor has especially negative reviews about CSC335?"
    print(f"\nSample query: {sample_query}")
    for result in retrieve(sample_query):
        print("-" * 80)
        print(f"{result['professor']} | {result['source_file']} | distance={result['distance']:.4f}")
        print(result["text"])


if __name__ == "__main__":
    main()
