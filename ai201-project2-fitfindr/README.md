# FitFindr

FitFindr is a secondhand fashion shopping and styling agent. It searches mock resale listings, retries failed searches with LLM-selected fallback strategies, checks price fairness, adds trend context, suggests an outfit from the user's wardrobe, and creates a short fit card.

The implementation follows the design in `planning.md`: the outer agent is a Groq tool-calling loop, while Python `dispatch_tool()` owns session state and safety checks.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```text
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run tests:

```bash
python -m pytest -q
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description` (`str`), `size` (`str \| None = None`), `max_price` (`float \| None = None`) | `list[dict]` of matching listing dictionaries sorted by relevance | Searches local mock listings using `load_listings()`, filtering by optional size and price. Returns `[]` instead of raising when nothing matches. |
| `retry_search_with_fallback` | `description` (`str`), `size` (`str \| None = None`), `max_price` (`float \| None = None`), `strategy` (`str = "stop"`), `reason` (`str = ""`), `previous_attempts` (`list[dict] \| None = None`) | `dict` with `results`, `strategy`, `reason`, `adjustments`, `attempted_query`, `attempted_queries`, `recovered`, `message`, and `next_step` | Executes one LLM-selected approved retry strategy after search returns no results. Python validates the strategy and calls `search_listings()` once. |
| `style_profile_memory` | `user_id` (`str`), `action` (`str`), `profile_update` (`dict \| None = None`) | `dict` style profile with preferences and optional `_warning` | Loads or updates local JSON-backed style memory in `data/style_profiles.json`. |
| `get_live_trend_context` | `description` (`str`), `category` (`str \| None = None`), `size` (`str \| None = None`), `platform` (`str = "depop"`), `lookback_days` (`int = 14`), `max_posts` (`int = 25`) | `dict` with trend tags, styles, cues, confidence, source note, and reasoning | Returns mockable public fashion trend context. Current implementation uses deterministic demo posts behind a replaceable fetch boundary. |
| `suggest_outfit` | `new_item` (`dict`), `wardrobe` (`dict`), `style_profile` (`dict \| None = None`), `trend_context` (`dict \| None = None`) | `str` outfit suggestion | Calls the LLM to style the selected listing with wardrobe items, remembered style preferences, and trend cues. Handles empty wardrobes with general styling advice. |
| `create_fit_card` | `outfit` (`str`), `new_item` (`dict`) | `str` caption or fallback message | Calls the LLM to turn the outfit and listing into a short shareable fit-card caption. |
| `estimate_price_fairness` | `item` (`dict`) | `dict` with `item_id`, `item_price`, `comparison_count`, `average_comparable_price`, `price_range`, `verdict`, and `reasoning` | Compares the selected item against local comparable listings and returns `good deal`, `fair price`, `priced high`, or `not enough data`. |

## Planning Loop

`run_agent(query, wardrobe, user_id="demo_user")` returns a session dict. It does not return only a text answer because the Gradio app needs structured fields for the listing, outfit, and fit-card panels.

The loop works like this:

1. Python creates a new session and parses default search fields from the query: `description`, `size`, and `max_price`.
2. Python loads style memory with `style_profile_memory(..., action="load")`. If memory fails, it stores a default profile and continues.
3. The agent sends `SYSTEM_PROMPT`, compact session context, user query, and `TOOL_DEFINITIONS` to Groq.
4. The LLM chooses a tool call. Python routes it through `dispatch_tool(tool_name, tool_args, session)`.
5. If `search_listings` returns results, dispatch stores `search_results` and `selected_item`, then the LLM can call price, trend, outfit, and fit-card tools.
6. If `search_listings` returns `[]`, dispatch returns JSON with approved retry strategies. The LLM chooses one strategy for `retry_search_with_fallback`.
7. If retry recovers results, dispatch stores the recovered results and selected item, then the LLM continues.
8. If retry fails but more attempts are allowed, dispatch returns `next_step="choose_another_retry_strategy"` and does not set `session["error"]`.
9. If retry returns `next_step="stop_no_results"` or the retry limit is reached, dispatch sets `session["error"]` and downstream styling tools are skipped.
10. When the LLM stops requesting tools, its final text is stored in `session["final_response"]`.
11. Python finalizes the session. If `fit_card` exists, it updates style memory. If required state is missing, it stores a controlled error.

This conditional flow mirrors `planning.md`: the LLM decides what tool to request, but Python enforces state safety and never lets outfit generation proceed without a selected listing.

## Example Agent Walkthrough

Example query:

```text
I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?
```

1. Python initializes the session before the LLM chooses tools.
   `run_agent()` creates the session dict, stores the original query, parses default search values, and loads style memory. For this query, `session["parsed"]` becomes roughly `{"description": "vintage graphic tee", "size": None, "max_price": 30}`. This happens before tool calling so the LLM has useful defaults and Python has a reliable fallback if tool arguments are incomplete.

2. The LLM calls `search_listings` because the user first needs actual secondhand options.
   The LLM should request something like `search_listings(description="vintage graphic tee", size="any", max_price=30)`. `dispatch_tool()` runs the Python function, stores the matching listing dicts in `session["search_results"]`, re-ranks them with remembered style preferences if available, and stores the top result in `session["selected_item"]`. This selected item becomes the single item used by later tools.

3. If search fails, the LLM calls `retry_search_with_fallback` because no selected item exists yet.
   When `search_listings` returns `[]`, `dispatch_tool()` returns JSON telling the LLM retry is available and lists approved strategies. The LLM chooses one strategy, such as `remove_size`, `raise_price`, `remove_size_and_raise_price`, `simplify_description`, `broaden_style_terms`, or `stop`. Python validates that strategy, executes one fallback search, records the attempted query in `session["search_retry"]["attempted_queries"]`, and either stores recovered results or returns `next_step="choose_another_retry_strategy"`. If retry stops or reaches the retry limit, `session["error"]` is set and styling tools are skipped.

4. The LLM calls `estimate_price_fairness` because a selected listing now exists.
   The LLM does not need to pass the listing itself. `dispatch_tool()` uses `session["selected_item"]`, calls `estimate_price_fairness(item=session["selected_item"])`, and stores the returned dict in `session["price_fairness"]`. This gives the listing panel context like `fair price` or `not enough data` without blocking outfit generation.

5. The LLM calls `get_live_trend_context` because trend cues can improve the outfit suggestion.
   `dispatch_tool()` uses the parsed description, selected item category, requested or selected size, and platform defaults. The tool stores trend tags, popular styles, styling cues, confidence, and reasoning in `session["trend_context"]`. If trend lookup is low confidence, the session still continues; the outfit prompt is told to avoid strong trend claims.

6. The LLM calls `suggest_outfit` because the agent now has the selected item plus styling context.
   `dispatch_tool()` passes `session["selected_item"]`, `session["wardrobe"]`, `session["style_profile"]`, and `session["trend_context"]` into `suggest_outfit()`. The tool calls the LLM to produce an outfit suggestion. If the wardrobe has items, the suggestion should name specific closet pieces. If the wardrobe is empty, it returns general styling advice instead of crashing.

7. The LLM calls `create_fit_card` because an outfit suggestion now exists.
   `dispatch_tool()` calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. The returned caption or fallback text is stored in `session["fit_card"]`. This is the final user-facing caption shown in the fit-card panel.

8. The LLM stops calling tools and returns final text.
   The final text is stored in `session["final_response"]`. The app may show it as a short FitFindr note in the listing panel, but the main UI still uses structured session fields for the listing, outfit, and fit card.

9. Python updates style memory after a successful fit card.
   If `session["fit_card"]` exists, `run_agent()` extracts style preferences from the selected item, query, trend context, and outfit suggestion. It then calls `style_profile_memory(action="update")` so later interactions can reuse preferences such as black, vintage, streetwear, baggy silhouettes, or chunky sneakers.

## State Management

The session dict is the single source of truth. It stores:

- `user_id`: stable id for style memory
- `query`: original user query
- `parsed`: `description`, `size`, and `max_price`
- `search_results`: current listing matches
- `search_retry`: retry result dict, including attempted retry strategies
- `search_adjustments`: user-visible changes made by successful retry
- `search_retry_message`: message shown in the listing panel
- `selected_item`: top listing passed to downstream tools
- `wardrobe`: wardrobe passed into `run_agent()`
- `style_profile`: loaded or updated style memory
- `memory_warning`: non-fatal memory load/save warning
- `price_fairness`: price comparison result
- `trend_context`: trend lookup result
- `outfit_suggestion`: output from `suggest_outfit`
- `fit_card`: output from `create_fit_card`
- `final_response`: final text returned by the planning LLM
- `error`: controlled early-exit message

Tools do not pass large objects through the LLM. For example, the LLM requests `estimate_price_fairness`, but `dispatch_tool()` passes `session["selected_item"]` directly. The same pattern is used for trend lookup, outfit suggestion, and fit-card creation.

## Architecture

```text
User query + wardrobe
    |
    v
