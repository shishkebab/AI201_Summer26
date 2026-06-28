# Provenance Guard Architecture Narrative

## Core architectural decisions

Provenance Guard will be a small Flask API service. The main job of the service is not to "prove" whether text was written by a person or by AI. The job is to collect multiple independent signals, combine them conservatively, explain the result plainly, and leave an appeal path when the system might be wrong.

The system will use two required detection signals:

1. **Groq LLM classifier**: asks a language model to judge whether the text reads as human-written or AI-generated. This captures holistic semantic and stylistic patterns that are hard to express as simple formulas.
2. **Stylometric heuristic analyzer**: computes measurable properties of the text, such as sentence-length variance, vocabulary diversity, punctuation density, repetition, and average sentence complexity. This captures the structure of the writing without asking a model to interpret the meaning.

These signals are intentionally different. The LLM signal is interpretive. The stylometric signal is statistical. Combining them is more useful than running two versions of the same detector.

## Detection signal decisions

### Signal 1: Groq LLM classifier

**What it measures:** The Groq LLM classifier measures whether the submitted text resembles writing patterns that a language model recognizes as AI-generated or human-written. It looks at the whole passage: flow, phrasing, specificity, voice, transitions, level of polish, topic handling, and whether the text feels generic, templated, or personally situated.

**Why this property may differ between human and AI writing:** AI-generated writing often has a smooth, evenly structured quality. It may use balanced paragraphs, predictable transitions, generalized claims, and consistent tone even when the subject would normally invite more unevenness or personal texture. Human writing is often more idiosyncratic: it may include sharper preferences, inconsistent rhythm, unusual details, local context, or rough edges that come from a specific person's choices. The LLM signal is useful because it can evaluate these holistic patterns better than a simple formula.

**What it cannot capture:** This signal cannot prove authorship. It only estimates resemblance to known writing patterns. It may misread polished human writing as AI-generated, especially in formal, academic, marketing, or professional styles. It may also miss AI text that has been heavily edited, prompted to imitate a personal voice, or mixed with human writing. It is weaker on very short submissions, poetry, experimental prose, niche technical writing, and text from writers whose style differs from the model's expectations. It also depends on an external model call, so failures, latency, prompt sensitivity, and model variability are real risks.

### Signal 2: Stylometric heuristic analyzer

**What it measures:** The stylometric analyzer measures the statistical shape of the text. The planned features are sentence length variance, average sentence length, type-token ratio, punctuation density, repeated phrase patterns, word count, sentence count, and possibly a simple complexity estimate. Together, these features describe rhythm, vocabulary spread, repetition, and structural regularity.

**Why this property may differ between human and AI writing:** Many AI-generated passages are optimized for fluency and coherence, which can make their sentence lengths, paragraph structure, punctuation, and vocabulary distribution unusually even. Human writing often has more irregular rhythm: short fragments beside long sentences, repeated favorite words, odd punctuation choices, digressions, abrupt turns, or highly specific vocabulary. A structural signal is useful because it does not ask a model for an opinion; it independently measures surface-level patterns in the text.

**What it cannot capture:** This signal cannot understand meaning, intent, source history, or whether a writer actually used AI. It can only measure structure. It is sensitive to genre and length: poems, dialogue, lists, short excerpts, children's writing, highly edited prose, and formulaic business writing can distort the statistics. A careful human editor can make AI text look more irregular, and a careful human writer can produce very smooth text that looks AI-like. Stylometry is also weak when the passage is too short to produce stable measurements.

The decision engine will be conservative because a false positive is especially harmful on a writing platform. Labeling a human creator's work as AI-generated is worse than failing to catch every AI-generated submission. For that reason, the system will require stronger evidence before showing a high-confidence AI label. Mixed evidence or weak evidence will produce an uncertain label instead of an accusation.

Confidence will mean "how strongly the system supports the displayed label," not "objective truth." A confidence score near `0.51` means the system barely has enough signal to lean in one direction, so the user-facing label should be uncertain. A confidence score near `0.95` means the signals are strong and aligned, so the label can speak more directly.

The first implementation will use file-backed storage instead of a database:

- `data/content_records.json` stores the current status for each submitted content item.
- `data/audit_log.jsonl` stores append-only decision and appeal events.

This keeps the project understandable while still supporting the required audit log and appeals workflow.

## The path from submitted text to the label the user sees

A single piece of text starts with a creator or platform client sending it to the **Content Submission Endpoint**, `POST /submit`. The request includes the text content and may include optional metadata such as a creator ID, title, or source page. This endpoint is the public front door for attribution analysis.

