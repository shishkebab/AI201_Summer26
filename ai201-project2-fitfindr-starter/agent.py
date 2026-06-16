"""
agent.py

FitFindr's LLM tool-calling planning loop. The public run_agent() contract stays
the same: it returns a session dict for the Gradio app to render.
"""

import json
import re

from config import DEFAULT_USER_ID, LLM_MODEL, MAX_TOOL_ROUNDS
from tools import (
    _get_groq_client,
    create_fit_card,
    estimate_price_fairness,
    get_live_trend_context,
    retry_search_with_fallback,
    search_listings,
    style_profile_memory,
    suggest_outfit,
)


SYSTEM_PROMPT = (
    "You are FitFindr, a secondhand fashion shopping and styling assistant. "
    "Use the available tools to search listings, retry failed searches, check "
    "price fairness, get trend context, suggest an outfit, and create a fit card. "
    "Do not invent listing details, prices, trend signals, or wardrobe items. "
    "If search_listings returns no results, call retry_search_with_fallback before "
    "giving up. You choose one approved retry strategy at a time: remove_size, "
    "raise_price, remove_size_and_raise_price, simplify_description, "
    "broaden_style_terms, or stop. Do not repeat a failed strategy. If retry "
    "also fails or you choose stop, explain what was tried and suggest broader "
    "search terms, a different size, or raising the budget. When calling tools, "
    "never pass null for optional string fields like size; use 'any' instead. Keep the final "
    "response brief because the app displays structured panels from session state."
)