run_agent(query, wardrobe, user_id)
    |
    | _new_session()
    | parse default description / size / max_price
    | style_profile_memory(action="load")
    v
Session State
    parsed = {description, size, max_price}
    wardrobe = passed-in wardrobe
    style_profile = remembered or default profile
    selected_item = None
    fit_card = None
    error = None
    |
    v
Groq Planning Loop
    |
    | SYSTEM_PROMPT
    | compact session context
    | user query
    | TOOL_DEFINITIONS
    v
LLM chooses a tool call
    |
    v
dispatch_tool(tool_name, tool_args, session)
    |
    +-- search_listings(description, size, max_price)
    |       |
    |       +-- results = []
    |       |       |
    |       |       v
    |       |   JSON tool result:
    |       |   next_step = "Call retry_search_with_fallback."
    |       |
    |       +-- results = [item, ...]
    |               |
    |               v
    |           Session State
    |           search_results = reranked results
    |           selected_item = search_results[0]
    |
    +-- retry_search_with_fallback(description, size, max_price, strategy, reason)
    |       |
    |       | LLM chooses one approved strategy:
    |       | remove_size, raise_price,
    |       | remove_size_and_raise_price,
    |       | simplify_description,
    |       | broaden_style_terms, or stop
    |       |
    |       +-- recovered = true
    |       |       |
    |       |       v
    |       |   Session State
    |       |   search_retry = retry_result
    |       |   search_results = recovered results
    |       |   search_adjustments = retry adjustments
    |       |   attempted_queries = prior attempts + current attempt
    |       |   search_retry_message = user-facing note
    |       |   selected_item = search_results[0]
    |       |
    |       +-- recovered = false, next_step = choose_another_retry_strategy
    |       |       |
    |       |       v
    |       |   JSON tool result returns attempted_queries
    |       |   LLM chooses a different approved strategy
    |       |
    |       +-- strategy = stop or retry limit reached
    |               |
    |               v
    |           [ERROR]
    |           search_retry = retry_result with attempted_queries
    |           search_retry_message = "Tried removing size..."
    |           session.error = retry message + no-results helper
    |           downstream tools are skipped
    |
    +-- estimate_price_fairness()
    |       |
    |       v
    |   Session State
    |   price_fairness = result for selected_item
    |
    +-- get_live_trend_context()
    |       |
    |       v
    |   Session State
    |   trend_context = trend or low-confidence fallback
    |
    +-- suggest_outfit()
    |       |
    |       v
    |   Session State
    |   outfit_suggestion = wardrobe-specific or general styling string
    |
    +-- create_fit_card()
            |
            v
        Session State
        fit_card = caption or fallback string
    |
    v