Before the endpoint does any analysis, the request passes through the **Rate Limiter**. The rate limiter is enforced by `Flask-Limiter`. It checks the caller identity, most likely by IP address for the class project and by creator ID if one is provided. If the caller has submitted too many requests in the configured window, the system stops here and returns a `429` response. No attribution label is created because no attribution decision was made.

If the request is allowed, the **Submission Controller** receives it. The controller is the Flask route handler for `POST /submit`. Its job is to coordinate the workflow, not to perform detection itself. It passes the incoming request to the validator, calls the detection pipeline, asks for a label, records the result, and returns the structured API response.

The text then goes to the **Request Validator**. The validator checks that the content field exists, is a string, is not empty, and is within the accepted length range. Invalid submissions stop here with a `400` response. This protects the detection pipeline from meaningless input and makes failures clear to the caller.

Valid text then goes to the **Text Normalizer**. The normalizer trims leading and trailing whitespace, standardizes line endings, and prepares a clean analysis copy of the text. The original wording is not rewritten. Normalization only removes formatting noise that could distort simple statistics.

The normalized text then goes to the **Content ID Generator**. This component creates a stable `content_id`, likely from a timestamp plus a hash of the text. The content ID lets the system connect the original decision, the audit log entry, and any future appeal without relying on the full text as the identifier.

Next, the Submission Controller hands the content ID and normalized text to the **Detection Pipeline Orchestrator**. The orchestrator is responsible for running all detection signals and collecting their outputs in one standard shape. Each signal must return its name, the score it produced, the features or rationale behind that score, and whether it completed successfully.

The first signal is the **Groq LLM Classifier**. This component sends the text to Groq with a narrow prompt that asks for a JSON-style judgment: an AI-likelihood score, a short rationale, and any uncertainty notes. The classifier converts the model response into a number between `0.0` and `1.0`, where `0.0` means strongly human-likely and `1.0` means strongly AI-likely. If Groq is unavailable or the model returns an unusable response, this signal is marked as failed rather than silently ignored.

The second signal is the **Stylometric Heuristic Analyzer**. This component runs locally in Python. It does not call an external model. It calculates structural features such as word count, sentence count, average sentence length, sentence length variance, type-token ratio, punctuation density, and repeated phrase patterns. It then maps those measurements to an AI-likelihood score between `0.0` and `1.0`. The analyzer also returns the measured features so the audit log can show what evidence was used.

Both signal outputs then go to the **Signal Normalizer**. This component makes sure every signal speaks the same language: `signal_name`, `ai_likelihood`, `confidence_or_quality`, `evidence`, and `status`. This matters because the LLM classifier and the stylometric analyzer produce very different raw information.

The normalized signals then go to the **Decision and Confidence Engine**. This component combines the signals into one attribution result. The planned starting weights are `60%` Groq LLM classifier and `40%` stylometric analyzer because the LLM can evaluate meaning and flow, while the stylometric signal provides an independent structural check. The engine will reduce confidence when the signals disagree, when the text is very short, or when one signal fails.

The Decision and Confidence Engine produces three values:

- `combined_ai_likelihood`: the weighted estimate that the text appears AI-generated.
- `confidence_score`: how strongly the system supports the displayed result after uncertainty penalties.
- `attribution_result`: one of `likely_ai_generated`, `likely_human_written`, or `uncertain`.

The planned thresholds are intentionally conservative:

- Show `likely_ai_generated` only when the combined AI likelihood is very high, around `0.82` or above, and confidence remains strong after disagreement penalties.
- Show `likely_human_written` when the combined AI likelihood is low, around `0.25` or below, and confidence is strong.
- Show `uncertain` for the wide middle area, for mixed signals, for very short text, or for degraded analysis.

If fewer than two signals complete successfully, the system should not pretend it ran a full multi-signal pipeline. It should return an `uncertain` result, record the failed signal in the audit log, and explain that there was not enough reliable evidence for a stronger label.

The attribution result and confidence score then go to the **Transparency Label Builder**. This component translates the technical decision into the plain-language label a reader sees. The label builder is where a `0.51` and a `0.95` become visibly different experiences.

The three planned label variants are:

- **High-confidence AI label**: "Likely AI-generated. Our review found strong AI-generation signals with {confidence}% confidence. The creator may appeal this label."
- **High-confidence human label**: "Likely human-written. Our review found strong human-writing signals with {confidence}% confidence."
- **Uncertain label**: "Origin unclear. Our review found mixed or limited signals with {confidence}% confidence, so this should not be treated as an AI-generated finding."

