# FitFindr - planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation ??the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed ??add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand listings dataset for items that match the user's requested clothing description, optional size, and maximum price. The implementation should call `load_listings()` from `utils/data_loader.py` and filter the returned listing dictionaries rather than reading `data/listings.json` directly.

**Input parameters:**
- `description` (str): The user's item/style request, such as `"vintage graphic tee"` or `"chunky black shoes"`; match this against listing `title`, `description`, `category`, `style_tags`, `colors`, and `brand`.
- `size` (str or None): The requested size, such as `"M"`, `"W30"`, or `"US 8"`; use `None` if the user did not specify a size so size filtering is skipped.
- `max_price` (float): The highest price the user wants to pay; only return listings where `price <= max_price`.

**What it returns:**
A list of listing dictionaries sorted from strongest to weakest match. Each result should include the original listing fields from `load_listings()`: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`, plus an optional `match_reason` string explaining why the listing matched the user's request. For the example query, likely matches include `lst_006` ("Graphic Tee - 2003 Tour Bootleg Style") and `lst_033` ("Vintage Band Tee - Faded Grey") because both are graphic/vintage tees under $30.

**What happens if it fails or returns nothing:**
If no listings match, return an empty list and have the agent tell the user that no matching listings were found. The agent should not call `suggest_outfit` or `create_fit_card`; instead, it should suggest relaxing one or more constraints, such as raising the budget, using broader style terms, or leaving size open.

---

### Tool 2: suggest_outfit

**What it does:**
Builds an outfit around one selected listing by pairing it with compatible items from the user's wardrobe. The implementation should accept a wardrobe in the same structure returned by `get_example_wardrobe()` or `get_empty_wardrobe()` from `utils/data_loader.py`.

**Input parameters:**
- `new_item` (dict): One listing dictionary returned by `search_listings`; it should contain at least `id`, `title`, `category`, `style_tags`, `colors`, `size`, `condition`, `price`, and `platform`.
- `wardrobe` (dict): A wardrobe dictionary with an `items` key containing a list of wardrobe item dictionaries; each wardrobe item should have `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty outfit suggestion string. When the wardrobe has items, the string should name the selected thrifted item, name specific wardrobe pieces to pair with it, and briefly explain why the colors, categories, or style tags work together. When the wardrobe is empty, the string should give general styling advice for the selected item instead of returning an empty string or raising an exception.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty or no wardrobe pieces coordinate with the selected listing, return a non-empty general styling suggestion string. The agent should still show the listing to the user and explain in the outfit text that it could not create a closet-specific outfit because there were no usable wardrobe items.

---

### Tool 3: create_fit_card

**What it does:**
Formats a completed outfit recommendation into a short, shareable fit card caption that the agent can show to the user. It should turn the outfit suggestion string from `suggest_outfit` plus the selected listing into a readable shopping-and-styling summary.

**Input parameters:**
- `outfit` (str): The non-empty outfit suggestion string returned by `suggest_outfit`.
- `new_item` (dict): The selected listing dictionary from `search_listings`; it provides the item title, price, platform, size, condition, colors, and style tags for the caption.

**What it returns:**
A 2-3 sentence fit card caption string suitable for an Instagram or TikTok outfit post. The caption should mention the selected item title, price, and platform naturally once each, describe the outfit vibe, and sound casual rather than like a product listing.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, return a descriptive error message string instead of raising an exception. If the LLM call fails or returns no caption, return a plain-text fallback string that includes the selected listing and outfit suggestion.

---

### Additional Tools (if any)

### Tool 4: estimate_price_fairness

**What it does:**
Estimates whether a selected secondhand listing is a good deal, fairly priced, or priced high compared with similar listings in the mock dataset. The implementation should call `load_listings()` from `utils/data_loader.py` and compare against listings with the same category first, then use overlapping `style_tags`, `colors`, and `brand` to find stronger comparable items.

**Input parameters:**
- `item` (dict): The selected listing dictionary, usually `session["selected_item"]`; it should include `id`, `title`, `category`, `price`, `condition`, `style_tags`, `colors`, `brand`, and `platform`.

**What it returns:**
A price fairness dictionary with `item_id`, `item_price`, `comparison_count`, `average_comparable_price`, `price_range`, `verdict`, and `reasoning`. `price_range` should include the minimum and maximum prices among comparable listings. `verdict` should be one of `"good deal"`, `"fair price"`, `"priced high"`, or `"not enough data"`. `reasoning` should briefly explain which comparable listings were used and why the verdict was chosen.

