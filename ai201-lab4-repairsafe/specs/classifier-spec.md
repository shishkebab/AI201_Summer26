# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
A repair is safe when it is routine maintenance or a minor cosmetic/fixture fix that uses basic tools, needs no permit or licensed professional, and would at worst cause cosmetic damage or a broken part if done incorrectly.
```

**caution:**
```
A repair is caution when it is a like-for-like repair or replacement on an existing fixture or component, usually with no permit required, where a careful homeowner could do it but mistakes could cause meaningful property damage, mild injury, or problems with household water or electrical systems.
```

**refuse:**
```
A repair is refuse when it involves gas work, electrical panels/service/new wiring/new circuits, new plumbing or main shutoffs, water heater replacement, structural/load-bearing/foundation/roof work, or any permitted/licensed work where an amateur mistake could cause fire, explosion, major flooding, structural failure, serious injury, or death.
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
Definitions only would be simple and cheap, but they leave too much room for the model to interpret boundary cases differently each time, especially "replace" versus "add" language in electrical and plumbing questions.

Definitions plus a few carefully chosen examples should be more reliable because the examples anchor the most important boundaries: routine cosmetic work is safe, like-for-like fixture or component replacement is caution, and work involving gas, panels, new wiring, new plumbing, main shutoffs, water heaters, or structure is refuse.

Asking the model to show step-by-step reasoning might improve attention to the boundary rules, but it also makes the response harder to parse and can produce overconfident explanations for the wrong tier, so I will instead tell it to apply the rules internally and output only the final tier and a one-sentence reason.

The classifier prompt will include the tier definitions, targeted few-shot examples for common edge cases, and an instruction to choose the higher-risk tier when the user's wording implies gas work, structural work, new wiring/circuits, new plumbing, permits, or a licensed professional.

For a genuinely ambiguous wording like "can I replace my own outlets?", the classifier should treat "replace" as a like-for-like swap at an existing location and classify it as caution unless the question mentions adding, moving, extending, running wire, or opening the electrical panel, which would make it refuse.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
The LLM should return exactly one JSON object and no surrounding Markdown, code fence, or extra explanation:

{"tier":"safe|caution|refuse","reason":"One sentence explaining the classification."}

The parser will load the response as JSON, require exactly the keys "tier" and "reason", validate that "tier" is one of VALID_TIERS, and require "reason" to be a non-empty string.

Example:
{"tier":"caution","reason":"Replacing an existing outlet is a like-for-like electrical component swap that a careful homeowner may attempt, but wiring mistakes can create meaningful electrical risk."}
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
[your prompt here]
```

**User message:**
```
[your prompt here]
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
Rule: Classify as refuse, not caution, when the repair requires gas work, new wiring or circuits, electrical panel/service work, new plumbing or main shutoffs, structural/load-bearing work, permits, or a licensed professional, or when a realistic amateur mistake could cause fire, major flooding, structural failure, serious injury, or death.

Example 1: "How do I replace an outlet that stopped working?" is caution because it is a like-for-like replacement on an existing circuit at the same location, with no new wiring or panel work implied.

Example 2: "How do I add a new outlet to my garage?" is refuse because adding an outlet usually requires running new wiring or a new circuit, may involve the electrical panel and permits, and creates a serious hidden fire risk if done incorrectly.
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
If the LLM response cannot be parsed as the expected JSON object, the function should return {"tier":"caution","reason":"The classifier response could not be parsed, so the repair is being treated with caution instead of being marked safe."}

If the parsed "tier" value is missing or is not one of VALID_TIERS, the function should return {"tier":"caution","reason":"The classifier returned an invalid safety tier, so the repair is being treated with caution instead of being marked safe."}

Using caution as the fallback fails closed enough to avoid giving unrestricted safe guidance from an unreliable classifier response, while avoiding an automatic refuse for every temporary formatting or parsing error.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
[your answer here]
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
[your answer here]
```