After the label is created, the full decision goes to the **Content Record Store**. This store writes or updates the current record for the content ID. The record includes the content ID, current status, attribution result, confidence score, label text, and timestamp. A newly analyzed item starts with status `active` unless the result is later appealed.

The same decision also goes to the **Audit Logger**. The audit logger appends a structured event to `data/audit_log.jsonl`. This event includes the timestamp, content ID, attribution result, confidence score, combined AI likelihood, each signal used, each signal's score or features, the final label text, and the content status. The audit log is append-only so the original decision remains visible even if an appeal happens later.

Finally, the **Response Formatter** returns the structured API response to the caller. The response includes the content ID, attribution result, confidence score, transparency label text, status, and a compact summary of the signals used. This is the response the platform would use to display the transparency label beside the submitted text.

## Appeal path after a label is shown

If a creator disagrees with a label, they send a request to the **Appeals Endpoint**, `POST /appeal`. The request includes the `content_id` and the creator's reasoning.

The appeal first goes through the **Appeal Validator**. It checks that the content ID exists and that the reasoning field is present and meaningful. Invalid appeals return a `400` response.

Valid appeals go to the **Appeal Handler**. The handler does not automatically re-classify the text. Instead, it updates the content's current status in the Content Record Store to `under_review`. This is important because the original decision should not disappear, but the platform should also stop treating the label as final while a human review is pending.

The appeal then goes to the **Audit Logger** as a new append-only event. The appeal event records the content ID, the original attribution result, the original confidence score, the creator's reasoning, the new `under_review` status, and the appeal timestamp. This satisfies the requirement that appeals be logged alongside the original decision.

The Appeals Endpoint returns a structured response confirming that the content is now `under_review`. The reader-facing platform can then display a review status instead of treating the original classification as settled.

## False positive scenario

The most important failure mode is a false positive: a human writer submits their own work, but Provenance Guard labels it as AI-generated. This is more harmful than missing some AI-generated work because it can damage a creator's reputation, discourage original writing, and make the platform feel hostile to careful or polished writers.

Imagine a human writer submits a clean, formal essay. The writing is polished, evenly structured, and uses conventional transitions. That text enters the same path as every other submission: `POST /submit`, rate limiting, validation, normalization, content ID generation, and then the detection pipeline.

The **Groq LLM Classifier** might score the essay as AI-likely because the voice is smooth, generalized, and highly organized. The **Stylometric Heuristic Analyzer** might also produce an AI-leaning score if the sentence lengths are very consistent, the vocabulary distribution is even, and the punctuation pattern is regular. This is exactly where the system can make a mistake: polished human writing can share surface traits with AI-generated writing.

The **Decision and Confidence Engine** should respond to this risk conservatively. It should not treat every AI-leaning score as a high-confidence AI label. It should reduce confidence when:

- the two signals disagree or only weakly agree
- the text is short
- the AI-likelihood score is near the middle rather than extreme
- the stylometric evidence is based on genre-sensitive features
- the LLM rationale uses vague clues like "polished" or "structured" without stronger evidence

For a borderline case, the system should produce `uncertain`, not `likely_ai_generated`. For example, if the combined AI likelihood is around `0.60` and the confidence score is around `0.51`, the label should say: "Origin unclear. Our review found mixed or limited signals with 51% confidence, so this should not be treated as an AI-generated finding." That wording matters because it prevents a weak signal from becoming a public accusation.

A false positive only reaches the reader-facing AI label if the signals align strongly enough to pass the conservative AI threshold. For example, the combined AI likelihood might be `0.86` and the confidence score might be `0.78`, producing: "Likely AI-generated. Our review found strong AI-generation signals with 78% confidence. The creator may appeal this label." Even here, the label says "likely," includes the confidence score, and explicitly tells the creator that appeal is available. It should not say "AI-written" as a fact.

When the creator appeals, they call `POST /appeal` with the `content_id` and their reasoning. Their reasoning might say that the piece is original, describe their drafting process, or explain why the style is formal. The **Appeal Validator** checks that the content exists and that the creator provided meaningful reasoning. The **Appeal Handler** then changes the content status to `under_review` without deleting the original decision.

The **Audit Logger** appends the appeal as a new event beside the original decision. The log now shows both the mistaken classification and the creator's challenge: original confidence score, original signal scores, label text, appeal reasoning, appeal timestamp, and new status. This is important because a reviewer can see why the system made the decision and why the creator disputes it.

Once the content is `under_review`, the platform should stop presenting the AI label as settled. The reader-facing experience can show a review status, while the backend keeps the original decision available for audit. Automated re-classification is not required; the appeal exists so a human process can correct the system when its signals are too blunt.

## Main flow diagrams

