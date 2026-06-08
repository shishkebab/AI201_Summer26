import sys

from vector_store import DEFAULT_TOP_K, build_vector_store, get_collection, retrieve


def ensure_vector_store():
    """Build the ChromaDB collection if it is empty."""
    collection = get_collection()
    if collection.count() == 0:
        print("ChromaDB collection is empty. Building vector store...")
        collection = build_vector_store(reset=True)
    print(f"ChromaDB collection has {collection.count()} chunk(s).")


def print_results(results):
    if not results:
        print("No chunks returned.")
        return

    for index, result in enumerate(results, start=1):
        print("=" * 80)
        print(f"Result {index}")
        print(f"Professor: {result['professor']}")
        print(f"Professor ID: {result['professor_id']}")
        print(f"Source file: {result['source_file']}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Distance: {result['distance']:.4f}")
        print("Text:")
        print(result["text"])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ensure_vector_store()
    print("Type a question to retrieve chunks. Press Enter, or type q/quit, to stop.")

    while True:
        query = input("\nQuestion: ").strip()
        if query.lower() in {"", "q", "quit"}:
            break

        results = retrieve(query, top_k=DEFAULT_TOP_K)
        print_results(results)


if __name__ == "__main__":
    main()
