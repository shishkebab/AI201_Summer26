<<<<<<< HEAD
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

_client = Groq(api_key=GROQ_API_KEY)
=======
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
>>>>>>> ai201-project1-unofficial-guide-starter/main


def generate_response(query, retrieved_chunks):
    """
<<<<<<< HEAD
    Generate a grounded answer from retrieved rule chunks.

    TODO — Milestone 3:

    `retrieved_chunks` is the list returned by retrieve(). Each item is a dict:
      - "text"     : the chunk text
      - "game"     : the game name
      - "distance" : similarity score (you can use this to filter weak matches)

    Before writing code, talk through these with your group:
      - How will you format the chunks into a context block for the prompt?
      - What instructions will stop the model from answering beyond what the
        rules say? (Grounding is the whole point — a confident wrong answer
        is worse than an honest "I don't know.")
      - How will you surface which game each answer comes from?

    Your response should:
      1. Answer using only the retrieved context — not the model's general knowledge
      2. Make clear which game the answer comes from
      3. Say so clearly when the answer isn't in the loaded rules

    Return the response as a plain string.
    """
    if not retrieved_chunks:
        return (
            "I couldn't find anything relevant in the loaded rule books. "
            "Try rephrasing your question — or check that your ingestion pipeline is working."
        )

    # Build context block: each chunk as a labeled block separated by "---"
    chunk_blocks = []
    for chunk in retrieved_chunks:
        chunk_blocks.append(f"[Source: {chunk['game']}]\n{chunk['text']}")
    context = "\n\n---\n\n".join(chunk_blocks)

    citation_instruction = (
        "At the end of your answer, cite the game(s) your answer draws from using "
        "this exact format on its own line:\n\n"
        "  [Source: <game_name>]\n\n"
        "If your answer draws from multiple games, list each on a separate line:\n\n"
        "  [Source: Catan]\n"
        "  [Source: Monopoly]\n\n"
        "Use only the game names exactly as they appear in the Source labels in the "
        "context. If the answer is not found in the context, omit the citation entirely."
    )

    system_prompt = (
        "You are a board game rules assistant. Answer the user's question using ONLY "
        "the rule text provided in the context below. "
        "Do not use any knowledge about board games that is not explicitly stated in that context. "
        "Do not infer, speculate, or fill in gaps from general knowledge — even if you believe you know the answer. "
        "If the context only partially answers the question, answer only what the text supports and state that the rest is not covered. "
        "If the answer is not found in the context at all, say so and nothing more.\n\n"
        + citation_instruction
    )

    user_message = f"Context:\n\n{context}\n\nQuestion: {query}"

    response = _client.chat.completions.create(
=======
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
>>>>>>> ai201-project1-unofficial-guide-starter/main
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
<<<<<<< HEAD

=======
>>>>>>> ai201-project1-unofficial-guide-starter/main
    return response.choices[0].message.content
