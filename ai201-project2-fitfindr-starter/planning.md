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

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent starts by calling `_new_session(query, wardrobe, user_id="demo_user")`, then calls `style_profile_memory(user_id=session["user_id"], action="load", profile_update=None)` and stores the returned profile in `session["style_profile"]`. If memory loading fails, store the empty default profile in `session["style_profile"]`, set `session["memory_warning"]`, and continue without stopping the interaction.

Next, parse the user message into `description`, `size`, and `max_price`. Use simple regex rather than an LLM because these fields are predictable, deterministic parsing is easier to test, and it avoids spending an LLM call before search. Plain string splitting alone is not enough because phrases like `"under $30"`, `"size M"`, `"US 8"`, and `"W30 L30"` need pattern matching.

The parser extracts `max_price` from patterns like `"under $30"` or `"$30"`, extracts `size` from patterns like `"size M"`, `"US 8"`, or waist sizes like `"W30"`, and builds `description` by removing the extracted price/size phrases from the original query. If the user does not provide a size, set `size = None`; if the user does not provide a maximum price, set `max_price = None`. Store these values in `session["parsed"]`.

First, call `search_listings(description=session["parsed"]["description"], size=session["parsed"]["size"], max_price=session["parsed"]["max_price"])` and store the return value as `session["search_results"]`. If `session["style_profile"]` contains preferred style tags, colors, categories, or disliked terms, use those preferences to break ties or re-rank matching listings after search; do not filter out all results just because they do not match memory. After `search_listings` runs, check whether `search_results` is empty. If it is empty, call an LLM-backed no-results message helper with `session["parsed"]`, store the returned message in `session["error"]`, then return the session early without calling `estimate_price_fairness`, `suggest_outfit`, `create_fit_card`, or the memory update step. If the LLM message helper fails, use a deterministic fallback that mentions the parsed description, size, max price, and concrete ways to broaden the search.

If `search_results` is not empty, set `session["selected_item"] = search_results[0]` because results are already sorted strongest to weakest match. Then call `estimate_price_fairness(item=session["selected_item"])` and store the returned dictionary as `session["price_fairness"]`. This tool is non-fatal: if it returns `verdict = "not enough data"` or low-confidence reasoning, keep that result in the session, avoid making a strong price claim, and continue to outfit generation.

Use the `wardrobe` argument already stored in `session["wardrobe"]`; do not load a separate wardrobe inside `run_agent`. Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])` and include `session["style_profile"]` as additional prompt context so the styling can reflect remembered preferences such as oversized fits, streetwear tags, black colors, or disliked terms. Store the returned string as `session["outfit_suggestion"]`.

After `suggest_outfit` runs, check whether `session["outfit_suggestion"]` is a non-empty string. If it is empty, set `session["error"]` to a helpful message saying the agent found a listing but could not create an outfit suggestion, then return the session early. If the wardrobe is empty, `suggest_outfit` should already return general styling advice, so the agent should continue as long as the string is non-empty.

Next, call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])` and store the returned string as `session["fit_card"]`. If `fit_card` is empty, set `session["error"]` to a helpful message saying the outfit was created but the fit card could not be generated and skip the memory update. If `fit_card` is non-empty, build a `profile_update` from the current query, selected item, wardrobe, and outfit suggestion: add selected listing `style_tags` to `preferred_style_tags`, selected listing `colors` to `preferred_colors`, selected listing `category` to `preferred_categories`, and simple query phrases like `"oversized"`, `"baggy"`, `"chunky sneakers"`, or `"minimal"` to `preferred_silhouettes` or `wardrobe_notes` when present. Call `style_profile_memory(user_id=session["user_id"], action="update", profile_update=profile_update)` and store the returned profile back in `session["style_profile"]`; if saving fails, set `session["memory_warning"]` but still return the selected item, price fairness, outfit suggestion, and fit card. The loop is done once the agent has either returned the no-results error session, returned an outfit-created-but-no-card error session, or returned a successful session containing `selected_item`, `price_fairness`, `outfit_suggestion`, `fit_card`, and updated `style_profile`.