JSON tool result returned to Groq
    |
    +-- LLM requests another tool
    |       |
    |       v
    |   repeat dispatch_tool(...)
    |
    +-- LLM returns final text
            |
            v
        Session State
        final_response = assistant text
            |
            v
Finalize Session
    |
    +-- missing selected_item / outfit / fit_card
    |       |
    |       v
    |   [ERROR] set controlled session.error
    |
    +-- fit_card exists
            |
            v
        style_profile_memory(action="update")
            |
            +-- save fails: memory_warning set, response kept
            |
            v
        Return session dict to app
```

## Error Handling

| Tool | Strategy | Concrete tested example |
|------|----------|-------------------------|
| `search_listings` | Returns `[]` instead of raising. The agent then asks the LLM to choose a retry strategy. | `test_search_empty_results` checks `"designer ballgown", size="XXS", max_price=5` returns `[]`. |
| `retry_search_with_fallback` | Invalid or repeated strategies return `next_step="choose_another_retry_strategy"`. `stop` or three failed retries return `stop_no_results`. Search exceptions are recorded in `attempted_query["error"]`. | Tests cover invalid strategy, repeated strategy, `stop`, third failed strategy, and a raised `"temporary search failure"`. |
| `style_profile_memory` | Missing memory returns a default profile. Malformed JSON returns a default profile with `_warning`. Invalid actions return a controlled warning. | `test_style_profile_memory_malformed_json_returns_safe_default` writes bad JSON and confirms no crash. |
| `get_live_trend_context` | Platform failures or no size match return low-confidence fallback context. | `test_get_live_trend_context_platform_failure_returns_fallback` monkeypatches a timeout and verifies `confidence == "low"`. |
| `suggest_outfit` | Empty wardrobe still returns general styling advice. LLM failure returns a deterministic fallback string. | `test_suggest_outfit_empty_wardrobe_handles_llm_failure` simulates a missing API key and gets a non-empty fallback. |
| `create_fit_card` | Empty outfit string returns a descriptive error message and does not call the LLM. LLM failure returns a plain-text fallback caption. | `test_create_fit_card_empty_outfit_returns_error` verifies whitespace input is handled safely. |
| `estimate_price_fairness` | Missing price/category or too few comparables returns `verdict="not enough data"` instead of raising. | `test_estimate_price_fairness_missing_price_returns_not_enough_data` confirms missing price is handled. |

Agent-level tests also cover LLM planning failures: unavailable Groq client, malformed tool arguments, max tool rounds, retry stop, retry limit, and downstream tools being skipped after final retry failure.

## Spec Reflection

One way the spec helped: `planning.md` forced the session keys and tool return shapes to be explicit before implementation. That made it much easier to test state flow, especially confirming that `selected_item` moves from search into price fairness, trend lookup, outfit suggestion, and fit-card creation.

One way implementation diverged: the original plan used a fixed Python retry order. But in orer to make LLM decides which parameters to be changed, retry was redesigned so the LLM chooses one approved strategy at a time while Python validates and executes it. This better matches the final architecture because the LLM owns planning decisions, but Python still prevents unsafe or repeated retries.

Another practical divergence: the trend-awareness tool is documented as checking public platform signals, but the implementation uses deterministic demo trend posts behind `_fetch_public_trend_posts()`. This keeps tests stable and avoids depending on external platform APIs during the project.

## AI Usage

1. After examining the implementation at later stage while writing the code with Claude, I realized that the entir process was deterministic, meaning that it follows a static flow instead of LLM deciding which tool to call. I directed AI to compare the FitFindr deterministic planning loop with the PlantAdvisor tool-calling loop and propose how to convert FitFindr while preserving the session dict contract. I kept the recommendation to preserve `run_agent() -> dict`, but revised the implementation so Python `dispatch_tool()` still controls state safety.

2. I directed Claude to design and implement the seventh retry tool. The first version used a fixed Python retry sequence. I later overrode that design because the agent architecture should let the LLM choose the retry strategy. The final version accepts approved strategies like `remove_size`, `raise_price`, and `broaden_style_terms`, while Python validates and executes them.

## Notes

- `data/style_profiles.json` is local memory and should not be treated as static dataset content.
- If the LLM passes `null` for optional string fields like `size`, Groq may reject the tool call before Python can normalize it. The system prompt now tells the LLM to use `"any"` instead of `null` for optional string fields.