APPROVED_RETRY_STRATEGIES = [
    "remove_size",
    "raise_price",
    "remove_size_and_raise_price",
    "simplify_description",
    "broaden_style_terms",
    "stop",
]


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": (
                "Search the local secondhand listings dataset. Use first for any "
                "shopping request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Item description keywords, such as vintage graphic tee.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional size filter. Omit for any size.",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Optional maximum price. Omit for no price ceiling.",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retry_search_with_fallback",
            "description": (
                "Execute one approved retry strategy after search_listings returns "
                "no results. Choose exactly one strategy: remove_size, raise_price, "
                "remove_size_and_raise_price, simplify_description, "
                "broaden_style_terms, or stop. Do not repeat strategies already "
                "listed in previous_attempts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "size": {"type": "string"},
                    "max_price": {"type": "number"},
                    "strategy": {
                        "type": "string",
                        "enum": APPROVED_RETRY_STRATEGIES,
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this retry strategy fits the failed search.",
                    },
                    "previous_attempts": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Retry attempts already made in this interaction.",
                    },
                },
                "required": ["description", "strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_price_fairness",
            "description": (
                "Estimate whether the selected listing's price is fair. Use after "
                "a listing has been selected."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_live_trend_context",
            "description": (
                "Get public fashion trend context for the selected item and size. "
                "Use before suggesting the outfit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "default": "depop"},
                    "lookback_days": {"type": "integer", "default": 14},
                    "max_posts": {"type": "integer", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_outfit",
            "description": (
                "Suggest an outfit using the selected listing, wardrobe, style "
                "profile, and trend context. Use after selecting a listing."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_fit_card",
            "description": (
                "Create a short fit-card caption from the outfit suggestion and "
                "selected listing. Use after suggest_outfit succeeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def _new_session(
    query: str,
    wardrobe: dict,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Initialize a fresh session dict for one FitFindr interaction."""
    return {
        "user_id": user_id,
        "query": query,
        "parsed": {},
        "search_results": [],
        "search_retry": None,
        "search_adjustments": [],
        "search_retry_message": None,
        "selected_item": None,
        "wardrobe": wardrobe,
        "style_profile": None,
        "memory_warning": None,
        "price_fairness": None,
        "trend_context": None,
        "outfit_suggestion": None,
        "fit_card": None,
        "final_response": None,
        "error": None,
    }


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


def _extract_profile_update(
    query: str,
    selected_item: dict,
    outfit_suggestion: str,
    trend_context: dict | None = None,
) -> dict:
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

    if isinstance(trend_context, dict) and trend_context.get("confidence") in {"high", "medium"}:
        update["preferred_style_tags"].extend(trend_context.get("trending_tags") or [])
        update["preferred_silhouettes"].extend(trend_context.get("popular_styles") or [])

    if "baggy jeans" in combined_text or "chunky sneakers" in combined_text:
        update["wardrobe_notes"] = "User likes baggy jeans and chunky sneakers."

    return update


def _fallback_trend_context(parsed: dict, selected_item: dict, reason: str) -> dict:
    """Return a non-fatal trend context when live trend lookup fails."""
    size = parsed.get("size") or selected_item.get("size")
    return {
        "platform": selected_item.get("platform", "depop"),
        "size_range": size,
        "sample_count": 0,
        "trending_tags": [],
        "popular_styles": [],
        "styling_cues": [],
        "confidence": "low",
        "source_note": "No usable recent public trend signal.",
        "reasoning": reason,
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
        "Try broadening the item description, removing the size filter, or "
        "raising the max price."
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
            model=LLM_MODEL,
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
        )
        message = response.choices[0].message.content.strip()
        if message:
            return message
    except Exception:
        pass

    return fallback


def _log_python_tool_call(tool_name: str, tool_args: dict) -> None:
    """Print the concrete arguments passed into a Python tool function."""
    args_text = json.dumps(tool_args, default=str)
    suffix = "..." if len(args_text) > 500 else ""
    print(f"[PYTHON TOOL CALL] {tool_name}({args_text[:500]}{suffix})")


def _log_tool_result(tool_name: str, result: object) -> None:
    """Print a compact tool result trace for terminal verification."""
    result_text = json.dumps(result, default=str)
    suffix = "..." if len(result_text) > 300 else ""
    print(f"[TOOL RESULT] {tool_name}: {result_text[:300]}{suffix}")


def _log_tool_skip(tool_name: str, reason: str) -> None:
    """Print a compact skipped-tool trace."""
    print(f"[TOOL SKIP] {tool_name}: {reason}")


def _json_result(result: object) -> str:
    """Serialize a tool result for the Groq tool-result message."""
    return json.dumps(result, default=str)


def _coerce_float(value: object) -> float | None:
    """Convert optional numeric tool args to float."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object, default: int) -> int:
    """Convert optional integer tool args to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_tool_args(raw_arguments: object) -> dict:
    """Parse Groq tool-call arguments into a safe dictionary."""
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _select_first_result(session: dict) -> None:
    """Store the top search result as the selected item when available."""
    if session.get("search_results"):
        session["selected_item"] = session["search_results"][0]


def _default_profile(user_id: str) -> dict:
    """Return the default shape used when style memory fails to load."""
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


def dispatch_tool(tool_name: str, tool_args: dict, session: dict) -> str:
    """Route one LLM tool call to the matching Python tool and update session."""
    tool_args = tool_args if isinstance(tool_args, dict) else {}

    if session.get("error") and tool_name not in {"search_listings", "retry_search_with_fallback"}:
        result = {"error": "Skipped because the interaction already has an error."}
        _log_tool_skip(tool_name, result["error"])
        return _json_result(result)

    try:
        if tool_name == "search_listings":
            parsed_defaults = session.get("parsed") or _parse_query(session["query"])
            description = str(tool_args.get("description") or parsed_defaults["description"])
            size = tool_args.get("size", parsed_defaults.get("size"))
            max_price = _coerce_float(tool_args.get("max_price", parsed_defaults.get("max_price")))
            session["parsed"] = {
                "description": description,
                "size": size,
                "max_price": max_price,
            }
            _log_python_tool_call(
                "search_listings",
                {
                    "description": description,
                    "size": size,
                    "max_price": max_price,
                },
            )
            results = search_listings(description=description, size=size, max_price=max_price)
            session["search_results"] = _rerank_with_style_profile(
                results,
                session.get("style_profile"),
            )
            _select_first_result(session)
            result = {
                "result_count": len(session["search_results"]),
                "results": session["search_results"][:5],
                "selected_item": session["selected_item"],
                "parsed": session["parsed"],
                "approved_retry_strategies": (
                    APPROVED_RETRY_STRATEGIES if not session["search_results"] else []
                ),
                "next_step": (
                    "Call retry_search_with_fallback."
                    if not session["search_results"]
                    else "Call estimate_price_fairness."
                ),
            }

        elif tool_name == "retry_search_with_fallback":
            parsed = session.get("parsed") or _parse_query(session["query"])
            existing_retry = session.get("search_retry")
            previous_attempts = []
            if isinstance(existing_retry, dict):
                previous_attempts = existing_retry.get("attempted_queries") or []
            provided_previous_attempts = tool_args.get("previous_attempts")
            if isinstance(provided_previous_attempts, list):
                previous_attempts = provided_previous_attempts
            retry_args = {
                "description": str(tool_args.get("description") or parsed.get("description") or ""),
                "size": tool_args.get("size", parsed.get("size")),
                "max_price": _coerce_float(tool_args.get("max_price", parsed.get("max_price"))),
                "strategy": tool_args.get("strategy") or "stop",
                "reason": tool_args.get("reason") or "",
                "previous_attempts": previous_attempts,
            }
            _log_python_tool_call("retry_search_with_fallback", retry_args)
            retry_result = retry_search_with_fallback(
                **retry_args,
            )
            session["search_retry"] = retry_result
            session["search_retry_message"] = retry_result.get("message")
            if retry_result.get("recovered"):
                session["search_results"] = _rerank_with_style_profile(
                    retry_result.get("results", []),
                    session.get("style_profile"),
                )
                session["search_adjustments"] = retry_result.get("adjustments", [])
                _select_first_result(session)
            elif retry_result.get("next_step") == "stop_no_results":
                retry_message = retry_result.get(
                    "message",
                    "I tried loosening the search but still found no matches.",
                )
                session["error"] = (
                    f"{retry_message}\n\n{_generate_no_results_message(parsed)}"
                )
            else:
                retry_result["approved_retry_strategies"] = APPROVED_RETRY_STRATEGIES
            result = retry_result

        elif tool_name == "estimate_price_fairness":
            if not isinstance(session.get("selected_item"), dict):
                result = {"error": "No selected item is available for price fairness."}
            else:
                _log_python_tool_call(
                    "estimate_price_fairness",
                    {"item": session["selected_item"]},
                )
                session["price_fairness"] = estimate_price_fairness(session["selected_item"])
                result = session["price_fairness"]

        elif tool_name == "get_live_trend_context":
            if not isinstance(session.get("selected_item"), dict):
                result = {"error": "No selected item is available for trend lookup."}
            else:
                parsed = session.get("parsed") or _parse_query(session["query"])
                selected_item = session["selected_item"]
                try:
                    trend_args = {
                        "description": parsed.get("description") or session["query"],
                        "category": selected_item.get("category"),
                        "size": parsed.get("size") or selected_item.get("size"),
                        "platform": tool_args.get("platform") or selected_item.get("platform", "depop"),
                        "lookback_days": _coerce_int(tool_args.get("lookback_days"), 14),
                        "max_posts": _coerce_int(tool_args.get("max_posts"), 25),
                    }
                    _log_python_tool_call("get_live_trend_context", trend_args)
                    session["trend_context"] = get_live_trend_context(
                        **trend_args,
                    )
                except Exception as exc:
                    session["trend_context"] = _fallback_trend_context(
                        parsed,
                        selected_item,
                        f"Live trend lookup failed unexpectedly: {exc}",
                    )
                result = session["trend_context"]

        elif tool_name == "suggest_outfit":
            if not isinstance(session.get("selected_item"), dict):
                result = {"error": "No selected item is available for outfit suggestion."}
            else:
                outfit_args = {
                    "new_item": session["selected_item"],
                    "wardrobe": session["wardrobe"],
                    "style_profile": session.get("style_profile"),
                    "trend_context": session.get("trend_context"),
                }
                _log_python_tool_call("suggest_outfit", outfit_args)
                session["outfit_suggestion"] = suggest_outfit(
                    **outfit_args,
                )
                if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
                    session["error"] = (
                        "I found a listing, but couldn't create an outfit suggestion for it."
                    )
                result = {"outfit_suggestion": session["outfit_suggestion"]}

        elif tool_name == "create_fit_card":
            if not isinstance(session.get("selected_item"), dict):
                result = {"error": "No selected item is available for fit card creation."}
            else:
                fit_card_args = {
                    "outfit": session.get("outfit_suggestion") or "",
                    "new_item": session["selected_item"],
                }
                _log_python_tool_call("create_fit_card", fit_card_args)
                session["fit_card"] = create_fit_card(
                    **fit_card_args,
                )
                if not session["fit_card"] or not session["fit_card"].strip():
                    session["error"] = (
                        "I created an outfit suggestion, but couldn't create a fit card."
                    )
                result = {"fit_card": session["fit_card"]}

        else:
            result = {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        result = {
            "error": f"Tool call failed for {tool_name}.",
            "message": str(exc),
        }

    _log_tool_result(tool_name, result)
    return _json_result(result)


def _build_context_message(session: dict) -> str:
    """Build a compact context message for the outer planning LLM."""
    wardrobe_items = []
    if isinstance(session.get("wardrobe"), dict):
        wardrobe_items = session["wardrobe"].get("items", []) or []
    style_profile = session.get("style_profile") or {}
    parsed = session.get("parsed") or _parse_query(session["query"])
    return (
        "Current FitFindr session context:\n"
        f"- parsed defaults: {json.dumps(parsed, default=str)}\n"
        f"- wardrobe item count: {len(wardrobe_items)}\n"
        f"- remembered style tags: {style_profile.get('preferred_style_tags', [])}\n"
        f"- remembered colors: {style_profile.get('preferred_colors', [])}\n"
        "Call tools in this expected order unless a tool result requires retry: "
        "search_listings, retry_search_with_fallback if needed, "
        "estimate_price_fairness, get_live_trend_context, suggest_outfit, "
        "create_fit_card."
    )


def _load_style_memory(session: dict) -> None:
    """Load style memory before the tool-calling loop."""
    _log_python_tool_call(
        "style_profile_memory",
        {
            "user_id": session["user_id"],
            "action": "load",
            "profile_update": None,
        },
    )
    try:
        session["style_profile"] = style_profile_memory(
            user_id=session["user_id"],
            action="load",
            profile_update=None,
        )
        if isinstance(session["style_profile"], dict) and session["style_profile"].get("_warning"):
            session["memory_warning"] = session["style_profile"]["_warning"]
    except Exception as exc:
        session["style_profile"] = _default_profile(session["user_id"])
        session["memory_warning"] = (
            "Style memory could not be loaded, so this answer only uses the "
            f"current query. ({exc})"
        )
    _log_tool_result("style_profile_memory load", session["style_profile"])


def _update_style_memory(session: dict) -> None:
    """Update style memory after a successful fit card."""
    if not session.get("fit_card") or not isinstance(session.get("selected_item"), dict):
        return
    profile_update = _extract_profile_update(
        query=session["query"],
        selected_item=session["selected_item"],
        outfit_suggestion=session.get("outfit_suggestion") or "",
        trend_context=session.get("trend_context"),
    )
    _log_python_tool_call(
        "style_profile_memory",
        {
            "user_id": session["user_id"],
            "action": "update",
            "profile_update": profile_update,
        },
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
    _log_tool_result("style_profile_memory update", session["style_profile"])


def _finalize_session(session: dict) -> None:
    """Make sure app-required state is coherent before returning."""
    if session.get("error"):
        return
    if not isinstance(session.get("selected_item"), dict):
        session["error"] = _generate_no_results_message(
            session.get("parsed") or _parse_query(session["query"])
        )
        return
    if not session.get("outfit_suggestion"):
        session["error"] = "I found a listing, but couldn't create an outfit suggestion for it."
        return
    if not session.get("fit_card"):
        session["error"] = "I created an outfit suggestion, but couldn't create a fit card."


def run_agent(
    query: str,
    wardrobe: dict,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Run the FitFindr automatic tool-calling agent and return the session."""
    session = _new_session(query, wardrobe, user_id)

    if not query or not query.strip():
        session["error"] = "Please enter what kind of item you want to find."
        return session

    session["parsed"] = _parse_query(query)
    _load_style_memory(session)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_context_message(session)},
        {"role": "user", "content": query},
    ]

    try:
        client = _get_groq_client()
    except Exception as exc:
        session["error"] = (
            "I couldn't reach the FitFindr planning model. Please check the "
            f"Groq API key and try again. ({exc})"
        )
        return session

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=250,
            )
        except Exception as exc:
            session["error"] = (
                "I couldn't reach the FitFindr planning model. Please try again. "
                f"({exc})"
            )
            return session

        if not response.choices:
            session["error"] = "The FitFindr planning model returned no choices."
            return session

        assistant_message = response.choices[0].message
        tool_calls = getattr(assistant_message, "tool_calls", None)
        if not tool_calls:
            session["final_response"] = getattr(assistant_message, "content", None) or ""
            break

        messages.append(assistant_message)
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = _safe_tool_args(tool_call.function.arguments)
            tool_result = dispatch_tool(tool_name, tool_args, session)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )
    else:
        session["error"] = (
            "I reached the maximum number of tool-calling steps. Please try "
            "rephrasing your search."
        )
        return session

    _finalize_session(session)
    if not session.get("error"):
        _update_style_memory(session)
    return session


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== FitFindr tool-calling path ===\n")
    result = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Found: {result['selected_item']['title']}")
        print(f"\nOutfit: {result['outfit_suggestion']}")
        print(f"\nFit card: {result['fit_card']}")
