# Spec: `run_agent()`

**File:** `agent.py`
**Status:** Partially pre-filled — complete the two blank fields before implementing

---

## Purpose

Orchestrate a single conversational turn for the Plant Advisor agent. Given a user message and the conversation history, call the LLM with available tools, execute any tool calls the LLM requests, and return the final text response.

This is the core of what makes Plant Advisor an *agent* rather than a simple chatbot: the ability to decide which tools to call, use their results to inform its response, and loop until it has everything it needs.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_message` | `str` | The user's current message |
| `history` | `list` | Gradio conversation history — list of `[user_msg, assistant_msg]` pairs |

**Output:** `str`

The agent's final text response for this turn. Should never be empty — if something goes wrong, return a user-readable fallback message.

---

## Design Decisions

*Read `specs/system-design.md` (especially the "How the Groq Tool Calling API Works" section) before reviewing these. Complete the two blank fields before writing any code.*

---

### Messages list structure

The messages list must start with the system prompt, then replay the conversation
history, then add the new user message. Gradio history is a list of `[user, assistant]`
pairs — convert each pair to two API-format dicts:

```python
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for user_msg, assistant_msg in history:
    messages.append({"role": "user", "content": user_msg})
    if assistant_msg:
        messages.append({"role": "assistant", "content": assistant_msg})

messages.append({"role": "user", "content": user_message})
```

---

### Initial LLM call

Pass the model, the messages list, the tool definitions, and `tool_choice="auto"`
so the LLM can decide whether to call a tool or respond directly:

```python
response = client.chat.completions.create(
    model=LLM_MODEL,
    messages=messages,
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",
)
```

---

### Detecting tool calls in the response

The response object has a `choices` list. Index 0 gives the assistant message.
Check its `tool_calls` attribute — if it's truthy, the LLM wants to call tools:

```python
assistant_message = response.choices[0].message

if not assistant_message.tool_calls:
    # No tool calls — LLM has a final answer
    ...
```

---

### Appending the assistant message

When there are tool calls, append the full assistant message object to `messages`
**before** appending any tool results. The API requires this ordering — a tool
result message must immediately follow the assistant message that requested it:

```python
messages.append(assistant_message)  # must come first
```

---

### Executing and appending tool results

For each tool call, extract the name and arguments, call `dispatch_tool()`, and
append the result as a `"tool"` role message. The `tool_call_id` links this result
back to the specific tool call that requested it:

```python
for tool_call in assistant_message.tool_calls:
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)
    tool_result = dispatch_tool(tool_name, tool_args)

    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result,
    })
```

---

### Loop termination conditions

*The loop should stop when: (a) the LLM returns a response with no tool calls, OR (b) the MAX_TOOL_ROUNDS limit is reached. Describe how you will detect each condition and what you will return in each case.*

```
The loop runs with a counter bounded by MAX_TOOL_ROUNDS (set to 5 in config.py).

(a) No tool calls — after each LLM call, check assistant_message.tool_calls.
    If it's falsy (None or empty), the LLM is done calling tools. Break out of
    the loop and fall through to extract the final text response.

(b) MAX_TOOL_ROUNDS reached — use `for round_num in range(MAX_TOOL_ROUNDS):`
    as the loop structure. If all MAX_TOOL_ROUNDS iterations are exhausted
    without hitting condition (a), the for-loop completes without a break.
    At that point there is no clean text response, so return a user-readable
    fallback string such as:
    "I reached the maximum number of tool-calling steps. Please try rephrasing."
```

---

### Extracting the final text response

*Once the loop exits because there are no more tool calls, how do you extract the text content from the response object? What field holds the string you should return?*

```
When the loop exits via condition (a) — no tool calls — the last `response`
object from client.chat.completions.create() holds the final answer.

Extract it with:
    response.choices[0].message.content

`choices[0]` is the first (and only) candidate response. `.message.content`
is the plain string the LLM produced. That string is what run_agent() returns.

Edge case: .content can be None. The Groq API sets content to None (not an
empty string) whenever the message contains tool_calls. On the final loop
iteration this should not happen, but it can occur if the LLM returns an
empty text response. Guard against it:

    return response.choices[0].message.content or "Sorry, I couldn't generate a response."

This satisfies the output contract: run_agent() should never return None or
an empty string.
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Trace of a working agent turn (what tools were called and in what order):**

```
Query: "How should I care for my calathea?"
  → Tool call: lookup_plant({'plant_name': 'calathea'})
  ← Result: {"found": true, "plant": {"display_name": "Calathea", "scientific_name": "Calathea ornata", "aliases": ["prayer plant", ...
  → Tool call: get_seasonal_conditions({})
  ← Result: {"name": "Summer", "months": ["June", "July", "August"], "description": "Peak growing season. Most houseplants are at th...
  
  Final response: According to the care data for your calathea, it requires low to medium indirect light, and it's best to avoid direct sunlight as it can destroy the decorative leaf patterns. The plant also prefers high humidity (50%+), so using a humidifier, misting frequently, or grouping it with other plants can help.

In terms of watering, it's essential to keep the soil consistently moist but not soggy. Calatheas are sensitive to minerals in tap water, so it's recommended to use filtered, distilled, or rainwater to prevent brown edges. Letting the water sit overnight can also help if you're using tap water.

As for fertilizing, you can fertilize your calathea monthly during the growing season with a diluted balanced fertilizer.

Given that it's currently summer, it's the peak growing season for most houseplants, including your calathea. You may need to water it more frequently, checking the soil every few days. Continue regular fertilizing on schedule, but avoid over-fertilizing. Also, be mindful of direct afternoon sun through windows, which can be intense enough to burn leaves.

Lastly, keep an eye out for pests like spider mites and fungus gnats, which thrive in hot, dry conditions. Check your plant weekly, and isolate it immediately if you notice any signs of infection.

By following these guidelines, you should be able to provide your calathea with the care it needs to thrive.
```

**What happens when you ask about a plant that isn't in the database?**

  → Tool call: lookup_plant({'plant_name': 'zozo'})
  ← Result: {"found": false, "name": "zozo", "message": "No plant matching 'zozo' was found in the database. The database co...

**One thing about the tool call API that surprised you:**

```
[your answer here]
```
