"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    def tokenize(value: object) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).lower()))

    def field_text(listing: dict, field: str) -> str:
        value = listing.get(field)
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value)

    query_tokens = tokenize(description)
    if not query_tokens:
        return []

    normalized_size = (size or "").strip().lower()
    should_filter_size = normalized_size not in {"", "any"}
    scored_listings: list[tuple[int, dict]] = []

    for listing in load_listings():
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        listing_size = str(listing.get("size", "")).lower()
        if should_filter_size and normalized_size not in listing_size:
            continue

        title_tokens = tokenize(field_text(listing, "title"))
        description_tokens = tokenize(field_text(listing, "description"))
        category_tokens = tokenize(field_text(listing, "category"))
        tag_tokens = tokenize(field_text(listing, "style_tags"))
        color_tokens = tokenize(field_text(listing, "colors"))
        brand_tokens = tokenize(field_text(listing, "brand"))

        score = 0
        score += 3 * len(query_tokens & title_tokens)
        score += 3 * len(query_tokens & tag_tokens)
        score += 2 * len(query_tokens & category_tokens)
        score += 2 * len(query_tokens & color_tokens)
        score += 2 * len(query_tokens & brand_tokens)
        score += len(query_tokens & description_tokens)

        if score > 0:
            scored_listings.append((score, listing))

    scored_listings.sort(
        key=lambda item: (
            item[0],
            -float(item[1].get("price", 0)),
            item[1].get("title", ""),
        ),
        reverse=True,
    )
    return [listing for _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    def format_item(item: dict) -> str:
        colors = ", ".join(item.get("colors", []) or ["unknown colors"])
        tags = ", ".join(item.get("style_tags", []) or ["no style tags"])
        notes = item.get("notes") or item.get("description") or "no extra notes"
        return (
            f"- {item.get('name') or item.get('title', 'Unnamed item')} "
            f"({item.get('category', 'unknown category')}; "
            f"colors: {colors}; style tags: {tags}; notes: {notes})"
        )

    item_colors = ", ".join(new_item.get("colors", []) or ["unknown colors"])
    item_tags = ", ".join(new_item.get("style_tags", []) or ["no style tags"])
    item_summary = (
        f"{new_item.get('title', 'Selected thrifted item')}\n"
        f"- category: {new_item.get('category', 'unknown')}\n"
        f"- size: {new_item.get('size', 'unknown')}\n"
        f"- condition: {new_item.get('condition', 'unknown')}\n"
        f"- price/platform: ${new_item.get('price', 'unknown')} on "
        f"{new_item.get('platform', 'unknown platform')}\n"
        f"- colors: {item_colors}\n"
        f"- style tags: {item_tags}\n"
        f"- description: {new_item.get('description', 'No description provided.')}"
    )

    wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
    has_wardrobe = bool(wardrobe_items)

    if has_wardrobe:
        wardrobe_text = "\n".join(format_item(item) for item in wardrobe_items)
        user_prompt = f"""
Suggest 1-2 complete outfits using this thrifted item and named pieces from the user's wardrobe.

Thrifted item:
{item_summary}

User wardrobe:
{wardrobe_text}

Requirements:
- Mention the thrifted item by name.
- Use specific wardrobe item names when possible.
- Explain briefly why the colors, categories, or style tags work together.
- Keep it concise and practical.
""".strip()
    else:
        user_prompt = f"""
The user's wardrobe is empty, so suggest general styling ideas for this thrifted item.

Thrifted item:
{item_summary}

Requirements:
- Do not say you can see closet items.
- Give 1-2 complete outfit ideas using general pieces someone might own.
- Mention that a more personal outfit is possible once wardrobe items are added.
- Explain briefly what vibe the item suits.
- Keep it concise and practical.
""".strip()

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are FitFindr, a concise secondhand fashion stylist. "
                        "Give useful outfit advice with specific pieces, colors, "
                        "and style reasoning. Avoid generic filler."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=450,
        )
        outfit = response.choices[0].message.content.strip()
        if outfit:
            return outfit
    except Exception:
        if has_wardrobe:
            return (
                "I could not reach the styling model, but this item should work "
                f"well with pieces from your wardrobe. Try {new_item.get('title', 'the thrifted item')} "
                f"with {wardrobe_items[0].get('name', 'a favorite closet piece')} and choose shoes "
                "or accessories that repeat one of the item's colors or style tags."
            )
        return (
            "I could not reach the styling model, but this item can still be styled "
            f"generally. Try {new_item.get('title', 'the thrifted item')} with a balanced basic, "
            "a complementary layer, and shoes that match its overall vibe."
        )

    if has_wardrobe:
        return (
            f"Try styling {new_item.get('title', 'the thrifted item')} with "
            f"{wardrobe_items[0].get('name', 'one of your wardrobe pieces')}. "
            "Use matching colors or shared style tags to choose shoes and accessories."
        )
    return (
        f"Try styling {new_item.get('title', 'the thrifted item')} with baggy jeans, "
        "chunky sneakers, and a denim or leather jacket. Add wardrobe items later "
        "for a more personal outfit suggestion."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "I couldn't create a fit card because the outfit suggestion was empty. "
            "Please generate an outfit suggestion first, then try creating the fit card again."
        )

    item_title = new_item.get("title", "the thrifted item")
    item_price = new_item.get("price", "unknown price")
    item_platform = new_item.get("platform", "unknown platform")
    item_colors = ", ".join(new_item.get("colors", []) or ["unknown colors"])
    item_tags = ", ".join(new_item.get("style_tags", []) or ["no style tags"])

    prompt = f"""
Write a short, shareable outfit caption for this thrifted find.

Thrifted item:
- title: {item_title}
- price: ${item_price}
- platform: {item_platform}
- category: {new_item.get('category', 'unknown')}
- size: {new_item.get('size', 'unknown')}
- condition: {new_item.get('condition', 'unknown')}
- colors: {item_colors}
- style tags: {item_tags}
- description: {new_item.get('description', 'No description provided.')}

Outfit suggestion:
{outfit.strip()}

Caption requirements:
- Write 2-3 sentences.
- Sound casual and authentic, like a real OOTD post.
- Mention the item name, price, and platform naturally exactly once each.
- Capture the outfit vibe with specific style language.
- Do not sound like a product listing or a formal ad.
""".strip()

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise, natural outfit captions for "
                        "secondhand fashion finds. Keep the tone casual, "
                        "specific, and social-media ready."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=180,
        )
        caption = response.choices[0].message.content.strip()
        if caption:
            return caption
    except Exception:
        return (
            "I couldn't create the fit card because the caption model was unavailable. "
            f"Plain-text fallback: style {item_title} from {item_platform} with this outfit: "
            f"{outfit.strip()}"
        )

    return (
        "I couldn't create the fit card because the caption model returned an empty response. "
        f"Plain-text fallback: style {item_title} with this outfit: {outfit.strip()}"
    )
