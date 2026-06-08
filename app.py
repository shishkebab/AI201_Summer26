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

    with gr.Row():
        with gr.Column(scale=3):
            gr.ChatInterface(
                fn=chat,
                chatbot=gr.Chatbot(
                    height=460,
                    placeholder=(
                        "<div style='text-align:center; color:#6b7280; margin-top:3rem;'>"
                        "Ask a question about the loaded professor reviews."
                        "</div>"
                    ),
                ),
                textbox=gr.Textbox(
                    placeholder='e.g. "Which professor has especially negative reviews about CSC335?"',
                    container=False,
                    scale=7,
                ),
                examples=[
                    "Which professor has especially negative reviews about CSC335?",
                    "Who teaches AI or ML/NLP classes?",
                    "Which professor seems to have hard exams?",
                    "Is Abu Ahmed a good choice for clear lectures and reasonable exams?",
                ],
                cache_examples=False,
            )

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
