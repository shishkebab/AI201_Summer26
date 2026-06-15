"""
agent.py

The FitFindr planning loop. Orchestrates the FitFindr tools in response to a
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
    estimate_price_fairness,
    search_listings,
    style_profile_memory,
    suggest_outfit,
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict, user_id: str = "demo_user") -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "user_id": user_id,          # stable user identifier for style memory
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "style_profile": None,       # remembered style preferences
        "memory_warning": None,      # non-fatal style memory warning
        "price_fairness": None,      # dict returned by estimate_price_fairness
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


def _normalize_terms(values: object) -> set[str]:
    """Normalize string/list values into a lowercase set."""
    if values is None:
        return set()
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = [values]
    return {
        str(value).strip().lower()
        for value in raw_values
        if str(value).strip()
    }


def _style_profile_score(listing: dict, style_profile: dict | None) -> int:
    """Return a small memory-based boost for ranking search results."""
    if not isinstance(listing, dict) or not isinstance(style_profile, dict):
        return 0

    listing_tags = _normalize_terms(listing.get("style_tags"))
    listing_colors = _normalize_terms(listing.get("colors"))
    listing_category = str(listing.get("category") or "").strip().lower()
    listing_text = " ".join(
        str(listing.get(field) or "")
        for field in ["title", "description", "category", "brand"]
    ).lower()

    score = 0
    score += 3 * len(listing_tags & _normalize_terms(style_profile.get("preferred_style_tags")))
    score += 2 * len(listing_colors & _normalize_terms(style_profile.get("preferred_colors")))
    if listing_category in _normalize_terms(style_profile.get("preferred_categories")):
        score += 2
    for silhouette in _normalize_terms(style_profile.get("preferred_silhouettes")):
        if silhouette in listing_text or silhouette in listing_tags:
            score += 1
    for disliked in _normalize_terms(style_profile.get("disliked_terms")):
        if disliked in listing_text or disliked in listing_tags or disliked in listing_colors:
            score -= 4
    return score


def _rerank_with_style_profile(results: list[dict], style_profile: dict | None) -> list[dict]:
    """Re-rank search results with memory as a boost, never as a hard filter."""
    if not isinstance(results, list) or not isinstance(style_profile, dict):
        return results
    return [
        listing
        for _, _, listing in sorted(
            (
                (_style_profile_score(listing, style_profile), -index, listing)
                for index, listing in enumerate(results)
            ),
            reverse=True,
        )
    ]


def _extract_profile_update(query: str, selected_item: dict, outfit_suggestion: str) -> dict:
    """Build a lightweight style-memory update from the completed interaction."""
    query_text = (query or "").lower()
    outfit_text = (outfit_suggestion or "").lower()
    combined_text = f"{query_text} {outfit_text}"

    keyword_map = {
        "preferred_silhouettes": ["oversized", "baggy", "chunky sneakers", "minimal"],
        "preferred_style_tags": ["streetwear", "preppy", "grunge", "cottagecore", "vintage"],
        "preferred_colors": ["black"],
    }
    update = {
        "preferred_style_tags": list(selected_item.get("style_tags", []) or []),
        "preferred_colors": list(selected_item.get("colors", []) or []),
        "preferred_silhouettes": [],
        "preferred_categories": [],
        "wardrobe_notes": None,
    }

    category = selected_item.get("category")
    if category:
        update["preferred_categories"].append(category)

    for field, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in combined_text:
                update.setdefault(field, []).append(keyword)

    if "baggy jeans" in combined_text or "chunky sneakers" in combined_text:
        update["wardrobe_notes"] = "User likes baggy jeans and chunky sneakers."

    return update


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
            # max_tokens=180,
        )
        message = response.choices[0].message.content.strip()
        if message:
            return message
    except Exception:
        pass

    return fallback


def run_agent(query: str, wardrobe: dict, user_id: str = "demo_user") -> dict:
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

        Step 5: Call estimate_price_fairness() with the selected item.
                Store the result in session["price_fairness"]. This should not
                stop the flow if the verdict is "not enough data".

        Step 6: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 7: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 8: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe, user_id)

    if not query or not query.strip():
        session["error"] = "Please enter what kind of item you want to find."
        return session

    print("[TOOL CALL] style_profile_memory load")
    try:
        session["style_profile"] = style_profile_memory(
            user_id=session["user_id"],
            action="load",
            profile_update=None,
        )
        if isinstance(session["style_profile"], dict) and session["style_profile"].get("_warning"):
            session["memory_warning"] = session["style_profile"]["_warning"]
    except Exception as exc:
        session["style_profile"] = {
            "user_id": session["user_id"],
            "preferred_style_tags": [],
            "preferred_colors": [],
            "preferred_silhouettes": [],
            "preferred_categories": [],
            "budget_notes": None,
            "wardrobe_notes": None,
            "disliked_terms": [],
            "last_updated": None,
        }
        session["memory_warning"] = (
            "Style memory could not be loaded, so this answer only uses the "
            f"current query. ({exc})"
        )

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
    session["search_results"] = _rerank_with_style_profile(
        session["search_results"],
        session["style_profile"],
    )
    if not session["search_results"]:
        print("[BRANCH] search_listings returned no results")
        print("[TOOL CALL] _generate_no_results_message")
        print("[SKIP] estimate_price_fairness")
        print("[SKIP] suggest_outfit")
        print("[SKIP] create_fit_card")
        print("[SKIP] style_profile_memory update")
        session["error"] = _generate_no_results_message(session["parsed"])
        return session

    session["selected_item"] = session["search_results"][0]
    print("[DEBUG] selected_item stored in session:")
    print(session["selected_item"])
    print("[DEBUG] selected_item id before estimate_price_fairness:", id(session["selected_item"]))

    print("[TOOL CALL] estimate_price_fairness")
    print("[DEBUG] selected_item passed into estimate_price_fairness:")
    print(session["selected_item"])
    try:
        session["price_fairness"] = estimate_price_fairness(session["selected_item"])
    except Exception as exc:
        selected_item = (
            session["selected_item"]
            if isinstance(session["selected_item"], dict)
            else {}
        )
        session["price_fairness"] = {
            "item_id": selected_item.get("id"),
            "item_price": selected_item.get("price"),
            "comparison_count": 0,
            "average_comparable_price": None,
            "price_range": {"min": None, "max": None},
            "verdict": "not enough data",
            "reasoning": (
                "Could not estimate price fairness because the price tool failed "
                f"unexpectedly: {exc}"
            ),
        }
    print("[DEBUG] price_fairness stored in session:")
    print(session["price_fairness"])

    print("[TOOL CALL] suggest_outfit")
    print("wardrobe item count:", len(session["wardrobe"].get("items", [])))
    print("[DEBUG] selected_item passed into suggest_outfit:")
    print(session["selected_item"])
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
        style_profile=session["style_profile"],
    )
    print("[DEBUG] outfit_suggestion stored in session:")
    print(session["outfit_suggestion"])
    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        session["error"] = (
            "I found a listing, but couldn't create an outfit suggestion for it."
        )
        print("[SKIP] create_fit_card")
        print("[SKIP] style_profile_memory update")
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
        print("[SKIP] style_profile_memory update")
        return session

    print("[TOOL CALL] style_profile_memory update")
    profile_update = _extract_profile_update(
        query=session["query"],
        selected_item=session["selected_item"],
        outfit_suggestion=session["outfit_suggestion"],
    )
    try:
        session["style_profile"] = style_profile_memory(
            user_id=session["user_id"],
            action="update",
            profile_update=profile_update,
        )
        if isinstance(session["style_profile"], dict) and session["style_profile"].get("_warning"):
            session["memory_warning"] = session["style_profile"]["_warning"]
    except Exception as exc:
        session["memory_warning"] = (
            "This outfit worked, but I could not save your preferences for next "
            f"time. ({exc})"
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
