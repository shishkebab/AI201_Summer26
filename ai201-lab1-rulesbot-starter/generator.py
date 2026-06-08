from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

_client = Groq(api_key=GROQ_API_KEY)


def generate_response(query, retrieved_chunks):
    """
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
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    return response.choices[0].message.content