**What happens if it fails or returns nothing:**
If `item` is missing required fields like `price` or `category`, return a result with `verdict = "not enough data"` and explain which fields were missing. If there are no comparable listings, return `verdict = "not enough data"` and have the agent avoid making a strong price claim. If there are only weak comparisons, return the best estimate but include low-confidence wording in `reasoning`.

### Tool 5: style_profile_memory

**What it does:**
Stores and retrieves a user's style preferences across interactions so the user does not need to repeat the same style context every time. The implementation should use a local JSON-backed memory file, such as `data/style_profiles.json`, and should store lightweight preference data only: favorite style tags, colors, silhouettes, categories, budget notes, wardrobe notes, and disliked terms if the user mentions any.

**Input parameters:**
- `user_id` (str): Stable identifier for the user. For the demo app, use `"demo_user"` because there is no login system.
- `action` (str): Either `"load"` or `"update"`. `"load"` retrieves the saved profile before search and styling; `"update"` merges new preferences after a successful outfit interaction.
- `profile_update` (dict | None): New preference data to merge when `action="update"`. It can include `preferred_style_tags` (list[str]), `preferred_colors` (list[str]), `preferred_silhouettes` (list[str]), `preferred_categories` (list[str]), `budget_notes` (str | None), `wardrobe_notes` (str | None), and `disliked_terms` (list[str]).

**What it returns:**
A style profile dictionary with `user_id`, `preferred_style_tags`, `preferred_colors`, `preferred_silhouettes`, `preferred_categories`, `budget_notes`, `wardrobe_notes`, `disliked_terms`, and `last_updated`. If no saved profile exists yet, return an empty default profile with list fields set to `[]` and note fields set to `None`.

**What happens if it fails or returns nothing:**
If no saved profile exists, return the empty default profile and continue. If the memory file cannot be read, return the empty default profile and set a non-fatal warning so the agent can continue without memory. If the memory file cannot be written during an update, keep the current outfit result, set `session["memory_warning"]`, and tell the user that preferences could not be saved for next time.

### Tool 6: get_live_trend_context

**What it does:**
Checks recent public posts, listings, or tags from a public fashion platform to identify styles currently popular in the user's size range. The implementation should use public or approved platform access only, such as an official API, public search endpoint, or a mockable platform client for testing. This tool should not replace the user's request, wardrobe, or style profile; it should provide current trend context that visibly influences `suggest_outfit`.

**Input parameters:**
- `description` (str): The parsed item description from `session["parsed"]["description"]`, such as `"vintage graphic tee"` or `"jacket"`.
- `category` (str | None): The selected listing category, such as `"tops"`, `"outerwear"`, `"bottoms"`, `"shoes"`, or `"accessories"`.
- `size` (str | None): The user's requested size from `session["parsed"]["size"]`, or the selected listing size if the user did not request a size.
- `platform` (str): Public fashion platform to check, such as `"depop"` or another supported platform.
- `lookback_days` (int): How recent the checked posts, listings, or tags should be, such as `7` or `14`.
- `max_posts` (int): Maximum number of recent public posts, listings, or tags to inspect.

**What it returns:**
A trend context dictionary with `platform`, `size_range`, `sample_count`, `trending_tags`, `popular_styles`, `styling_cues`, `confidence`, `source_note`, and `reasoning`. `trending_tags` should contain popular tags found in the sampled public posts, such as `"streetwear"`, `"oversized"`, `"y2k"`, or `"gorpcore"`. `popular_styles` should translate those tags into human-readable style directions. `styling_cues` should contain concrete outfit cues to pass into `suggest_outfit`, such as `"style with baggy denim"`, `"add chunky shoes"`, or `"repeat black in accessories"`. `confidence` should be `"high"`, `"medium"`, or `"low"` depending on sample size and size-range match quality.

**What happens if it fails or returns nothing:**
If the platform request fails, times out, is rate-limited, or returns malformed data, return a fallback trend context with `confidence = "low"`, `sample_count = 0`, empty `trending_tags`, empty `popular_styles`, and reasoning that live trend data was unavailable. If recent posts exist but none match the user's size range, return `confidence = "low"` and tell the agent not to make a strong trend claim. If only a small number of posts match, return the best available cues but mark the result as low confidence. The agent should never stop the interaction because trend lookup failed.

