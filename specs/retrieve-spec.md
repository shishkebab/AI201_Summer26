# Spec: `retrieve()`

**File:** `retriever.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user's natural language query, find the most relevant chunks from the vector store using semantic similarity search. Return them ranked by relevance so that `generate_response()` can use them as context.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's natural language question |
| `n_results` | `int` | Maximum number of chunks to return (default: `N_RESULTS` from `config.py`) |

**Output:** `list[dict]`

Each dict in the returned list must contain exactly these keys:

| Key | Type | Description |
|-----|------|-------------|
| `"text"` | `str` | The chunk text |
| `"game"` | `str` | The game name this chunk came from |
| `"distance"` | `float` | Cosine distance score — lower means more similar to the query |

Results should be ordered from most to least relevant (lowest to highest distance). Returns an empty list `[]` if the collection contains no documents.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Query approach

*Describe how you will use `_collection.query()` to find relevant chunks. What arguments will you pass, and why?*

```
[your answer here]
```

---

### Return structure

*Sketch out what one item in your return list looks like as a concrete example. Where does each field come from in the query results?*

```
One item in the return list looks like:

{
    "text": "Players take turns rolling two dice and moving their token...",
    "game": "Monopoly",
    "distance": 0.312
}

Where each field comes from in the raw ChromaDB query result:
- "text"     ← results["documents"][0][i]   (the stored document string)
- "game"     ← results["metadatas"][0][i]["game"]  (the metadata dict we stored in embed_and_store)
- "distance" ← results["distances"][0][i]   (cosine distance ChromaDB computed)

Python pseudocode to build the list:

results = _collection.query(
    query_texts=[query],
    n_results=n_results,
    include=["documents", "metadatas", "distances"],
)
return [
    {
        "text": doc,
        "game": meta["game"],
        "distance": dist,
    }
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )
]

ChromaDB already returns results sorted lowest-distance first, so no
additional sort is needed.
```

---

### Handling the nested result structure

*`_collection.query()` returns nested lists. Describe what index you need to access to get the actual list of results for a single query, and why the nesting exists.*

```
The nesting exists because _collection.query() is designed to accept a
*batch* of queries at once (query_texts is a list). Each element of the
outer list corresponds to one query string. Since we always pass a single
query, the outer list always has exactly one element.

So the shape is:

results["documents"]  →  [ [chunk_A, chunk_B, chunk_C] ]
                              ^--- index [0] gives our results

results["documents"][0]  →  [chunk_A, chunk_B, chunk_C]  ← what we want

The same [0] index applies to all three keys we use:
  results["documents"][0]   → list of text strings
  results["metadatas"][0]   → list of metadata dicts
  results["distances"][0]   → list of float scores

Without [0], you'd be iterating over a list containing one list instead
of over the actual results.
```

---

### Relevance threshold

*Will you filter out results above a certain distance score, or return all `n_results` regardless of how relevant they are? What are the tradeoffs of each approach?*

```
Decision: return all n_results without filtering.

Reasoning:

Returning all n_results (no threshold):
  + Simple — no magic constant to tune.
  + The LLM in generate_response() can ignore irrelevant context on its own.
  + Avoids the failure mode where every result is filtered out and the bot
    has nothing to work with, even for reasonable questions.
  - May pass weakly-relevant chunks to the LLM, slightly diluting context.

Filtering above a distance threshold (e.g., drop anything > 0.7):
  + Keeps only genuinely relevant chunks; reduces noise in the prompt.
  - Requires choosing a threshold — too tight and valid results get dropped,
    too loose and it's equivalent to no filter.
  - Can return an empty list for out-of-domain queries, which requires
    generate_response() to handle a "no context" case gracefully.

For this project, N_RESULTS is already small (3), so the cost of including
a mildly-irrelevant chunk is low. No threshold is the right default here.
If the LLM starts hallucinating on off-topic questions, adding a threshold
(e.g., > 0.8 for cosine distance) would be the next thing to try.
```

---

### Edge cases

*How does your implementation behave when: (a) the collection is empty, (b) the query matches no chunks well, (c) the query matches chunks from multiple games?*

```
[your answer here]
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 3.*

**Test query and top result returned:**

```
Query: [your test query]
Top result game: [game name]
Distance score: [score]
Does it make sense? [yes / no / explain]
```

**One thing about the query results that surprised you:**

```
[your answer here]
```