---

## State Management

**How does information from one tool get passed to the next?**
`run_agent(query, wardrobe, user_id="demo_user")` creates one session dict with `_new_session(query, wardrobe, user_id)` and uses that dict as the single source of truth for the whole interaction. The session starts with `user_id`, `query`, `parsed = {}`, `search_results = []`, `selected_item = None`, `wardrobe`, `style_profile = None`, `memory_warning = None`, `price_fairness = None`, `outfit_suggestion = None`, `fit_card = None`, and `error = None`.

Before parsing, the agent loads memory with `style_profile_memory(user_id=session["user_id"], action="load", profile_update=None)` and stores the result in `session["style_profile"]`. If loading fails, it stores an empty default profile and sets `session["memory_warning"]`, but `session["error"]` remains `None` because memory is not required to complete the current request.

After parsing, the agent stores `session["parsed"] = {"description": description, "size": size, "max_price": max_price}`. Those parsed values are passed directly into `search_listings`, and the returned list is stored in `session["search_results"]`. If the list is empty, the agent uses the parsed values to generate `session["error"]` with an LLM-backed no-results helper, then returns the session immediately, leaving `selected_item`, `price_fairness`, `outfit_suggestion`, and `fit_card` as `None`. The loaded `style_profile` remains in the session for debugging, but it is not updated on a no-results run.

If search succeeds, the agent stores the top result as `session["selected_item"] = session["search_results"][0]`. That same selected listing is passed into `estimate_price_fairness`, and the returned dictionary is stored as `session["price_fairness"]`. The price fairness result is supporting context only, so even `"not enough data"` stays in the session and the agent continues.

The selected listing, `session["wardrobe"]`, and `session["style_profile"]` are used to build the `suggest_outfit` prompt, and the returned string is stored as `session["outfit_suggestion"]`. If that string is empty, the agent sets `session["error"]` and returns early with the selected item and price fairness result still available in the session. The agent does not update style memory when no outfit was created.

If the outfit suggestion is non-empty, the agent passes `session["outfit_suggestion"]` and `session["selected_item"]` into `create_fit_card`. The returned caption or fallback string is stored in `session["fit_card"]`. If `fit_card` is non-empty, the agent builds a `profile_update` from the query, selected item, and outfit suggestion, then calls `style_profile_memory(..., action="update", profile_update=profile_update)` and stores the returned profile in `session["style_profile"]`. If the update fails, set `session["memory_warning"]` and keep the completed user-facing response. On a successful run, `session["error"]` remains `None`, and the final session contains all data needed by the app: the original query, parsed filters, search results, selected listing, wardrobe, style profile, memory warning if any, price fairness result, outfit suggestion, and fit card. Because the app has three output panels, `session["price_fairness"]` should be displayed in the listing/results panel alongside the selected item rather than in a new panel.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the user's `description`, `size`, and `max_price` filters, so the tool returns `[]`. | Call the no-results message helper with `session["parsed"]`, store the returned user-facing message in `session["error"]`, and return early without calling `estimate_price_fairness`, `suggest_outfit`, or `create_fit_card`. The helper asks the LLM to explain what failed and suggest concrete search adjustments; if the LLM is unavailable, it falls back to a deterministic message that mentions the parsed filters and suggests broadening the description, removing the size filter, or raising the max price. |
| estimate_price_fairness | The selected item is missing required fields such as `price` or `category`, no comparable listings exist in the dataset, or the only comparable listings are weak matches. | Do not treat this as a fatal error. Store the returned dictionary in `session["price_fairness"]`; if `verdict` is `"not enough data"`, the agent should say it cannot confidently judge whether the price is fair and should avoid phrases like "good deal" or "overpriced." If comparisons are weak, show the best available verdict with low-confidence wording in the listing/results panel and continue to `suggest_outfit`. |
| style_profile_memory | No saved profile exists, the profile file cannot be read, or the profile file cannot be written after a successful outfit. | If no profile exists, return an empty default profile and continue normally. If loading fails, store the empty default profile in `session["style_profile"]`, set `session["memory_warning"] = "Style memory could not be loaded, so this answer only uses the current query."`, and continue. If saving fails after the fit card is created, keep the final response and set `session["memory_warning"] = "This outfit worked, but I could not save your preferences for next time."` |
| suggest_outfit | The wardrobe is empty, such as when the agent receives `get_empty_wardrobe()` with `items: []`. | Do not treat this as a fatal error. Keep `session["selected_item"]`, call `suggest_outfit` with the empty wardrobe, and store the returned general styling advice string in `session["outfit_suggestion"]`. The advice should tell the user that the agent found a listing but does not have closet items to pair it with yet, then offer a generic styling idea and invite the user to add wardrobe items for a more personal outfit. |
| create_fit_card | The outfit input is empty or whitespace-only, or the LLM cannot create a caption. | If `session["outfit_suggestion"]` is empty before calling the tool, set `session["error"]` and return early. If `create_fit_card` returns a fallback/error string, store that string in `session["fit_card"]` so the user still gets the selected listing and outfit suggestion in plain text. |

