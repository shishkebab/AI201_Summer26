# FitFindr ??planning.md

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
- `size` (str): The requested size, such as `"M"`, `"W30"`, `"US 8"`, or `"any"` if the user did not specify a size; when set to `"any"`, do not filter by size.
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
An outfit dictionary containing `new_item`, `wardrobe_items`, `style_summary`, and `reasoning`. `new_item` is the selected listing, `wardrobe_items` is a list of chosen wardrobe item dictionaries that complete the outfit, `style_summary` is a short user-facing outfit description, and `reasoning` explains why the pieces work together based on category balance, colors, and shared style tags. For example, a graphic tee may be paired with baggy straight-leg jeans, chunky white sneakers, a vintage black denim jacket, and a black crossbody bag.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty or no wardrobe pieces coordinate with the selected listing, return an outfit dictionary with the `new_item`, an empty `wardrobe_items` list, and a `style_summary` that gives a general styling suggestion. The agent should still show the listing to the user, but it should explain that it could not create a closet-specific outfit because there were no usable wardrobe items.

---

### Tool 3: create_fit_card

**What it does:**
Formats a completed outfit recommendation into a clear fit card that the agent can show to the user. It should turn the structured outfit from `suggest_outfit` into a readable shopping-and-styling summary.

**Input parameters:**
- `outfit` (dict): The outfit dictionary returned by `suggest_outfit`; it should include `new_item` (dict), `wardrobe_items` (list[dict]), `style_summary` (str), and `reasoning` (str).

**What it returns:**
A fit card dictionary with `title`, `listing_summary`, `outfit_items`, `styling_notes`, and `purchase_details`. `title` is a short name for the look, `listing_summary` describes the secondhand item including title, size, condition, price, and platform, `outfit_items` lists the new item plus each wardrobe piece used, `styling_notes` explains how to wear the outfit, and `purchase_details` stores the listing id, price, and platform for the item the user may buy.

**What happens if it fails or returns nothing:**
If the outfit is missing required data such as `new_item`, listing price, platform, or style notes, the tool should return `None` or an error message describing the missing fields. The agent should not discard the recommendation; it should show the listing and outfit details in plain text and mention that a formatted fit card could not be created because the outfit data was incomplete.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent starts by parsing the user message into `description`, `size`, and `max_price`. If the user does not provide a size, set `size = "any"`. if the user does not provide a maximum price, set `max_price` to a high default value so price does not filter out otherwise relevant listings. Store these values in session state as `search_query`.

First, call `search_listings(description=search_query["description"], size=search_query["size"], max_price=search_query["max_price"])` and store the return value as `session["search_results"]`. After `search_listings` runs, check whether `search_results` is empty. If it is empty, set `session["error_message"] = "No matching listings were found."`, build a response that suggests relaxing the budget, size, or style terms, and return early without calling `suggest_outfit` or `create_fit_card`.

If `search_results` is not empty, set `session["selected_item"] = search_results[0]` because results are already sorted strongest to weakest match. Next, choose the wardrobe: use the current user's saved wardrobe if one exists in session state, otherwise use `get_example_wardrobe()` for the sample interaction, and use `get_empty_wardrobe()` only for a brand-new user with no wardrobe items. Store that wardrobe as `session["wardrobe"]`, then call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])` and store the result as `session["outfit"]`.

After `suggest_outfit` runs, check whether `session["outfit"]` exists and includes `new_item`, `wardrobe_items`, and `style_summary`. If the outfit is missing or invalid, create a fallback outfit in session state with the selected listing, an empty `wardrobe_items` list, and a general styling suggestion based on the listing's `category`, `colors`, and `style_tags`. If the outfit is valid but `wardrobe_items` is empty, continue with that outfit and set `session["warning_message"]` explaining that the agent could not create a closet-specific outfit.

Next, call `create_fit_card(outfit=session["outfit"])` and store the result as `session["fit_card"]`. After `create_fit_card` runs, check whether `fit_card` is present and contains `title`, `listing_summary`, `outfit_items`, `styling_notes`, and `purchase_details`. If the fit card is missing or incomplete, return a plain-text response using `session["selected_item"]` and `session["outfit"]`; otherwise, return a final response that includes the top listing, any other strong search matches, and the formatted fit card. The loop is done once the agent has either returned the no-results error response, returned the plain-text fallback, or returned the completed fit card response.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the user's `description`, `size`, and `max_price` filters, so the tool returns `[]`. | Set `session["error_message"] = "No matching listings were found."` and return early without calling `suggest_outfit` or `create_fit_card`. Tell the user: "I couldn't find any listings that match that item, size, and budget." Then offer specific next steps: raise the max price, remove the size filter by using `size="any"`, or broaden the description from something narrow like `"vintage graphic tee"` to `"graphic tee"` or `"vintage top"`. |
| suggest_outfit | The wardrobe is empty, such as when the agent receives `get_empty_wardrobe()` with `items: []`. | Keep `session["selected_item"]`, create a fallback outfit with `wardrobe_items = []`, add a general styling suggestion based on the listing's category/colors/style tags, and set `session["warning_message"] = "No closet-specific outfit could be created because your wardrobe is empty."` Tell the user: "I found a listing, but I don't have closet items to pair it with yet." Then offer a generic styling idea, such as pairing a graphic tee with baggy jeans, chunky sneakers, and a denim or leather jacket, and invite the user to add wardrobe items for a more personal outfit. |
| create_fit_card | The outfit input is missing required fields such as `new_item`, `style_summary`, listing price, platform, or item details. | Set `session["warning_message"] = "The fit card could not be created because the outfit data was incomplete."` Do not discard the recommendation. Tell the user: "I couldn't format this as a fit card, but here's the recommendation in plain text." Then show the selected listing details that are available, the wardrobe pieces or generic styling notes from `session["outfit"]`, and any missing information that prevented the card from being created. |