### Tool 7: retry_search_with_fallback

**What it does:**
Executes one LLM-selected retry strategy after `search_listings` returns no results. In the automatic tool-calling agent, `dispatch_tool()` tells the LLM which approved retry strategies are available, and the LLM chooses the next strategy based on the failed filters and the user's wording. Python still validates the strategy, transforms the search parameters safely, calls `search_listings()` once, records the attempted query, and prevents repeated or unsafe retries.

**Input parameters:**
- `description` (str): The parsed item description from `session["parsed"]["description"]`.
- `size` (str | None): The parsed size from `session["parsed"]["size"]`.
- `max_price` (float | None): The parsed max price from `session["parsed"]["max_price"]`.
- `strategy` (str): One LLM-selected approved strategy: `"remove_size"`, `"raise_price"`, `"remove_size_and_raise_price"`, `"simplify_description"`, `"broaden_style_terms"`, or `"stop"`.
- `reason` (str): Short explanation of why the LLM chose this strategy.
- `previous_attempts` (list[dict] | None): Retry attempts already made in this interaction so the LLM and Python do not repeat the same strategy.

**What it returns:**
A retry result dictionary with `results`, `strategy`, `reason`, `adjustments`, `attempted_query`, `attempted_queries`, `recovered`, `message`, and `next_step`.
- `results` (list[dict]): Matching listing dictionaries from the first successful fallback search, or `[]` if all attempts fail.
- `strategy` (str): The approved strategy that was executed.
- `reason` (str): The LLM's explanation for choosing that strategy.
- `adjustments` (list[str]): Human-readable changes made by the selected strategy, such as `"removed size filter"` or `"raised max price by 25%"`.
- `attempted_query` (dict): The single query attempted by this call, including `description`, `size`, `max_price`, `strategy`, `adjustments`, `result_count`, and optional `error`.
- `attempted_queries` (list[dict]): All retry attempts so far, including previous attempts plus the current `attempted_query`.
- `recovered` (bool): `True` if a fallback search found results.
- `message` (str): The user-facing explanation of what was adjusted or what was tried before failing.
- `next_step` (str): Guidance for the LLM, such as `"continue_to_price_fairness"`, `"choose_another_retry_strategy"`, or `"stop_no_results"`.

**Approved retry strategies:**
- `"remove_size"`: Remove the size filter but keep the same description and max price.
- `"raise_price"`: Keep the same description and size, but raise `max_price` by 25%.
- `"remove_size_and_raise_price"`: Remove the size filter and raise `max_price` by 25%.
- `"simplify_description"`: Simplify the item description, remove size, and use the raised price if available.
- `"broaden_style_terms"`: Replace narrow style words with broader category/style terms, such as `"vintage graphic tee"` to `"graphic tee"` or `"tee"`.
- `"stop"`: Do not retry because loosening constraints would ignore the user's intent too much or the retry limit has been reached.

**LLM decision guidance:**
If the user specified a size strongly, try `"raise_price"` before removing size. If the user said `"must be size XS"` or `"only XS"`, do not remove size unless no other reasonable strategy remains. If the budget sounded flexible, `"raise_price"` is allowed, but the final message must say the budget was loosened. If the description is very specific, choose `"simplify_description"` or `"broaden_style_terms"`. Do not repeat a strategy already in `attempted_queries`. Stop after three failed retry strategies.

**What happens if it fails or returns nothing:**
If the LLM passes an unapproved strategy, return `recovered = False`, `next_step = "choose_another_retry_strategy"`, and a message explaining the valid strategy names. If the selected retry search returns no results, append the failed attempt and return `next_step = "choose_another_retry_strategy"` unless three failed retry strategies have already been attempted. If the LLM chooses `"stop"` or the retry limit is reached, return `next_step = "stop_no_results"` so `dispatch_tool()` can set `session["error"]`. The tool should never raise for normal retry failure; exceptions from `search_listings()` are recorded in `attempted_query["error"]`.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent now uses a PlantAdvisor-style automatic LLM tool-calling loop while preserving the same public contract: `run_agent(query, wardrobe, user_id="demo_user")` returns a session dictionary. Python still creates `_new_session()`, loads `style_profile_memory(..., action="load")`, parses default `description`, `size`, and `max_price` values with regex, then sends `SYSTEM_PROMPT`, compact session context, the user query, and `TOOL_DEFINITIONS` to Groq.