---

## Architecture

```text
User query
    |
    | raw text request
    v
Planning Loop
    |
    | _new_session(query, wardrobe, user_id="demo_user")
    v
style_profile_memory(user_id, action="load", profile_update=None)
    |
    +-- no saved profile
    |       |
    |       v
    |   Session State
    |   style_profile = empty default profile
    |
    +-- load fails
    |       |
    |       v
    |   Session State
    |   style_profile = empty default profile
    |   memory_warning = "Style memory could not be loaded..."
    |
    +-- load succeeds
            |
            v
        Session State
        style_profile = remembered preferences
    |
    | regex/string parse into parsed:
    | description, size, max_price
    v
Session State
    | parsed = {
    |   description: "...",
    |   size: None or requested size,
    |   max_price: None or number
    | }
    | wardrobe = passed-in wardrobe argument
    | style_profile = remembered or empty preferences
    |
    v
search_listings(description, size, max_price)
    |
    | uses load_listings()
    |
    +-- results = []
    |       |
    |       v
    |   generate_no_results_message(parsed)
    |       |
    |       +-- LLM succeeds:
    |       |   session.error = helpful search-refinement message
    |       |
    |       +-- LLM fails:
    |           session.error = deterministic fallback message
    |       |
    |       v
    |   Return session early without calling estimate_price_fairness, suggest_outfit, or create_fit_card
    |
    +-- results = [listing_1, listing_2, ...]
            |
            v
        Session State
        search_results = results
        optional re-rank/tie-break with style_profile
        selected_item = results[0]
            |
            | selected_item
            v
estimate_price_fairness(selected_item)
    |
    | uses load_listings() for comparable listings
    |
    +-- verdict = "not enough data"
    |       |
    |       v
    |   Session State
    |   price_fairness = {
    |     verdict: "not enough data",
    |     reasoning: "Cannot confidently judge price fairness."
    |   }
    |       |
    |       v
    |   continue without making a strong price claim
    |
    +-- verdict = "good deal", "fair price", or "priced high"
            |
            v
        Session State
        price_fairness = {
          item_price: number,
          comparison_count: number,
          average_comparable_price: number,
          verdict: "...",
          reasoning: "..."
        }
            |
            | selected_item + wardrobe + style_profile
            v
suggest_outfit(selected_item, wardrobe)
    |
    | wardrobe comes from run_agent(query, wardrobe)
    | style_profile adds remembered preferences to the prompt
    |
    +-- wardrobe.items = []
    |       |
    |       v
    |   Session State
    |   outfit_suggestion = general styling advice string
    |       |
    |       v
    |   continue to create_fit_card(outfit_suggestion, selected_item)
    |
    +-- outfit_suggestion = "" or None
    |       |
    |       v
    |   [ERROR]
    |   session.error = "Found a listing, but could not create an outfit suggestion."
    |       |
    |       v
    |   Return session early
    |
    +-- outfit_suggestion = non-empty string
            |
            v
        Session State
        outfit_suggestion = "..."
            |
            | outfit_suggestion + selected_item
            v
create_fit_card(outfit_suggestion, selected_item)
    |
    +-- fit_card = "" or None
    |       |
    |       v
    |   [ERROR]
    |   session.error = "Created an outfit, but could not create a fit card."
    |       |
    |       v
    |   Return session with selected_item + price_fairness + outfit_suggestion
    |
    +-- fit_card = caption or fallback string
            |
            v
        Session State
        fit_card = "..."
            |
            | build profile_update from query, selected_item,
            | outfit_suggestion, colors, style_tags, and category
            v
style_profile_memory(user_id, action="update", profile_update)
    |
    +-- save fails
    |       |
    |       v
    |   Session State
    |   memory_warning = "This outfit worked, but preferences could not be saved."
    |       |
    |       v
    |   Return final response anyway
    |
    +-- save succeeds
            |
            v
        Session State
        style_profile = updated remembered preferences
            |
            v
Return final response with selected_item, price_fairness, style_profile, outfit_suggestion, fit_card, and optional memory_warning
```

