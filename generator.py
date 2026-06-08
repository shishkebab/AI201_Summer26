import os

from dotenv import load_dotenv
from groq import Groq


LLM_MODEL = "llama-3.3-70b-versatile"

_client = None


def get_client():
    """Create the Groq client lazily so missing keys produce a clear runtime error."""
    global _client
    if _client is None:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GROQ_API_KEY. Add GROQ_API_KEY=... to .env before using the chat app."
            )
        _client = Groq(api_key=api_key)
    return _client


def format_context(retrieved_chunks):
    """Format retrieved ChromaDB chunks as source-labeled context blocks."""
    blocks = []
    for chunk in retrieved_chunks:
        source_label = (
            f"{chunk['professor']} | {chunk['source_file']} | "
            f"{chunk['chunk_id']} | distance={chunk['distance']:.4f}"
        )
        blocks.append(f"[Source: {source_label}]\n{chunk['text']}")
    return "\n\n---\n\n".join(blocks)


def format_source_list(retrieved_chunks):
    """Build candidate source labels from retrieved chunks."""
    seen = set()
    lines = []
    for chunk in retrieved_chunks:
        key = (chunk["professor"], chunk["source_file"], chunk["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"- {chunk['professor']} ({chunk['source_file']}, {chunk['chunk_id']})"
        )
    return "\n".join(lines)


def generate_response(query, retrieved_chunks):
    """
    Generate a grounded answer from retrieved professor review chunks.

    The model must answer from retrieved context only and include source
    attribution in the final response.
    """
    if not retrieved_chunks:
        return (
            "Answer: I could not find an answer in the retrieved review context.\n\n"
            "Sources: None"
        )

    context = format_context(retrieved_chunks)
    source_list = format_source_list(retrieved_chunks)

    system_prompt = (
        "You are an assistant for an unofficial guide to University of Arizona CS professors. "
        "Answer the user's question using ONLY the retrieved RateMyProfessors review chunks "
        "provided in the context. Do not use outside knowledge, assumptions, or general beliefs "
        "about professors, courses, universities, or teaching. If the context only partially "
        "answers the question, answer only the supported part and say what is not covered. "
        "If the answer is not found in the context, say that the answer is not found in the "
        "retrieved context. Do not invent source names or citations. In the Sources section, "
        "include only the source entries for chunks that directly support your answer. Copy "
        "those source entries exactly from the available source list. If the answer is not "
        "found, write Sources: None.\n\n"
        "Return exactly this format:\n"
        "Answer: <grounded answer>\n\n"
        "Sources:\n"
        "<only the supporting source entries, or None>"
    )

    user_message = (
        f"Context:\n\n{context}\n\n"
        f"Question: {query}\n\n"
        "Available source entries:\n"
        f"{source_list}"
    )

    response = get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content