The LLM decides which tool to request next. Each requested tool call is routed through `dispatch_tool(tool_name, tool_args, session)`, which calls the real Python function, mutates the session dict, logs the call/result, and returns a JSON tool-result message back to the LLM. The expected successful order is `search_listings`, `retry_search_with_fallback` if search has no results, `estimate_price_fairness`, `get_live_trend_context`, `suggest_outfit`, and `create_fit_card`.

`dispatch_tool()` owns state safety. When the LLM calls `search_listings`, dispatch stores `session["parsed"]`, stores and style-profile-reranks `session["search_results"]`, and sets `session["selected_item"] = session["search_results"][0]` if results exist. If `search_listings` returns `[]`, the JSON tool result includes `next_step = "Call retry_search_with_fallback."`, the approved retry strategy names, and no selected item.

For retry, the LLM chooses one approved strategy and passes it to `retry_search_with_fallback`. If the retry recovers results, dispatch stores `session["search_retry"]`, `session["search_adjustments"]`, `session["search_retry_message"]`, recovered `session["search_results"]`, re-ranks the recovered results with style memory, and sets `session["selected_item"] = session["search_results"][0]`. If that strategy fails but the retry limit has not been reached, dispatch stores the attempt and returns JSON with `next_step = "choose_another_retry_strategy"` so the LLM can choose a different strategy. If the LLM chooses `"stop"` or three retry strategies have failed, dispatch sets `session["error"]` using the retry message plus the no-results helper, and downstream tools are skipped.

For supporting context tools, dispatch uses the session rather than trusting the LLM to pass large objects. `estimate_price_fairness` reads `session["selected_item"]` and stores `session["price_fairness"]`; `get_live_trend_context` reads the parsed description and selected item and stores `session["trend_context"]`; `suggest_outfit` reads `selected_item`, `wardrobe`, `style_profile`, and `trend_context` and stores `session["outfit_suggestion"]`; `create_fit_card` reads `outfit_suggestion` and `selected_item` and stores `session["fit_card"]`.

When the LLM stops calling tools, its final text is stored in `session["final_response"]`. Python then finalizes the session: if no selected item, outfit, or fit card exists, it sets a controlled `session["error"]`; if a fit card exists, it updates style memory with `style_profile_memory(..., action="update")`. If the planning LLM fails, returns no choices, calls too many tool rounds, passes malformed tool arguments, or calls an unknown tool, the agent returns a controlled session result instead of crashing.

---

## State Management

**How does information from one tool get passed to the next?**
`run_agent(query, wardrobe, user_id="demo_user")` creates one session dict with `_new_session(query, wardrobe, user_id)` and keeps that dict as the single source of truth even though the LLM chooses tool calls. The session starts with `user_id`, `query`, `parsed = {}`, `search_results = []`, `search_retry = None`, `search_adjustments = []`, `search_retry_message = None`, `selected_item = None`, `wardrobe`, `style_profile = None`, `memory_warning = None`, `price_fairness = None`, `trend_context = None`, `outfit_suggestion = None`, `fit_card = None`, `final_response = None`, and `error = None`.

Before the LLM planning loop starts, Python loads style memory and parses default search values into `session["parsed"]`. The LLM receives those defaults in a compact context message, but `dispatch_tool()` still validates and stores actual tool arguments when each tool is called.

All tool-to-tool state is passed through the session by `dispatch_tool()`. `search_listings` stores parsed filters, matching listings, and the top selected item. `retry_search_with_fallback` appends LLM-selected retry attempts to `session["search_retry"]["attempted_queries"]`, stores recovered results when a strategy works, or leaves `session["error"]` unset while the LLM may choose another strategy. `estimate_price_fairness`, `get_live_trend_context`, `suggest_outfit`, and `create_fit_card` read the already-stored state they need and write their outputs back to `price_fairness`, `trend_context`, `outfit_suggestion`, and `fit_card`.