---

## AI Tool Plan

**Milestone 3 - Individual tool implementations:**
For `search_listings`, I will give Claude the `Tool 1: search_listings` block from the Tools section, the `Error Handling` row for `search_listings`, and the `utils/data_loader.py` helper description that says to use `load_listings()`. I expect Claude to produce a Python function that accepts `description`, `size`, and `max_price`, loads listings through `load_listings()`, filters by all three inputs, sorts the strongest matches first, includes the original listing fields, and returns an empty list when nothing matches. Before using it, I will review the code to confirm it does not read `data/listings.json` directly, handles `size="any"`, checks price with `price <= max_price`, and searches title, description, category, style tags, colors, and brand; then I will test it with three queries: one that should match graphic tees under $30, one that should match shoes under $50, and one impossible query that should return `[]`.

For `suggest_outfit`, I will give Claude the `Tool 2: suggest_outfit` block, the wardrobe schema from `data/wardrobe_schema.json`, and the `A Complete Interaction` Step 2 example. I expect Claude to produce a Python function that accepts a selected listing and a wardrobe dict, calls the LLM, and returns a non-empty outfit suggestion string. Before using it, I will check that the function accepts wardrobes from both `get_example_wardrobe()` and `get_empty_wardrobe()`, does not crash when `items` is empty, and returns general styling advice when no closet-specific outfit can be created.

For `create_fit_card`, I will give Claude the `Tool 3: create_fit_card` block and the final output description from `A Complete Interaction`. I expect Claude to produce a Python function that accepts the outfit suggestion string from `suggest_outfit` plus the selected listing as `new_item`, then returns a 2-3 sentence fit card caption string. Before using it, I will verify that the generated code guards against an empty outfit string, preserves listing details like title, price, and platform in the prompt, and returns a clear error or fallback string instead of raising an exception.

For `estimate_price_fairness`, I will give Claude the `Tool 4: estimate_price_fairness` block, the `Error Handling` row for `estimate_price_fairness`, and the `data/listings.json` field shape. I expect Claude to produce a Python function that accepts the selected listing dict, calls `load_listings()` from `utils/data_loader.py`, finds comparable listings by category first and then stronger overlaps in style tags, colors, and brand, and returns a dictionary with `item_id`, `item_price`, `comparison_count`, `average_comparable_price`, `price_range`, `verdict`, and `reasoning`. Before using it, I will check that missing `price` or `category` returns `verdict = "not enough data"`, no comparable listings avoids a price claim, and weak comparisons include low-confidence wording.

