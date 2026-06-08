<<<<<<< HEAD
import gradio as gr
from ingest import load_documents, chunk_document
from retriever import embed_and_store, retrieve, get_collection
from generator import generate_response


# ---------------------------------------------------------------------------
# Ingestion — runs once on startup
# ---------------------------------------------------------------------------

def run_ingestion():
    """
    Load rule documents, chunk them, and store in ChromaDB.

    If the vector store is already populated, ingestion is skipped.
    To re-ingest (e.g. after changing your chunking strategy), delete the
    ./chroma_db folder and restart the app.
    """
    collection = get_collection()

    if collection.count() > 0:
        print(f"Vector store already populated ({collection.count()} chunks). Skipping ingestion.")
        print("To re-ingest, delete the ./chroma_db folder and restart.")
        return

    print("Ingesting rule documents...")
    documents = load_documents()
    all_chunks = []

    for doc in documents:
        chunks = chunk_document(doc["text"], doc["game"])
        all_chunks.extend(chunks)

    if all_chunks:
        embed_and_store(all_chunks)
        # print(all_chunks[0:10])
        print(f"Ingestion complete. {len(all_chunks)} chunks stored.")
    else:
        print(
            "\n⚠️  No chunks produced. Make sure chunk_document() is implemented in ingest.py.\n"
            "    RulesBot will start, but won't be able to answer questions yet.\n"
        )


# ---------------------------------------------------------------------------
# Chat handler
# ---------------------------------------------------------------------------

def chat(message, history):
    if not message.strip():
        return ""
    retrieved = retrieve(message)
    return generate_response(message, retrieved)


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="indigo"),
    title="RulesBot",
) as demo:

    gr.HTML("""
        <div style="text-align:center; padding:1.25rem 0 0.5rem;">
            <h1 style="font-size:2rem; font-weight:700; color:#312e81; margin:0;">
                🎲 RulesBot
            </h1>
            <p style="color:#6b7280; font-size:1rem; margin:0.4rem 0 0;">
                Ask anything about your board games — answers straight from the rulebook.
            </p>
        </div>
    """)
=======
from pathlib import Path

import gradio as gr

import collect_raw
from generator import generate_response
from vector_store import DEFAULT_TOP_K, build_vector_store, get_collection, retrieve


DOCUMENTS_DIR = Path("documents")


def document_files():
    """Return collected plaintext professor documents."""
    if not DOCUMENTS_DIR.exists():
        return []
    return sorted(DOCUMENTS_DIR.glob("*.txt"))


def ensure_documents():
    """Collect raw documents only when the documents folder has no .txt files."""
    files = document_files()
    if files:
        print(f"Found {len(files)} document file(s). Skipping raw collection.")
        return

    print("No document files found. Running collect_raw.py...")
    collect_raw.main()


def ensure_vector_store():
    """Build ChromaDB only when the collection is empty."""
    collection = get_collection()
    count = collection.count()
    if count > 0:
        print(f"Vector store already populated with {count} chunk(s). Skipping chunking/embedding.")
        return collection

    print("Vector store is empty. Chunking documents and building ChromaDB...")
    collection = build_vector_store(reset=True)
    print(f"Vector store ready with {collection.count()} chunk(s).")
    return collection


def startup():
    """Run the full pipeline only as needed before launching the UI."""
    print("\n" + "=" * 60)
    print("  Unofficial UA CS Professor Guide - starting")
    print("=" * 60)
    ensure_documents()
    ensure_vector_store()
    print("=" * 60 + "\n")


def chat(message, history):
    """Retrieve professor review chunks and generate a grounded answer."""
    if not message.strip():
        return ""

    retrieved_chunks = retrieve(message, top_k=DEFAULT_TOP_K)
    try:
        return generate_response(message, retrieved_chunks)
    except Exception as exc:
        return (
            "Answer: I could not generate a response because the LLM call failed.\n\n"
            f"Sources: None\n\nError: {exc}"
        )


with gr.Blocks(
    title="Unofficial UA CS Professor Guide",
) as demo:
    gr.HTML(
        """
        <div style="text-align:center; padding:1rem 0 0.5rem;">
            <h1 style="font-size:2rem; font-weight:700; margin:0;">
                Unofficial UA CS Professor Guide
            </h1>
            <p style="color:#4b5563; font-size:1rem; margin:0.4rem 0 0;">
                Ask about professor reviews, courses, teaching style, exams, and difficulty.
            </p>
        </div>
        """
    )