When the LLM returns final text instead of another tool call, the agent stores that text in `session["final_response"]`. The Gradio app still reads the same structured fields as before; if `final_response` exists, it can be displayed as a short FitFindr note in the listing/results panel. Style memory is updated only after `fit_card` exists, and memory failures set `session["memory_warning"]` without discarding the completed response.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| LLM planning loop | Groq is unavailable, returns no choices, exceeds `MAX_TOOL_ROUNDS`, or returns malformed tool-call arguments. | Return a controlled session error instead of crashing. Malformed tool arguments become `{}` and `dispatch_tool()` falls back to parsed defaults where possible. If max rounds are reached, set `session["error"]` asking the user to rephrase. |
| dispatch_tool | The LLM requests an unknown tool or asks for a tool before required state exists, such as `suggest_outfit` before `selected_item`. | Return a JSON error result for that tool call and keep the session intact. If `session["error"]` is already set, skip downstream tools and return a JSON skip/error result. |
| search_listings | No listings match the user's original `description`, `size`, and `max_price` filters, so the tool returns `[]`. | `dispatch_tool()` stores `session["search_results"] = []` and returns a JSON result telling the LLM to call `retry_search_with_fallback`. The JSON includes approved retry strategies so the LLM can choose one. It does not call outfit or fit-card tools without a selected item. |
| retry_search_with_fallback | The LLM selects an invalid strategy, repeats a previous strategy, the selected fallback returns no results, or the selected fallback raises an exception. | Validate the strategy against the approved list. Invalid or repeated strategies return JSON asking the LLM to choose another strategy. Failed retry searches are appended to `attempted_queries` and return `next_step = "choose_another_retry_strategy"` until three strategies have failed. If a strategy succeeds, store `search_retry`, recovered `search_results`, `search_adjustments`, `search_retry_message`, and `selected_item`, then let the LLM continue. If the LLM chooses `"stop"` or the retry limit is reached, set `session["error"]` with a message that says exactly what was tried and suggests broader item terms, a different size, or a higher budget. |
| estimate_price_fairness | The selected item is missing required fields such as `price` or `category`, no comparable listings exist in the dataset, or the only comparable listings are weak matches. | Do not treat this as a fatal error. Store the returned dictionary in `session["price_fairness"]`; if `verdict` is `"not enough data"`, the agent should say it cannot confidently judge whether the price is fair and should avoid phrases like "good deal" or "overpriced." If comparisons are weak, show the best available verdict with low-confidence wording in the listing/results panel and continue to `suggest_outfit`. |
| get_live_trend_context | The public platform request fails, times out, is rate-limited, returns malformed data, has no recent matches in the user's size range, or has too small a matching sample. | Do not treat this as fatal. Store a fallback trend context in `session["trend_context"]` with `confidence = "low"`, `sample_count = 0` if no usable data was found, and reasoning that live trend data was unavailable or too limited. Continue to `suggest_outfit`; the outfit should still use the selected item, wardrobe, and style profile, but should avoid strong trend claims. |
| style_profile_memory | No saved profile exists, the profile file cannot be read, or the profile file cannot be written after a successful outfit. | If no profile exists, return an empty default profile and continue normally. If loading fails, store the empty default profile in `session["style_profile"]`, set `session["memory_warning"] = "Style memory could not be loaded, so this answer only uses the current query."`, and continue. If saving fails after the fit card is created, keep the final response and set `session["memory_warning"] = "This outfit worked, but I could not save your preferences for next time."` |
| suggest_outfit | The wardrobe is empty, such as when the agent receives `get_empty_wardrobe()` with `items: []`. | Do not treat this as a fatal error. Keep `session["selected_item"]`, call `suggest_outfit` with the empty wardrobe, and store the returned general styling advice string in `session["outfit_suggestion"]`. The advice should tell the user that the agent found a listing but does not have closet items to pair it with yet, then offer a generic styling idea and invite the user to add wardrobe items for a more personal outfit. |
| create_fit_card | The outfit input is empty or whitespace-only, or the LLM cannot create a caption. | If `session["outfit_suggestion"]` is empty before calling the tool, set `session["error"]` and return early. If `create_fit_card` returns a fallback/error string, store that string in `session["fit_card"]` so the user still gets the selected listing and outfit suggestion in plain text. |

---

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

Shared configuration values live in `config.py`: `LLM_MODEL`, `MAX_TOOL_ROUNDS`, `DEFAULT_USER_ID`, and `GROQ_API_KEY`. The agent loop and LLM-backed tools should use `LLM_MODEL` instead of hardcoding the model string in multiple places.

---

## AI Tool Plan