These diagrams show the two paths the system must implement. The signal steps are shown in sequence because that is the easiest contract to implement and test, but the two signals remain conceptually independent: Signal 2 does not depend on Signal 1's opinion; the orchestrator simply carries both results forward.

### Submission flow

```text
[Creator or Platform Client]
        |
        | POST /submit
        | passes: raw text + optional creator_id/title/source
        v
[Submission Controller]
        |
        | passes: raw text + request metadata
        v
[Rate Limiter + Request Validator]
        |
        | passes: accepted raw text + validated metadata
        v
[Text Normalizer + Content ID Generator]
        |
        | passes: normalized text + content_id
        v
[Signal 1: Groq LLM Classifier]
        |
        | passes: signal_1_score + LLM rationale + normalized text
        v
[Signal 2: Stylometric Heuristic Analyzer]
        |
        | passes: signal_1_score + signal_2_score + stylometric features
        v
[Decision and Confidence Engine]
        |
        | passes: combined_ai_likelihood + confidence_score + attribution_result
        v
[Transparency Label Builder]
        |
        | passes: label text + decision packet
        v
[Audit Logger]
        |
        | writes: decision event with confidence score, signals used, label text
        | passes: auditable decision packet
        v
[Response Formatter]
        |
        | returns: content_id + attribution_result + confidence_score
        |          + transparency label + signal summaries + status
        v
[Creator or Platform Client]
```

The submission response is the reader-facing contract: it gives the platform the exact transparency label to display, plus enough structured detail to explain how the decision was reached.

### Appeal flow

```text
[Creator]
        |
        | POST /appeal
        | passes: content_id + creator reasoning + optional creator_id/contact
        v
[Appeal Controller]
        |
        | passes: content_id + appeal reason
        v
[Appeal Validator]
        |
        | passes: valid appeal + existing content record
        v
[Content Record Store]
        |
        | updates: status active -> under_review
        | passes: updated status + original decision summary
        v
[Audit Logger]
        |
        | writes: appeal event with reason, previous status, new status
        | passes: appeal_id + under_review status
        v
[Response Formatter]
        |
        | returns: appeal_id + content_id + status under_review + received_at
        v
[Creator]
```

The appeal flow does not erase or replace the original attribution decision. It adds a new audit event and changes the current content status so the platform can stop treating the label as settled while review is pending.

## API surface contract

The API surface should stay small and explicit. Every endpoint either creates an attribution decision, contests a decision, or reads back system state for transparency.

```text
Client / Platform
      |
      | POST /submit
      v
+--------------------------+
| Content Submission API   |
+--------------------------+
      |
      | creates content_id, decision, label, audit event
      v
+--------------------------+
| Content + Audit Storage  |
+--------------------------+
      ^
      | creates appeal event and status change
      |
+--------------------------+
| Appeals API              |
+--------------------------+
      ^
      | POST /appeal
      |
Creator

Reviewer / Demo Client
      |
      | GET /log
      | GET /content/<content_id>
      v
+--------------------------+
| Read APIs                |
+--------------------------+
```

### `POST /submit`

Creates a new attribution analysis for a piece of text. This is the main submission endpoint and the only endpoint that runs the detection pipeline.

**Accepts JSON:**

```json
{
  "content": "The text to analyze.",
  "creator_id": "creator_123",
  "title": "Optional title",
  "source": "optional-platform-location"
}
```

Required fields:

- `content`: non-empty string containing the text to analyze.

Optional fields:

- `creator_id`: stable creator identifier if the client has one.
- `title`: human-readable title for the content.
- `source`: page, draft ID, or platform context where the content came from.

**Returns `201 Created` JSON:**

```json
{
  "content_id": "cnt_20260627_ab12cd34",
  "status": "active",
  "attribution_result": "uncertain",
  "confidence_score": 0.51,
  "combined_ai_likelihood": 0.6,
  "transparency_label": "Origin unclear. Our review found mixed or limited signals with 51% confidence, so this should not be treated as an AI-generated finding.",
  "signals": [
    {
      "name": "groq_llm_classifier",
      "status": "completed",
      "ai_likelihood": 0.67,
      "evidence": {
        "rationale": "The text is polished and uses predictable transitions, but includes some specific personal details."
      }
    },
    {
      "name": "stylometric_heuristics",
      "status": "completed",
      "ai_likelihood": 0.49,
      "evidence": {
        "sentence_length_variance": 18.4,
        "type_token_ratio": 0.62,
        "punctuation_density": 0.04
      }
    }
  ],
  "created_at": "2026-06-27T21:00:00Z"
}
```

Possible errors:

