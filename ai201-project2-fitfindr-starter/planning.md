# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

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