**Milestone 3 - Individual tool implementations:**
For `search_listings`, I will give Claude the `Tool 1: search_listings` block from the Tools section, the `Error Handling` row for `search_listings`, and the `utils/data_loader.py` helper description that says to use `load_listings()`. I expect Claude to produce a Python function that accepts `description`, `size`, and `max_price`, loads listings through `load_listings()`, filters by all three inputs, sorts the strongest matches first, includes the original listing fields, and returns an empty list when nothing matches. Before using it, I will review the code to confirm it does not read `data/listings.json` directly, handles `size="any"`, checks price with `price <= max_price`, and searches title, description, category, style tags, colors, and brand; then I will test it with three queries: one that should match graphic tees under $30, one that should match shoes under $50, and one impossible query that should return `[]`.

For `suggest_outfit`, I will give Claude the `Tool 2: suggest_outfit` block, the wardrobe schema from `data/wardrobe_schema.json`, and the `A Complete Interaction` Step 2 example. I expect Claude to produce a Python function that accepts a selected listing and a wardrobe dict, calls the LLM, and returns a non-empty outfit suggestion string. Before using it, I will check that the function accepts wardrobes from both `get_example_wardrobe()` and `get_empty_wardrobe()`, does not crash when `items` is empty, and returns general styling advice when no closet-specific outfit can be created.

For `create_fit_card`, I will give Claude the `Tool 3: create_fit_card` block and the final output description from `A Complete Interaction`. I expect Claude to produce a Python function that accepts the outfit suggestion string from `suggest_outfit` plus the selected listing as `new_item`, then returns a 2-3 sentence fit card caption string. Before using it, I will verify that the generated code guards against an empty outfit string, preserves listing details like title, price, and platform in the prompt, and returns a clear error or fallback string instead of raising an exception.

For `estimate_price_fairness`, I will give Claude the `Tool 4: estimate_price_fairness` block, the `Error Handling` row for `estimate_price_fairness`, and the `data/listings.json` field shape. I expect Claude to produce a Python function that accepts the selected listing dict, calls `load_listings()` from `utils/data_loader.py`, finds comparable listings by category first and then stronger overlaps in style tags, colors, and brand, and returns a dictionary with `item_id`, `item_price`, `comparison_count`, `average_comparable_price`, `price_range`, `verdict`, and `reasoning`. Before using it, I will check that missing `price` or `category` returns `verdict = "not enough data"`, no comparable listings avoids a price claim, and weak comparisons include low-confidence wording.

For `style_profile_memory`, I will give Claude the `Tool 5: style_profile_memory` block, the `State Management` section, the `Error Handling` row for memory, and the two-interaction example from `A Complete Interaction`. I expect Claude to produce a deterministic JSON-backed helper, not an LLM call, that can load an empty default profile, merge preference updates without duplicating list values, write the profile back to `data/style_profiles.json`, and return a consistent profile dict. Before using it, I will check that it handles a missing profile file, malformed JSON, missing `user_id`, read failure, write failure, and repeated updates without crashing.

For `get_live_trend_context`, I will give Claude the `Tool 6: get_live_trend_context` block, the `Error Handling` row for trend lookup, and the `Architecture` section showing where trend context feeds into `suggest_outfit`. I expect Claude to produce a mockable public-platform lookup function that accepts `description`, `category`, `size`, `platform`, `lookback_days`, and `max_posts`, inspects recent public posts/listings/tags through approved access or a replaceable platform client, and returns `platform`, `size_range`, `sample_count`, `trending_tags`, `popular_styles`, `styling_cues`, `confidence`, `source_note`, and `reasoning`. Before using it, I will check that live failures, rate limits, malformed responses, no size-range matches, and tiny sample sizes all return low-confidence fallback dictionaries instead of raising.

For `retry_search_with_fallback`, I will give Claude the `Tool 7: retry_search_with_fallback` block, the `Planning Loop` branch for empty search results, and the `Error Handling` rows for `search_listings` and retry. I expect Claude to produce an LLM-guided retry executor that accepts one approved `strategy` selected by the LLM, validates the strategy, transforms the search parameters, calls `search_listings` once, records the attempted query with `result_count` or `error`, and returns JSON telling the LLM whether to continue, choose another retry strategy, or stop. Before using it, I will check that invalid or repeated strategies are rejected, the tool does not mutate `session["parsed"]`, search exceptions are recorded, and normal retry failures never crash the agent.

