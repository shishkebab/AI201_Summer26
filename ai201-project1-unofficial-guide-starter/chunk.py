import os
import re


DOCS_PATH = "documents"


def professor_id_from_filename(filename):
    """Get the RateMyProfessors numeric id from a source filename."""
    return filename.split("_", 1)[0]


def professor_name_from_text(text, fallback):
    """Read the professor name from the document header when available."""
    for line in text.splitlines():
        if line.startswith("Professor:"):
            professor_name = line.replace("Professor:", "", 1).strip()
            if professor_name:
                return professor_name
    return fallback


def chunk_id_prefix(filename):
    """Build a stable id prefix from the source filename."""
    stem = filename.replace(".txt", "")
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")


def load_documents():
    """Load all .txt professor review documents from the documents folder."""
    documents = []
    for filename in sorted(os.listdir(DOCS_PATH)):
        if filename.endswith(".txt"):
            filepath = os.path.join(DOCS_PATH, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            fallback_name = filename.replace(".txt", "").replace("_", " ").title()
            professor_name = professor_name_from_text(text, fallback_name)
            documents.append({
                "professor": professor_name,
                "professor_id": professor_id_from_filename(filename),
                "filename": filename,
                "text": text,
            })
    print(f"Loaded {len(documents)} professor document(s): {[d['professor'] for d in documents]}")
    return documents


def chunk_document(text, professor_name, source_file="", professor_id=""):
    """
    Split a professor review document into chunks ready for embedding.

    Strategy: character-based sliding window with overlap, using planning.md:
      - chunk_size = 500 characters
      - overlap = 75 characters
      - min_length = 50 characters

    Returns a list of dicts, each with:
      - "text"         : the chunk text
      - "professor"    : the professor name
      - "professor_id" : the RateMyProfessors id
      - "source_file"  : the source text filename
      - "chunk_id"     : a unique chunk id
    """
    chunk_size = 382
    overlap = 75
    min_length = 50

    chunks = []
    prefix = chunk_id_prefix(source_file) if source_file else professor_name.lower().replace(" ", "_")
    counter = 0

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()

        if len(chunk_text) >= min_length:
            chunks.append({
                "text": chunk_text,
                "professor": professor_name,
                "professor_id": professor_id,
                "source_file": source_file,
                "chunk_id": f"{prefix}_{counter}",
            })
            counter += 1

        start += chunk_size - overlap

    return chunks


def build_chunks():
    """Load documents and chunk each one."""
    all_chunks = []
    for document in load_documents():
        chunks = chunk_document(
            document["text"],
            document["professor"],
            document["filename"],
            document["professor_id"],
        )
        all_chunks.extend(chunks)
    return all_chunks
