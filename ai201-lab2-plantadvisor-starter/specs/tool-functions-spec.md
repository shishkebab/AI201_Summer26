# Spec: Tool Functions

**File:** `tools.py`
**Status:** `get_seasonal_conditions` — Pre-implemented, read through. `lookup_plant` — complete spec fields before implementing.

---

## Purpose

These two functions are the tools the agent can call. They retrieve structured data from the local plant database and seasonal data files and return it to the agent loop, which passes it to the LLM as context for generating a response.

---

## Function 1: `lookup_plant()`

### Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `plant_name` | `str` | The plant name as entered by the user or chosen by the LLM — may be any casing, common name, scientific name, or alias |

**Output:** `dict`

When the plant is **found**, return:
```python
{"found": True, "plant": <the full plant dict from _plant_db>}
```

When the plant is **not found**, return:
```python
{"found": False, "name": <normalized input>, "message": <helpful string>}
```

---

### Design Decisions        

*Complete the two blank fields below before writing code. The others are pre-filled for you.*


---

#### Input normalization

Strip leading/trailing whitespace and convert to lowercase before any comparison.

```python
normalized = plant_name.strip().lower()
```

---

#### Search order

Search in this order: direct key → display name → aliases. Keys are the fastest
lookup (O(1) dict access), so check those first. Display names are the next most
likely match for clean user input. Aliases are the broadest net, so they go last.

```
1. Direct key match: normalized in _plant_db
2. Display name match: plant["display_name"].lower() == normalized
3. Alias match: normalized in [alias.lower() for alias in plant["aliases"]]
```

---

#### Alias matching approach

*Aliases are stored as a list of strings. How will you check if the normalized input matches any alias in the list? Write your approach in pseudocode or plain English.*


The search happens inside a loop over all plants in `_plant_db`. At the alias step, I'd lowercase every alias in the list on the fly and check membership:

```
For each plant in _plant_db.values():
    If normalized matches any alias.lower() in plant["aliases"]:
        return that plant
```

In code, that's a single `any()` call per plant:

```python
if any(normalized == alias.lower() for alias in plant["aliases"]):
    return {"found": True, "plant": plant}
```

**Why `any()` over a list comprehension:** `any()` short-circuits — it stops as soon as a match is found rather than lowercasing every alias first. For the 15-plant dataset here the difference is negligible, but it's the right habit.

**Why not pre-build an index:** The spec's search order (key → display name → alias) implies a per-query loop, and with only 15 plants it's fast enough. An index would be the right call if the database were large or hot-path performance mattered — but that's out of scope for this spec.

The normalization from the earlier section (`plant_name.strip().lower()`) already handles the `"SNAKE PLANT"` test case, and `"devil's ivy"` will resolve correctly as long as that string appears verbatim (apostrophe and all) in the `aliases` list for pothos.


---

#### Not-found message

*When a plant isn't found, the agent will read your message and use it to decide what to tell the user. Write the exact string you'll return — make it useful to the agent, not just to a human reading logs.*

I already have both files from the previous read, so I can answer directly without re-reading them.

---

The key constraint the spec calls out is: **"make it useful to the agent, not just to a human reading logs."** That means this message is consumed by the LLM (llama-3.3-70b via Groq), not printed to a terminal. It should tell the model what happened and implicitly suggest what to do next.

Here's what I'd write:

```python
f"No plant matching '{normalized}' was found in the database. The database contains common houseplants by slug key, display name, and aliases. Ask the user to check their spelling or try a common name, scientific name, or alternate alias."
```

**Why this wording:**

- **Includes the normalized input** — the LLM can echo back to the user exactly what it searched for, making the response feel grounded rather than generic
- **Describes what the database covers** — gives the model enough context to reason about *why* it might have missed (e.g., "monstera" is in there, but "monstera deliciosa" as a full string might not be)
- **Ends with a suggested action** — "ask the user to check spelling or try an alias" nudges the LLM toward a helpful follow-up rather than a dead-end "plant not found" reply
- **Avoids log-speak** like `"KeyError"` or `"lookup failed"` — those are useless to the model

The `"name": normalized` field in the return dict already carries the searched term structurally, but repeating it inline in `message` means the LLM sees it in the natural language context it will use when composing its reply.

---

#### Implementation Notes

*Fill this in after implementing and running the app.*