After Claude generates the seven functions, I will use Claude to integrate them into the project files and review them against the Tools section. Claude should make the code consistent with the existing project structure, import helper functions from `utils/data_loader.py`, keep style profile memory deterministic and local, keep live trend access behind a mockable client boundary, keep retry execution controlled by approved strategies, and avoid changing unrelated files. I will verify the milestone by running focused tests or manual function calls for successful search, retry recovered by each approved strategy, invalid retry strategy, repeated retry strategy, retry stop strategy, retry limit reached with attempted queries recorded, successful price fairness, missing-field price fairness, no-comparable price fairness, successful live trend lookup, trend fallback on platform failure, no size-range trend match, example wardrobe styling with trend cues, empty wardrobe styling, complete fit card creation, incomplete outfit fallback, style profile load with no existing memory, style profile update, and two sequential interactions where the second uses preferences saved by the first.

**Milestone 4 - Planning loop and state management:**
I will use Codex to implement a PlantAdvisor-style automatic LLM tool-calling loop while preserving `run_agent(query, wardrobe, user_id="demo_user") -> session dict`. I will give Codex the completed `Planning Loop`, `State Management`, `Error Handling`, `Architecture`, and `A Complete Interaction` sections. I expect it to create `config.py`, central `SYSTEM_PROMPT`, `TOOL_DEFINITIONS`, `dispatch_tool(tool_name, tool_args, session)`, centralized logging helpers, and a Groq loop that sends tool-result JSON messages back to the LLM.

I will use Claude as a reviewer by giving it the generated `agent.py` plus the same planning sections. I will ask Claude to check that the LLM controls tool order, but Python dispatch still enforces session safety: no outfit without `selected_item`, no fit card without `outfit_suggestion`, retry after no search results, controlled errors for unknown tools or malformed arguments, and memory update only after a successful fit card.

To verify the final planning loop, I will run tool-calling agent tests with a fake Groq client. The tests should cover: successful LLM tool-call sequence populates `selected_item`, `price_fairness`, `trend_context`, `outfit_suggestion`, `fit_card`, and `final_response`; no-results search followed by an LLM-selected recovered retry continues to outfit and fit-card generation; recovered retry stores `search_retry`, `search_adjustments`, `search_retry_message`, and attempted queries; failed retry returns JSON allowing the LLM to choose another strategy; retry stop or retry limit sets `session["error"]` and leaves downstream fields as `None`; unknown tool calls return JSON errors; malformed tool arguments fall back to parsed defaults; `MAX_TOOL_ROUNDS` returns a controlled error; and LLM unavailability returns a controlled error. I will also keep the individual tool tests for search, retry, price fairness, trend context, style memory, outfit generation, and fit-card generation.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish ??tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

FitFindr uses an automatic LLM tool-calling loop to search secondhand listings, pick an item, check price fairness, check trend context, style the item with the passed-in wardrobe, and create a fit card. For the example query, the LLM should first request `search_listings(description="vintage graphic tee", size=None, max_price=30)`. `dispatch_tool()` executes that Python tool, stores the returned listings in `session["search_results"]`, stores the top result in `session["selected_item"]`, and returns the tool result to the LLM as JSON. The LLM can then request `estimate_price_fairness`, `get_live_trend_context`, `suggest_outfit`, and `create_fit_card`; dispatch uses session state for the selected listing, wardrobe, style profile, and trend context instead of making the LLM pass those large objects around.

**Step 1:**
Python initializes the session, loads style memory, and parses defaults from the query: description = `"vintage graphic tee"`, size = `None`, and max price = 30. The LLM planning loop receives those defaults and requests `search_listings`. `dispatch_tool()` calls `search_listings(description="vintage graphic tee", size=None, max_price=30)`, re-ranks the results with style memory if useful, stores matches such as the black 2003 tour bootleg-style tee and faded grey vintage band tee in `session["search_results"]`, and sets `session["selected_item"] = session["search_results"][0]`.

**Step 2:**
The LLM requests `estimate_price_fairness`. `dispatch_tool()` ignores any need for the LLM to pass the item and instead uses the exact `session["selected_item"]`. It stores the returned dict in `session["price_fairness"]`. If comparable tees in the dataset show that $24 is close to the comparable average, the final output can say the listing looks fairly priced; if the tool returns `"not enough data"`, the final output avoids a strong deal claim.