For `style_profile_memory`, I will give Claude the `Tool 5: style_profile_memory` block, the `State Management` section, the `Error Handling` row for memory, and the two-interaction example from `A Complete Interaction`. I expect Claude to produce a deterministic JSON-backed helper, not an LLM call, that can load an empty default profile, merge preference updates without duplicating list values, write the profile back to `data/style_profiles.json`, and return a consistent profile dict. Before using it, I will check that it handles a missing profile file, malformed JSON, missing `user_id`, read failure, write failure, and repeated updates without crashing.

After Claude generates the five functions, I will use Claude to integrate them into the project files and review them against the Tools section. Claude should make the code consistent with the existing project structure, import helper functions from `utils/data_loader.py`, keep style profile memory deterministic and local, and avoid changing unrelated files. I will verify the milestone by running focused tests or manual function calls for successful search, no-results search, successful price fairness, missing-field price fairness, no-comparable price fairness, example wardrobe styling, empty wardrobe styling, complete fit card creation, incomplete outfit fallback, style profile load with no existing memory, style profile update, and two sequential interactions where the second uses preferences saved by the first.

**Milestone 4 - Planning loop and state management:**
I will give Claude the completed `Planning Loop`, `State Management` once completed, `Error Handling`, `Architecture` ASCII diagram, and `A Complete Interaction` sections from `planning.md`. I expect Claude to produce the agent control flow that loads `style_profile_memory` at the start, parses a user query into `description`, `size`, and `max_price`, stores those values in `session["parsed"]`, calls `search_listings`, optionally re-ranks matches using remembered preferences, branches early on empty results with an LLM-generated no-results message plus deterministic fallback, stores `selected_item = results[0]`, calls `estimate_price_fairness(session["selected_item"])`, stores the returned dict in `session["price_fairness"]`, continues even if the verdict is `"not enough data"`, uses the wardrobe and style profile passed through the session, calls `suggest_outfit`, stores the returned string in `session["outfit_suggestion"]`, calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`, updates style memory after a successful fit card, and returns the completed session.

I will use Claude as a reviewer for Milestone 4 by giving it the same `Planning Loop` section and `Architecture` diagram plus the generated planning-loop code. I will ask Claude to identify any missing branch, incorrect state key, or mismatch with the documented tool return shapes. Before trusting the implementation, I will manually trace the code against the `A Complete Interaction` example and verify that the session contains `user_id`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `style_profile`, `memory_warning`, `price_fairness`, `outfit_suggestion`, `fit_card`, and `error` at the correct points.

To verify the final planning loop, I will run five end-to-end scenarios: the example vintage graphic tee query should return listings, a price fairness result, outfit advice, a fit card, and an updated style profile; a query with no matching listings should return early with an error message that explains the failed parsed filters and suggests concrete search adjustments, and should not call price fairness, outfit, fit-card, or memory-update logic; a run where `estimate_price_fairness` returns `"not enough data"` should still continue to outfit and fit-card generation while avoiding a strong price claim; a run with `get_empty_wardrobe()` should still return the selected listing with price context and general styling notes in `session["outfit_suggestion"]`; and two sequential interactions should prove memory works by saving preferences from the first interaction and using them in the second without the user re-entering those preferences.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish ??tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

FitFindr searches secondhand clothing listings, picks the best item for the user's request, estimates whether that listing's price is fair, then styles it with the wardrobe passed into `run_agent()` so the user gets shopping context and an outfit idea. For the example query, the request triggers `search_listings(description="vintage graphic tee", size=None, max_price=30)`, the selected listing triggers `estimate_price_fairness(item=<chosen listing>)`, the same selected listing triggers `suggest_outfit(new_item=<chosen listing>, wardrobe=<passed-in wardrobe>)`, and the completed outfit suggestion triggers `create_fit_card(outfit=<outfit suggestion string>, new_item=<chosen listing>)`. If search finds nothing, FitFindr should set `session["error"]` to an LLM-generated message that explains the failed filters and suggests what to try next, with a deterministic fallback if the LLM is unavailable; if price fairness has `"not enough data"`, it should avoid a strong price claim and keep going; if the wardrobe is empty from `get_empty_wardrobe()`, it should still show the listing with a general styling suggestion string; if the fit card cannot be created, it should return a descriptive fallback string rather than crashing.

**Step 1:**
The agent reads the user query and identifies three search constraints: item description = "vintage graphic tee", size = `None` because the user did not specify a size, and max price = 30. It stores those values in `session["parsed"]`, calls `search_listings(description="vintage graphic tee", size=None, max_price=30)`, and that tool uses `load_listings()` from `utils/data_loader.py` to search the mock secondhand listings. The tool returns matching listings such as the black 2003 tour bootleg-style graphic tee for $24 and the faded grey vintage band tee for $19; if it returns no matches, the agent generates a helpful no-results message from `session["parsed"]`, stores it in `session["error"]`, and stops the tool chain.

**Step 2:**
The agent chooses the strongest match from Step 1, likely the black "Graphic Tee - 2003 Tour Bootleg Style" because it is a vintage-style graphic tee under $30 and fits the user's baggy jeans/chunky sneakers style. It calls `estimate_price_fairness(item=session["selected_item"])` using that exact selected listing and stores the returned dict in `session["price_fairness"]`. If comparable tees in the dataset show that $24 is close to the comparable average, the agent can say the listing looks like a fair price; if the tool returns `"not enough data"`, the agent says it cannot confidently judge the price and continues without making a deal claim.

**Step 3:**
The agent uses the wardrobe passed into `run_agent()` and calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. The tool returns an outfit suggestion string using the new tee with wardrobe pieces like baggy straight-leg jeans, chunky white sneakers, a vintage black denim jacket, and a black crossbody bag; if the wardrobe is empty from `get_empty_wardrobe()`, the string gives general styling advice instead of wardrobe-specific pairings.

**Step 4:**
The agent sends the outfit suggestion from Step 3 and the selected listing to `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. This tool formats the chosen listing, price, platform, colors, style tags, and styling notes into a short user-friendly caption string. If the outfit suggestion is empty or the caption model fails, the tool returns a descriptive fallback string so the user still gets a useful answer.