>>>>>>> ai201-project1-unofficial-guide-starter/main

    with gr.Row():
        with gr.Column(scale=3):
            gr.ChatInterface(
                fn=chat,
<<<<<<< HEAD
                type="messages",
                chatbot=gr.Chatbot(
                    height=440,
                    type="messages",
                    placeholder=(
                        "<div style='text-align:center; color:#9ca3af; margin-top:3rem;'>"
                        "Ask a rules question to get started — no arguing required 🎯"
=======
                chatbot=gr.Chatbot(
                    height=460,
                    placeholder=(
                        "<div style='text-align:center; color:#6b7280; margin-top:3rem;'>"
                        "Ask a question about the loaded professor reviews."
>>>>>>> ai201-project1-unofficial-guide-starter/main
                        "</div>"
                    ),
                ),
                textbox=gr.Textbox(
<<<<<<< HEAD
                    placeholder='e.g. "Can I build a road through someone else\'s settlement?"',
=======
                    placeholder='e.g. "Which professor has especially negative reviews about CSC335?"',
>>>>>>> ai201-project1-unofficial-guide-starter/main
                    container=False,
                    scale=7,
                ),
                examples=[
<<<<<<< HEAD
                    "How do you set up the board in Catan?",
                    "What happens if you roll a 7 in Catan?",
                    "How does the Spymaster give clues in Codenames?",
                    "What happens when a city gets a 4th disease cube in Pandemic?",
                    "Can two players claim the same route in Ticket to Ride?",
                    "How do you get out of Jail in Monopoly?",
                    "How does attacking work in Risk?",
                    "What is a Wild Draw Four and when can you play it in Uno?",
                    "How does making a Suggestion work in Clue?",
=======
                    "Which professor has especially negative reviews about CSC335?",
                    "Who teaches AI or ML/NLP classes?",
                    "Which professor seems to have hard exams?",
                    "Is Abu Ahmed a good choice for clear lectures and reasonable exams?",
>>>>>>> ai201-project1-unofficial-guide-starter/main
                ],
                cache_examples=False,
            )

<<<<<<< HEAD
        with gr.Column(scale=1, min_width=180):
            gr.HTML("""
                <div style="background:#f5f3ff; border:1px solid #ddd6fe;
                            border-radius:10px; padding:1rem; margin-top:0.5rem;">
                    <p style="font-size:0.8rem; font-weight:700; color:#4c1d95;
                               margin:0 0 0.5rem; letter-spacing:0.05em;">
                        📚 LOADED RULE BOOKS
                    </p>
                    <ul style="font-size:0.85rem; color:#5b21b6; list-style:none;
                                padding:0; margin:0; line-height:1.8;">
                        <li>🏔️ Catan</li>
                        <li>🔍 Clue</li>
                        <li>🎯 Codenames</li>
                        <li>🏦 Monopoly</li>
                        <li>🦠 Pandemic</li>
                        <li>🌍 Risk</li>
                        <li>🚂 Ticket to Ride</li>
                        <li>🃏 Uno</li>
                    </ul>
                    <hr style="border:none; border-top:1px solid #ddd6fe; margin:0.75rem 0;">
                    <p style="font-size:0.75rem; color:#7c3aed; margin:0; line-height:1.5;">
                        Answers are grounded in the loaded rules only. If a rule
                        isn't in the books, RulesBot will say so.
                    </p>
                </div>
            """)


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  RulesBot — starting up")
    print("="*50 + "\n")
    run_ingestion()
    # demo.queue()
    demo.launch()
=======
        with gr.Column(scale=1, min_width=220):
            gr.HTML(
                """
                <div style="border:1px solid #d1d5db; border-radius:8px; padding:1rem; margin-top:0.5rem;">
                    <p style="font-size:0.8rem; font-weight:700; color:#1f2937; margin:0 0 0.5rem;">
                        Grounding
                    </p>
                    <p style="font-size:0.85rem; color:#4b5563; line-height:1.5; margin:0;">
                        Answers use only retrieved RateMyProfessors review chunks from the local
                        ChromaDB collection. Each response should include an answer and sources.
                    </p>
                </div>
                """
            )


if __name__ == "__main__":
    startup()
    demo.launch(theme=gr.themes.Soft(primary_hue="blue"))
>>>>>>> ai201-project1-unofficial-guide-starter/main