**Step 3:**
The LLM requests `get_live_trend_context`. `dispatch_tool()` uses `session["parsed"]["description"]`, `session["selected_item"]["category"]`, the requested or selected size, and default platform settings to call the trend tool. It stores the returned dict in `session["trend_context"]`. If recent public platform tags return cues like `"style with baggy denim"` or `"add chunky shoes"`, those cues can visibly influence the outfit; if trend lookup is low-confidence, the final output avoids strong trend claims.

**Step 4:**
The LLM requests `suggest_outfit`. `dispatch_tool()` passes the selected listing, `session["wardrobe"]`, `session["style_profile"]`, and `session["trend_context"]` into the tool. The returned string is stored in `session["outfit_suggestion"]`; it should use named wardrobe pieces when available or general styling advice when the wardrobe is empty.

**Step 5:**
The LLM requests `create_fit_card`. `dispatch_tool()` calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])` and stores the returned caption or fallback string in `session["fit_card"]`. When the LLM stops requesting tools, its final text is stored as `session["final_response"]`, and Python updates style memory if `fit_card` exists.

**Final output to user:**
The user sees a short list of the best matching listings, with the top recommendation highlighted: "Graphic Tee - 2003 Tour Bootleg Style," size L, good condition, $24 on Depop. In the same listing/results panel, the user also sees the price fairness result, such as "Price check: fair price - $24 is close to the average comparable tee price in the dataset," plus a trend source note such as "Trend check: medium confidence from 18 recent Depop posts in this size range; oversized streetwear and black-and-denim styling are showing up often." They also see an outfit suggestion string plus a short fit card caption showing how to style it with their baggy straight-leg jeans, chunky white sneakers, vintage black denim jacket, and black crossbody bag.

**Fallback search example:**
If the user asks for `"vintage graphic tee size XS under $30"` and the first `search_listings` tool result has no exact matches, the JSON result tells the LLM that retry is available and lists the approved strategies. The LLM sees that size XS may be too restrictive and chooses `strategy="remove_size"` with a reason such as `"The item description and budget are reasonable, but size XS may be too restrictive in the mock dataset."` It requests `retry_search_with_fallback(description="vintage graphic tee", size="XS", max_price=30, strategy="remove_size", reason=<reason>)`.

If removing `size="XS"` finds the black 2003 tour bootleg-style graphic tee and the faded grey vintage band tee, `dispatch_tool()` stores those recovered results in `session["search_results"]`, stores `["removed size filter"]` in `session["search_adjustments"]`, stores the explanation in `session["search_retry_message"]`, records the attempt in `session["search_retry"]["attempted_queries"]`, and selects the first recovered item. The listing panel should show a note like, `"Search note: I did not find an exact size XS match, so I removed the size filter and found options under $30."` The LLM can then continue normally to price fairness, live trend context, outfit suggestion, fit card, and final response.

If `remove_size` fails, `dispatch_tool()` returns JSON with `next_step = "choose_another_retry_strategy"` and the existing `attempted_queries`. The LLM may then choose another approved strategy, such as `"raise_price"` if the budget seems flexible or `"simplify_description"` if the item wording is too narrow. If the LLM chooses `"stop"` or three retry strategies fail, `dispatch_tool()` stores the failed retry result and sets `session["error"]` to a message like, `"I could not find exact matches after trying to remove the size filter and raise the max price by 25%. Try a broader item name, a different size, or a higher budget."` The LLM should not call price fairness, trend, outfit, or fit-card tools after that error.

**Style profile memory example:**
Interaction 1 starts with no saved memory. The user says, "I like oversized streetwear, black pieces, baggy jeans, and chunky sneakers. Find me a vintage graphic tee under $30." The agent loads an empty default `style_profile`, completes the normal search, price check, outfit, and fit-card flow, then updates memory with preferences such as `preferred_style_tags = ["streetwear", "vintage", "graphic tee"]`, `preferred_colors = ["black"]`, `preferred_silhouettes = ["oversized", "baggy"]`, `preferred_categories = ["tops"]`, and `wardrobe_notes = "User likes baggy jeans and chunky sneakers."`

Interaction 2 happens later with the same `user_id = "demo_user"`. The user only says, "Find me a jacket under $50," without repeating their style preferences. The agent loads the saved `style_profile` before search, uses it to prefer jacket listings that overlap with remembered tags like `streetwear`, `vintage`, oversized shapes, and black or dark colors, then uses the same memory in the outfit prompt so the suggestion can mention baggy jeans and chunky sneakers even though the second query did not restate them.