---

## Architecture

```text
User query
    |
    | raw text request
    v
Planning Loop
    |
    | parse into search_query:
    | description, size, max_price
    v
Session State
    | search_query = {
    |   description: "...",
    |   size: "any" or requested size,
    |   max_price: number
    | }
    |
    v
search_listings(description, size, max_price)
    |
    | uses load_listings()
    |
    +-- results = []
    |       |
    |       v
    |   [ERROR]
    |   session.error_message = "No matching listings were found."
    |       |
    |       v
    |   Return early with suggestions to relax budget, size, or style terms
    |
    +-- results = [listing_1, listing_2, ...]
            |
            v
        Session State
        search_results = results
        selected_item = results[0]
            |
            | selected_item + wardrobe
            v
suggest_outfit(selected_item, wardrobe)
    |
    | wardrobe comes from saved session wardrobe,
    | get_example_wardrobe(), or get_empty_wardrobe()
    |
    +-- wardrobe.items = []
    |       |
    |       v
    |   Session State
    |   outfit = fallback outfit with selected_item,
    |            wardrobe_items = [],
    |            and general styling notes
    |   warning_message = "No closet-specific outfit could be created."
    |       |
    |       v
    |   continue to create_fit_card(outfit)
    |
    +-- outfit missing/invalid
    |       |
    |       v
    |   Session State
    |   outfit = fallback outfit with selected_item,
    |            no wardrobe_items, and general styling notes
    |   warning_message = "Could not create a closet-specific outfit."
    |
    +-- outfit valid
            |
            v
        Session State
        outfit = {
          new_item,
          wardrobe_items,
          style_summary,
          reasoning
        }
            |
            | outfit
            v
create_fit_card(outfit)
    |
    +-- fit_card missing/incomplete
    |       |
    |       v
    |   Return plain-text response using selected_item + outfit
    |
    +-- fit_card complete
            |
            v
        Session State
        fit_card = {
          title,
          listing_summary,
          outfit_items,
          styling_notes,
          purchase_details
        }
            |
            v
Return final response with top listing, other strong matches, and fit card
```

---

## AI Tool Plan

**Milestone 3 - Individual tool implementations:**
For `search_listings`, I will give Claude the `Tool 1: search_listings` block from the Tools section, the `Error Handling` row for `search_listings`, and the `utils/data_loader.py` helper description that says to use `load_listings()`. I expect Claude to produce a Python function that accepts `description`, `size`, and `max_price`, loads listings through `load_listings()`, filters by all three inputs, sorts the strongest matches first, includes the original listing fields, and returns an empty list when nothing matches. Before using it, I will review the code to confirm it does not read `data/listings.json` directly, handles `size="any"`, checks price with `price <= max_price`, and searches title, description, category, style tags, colors, and brand; then I will test it with three queries: one that should match graphic tees under $30, one that should match shoes under $50, and one impossible query that should return `[]`.

For `suggest_outfit`, I will give Claude the `Tool 2: suggest_outfit` block, the wardrobe schema from `data/wardrobe_schema.json`, and the `A Complete Interaction` Step 2 example. I expect Claude to produce a Python function that accepts a selected listing and a wardrobe dict, chooses compatible wardrobe items by category, color, and style tags, and returns an outfit dict with `new_item`, `wardrobe_items`, `style_summary`, and `reasoning`. Before using it, I will check that the function accepts wardrobes from both `get_example_wardrobe()` and `get_empty_wardrobe()`, does not crash when `items` is empty, and returns a fallback outfit with general styling notes when no closet-specific outfit can be created.

For `create_fit_card`, I will give Claude the `Tool 3: create_fit_card` block and the final output description from `A Complete Interaction`. I expect Claude to produce a Python function that accepts the outfit dict from `suggest_outfit` and returns a fit card dict with `title`, `listing_summary`, `outfit_items`, `styling_notes`, and `purchase_details`. Before using it, I will verify that the generated code checks for missing required fields, preserves listing details like title, size, condition, price, and platform, and returns `None` or a clear error when the outfit input is incomplete.

