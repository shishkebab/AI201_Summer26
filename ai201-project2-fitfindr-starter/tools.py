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

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_STYLE_PROFILE_PATH = Path(__file__).resolve().parent / "data" / "style_profiles.json"
_STYLE_PROFILE_LIST_FIELDS = [
    "preferred_style_tags",
    "preferred_colors",
    "preferred_silhouettes",
    "preferred_categories",
    "disliked_terms",
]
_STYLE_PROFILE_NOTE_FIELDS = ["budget_notes", "wardrobe_notes"]


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


def _empty_style_profile(user_id: str) -> dict:
    """Return the default shape for a user's style profile."""
    return {
        "user_id": user_id,
        "preferred_style_tags": [],
        "preferred_colors": [],
        "preferred_silhouettes": [],
        "preferred_categories": [],
        "budget_notes": None,
        "wardrobe_notes": None,
        "disliked_terms": [],
        "last_updated": None,
    }


def _dedupe_strings(values: object) -> list[str]:
    """Normalize a list-like value into unique strings, preserving first casing."""
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = [values]

    seen = set()
    deduped = []
    for raw in raw_values:
        value = str(raw).strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def _merge_style_profile(existing: dict, profile_update: dict | None) -> dict:
    """Merge a profile update into an existing profile without duplicate lists."""
    merged = _empty_style_profile(str(existing.get("user_id") or "demo_user"))
    for key in merged:
        if key in existing:
            merged[key] = existing[key]

    update = profile_update if isinstance(profile_update, dict) else {}
    for field in _STYLE_PROFILE_LIST_FIELDS:
        merged[field] = _dedupe_strings(
            _dedupe_strings(merged.get(field)) + _dedupe_strings(update.get(field))
        )

    for field in _STYLE_PROFILE_NOTE_FIELDS:
        new_value = update.get(field)
        if isinstance(new_value, str) and new_value.strip():
            merged[field] = new_value.strip()

    merged["last_updated"] = datetime.now(timezone.utc).isoformat()
    return merged