**Test: does `"devil's ivy"` return the pothos entry?**
```
[yes / no — if no, describe what happened]
```
```python
>>> print(lookup_plant("devil's ivy"))
{'found': True, 'plant': {'display_name': 'Pothos', 'scientific_name': 'Epipremnum aureum', 'aliases': ['golden pothos', "devil's ivy", "hunter's robe", 'silver vine'], 'difficulty': 'easy', 'watering': {'frequency': 'every 1–2 weeks', 'description': "Allow the top inch of soil to dry out between waterings. Drooping leaves are a reliable signal it's time towater.", 'overwatering_signs': ['yellowing leaves', 'mushy stems', 'root rot', 'gnats in soil'], 'underwatering_signs': ['wilting', 'dry brown leaf tips', 'crispy edges', 'soil pulling away from pot edges']}, 'light': {'requirement': 'low to bright indirect', 'description': 'Highly adaptable. Thrives in bright indirect light but tolerates low light. Direct sun will scorch the leaves.', 'avoid': 'direct sunlight'}, 'humidity': 'tolerant of average household humidity (40–60%)', 'temperature': '65–85°F (18–29°C)', 'fertilizing': 'monthly during spring and summer with a balanced liquid fertilizer; stop in fall and winter', 'common_issues': ['yellowing leaves from overwatering', 'leggy and sparse growth in low light', 'brown tips from inconsistent watering or dry air'], 'seasonal_notes': {'spring': 'Resume fertilizing. Increase watering frequency as growth picks up.', 'summer': 'Water more frequently. Watch for fungus gnats if soil stays too wet.', 'fall': 'Taper off fertilizer. Start reducing watering frequency.', 'winter': 'Water sparingly. Bright indirect light becomes more important. No fertilizer.'}}}
```

**Test: does `"SNAKE PLANT"` return the snake plant entry?**
```
[yes / no — if no, describe what happened]
```
```python
>>> print(lookup_plant("SNAKE PLANT"))
{'found': True, 'plant': {'display_name': 'Snake Plant', 'scientific_name': 'Dracaena trifasciata', 'aliases': ['sansevieria', "mother-in-law's tongue", "saint george's sword", "viper's bowstring hemp"], 'difficulty': 'easy', 'watering': {'frequency': 'every 2–6 weeks depending on season', 'description': 'One of the most drought-tolerant houseplants. Allow soil to dry completely between waterings. When in doubt, wait.', 'overwatering_signs': ['mushy base', 'yellowing leaves at the base', 'root rot', 'soft spots on leaves'], 'underwatering_signs': ['wrinkled or curling leaves', 'dry brown tips', 'leaves leaning outward']}, 'light': {'requirement': 'low to bright indirect', 'description': 'Survives almost anywhere. Grows fastest in bright indirect light but is genuinely one of the best low-light plants.', 'avoid': 'prolonged direct sunlight in summer'}, 'humidity': 'low humidity tolerant — thrives in typical dry indoor environments', 'temperature': '60–80°F (15–27°C); avoid temperatures below 50°F', 'fertilizing': '2–3 times per year during the growing season; never in winter', 'common_issues': ['root rot from overwatering — the most common cause of death', 'brown tips from fluoride in tap water or physical damage', 'slow growth in low light (normal, not a problem)'], 'seasonal_notes': {'spring': 'Repot if root-bound. Begin light fertilizing.', 'summer': 'Water slightly more often. Check for spider mites in hot dry conditions.', 'fall': 'Reduce watering significantly.', 'winter': 'Water once a month or less. Keep away from cold drafts.'}}}
```


**One edge case you discovered while implementing:**
```
[your answer here]
```

---

## Function 2: `get_seasonal_conditions()`

### Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `season` | `str \| None` | One of `"spring"`, `"summer"`, `"fall"`, `"winter"`, or `None` to auto-detect |

**Output:** `dict`

The full season dict from `_season_data`, plus one additional field:

| Added field | Type | Value |
|-------------|------|-------|
| `"detected_season"` | `bool` | `True` if auto-detected from the month; `False` if season was passed as an argument |

---

### Design Decisions

*This function is pre-implemented — read through these fields and the code before working on `lookup_plant`.*

---

#### Auto-detection logic

When `season` is `None`, get the current calendar month with `datetime.now().month`
and look it up in the `_MONTH_TO_SEASON` dict, which maps month numbers to season strings.

```python
current_month = datetime.now().month
season_key = _MONTH_TO_SEASON[current_month]
```

---

#### Season validation

If the caller passes an invalid season string (e.g., `"monsoon"`), the function
falls back to auto-detection — same as if `None` were passed. The `VALID_SEASONS`
set acts as the gate:

```python
VALID_SEASONS = {"spring", "summer", "fall", "winter"}
if season and season.lower() in VALID_SEASONS:
    ...  # use provided season
else:
    ...  # auto-detect
```

---

#### Return structure

The full season dict from `_season_data`, plus a `detected_season` boolean. Example for spring:

```python
{
    "season": "spring",
    "watering": "Increase watering frequency as plants break dormancy ...",
    "fertilizing": "Resume feeding with a balanced fertilizer ...",
    "light": "Days are lengthening — move plants closer to windows ...",
    "pests": "Watch for spider mites and aphids as temperatures rise ...",
    "detected_season": True   # True = auto-detected; False = caller specified
}
```

---

#### Implementation Notes

*Fill this in after testing.*

**Test: does calling with `season=None` return the correct season for the current month?**
```
Current month: [month]
Expected season: [season]
Returned season: [season]
```

**Test: does calling with `season="winter"` return winter data regardless of the current month?**
```
[yes / no]
```
