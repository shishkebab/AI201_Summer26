import os


DOCS_PATH = "documents"


def load_documents():
    """Load all .txt professor review documents from the documents folder."""
    documents = []
    for filename in sorted(os.listdir(DOCS_PATH)):
        if filename.endswith(".txt"):
            filepath = os.path.join(DOCS_PATH, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            professor_name = filename.replace(".txt", "").replace("_", " ").title()
            documents.append({
                "professor": professor_name,
                "filename": filename,
                "text": text,
            })
    print(f"Loaded {len(documents)} professor document(s): {[d['professor'] for d in documents]}")
    return documents


def chunk_document(text, professor_name):
    """
    Split a professor review document into chunks ready for embedding.

    Strategy: character-based sliding window with overlap, using planning.md:
      - chunk_size = 500 characters
      - overlap = 75 characters
      - min_length = 50 characters

    Returns a list of dicts, each with:
      - "text"      : the chunk text
      - "professor" : the professor name
      - "chunk_id"  : a unique chunk id
    """
    chunk_size = 500
    overlap = 75
    min_length = 50

    chunks = []
    prefix = professor_name.lower().replace(" ", "_")
    counter = 0

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()

        if len(chunk_text) >= min_length:
            chunks.append({
                "text": chunk_text,
                "professor": professor_name,
                "chunk_id": f"{prefix}_{counter}",
            })
            counter += 1

        start += chunk_size - overlap

    return chunks


def build_chunks():
    """Load documents and chunk each one."""
    all_chunks = []
    for document in load_documents():
        chunks = chunk_document(document["text"], document["professor"])
        all_chunks.extend(chunks)
    return all_chunks