- `400 Bad Request`: missing content, empty content, wrong type, or text outside accepted length limits.
- `429 Too Many Requests`: caller exceeded the submission rate limit.
- `500 Internal Server Error`: unexpected server failure. The response should not expose secrets or raw provider errors.

If one detection signal fails but the request itself is valid, the endpoint should still return a structured response when possible. The result should become `uncertain` if fewer than two signals complete successfully.

### `POST /appeal`

Creates an appeal for an existing attribution decision and marks the content as `under_review`. This endpoint does not run automated re-classification.

**Accepts JSON:**

```json
{
  "content_id": "cnt_20260627_ab12cd34",
  "creator_id": "creator_123",
  "reason": "I wrote this myself. The piece is formal because it was adapted from my class essay draft.",
  "contact": "creator@example.com"
}
```

Required fields:

- `content_id`: ID returned by `POST /submit`.
- `reason`: creator's explanation for contesting the label.

Optional fields:

- `creator_id`: stable creator identifier if available.
- `contact`: contact information for follow-up review.

**Returns `200 OK` JSON:**

```json
{
  "appeal_id": "app_20260627_9f8e7d6c",
  "content_id": "cnt_20260627_ab12cd34",
  "status": "under_review",
  "message": "Appeal received. This content is now under review.",
  "received_at": "2026-06-27T21:05:00Z"
}
```

Possible errors:

- `400 Bad Request`: missing content ID, missing reason, or empty reason.
- `404 Not Found`: no content record exists for the provided content ID.
- `409 Conflict`: the content is already under review and a duplicate appeal should not create a second active review.

### `GET /content/<content_id>`

Returns the current state of one analyzed content item. This is useful for a platform UI that needs to check whether a label is still active or has moved under review.

**Accepts path parameter:**

- `content_id`: ID returned by `POST /submit`.

**Returns `200 OK` JSON:**

```json
{
  "content_id": "cnt_20260627_ab12cd34",
  "status": "under_review",
  "attribution_result": "likely_ai_generated",
  "confidence_score": 0.78,
  "combined_ai_likelihood": 0.86,
  "transparency_label": "Likely AI-generated. Our review found strong AI-generation signals with 78% confidence. The creator may appeal this label.",
  "created_at": "2026-06-27T21:00:00Z",
  "updated_at": "2026-06-27T21:05:00Z"
}
```

Possible errors:

- `404 Not Found`: no content record exists for the provided content ID.

### `GET /log`

Returns recent structured audit log entries for demonstration and transparency. This endpoint should show attribution decisions and appeals in the order they were recorded.

**Accepts optional query parameters:**

- `limit`: maximum number of log entries to return. Default should be `20`.
- `content_id`: if provided, only return log entries for one content item.

**Returns `200 OK` JSON:**

```json
{
  "entries": [
    {
      "event_type": "decision_created",
      "content_id": "cnt_20260627_ab12cd34",
      "attribution_result": "likely_ai_generated",
      "confidence_score": 0.78,
      "combined_ai_likelihood": 0.86,
      "label_text": "Likely AI-generated. Our review found strong AI-generation signals with 78% confidence. The creator may appeal this label.",
      "signals": [
        {
          "name": "groq_llm_classifier",
          "ai_likelihood": 0.9,
          "status": "completed"
        },
        {
          "name": "stylometric_heuristics",
          "ai_likelihood": 0.8,
          "status": "completed"
        }
      ],
      "created_at": "2026-06-27T21:00:00Z"
    },
    {
      "event_type": "appeal_created",
      "appeal_id": "app_20260627_9f8e7d6c",
      "content_id": "cnt_20260627_ab12cd34",
      "previous_status": "active",
      "new_status": "under_review",
      "reason": "I wrote this myself. The piece is formal because it was adapted from my class essay draft.",
      "created_at": "2026-06-27T21:05:00Z"
    }
  ]
}
```

Possible errors:

- `400 Bad Request`: invalid `limit` value.

### `GET /health`

Returns a simple health check for local development and demos. It should not run the detection pipeline or call Groq.

**Returns `200 OK` JSON:**

```json
{
  "status": "ok",
  "service": "provenance-guard"
}
```

## Supporting read path

The project will also expose a **Log Endpoint**, `GET /log`, for development and demonstration. This endpoint reads recent entries from `data/audit_log.jsonl` and returns them as structured JSON. The README can document this output and include at least three visible entries to satisfy the audit log requirement.

If the stretch analytics dashboard is implemented later, it should read from the same audit log rather than inventing a separate tracking system. Detection patterns, appeal rates, and confidence distributions can all be derived from the append-only events.