After Claude generates the three functions, I will use Claude to integrate them into the project files and review them against the Tools section. Claude should make the code consistent with the existing project structure, import helper functions from `utils/data_loader.py`, and avoid changing unrelated files. I will verify the milestone by running focused tests or manual function calls for successful search, no-results search, example wardrobe styling, empty wardrobe styling, complete fit card creation, and incomplete outfit fallback.

**Milestone 4 - Planning loop and state management:**
I will give Claude the completed `Planning Loop`, `State Management` once completed, `Error Handling`, `Architecture` ASCII diagram, and `A Complete Interaction` sections from `planning.md`. I expect Claude to produce the agent control flow that parses a user query into `description`, `size`, and `max_price`, stores `search_query` in session state, calls `search_listings`, branches early on empty results, stores `selected_item = results[0]`, loads the correct wardrobe, calls `suggest_outfit`, handles empty or invalid outfits, calls `create_fit_card`, and returns either a formatted fit card or a plain-text fallback.

I will use Claude as a reviewer for Milestone 4 by giving it the same `Planning Loop` section and `Architecture` diagram plus the generated planning-loop code. I will ask Claude to identify any missing branch, incorrect state key, or mismatch with the documented tool return shapes. Before trusting the implementation, I will manually trace the code against the `A Complete Interaction` example and verify that the session contains `search_query`, `search_results`, `selected_item`, `wardrobe`, `outfit`, and either `fit_card`, `warning_message`, or `error_message` at the correct points.

To verify the final planning loop, I will run three end-to-end scenarios: the example vintage graphic tee query should return listings plus a fit card; a query with no matching listings should return early with the no-results message and should not call outfit or fit-card logic; and a run with `get_empty_wardrobe()` should still return the selected listing with general styling notes and a warning that no closet-specific outfit was created.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish ??tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

FitFindr searches secondhand clothing listings, picks the best item for the user's request, then styles it with the user's wardrobe so the user gets both shopping options and an outfit idea. For the example query, the request triggers `search_listings(description="vintage graphic tee", size="any", max_price=30)`, a selected listing triggers `suggest_outfit(new_item=<chosen listing>, wardrobe=get_example_wardrobe())`, and the completed outfit triggers `create_fit_card(outfit=<suggested outfit>)`. If search finds nothing, FitFindr should say that no matching listings were found and suggest relaxing the query; if the wardrobe is empty from `get_empty_wardrobe()` or no outfit works, it should still show the listing with a general styling suggestion; if the fit card cannot be created because outfit data is incomplete, it should return the outfit details in plain text instead.

**Step 1:**
The agent reads the user query and identifies three search constraints: item description = "vintage graphic tee", size = "any" because the user did not specify a size, and max price = 30. It calls `search_listings(description="vintage graphic tee", size="any", max_price=30)`, and that tool uses `load_listings()` from `utils/data_loader.py` to search the mock secondhand listings. The tool returns matching listings such as the black 2003 tour bootleg-style graphic tee for $24 and the faded grey vintage band tee for $19; if it returns no matches, the agent stops the tool chain and tells the user no matching listings were found, then suggests relaxing the budget, style terms, or size.

**Step 2:**
The agent chooses the strongest match from Step 1, likely the black "Graphic Tee - 2003 Tour Bootleg Style" because it is a vintage-style graphic tee under $30 and fits the user's baggy jeans/chunky sneakers style. It loads the sample closet with `get_example_wardrobe()` and calls `suggest_outfit(new_item=<chosen listing>, wardrobe=get_example_wardrobe())`. The tool returns an outfit using the new tee with wardrobe pieces like baggy straight-leg jeans, chunky white sneakers, a vintage black denim jacket, and a black crossbody bag; if the wardrobe is empty from `get_empty_wardrobe()` or no pieces coordinate well, the agent still recommends the listing and gives a general styling idea instead of a wardrobe-specific outfit.

**Step 3:**
The agent sends the outfit from Step 2 to `create_fit_card(outfit=<suggested outfit>)`. This tool formats the chosen listing, wardrobe items, colors, style tags, and styling notes into a user-friendly fit card. If the outfit data is missing required details, the agent skips the card format and returns the same recommendation in plain text so the user still gets a useful answer.

**Final output to user:**
The user sees a short list of the best matching listings, with the top recommendation highlighted: "Graphic Tee - 2003 Tour Bootleg Style," size L, good condition, $24 on Depop. They also see a fit card showing how to style it with their baggy straight-leg jeans, chunky white sneakers, vintage black denim jacket, and black crossbody bag, plus a brief explanation that the outfit works because the black graphic tee matches the user's streetwear/vintage preference and balances well with baggy denim and chunky shoes.