**Final output to user:**
The user sees a short list of the best matching listings, with the top recommendation highlighted: "Graphic Tee - 2003 Tour Bootleg Style," size L, good condition, $24 on Depop. In the same listing/results panel, the user also sees the price fairness result, such as "Price check: fair price - $24 is close to the average comparable tee price in the dataset," or a low-confidence note if there is not enough comparable data. They also see an outfit suggestion string plus a short fit card caption showing how to style it with their baggy straight-leg jeans, chunky white sneakers, vintage black denim jacket, and black crossbody bag.

**Style profile memory example:**
Interaction 1 starts with no saved memory. The user says, "I like oversized streetwear, black pieces, baggy jeans, and chunky sneakers. Find me a vintage graphic tee under $30." The agent loads an empty default `style_profile`, completes the normal search, price check, outfit, and fit-card flow, then updates memory with preferences such as `preferred_style_tags = ["streetwear", "vintage", "graphic tee"]`, `preferred_colors = ["black"]`, `preferred_silhouettes = ["oversized", "baggy"]`, `preferred_categories = ["tops"]`, and `wardrobe_notes = "User likes baggy jeans and chunky sneakers."`

Interaction 2 happens later with the same `user_id = "demo_user"`. The user only says, "Find me a jacket under $50," without repeating their style preferences. The agent loads the saved `style_profile` before search, uses it to prefer jacket listings that overlap with remembered tags like `streetwear`, `vintage`, oversized shapes, and black or dark colors, then uses the same memory in the outfit prompt so the suggestion can mention baggy jeans and chunky sneakers even though the second query did not restate them.
