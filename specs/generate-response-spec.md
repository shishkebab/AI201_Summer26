# Spec: `generate_response()`

**File:** `generator.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user query and a list of retrieved rule chunks, generate a response that directly answers the question using only the retrieved text as context. The response must be grounded — it should not draw on the model's general knowledge of board games, only on what was retrieved.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's original question |
| `retrieved_chunks` | `list[dict]` | Ranked list of chunks from `retrieve()`, each with `"text"`, `"game"`, and `"distance"` |

**Output:** `str`

A plain string containing the response to show the user. The response should:
- Answer the question using only the retrieved rule text.
- Identify which game the answer comes from.
- Acknowledge clearly when the answer is not found in the loaded rules.

Returns a fallback string (not an error) when `retrieved_chunks` is empty.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Context formatting

*How will you format the retrieved chunks before passing them to the LLM? Describe the structure — not the code. Consider: will you label chunks by game? Include distance scores? Separate chunks with delimiters?*

```
Each chunk is formatted as a labeled block with a game header and plain text body,
separated by a horizontal delimiter:

  [Source: Catan]
  Players take turns rolling two dice and moving their token clockwise...

  ---

  [Source: Monopoly]
  When a player passes Go, they collect $200 from the bank...

Rules:
- Label every chunk with [Source: <game>] so the LLM can attribute its answer.
- Separate chunks with "---" to signal clear boundaries between sources.
- Omit distance scores — they are retrieval artifacts, not semantic content,
  and can cause the model to hedge or misweight chunks.
- Use plain text, not JSON or XML — prose chunks don't benefit from markup
  at this scale (<=5 chunks, ~300 chars each).
- The assembled context string goes in the user message, not the system message,
  because it is query-specific data rather than standing instructions.
```

---

### System prompt — grounding instruction

*Write the exact system prompt instruction you will use to prevent the model from answering beyond the retrieved text. This is the most important design decision in this function.*

```
You are a board game rules assistant. Answer the user's question using ONLY the rule text provided in the context below. 
Do not use any knowledge about board games that is not explicitly stated in that context. 
Do not infer, speculate, or fill in gaps from general knowledge — even if you believe you know the answer. 
If the context only partially answers the question, answer only what the text supports and state that the rest is not covered. 
If the answer is not found in the context at all, say so and nothing more.
```

---

### System prompt — citation instruction

*Write the exact instruction you will use to tell the model to identify which game its answer comes from.*

```
At the end of your answer, cite the game(s) your answer draws from using
this exact format on its own line:

  [Source: <game_name>]

If your answer draws from multiple games, list each on a separate line:

  [Source: Catan]
  [Source: Monopoly]

Use only the game names exactly as they appear in the Source labels in the
context. If the answer is not found in the context, omit the citation entirely.

```

---

### Fallback behavior

*What should the response say when the answer isn't found in the loaded rule books? Write the exact fallback message.*

```
[your answer here]
```

---

### Handling low-relevance chunks

*`retrieved_chunks` may include chunks with high distance scores (weak relevance). Will you filter these out before building context, pass them all in, or handle them another way? What are the tradeoffs?*

```
[your answer here]
```

---

### Message structure

*Describe how you will structure the messages list for the API call — what goes in the system message vs. the user message?*

```
[your answer here]
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Test query and response:**

```
Query: [your test query]
Response: [abbreviated response]
Correctly grounded? [yes / no]
Cited the right game? [yes / no]
```

**One thing you changed from your original spec after seeing the actual output:**

```
[your answer here]
```
