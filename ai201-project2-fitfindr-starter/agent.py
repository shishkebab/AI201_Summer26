"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import (
    _get_groq_client,
    create_fit_card,
    search_listings,
    suggest_outfit,
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """Extract description, size, and max_price from a simple user query."""
    description = query.strip()

    price_match = re.search(
        r"(?:under|below|less than|max(?:imum)?|up to)\s*\$?\s*(\d+(?:\.\d+)?)",
        description,
        flags=re.IGNORECASE,
    )
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", description)
    max_price = float(price_match.group(1)) if price_match else None

    size = None
    for pattern in [
        r"\bsize\s+([a-z]{1,3}\b|us\s*\d+(?:\.\d+)?|w\d{2}(?:\s*l\d{2})?|\d+(?:\.\d+)?)",
        r"\b(us\s*\d+(?:\.\d+)?)\b",
        r"\b(w\d{2}(?:\s*l\d{2})?)\b",
    ]:
        size_match = re.search(pattern, description, flags=re.IGNORECASE)
        if size_match:
            size = re.sub(r"\s+", " ", size_match.group(1).upper()).strip()
            break

    for pattern in [
        r"(?:under|below|less than|max(?:imum)?|up to)\s*\$?\s*\d+(?:\.\d+)?",
        r"\$\s*\d+(?:\.\d+)?",
        r"\bsize\s+(?:[a-z]{1,3}\b|us\s*\d+(?:\.\d+)?|w\d{2}(?:\s*l\d{2})?|\d+(?:\.\d+)?)",
        r"\bus\s*\d+(?:\.\d+)?\b",
        r"\bw\d{2}(?:\s*l\d{2})?\b",
        r"\b(?:i'?m|i am|looking for|want|need|find me|show me)\b",
        r"\b(?:what'?s out there|how would i style it)\b",
    ]:
        description = re.sub(pattern, " ", description, flags=re.IGNORECASE)

    description = re.sub(r"[?.,!]", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "description": description or query.strip(),
        "size": size,
        "max_price": max_price,
    }


def _fallback_no_results_message(parsed: dict) -> str:
    """Return a deterministic no-results message if the LLM is unavailable."""
    description = parsed.get("description") or "that item"
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    filters = []
    if size:
        filters.append(f"size {size}")
    if max_price is not None:
        filters.append(f"under ${max_price:g}")
    filter_text = f" with {' and '.join(filters)}" if filters else ""

    return (
        f"I couldn't find any listings for '{description}'{filter_text}. "
        # "Try broadening the item description, removing the size filter, or raising the max price."
    )


def _generate_no_results_message(parsed: dict) -> str:
    """Ask the LLM to explain the failed search and suggest next steps."""
    fallback = _fallback_no_results_message(parsed)
    prompt = f"""
The user searched for a secondhand clothing item, but no listings matched.

Parsed search:
- description: {parsed.get("description")}
- size: {parsed.get("size")}
- max_price: {parsed.get("max_price")}

Write a short helpful response to the user. It should:
- say what failed
- mention the filters that may have been too restrictive
- suggest 2-3 concrete ways to adjust the search
- not pretend there are matching listings
""".strip()

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You help users refine secondhand clothing searches. "
                        "Be concise, specific, and honest about no-result searches."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=180,
        )
        message = response.choices[0].message.content.strip()
        if message:
            return message
    except Exception:
        pass

    return fallback


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    if not query or not query.strip():
        session["error"] = "Please enter what kind of item you want to find."
        return session

    session["parsed"] = _parse_query(query)

    print("[TOOL CALL] search_listings")
    print("description:", session["parsed"]["description"])
    print("size:", session["parsed"]["size"])
    print("max_price:", session["parsed"]["max_price"])
    session["search_results"] = search_listings(
        description=session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    if not session["search_results"]:
        print("[BRANCH] search_listings returned no results")
        print("[TOOL CALL] _generate_no_results_message")
        print("[SKIP] suggest_outfit")
        print("[SKIP] create_fit_card")
        session["error"] = _generate_no_results_message(session["parsed"])
        return session

    session["selected_item"] = session["search_results"][0]
    print("[DEBUG] selected_item stored in session:")
    print(session["selected_item"])
    print("[DEBUG] selected_item id before suggest_outfit:", id(session["selected_item"]))

    print("[TOOL CALL] suggest_outfit")
    print("wardrobe item count:", len(session["wardrobe"].get("items", [])))
    print("[DEBUG] selected_item passed into suggest_outfit:")
    print(session["selected_item"])
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    print("[DEBUG] outfit_suggestion stored in session:")
    print(session["outfit_suggestion"])
    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = (
            "I found a listing, but couldn't create an outfit suggestion for it."
        )
        print("[SKIP] create_fit_card")
        return session

    print("[TOOL CALL] create_fit_card")
    print("[DEBUG] outfit_suggestion passed into create_fit_card:")
    print(session["outfit_suggestion"])
    print("[DEBUG] selected_item passed into create_fit_card:")
    print(session["selected_item"])
    print("[DEBUG] selected_item id before create_fit_card:", id(session["selected_item"]))
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )
    if not session["fit_card"] or not session["fit_card"].strip():
        session["error"] = (
            "I created an outfit suggestion, but couldn't create a fit card."
        )

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