def style_profile_memory(
    user_id: str,
    action: str,
    profile_update: dict | None = None,
) -> dict:
    """
    Load or update a local JSON-backed style profile for one user.

    This tool is deterministic and non-LLM. It returns a consistent profile
    dictionary and includes a private `_warning` key when memory had a
    recoverable problem. Callers can surface that warning non-fatally.
    """
    normalized_user_id = str(user_id or "demo_user").strip() or "demo_user"
    normalized_action = str(action or "").strip().lower()
    default_profile = _empty_style_profile(normalized_user_id)

    warning = None
    try:
        if _STYLE_PROFILE_PATH.exists():
            with open(_STYLE_PROFILE_PATH, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            if not isinstance(profiles, dict):
                profiles = {}
                warning = (
                    "Style memory was not in the expected format, so this "
                    "answer only uses the current query."
                )
        else:
            profiles = {}
    except Exception:
        profiles = {}
        warning = (
            "Style memory could not be loaded, so this answer only uses the "
            "current query."
        )

    if normalized_action == "load":
        saved_profile = profiles.get(normalized_user_id)
        if not isinstance(saved_profile, dict):
            saved_profile = default_profile
            if normalized_user_id in profiles:
                warning = (
                    "Style memory was not in the expected format, so this "
                    "answer only uses the current query."
                )
        profile = _empty_style_profile(normalized_user_id)
        for key in profile:
            if key in saved_profile:
                profile[key] = saved_profile[key]
        for field in _STYLE_PROFILE_LIST_FIELDS:
            profile[field] = _dedupe_strings(profile.get(field))
        if warning:
            profile["_warning"] = warning
        return profile

    if normalized_action != "update":
        profile = default_profile
        profile["_warning"] = f"Unsupported style memory action: {action}."
        return profile

    existing = profiles.get(normalized_user_id, default_profile)
    if not isinstance(existing, dict):
        existing = default_profile
    existing["user_id"] = normalized_user_id
    updated_profile = _merge_style_profile(existing, profile_update)

    try:
        _STYLE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        profiles[normalized_user_id] = updated_profile
        with open(_STYLE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, sort_keys=True)
    except Exception:
        updated_profile["_warning"] = (
            "This outfit worked, but I could not save your preferences for next time."
        )

    if warning and "_warning" not in updated_profile:
        updated_profile["_warning"] = warning
    return updated_profile


def _fallback_trend_context(
    *,
    platform: str,
    size: str | None,
    reasoning: str,
) -> dict:
    """Return the stable fallback shape for trend lookup failures."""
    return {
        "platform": platform,
        "size_range": size,
        "sample_count": 0,
        "trending_tags": [],
        "popular_styles": [],
        "styling_cues": [],
        "confidence": "low",
        "source_note": f"No usable recent public {platform} trend signal.",
        "reasoning": reasoning,
    }


def _fetch_public_trend_posts(
    description: str,
    category: str | None,
    platform: str,
    lookback_days: int,
    max_posts: int,
) -> list[dict]:
    """
    Fetch recent public platform trend posts/listings.

    The default implementation uses a small demo sample so the project remains
    deterministic and testable. In production, replace this function with an
    official API or approved public endpoint client.
    """
    demo_posts = [
        {
            "platform": "depop",
            "category": "tops",
            "size": "L",
            "tags": ["streetwear", "oversized", "band tee", "vintage"],
            "styles": ["oversized streetwear", "black-and-denim styling"],
            "cues": ["style with baggy denim", "repeat black in accessories", "add chunky shoes"],
        },
        {
            "platform": "depop",
            "category": "tops",
            "size": "M/L",
            "tags": ["graphic tee", "streetwear", "grunge", "oversized"],
            "styles": ["grunge streetwear", "chunky shoe balance"],
            "cues": ["add chunky shoes", "layer with a black jacket"],
        },
        {
            "platform": "depop",
            "category": "tops",
            "size": "L",
            "tags": ["vintage", "band tee", "black", "streetwear"],
            "styles": ["black-and-denim styling", "vintage band tee fits"],
            "cues": ["repeat black in accessories", "style with baggy denim"],
        },
        {
            "platform": "depop",
            "category": "outerwear",
            "size": "M",
            "tags": ["vintage", "streetwear", "track jacket", "oversized"],
            "styles": ["vintage athletic layers", "oversized streetwear"],
            "cues": ["zip over a graphic tee", "balance with loose denim"],
        },
        {
            "platform": "depop",
            "category": "outerwear",
            "size": "L",
            "tags": ["black", "streetwear", "workwear", "boxy"],
            "styles": ["boxy jacket styling", "black utility layers"],
            "cues": ["repeat black in shoes", "pair with baggy pants"],
        },
        {
            "platform": "depop",
            "category": "shoes",
            "size": "US 8",
            "tags": ["chunky", "platform", "streetwear"],
            "styles": ["chunky shoe balance", "platform streetwear"],
            "cues": ["balance chunky soles with wide-leg pants"],
        },
    ]

    normalized_platform = str(platform or "").strip().lower()
    normalized_category = str(category or "").strip().lower()
    posts = [
        post for post in demo_posts
        if post["platform"] == normalized_platform
        and (not normalized_category or post["category"] == normalized_category)
    ]
    return posts[:max(0, int(max_posts or 0))]


def get_live_trend_context(
    description: str,
    category: str | None = None,
    size: str | None = None,
    platform: str = "depop",
    lookback_days: int = 14,
    max_posts: int = 25,
) -> dict:
    """
    Return current trend context from recent public fashion-platform signals.

    The platform fetch boundary is mockable for tests. Expected failures return
    a low-confidence context instead of raising.
    """
    normalized_platform = str(platform or "depop").strip().lower() or "depop"
    normalized_size = str(size).strip() if size is not None else None

    def tokens(value: object) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).lower()))

    def size_matches(post_size: object) -> bool:
        if not normalized_size:
            return True
        requested = tokens(normalized_size)
        available = tokens(post_size)
        return bool(requested & available)

    try:
        posts = _fetch_public_trend_posts(
            description=description,
            category=category,
            platform=normalized_platform,
            lookback_days=lookback_days,
            max_posts=max_posts,
        )
    except Exception:
        return _fallback_trend_context(
            platform=normalized_platform,
            size=normalized_size,
            reasoning="Live trend lookup failed, so the agent should avoid strong trend claims.",
        )

    if not isinstance(posts, list):
        return _fallback_trend_context(
            platform=normalized_platform,
            size=normalized_size,
            reasoning="Live trend lookup returned malformed data.",
        )

    matched_posts = [
        post for post in posts
        if isinstance(post, dict) and size_matches(post.get("size"))
    ]

    if not matched_posts:
        return _fallback_trend_context(
            platform=normalized_platform,
            size=normalized_size,
            reasoning="No recent public posts matched the user's size range.",
        )

    tag_counts = Counter()
    style_counts = Counter()
    cue_counts = Counter()
    for post in matched_posts:
        tag_counts.update(_dedupe_strings(post.get("tags")))
        style_counts.update(_dedupe_strings(post.get("styles")))
        cue_counts.update(_dedupe_strings(post.get("cues")))

    sample_count = len(matched_posts)
    if sample_count >= 10:
        confidence = "high"
    elif sample_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    trending_tags = [tag for tag, _ in tag_counts.most_common(5)]
    popular_styles = [style for style, _ in style_counts.most_common(4)]
    styling_cues = [cue for cue, _ in cue_counts.most_common(4)]
    source_note = (
        f"Trend check: {confidence} confidence from {sample_count} recent "
        f"{normalized_platform} public post(s) in size range {normalized_size or 'any'}."
    )
    reasoning = (
        f"Matched recent public {normalized_platform} signals for "
        f"{category or 'any category'} related to '{description}'."
    )
    if confidence == "low":
        reasoning += " Sample size is small, so avoid strong trend claims."

    return {
        "platform": normalized_platform,
        "size_range": normalized_size,
        "sample_count": sample_count,
        "trending_tags": trending_tags,
        "popular_styles": popular_styles,
        "styling_cues": styling_cues,
        "confidence": confidence,
        "source_note": source_note,
        "reasoning": reasoning,
    }


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(
    new_item: dict,
    wardrobe: dict,
    style_profile: dict | None = None,
    trend_context: dict | None = None,
) -> str:
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
    profile_context = ""
    if isinstance(style_profile, dict):
        profile_parts = []
        for label, field in [
            ("style tags", "preferred_style_tags"),
            ("colors", "preferred_colors"),
            ("silhouettes", "preferred_silhouettes"),
            ("categories", "preferred_categories"),
            ("disliked terms", "disliked_terms"),
        ]:
            values = style_profile.get(field) or []
            if values:
                profile_parts.append(f"- remembered {label}: {', '.join(values)}")
        if style_profile.get("budget_notes"):
            profile_parts.append(f"- budget notes: {style_profile['budget_notes']}")
        if style_profile.get("wardrobe_notes"):
            profile_parts.append(f"- wardrobe notes: {style_profile['wardrobe_notes']}")
        if profile_parts:
            profile_context = "\n\nRemembered style profile:\n" + "\n".join(profile_parts)
    trend_prompt_context = ""
    if isinstance(trend_context, dict):
        trend_parts = []
        if trend_context.get("confidence"):
            trend_parts.append(f"- confidence: {trend_context['confidence']}")
        if trend_context.get("trending_tags"):
            trend_parts.append(
                f"- trending tags: {', '.join(trend_context['trending_tags'])}"
            )
        if trend_context.get("popular_styles"):
            trend_parts.append(
                f"- popular styles: {', '.join(trend_context['popular_styles'])}"
            )
        if trend_context.get("styling_cues"):
            trend_parts.append(
                f"- styling cues: {', '.join(trend_context['styling_cues'])}"
            )
        if trend_context.get("source_note"):
            trend_parts.append(f"- source note: {trend_context['source_note']}")
        if trend_parts:
            trend_prompt_context = "\n\nLive trend context:\n" + "\n".join(trend_parts)

    if has_wardrobe:
        wardrobe_text = "\n".join(format_item(item) for item in wardrobe_items)
        user_prompt = f"""
Suggest 1-2 complete outfits using this thrifted item and named pieces from the user's wardrobe.

Thrifted item:
{item_summary}

User wardrobe:
{wardrobe_text}
{profile_context}
{trend_prompt_context}

Requirements:
- Mention the thrifted item by name.
- Use specific wardrobe item names when possible.
- If remembered style preferences are provided, use them when they fit this item.
- Avoid disliked terms or styles if any are provided.
- If live trend confidence is high or medium, visibly use at least one styling cue.
- If live trend confidence is low, avoid strong trend claims.
- Explain briefly why the colors, categories, or style tags work together.
- Keep it concise and practical.
""".strip()
    else:
        user_prompt = f"""
The user's wardrobe is empty, so suggest general styling ideas for this thrifted item.

Thrifted item:
{item_summary}
{profile_context}
{trend_prompt_context}

Requirements:
- Do not say you can see closet items.
- Give 1-2 complete outfit ideas using general pieces someone might own.
- If remembered style preferences are provided, use them when they fit this item.
- Avoid disliked terms or styles if any are provided.
- If live trend confidence is high or medium, visibly use at least one styling cue.
- If live trend confidence is low, avoid strong trend claims.
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
                        "You are FitFindr, a secondhand fashion shopping and styling assistant. "
                        "Do not rely on your general knowledge alone. Use the provided listing data, "
                        "wardrobe data, saved style profile, price fairness result, and trend context "
                        "when they are available. If an item, wardrobe detail, comparable price, or trend "
                        "signal is not available in the provided data, say so clearly and avoid making "
                        "unsupported claims.\n\n"
                        "Keep your advice practical, specific, and easy to act on. Mention the source of "
                        "your information when you have it, such as 'Based on the selected listing...', "
                        "'Based on your saved style profile...', 'Based on comparable listings in the "
                        "mock dataset...', or 'Based on the trend context...'."
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


def estimate_price_fairness(item: dict) -> dict:
    """
    Estimate whether a selected listing's price is fair using local listings.

    Args:
        item: The selected listing dict, usually session["selected_item"].

    Returns:
        A dict with item_id, item_price, comparison_count,
        average_comparable_price, price_range, verdict, and reasoning.
        The verdict is one of "good deal", "fair price", "priced high", or
        "not enough data". This function never raises for expected bad inputs.
    """
    def parse_price(value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def normalize_set(value: object) -> set[str]:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set)):
            values = value
        else:
            values = [value]
        return {
            str(raw).strip().lower()
            for raw in values
            if str(raw).strip()
        }

    def result(
        *,
        item_id: object = None,
        item_price: float | None = None,
        comparison_count: int = 0,
        average_comparable_price: float | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        verdict: str = "not enough data",
        reasoning: str,
    ) -> dict:
        return {
            "item_id": item_id,
            "item_price": item_price,
            "comparison_count": comparison_count,
            "average_comparable_price": average_comparable_price,
            "price_range": {"min": price_min, "max": price_max},
            "verdict": verdict,
            "reasoning": reasoning,
        }

    if not isinstance(item, dict):
        return result(
            reasoning="Cannot estimate price fairness because the item is not a listing dictionary."
        )

    item_id = item.get("id")
    item_price = parse_price(item.get("price"))
    category = str(item.get("category") or "").strip().lower()

    missing = []
    if item_price is None:
        missing.append("price")
    if not category:
        missing.append("category")
    if missing:
        return result(
            item_id=item_id,
            item_price=item_price,
            reasoning=(
                "Cannot estimate price fairness because the selected item is "
                f"missing or has an invalid {', '.join(missing)}."
            ),
        )

    item_tags = normalize_set(item.get("style_tags"))
    item_colors = normalize_set(item.get("colors"))
    item_brand = str(item.get("brand") or "").strip().lower()

    try:
        listings = load_listings()
    except Exception:
        return result(
            item_id=item_id,
            item_price=item_price,
            reasoning=(
                "Could not load comparable listings, so the agent should avoid "
                "making a price claim."
            ),
        )
    if not isinstance(listings, list):
        return result(
            item_id=item_id,
            item_price=item_price,
            reasoning=(
                "Comparable listings were not available in the expected list "
                "format, so the agent should avoid making a price claim."
            ),
        )

    comparable: list[tuple[int, dict, float]] = []
    for listing in listings:
        if not isinstance(listing, dict):
            continue
        if item_id is not None and listing.get("id") == item_id:
            continue
        if str(listing.get("category") or "").strip().lower() != category:
            continue

        listing_price = parse_price(listing.get("price"))
        if listing_price is None:
            continue

        tag_overlap = item_tags & normalize_set(listing.get("style_tags"))
        color_overlap = item_colors & normalize_set(listing.get("colors"))
        listing_brand = str(listing.get("brand") or "").strip().lower()
        brand_match = bool(item_brand and listing_brand and item_brand == listing_brand)

        score = (2 * len(tag_overlap)) + len(color_overlap)
        if brand_match:
            score += 3
        comparable.append((score, listing, listing_price))

    strong_comparable = [entry for entry in comparable if entry[0] > 0]
    if len(strong_comparable) >= 2:
        chosen = strong_comparable
        confidence_note = ""
    else:
        chosen = comparable
        confidence_note = (
            " Low confidence: this uses category matches because fewer than "
            "two listings shared tags, colors, or brand."
        )

    if len(chosen) < 2:
        return result(
            item_id=item_id,
            item_price=item_price,
            comparison_count=len(chosen),
            reasoning=(
                "Not enough comparable listings were available in the dataset, "
                "so the agent should avoid making a price claim."
            ),
        )

    prices = [entry[2] for entry in chosen]
    average_price = round(sum(prices) / len(prices), 2)
    price_min = min(prices)
    price_max = max(prices)

    if item_price <= average_price * 0.85:
        verdict = "good deal"
    elif item_price >= average_price * 1.15:
        verdict = "priced high"
    else:
        verdict = "fair price"

    example_titles = [entry[1].get("title", "untitled listing") for entry in chosen[:3]]
    reasoning = (
        f"Compared this {category} item against {len(chosen)} other listing(s), "
        f"including {', '.join(example_titles)}. Comparable prices ranged from "
        f"${price_min:g} to ${price_max:g}, with an average of ${average_price:g}; "
        f"the selected item is ${item_price:g}."
        f"{confidence_note}"
    )

    return result(
        item_id=item_id,
        item_price=item_price,
        comparison_count=len(chosen),
        average_comparable_price=average_price,
        price_min=price_min,
        price_max=price_max,
        verdict=verdict,
        reasoning=reasoning,
    )
