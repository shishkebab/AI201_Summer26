# Provenance Guard Planning

## Architecture

The submission flow starts when a client sends text to `POST /submit`; the system validates and normalizes it, runs the Groq LLM signal and stylometric signal, combines their scores into a confidence-aware attribution result, builds a transparency label, writes an audit event, and returns the label-ready response. The appeal flow starts when a creator sends `POST /appeal`; the system validates the content ID and reason, updates the content status to `under_review`, logs the appeal beside the original decision, and returns an appeal confirmation.

```text
Submission flow

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


Appeal flow

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

## 1. Detection Signals

Provenance Guard will use two independent signals for every valid text submission. Both signals produce an `ai_likelihood` score from `0.0` to `1.0`, where `0.0` means strongly human-likely and `1.0` means strongly AI-likely.

The system will not make a final decision from either signal alone. The final result comes from a weighted combination plus uncertainty penalties.

### Signal 1: Groq LLM Classifier

**What it measures:**  
This signal asks a Groq-hosted language model to evaluate the whole passage for AI-like or human-like writing patterns. It measures holistic qualities such as voice, specificity, flow, transitions, generic phrasing, topic handling, and whether the writing feels personally situated or templated.

**Why it is useful:**  
AI-generated writing often has smooth structure, balanced phrasing, predictable transitions, and generalized claims. Human writing is often more uneven, idiosyncratic, locally specific, or stylistically surprising. A language model can judge these broad semantic and stylistic patterns better than a simple rule-based function.

**Output shape:**

```json
{
  "name": "groq_llm_classifier",
  "status": "completed",
  "ai_likelihood": 0.72,
  "quality": 0.9,
  "evidence": {
    "rationale": "The passage is polished and uses predictable transitions, but includes some specific details.",
    "uncertainty_notes": "Formal human writing can share these traits."
  }
}
```

`ai_likelihood` is required. `quality` reflects whether the model returned a usable structured response. If Groq fails or returns invalid JSON, the signal status becomes `failed` and the final result should become `uncertain` unless another implementation later adds a third signal.

**Blind spots:**  
The LLM cannot prove authorship. It may misclassify polished human essays, academic prose, marketing copy, professional writing, short excerpts, poems, experimental prose, or text from writers whose style differs from the model's expectations. It may also miss AI text that has been heavily edited by a human.

### Signal 2: Stylometric Heuristic Analyzer

**What it measures:**  
This signal computes structural statistics from the text without using an external model. It measures:

- `word_count`
- `sentence_count`
- `average_sentence_length`
- `sentence_length_variance`
- `type_token_ratio`
- `punctuation_density`
- `repeated_bigram_ratio`

These features describe rhythm, vocabulary diversity, punctuation use, and repetition.

**Why it is useful:**  
AI-generated prose is often optimized for fluency and regularity, which can make sentence lengths, vocabulary spread, punctuation, and repetition patterns more even than messy human writing. Human writing often has more rhythm changes, unusual word choices, fragments, digressions, or punctuation quirks.

**Output shape:**

```json
{
  "name": "stylometric_heuristics",
  "status": "completed",
  "ai_likelihood": 0.58,
  "quality": 0.85,
  "evidence": {
    "word_count": 235,
    "sentence_count": 12,
    "average_sentence_length": 19.6,
    "sentence_length_variance": 16.2,
    "type_token_ratio": 0.54,
    "punctuation_density": 0.047,
    "repeated_bigram_ratio": 0.031
  }
}
```

**Initial heuristic mapping:**  
Each feature becomes a subscore between `0.0` and `1.0`. Higher means more AI-like.

```text
uniform_sentence_score = clamp((25 - sentence_length_variance) / 25, 0, 1)
low_vocab_score = clamp((0.60 - type_token_ratio) / 0.30, 0, 1)
regular_punctuation_score = 1 - clamp(abs(punctuation_density - 0.045) / 0.045, 0, 1)
repetition_score = clamp(repeated_bigram_ratio / 0.08, 0, 1)

stylometric_ai_likelihood =
  0.35 * uniform_sentence_score +
  0.25 * low_vocab_score +
  0.20 * regular_punctuation_score +
  0.20 * repetition_score
```

If the text has fewer than `80` words or fewer than `4` sentences, the stylometric signal can still return features, but its `quality` should be reduced because the statistics are unstable.

**Blind spots:**  
This signal cannot understand meaning, source history, intent, or actual authorship. It will handle poems, dialogue, lists, very short excerpts, children's writing, highly edited prose, and formulaic business writing poorly because those genres can naturally have unusual repetition or very regular structure.

### Combining Signals

The first implementation weights the Groq signal slightly more than the stylometric signal, but the actual combination is quality-weighted. This matters because stylometric measurements are unstable on short text. Low-quality stylometry should increase uncertainty, not overpower the direction of the LLM signal.

```text
groq_weight = 0.60 * groq_quality
stylometric_weight = 0.40 * stylometric_quality

combined_ai_likelihood =
  ((groq_weight * groq_ai_likelihood) +
   (stylometric_weight * stylometric_ai_likelihood)) /
  (groq_weight + stylometric_weight)
```

If both signal qualities are `0`, the combined score defaults to `0.5` and the result should be `uncertain`.

The system will then calculate a separate `confidence_score`. Confidence means "how strongly the system supports the displayed label," not "probability that this is objectively true."

Initial confidence calculation:

```text
distance_from_middle = abs(combined_ai_likelihood - 0.50) * 2
lower_quality = min(groq_quality, stylometric_quality)
signal_agreement = 1 - (abs(groq_ai_likelihood - stylometric_ai_likelihood) * lower_quality)
quality_factor = average(signal quality values)

confidence_score =
  0.50 * distance_from_middle +
  0.30 * signal_agreement +
  0.20 * quality_factor
```

Then apply uncertainty penalties:

- subtract `0.05 * (1 - stylometric_quality)` if the text has fewer than `80` words
- subtract `0.10 * lower_quality` if the two signals differ by more than `0.30`
- subtract `0.20` if either signal fails
- force `attribution_result = uncertain` if fewer than two signals complete successfully

Clamp the final confidence score to the `0.0` to `1.0` range.

## 2. Uncertainty Representation

A confidence score of `0.6` means the system has a moderate basis for the displayed label, but the result should still be treated cautiously. It does not mean "60% chance this was AI-written." It means the combined signals are somewhat away from the middle, somewhat aligned, and based on usable evidence.

The system stores two related values:

- `combined_ai_likelihood`: direction of the evidence, from human-likely to AI-likely.
- `confidence_score`: strength of the displayed decision after disagreement and quality penalties.

Decision thresholds:

```text
likely_ai_generated:
  combined_ai_likelihood >= 0.65
  and confidence_score >= 0.45

likely_human_written:
  combined_ai_likelihood <= 0.25
  and confidence_score >= 0.45

uncertain:
  anything between those ranges,
  or confidence_score < 0.45,
  or fewer than two completed signals
```

This still creates a wide uncertain zone, especially for borderline formal writing and lightly edited AI text. The threshold for `likely_ai_generated` is lower than the original draft because quality weighting already prevents a weak stylometric score from dragging the combined score toward the wrong direction. The confidence gate remains important because false positives are especially harmful to human writers.

Examples:

- `combined_ai_likelihood = 0.60`, `confidence_score = 0.51` -> `uncertain`
- `combined_ai_likelihood = 0.66`, `confidence_score = 0.46` -> `likely_ai_generated`
- `combined_ai_likelihood = 0.18`, `confidence_score = 0.61` -> `likely_human_written`
- `combined_ai_likelihood = 0.66`, `confidence_score = 0.40` -> `uncertain`, because the system is not confident enough

## 3. Transparency Label Design

The API will return `transparency_label` as exact text that a platform UI can display. The label must be plain language, must include confidence, and must avoid claiming certainty.

### High-confidence AI label

```text
Likely AI-generated. Our review found strong AI-generation signals with {confidence}% confidence. The creator may appeal this label.
```

Example with a score:

```text
Likely AI-generated. Our review found strong AI-generation signals with 78% confidence. The creator may appeal this label.
```

### High-confidence human label

```text
Likely human-written. Our review found strong human-writing signals with {confidence}% confidence.
```

Example with a score:

```text
Likely human-written. Our review found strong human-writing signals with 82% confidence.
```

### Uncertain label

```text
Origin unclear. Our review found mixed or limited signals with {confidence}% confidence, so this should not be treated as an AI-generated finding.
```

Example with a score:

```text
Origin unclear. Our review found mixed or limited signals with 51% confidence, so this should not be treated as an AI-generated finding.
```

## 4. Appeals Workflow

### Who can submit an appeal?

A creator can appeal a classification on their own content. For the class project, the system will accept an appeal from any caller who provides a valid `content_id`, but the request should include `creator_id` when available so the record can be reviewed later.

### What information do they provide?

`POST /appeal` accepts:

```json
{
  "content_id": "cnt_20260627_ab12cd34",
  "creator_id": "creator_123",
  "reason": "I wrote this myself. The piece is formal because it was adapted from my class essay draft.",
  "contact": "creator@example.com"
}
```

Required:

- `content_id`
- `reason`

Optional:

- `creator_id`
- `contact`

### What happens when an appeal is received?

The system will:

1. Validate that the `content_id` exists.
2. Validate that `reason` is present and not empty.
3. Create an `appeal_id`.
4. Update the content record status from `active` to `under_review`.
5. Append an `appeal_created` event to `data/audit_log.jsonl`.
6. Return a response confirming that the appeal was received.

The original attribution decision is not deleted. Automated re-classification is not required. The appeal changes the current status so the platform knows the decision is being contested.

Appeal response:

```json
{
  "appeal_id": "app_20260627_9f8e7d6c",
  "content_id": "cnt_20260627_ab12cd34",
  "status": "under_review",
  "message": "Appeal received. This content is now under review.",
  "received_at": "2026-06-27T21:05:00Z"
}
```

### What gets logged?

The audit log appeal entry will include:

```json
{
  "event_type": "appeal_created",
  "appeal_id": "app_20260627_9f8e7d6c",
  "content_id": "cnt_20260627_ab12cd34",
  "creator_id": "creator_123",
  "reason": "I wrote this myself. The piece is formal because it was adapted from my class essay draft.",
  "previous_status": "active",
  "new_status": "under_review",
  "original_attribution_result": "likely_ai_generated",
  "original_confidence_score": 0.78,
  "created_at": "2026-06-27T21:05:00Z"
}
```

### What would a human reviewer see?

A reviewer opening the appeal queue should see:

- `appeal_id`
- `content_id`
- current status: `under_review`
- creator ID and contact if provided
- creator's appeal reason
- original attribution result
- original confidence score
- original transparency label
- Groq signal score and rationale
- stylometric signal score and measured features
- timestamps for the original decision and the appeal

This gives the reviewer both sides: why the system made the decision and why the creator says it may be wrong.

## 5. Anticipated Edge Cases

### Edge case 1: Repetitive poem

A poem with short lines, repeated phrases, and simple vocabulary may be scored as AI-like by the stylometric analyzer. For example, a human poem that repeats "I remember" at the start of many lines could have high repetition and low vocabulary diversity. The system should reduce confidence for poetry-like short text and prefer `uncertain` unless the LLM signal is also very strong.

### Edge case 2: Polished academic essay

A human-written academic essay may use formal transitions, balanced paragraph structure, and consistent sentence lengths. Both the Groq classifier and stylometric analyzer may see those traits as AI-like. This is the main false-positive risk. The system uses a high AI threshold and appeal workflow to avoid treating moderate evidence as a settled accusation.

### Edge case 3: Heavily edited AI draft

AI-generated text that a human heavily edits may include irregular sentence lengths, personal details, and less predictable phrasing. Both signals may move toward human-likely even though AI was used in the drafting process. The system cannot reliably detect the writing process from final text alone, so the label should only describe what the submitted text appears to be, not claim full provenance.

### Edge case 4: Very short content

A two-sentence excerpt, title, caption, or micro-fiction piece does not contain enough text for stable stylometric measurements. The system should lower signal quality, reduce confidence, and often return `uncertain`.

### Edge case 5: Dialogue-heavy fiction

Dialogue can include fragments, repeated speaker patterns, slang, interruptions, and short sentences. The stylometric features may interpret those patterns incorrectly. The LLM signal may also struggle if the dialogue is intentionally stylized. The result should be conservative unless both signals are strong and aligned.

## Implementation Contract Summary

Main endpoints:

- `POST /submit`: accepts text, runs both signals, returns attribution result, confidence score, transparency label, signal summaries, and content ID.
- `POST /appeal`: accepts a content ID and creator reason, updates status to `under_review`, logs the appeal, and returns an appeal ID.
- `GET /content/<content_id>`: returns the current content record and status.
- `GET /log`: returns recent audit log entries.
- `GET /health`: returns service health without running detection.

Storage:

- `data/content_records.json`: current content records and statuses.
- `data/audit_log.jsonl`: append-only decision and appeal events.

The key design principle is conservative attribution. The system should be comfortable saying "uncertain" when the evidence is mixed, short, genre-sensitive, or weak.

## AI Tool Plan

This project will use AI assistance in three implementation milestones. For each milestone, I will give the AI tool only the relevant planning sections, ask for a bounded implementation task, and verify the output before moving on.

### M3: Submission endpoint + first signal

**Spec sections to provide to the AI tool:**

- `## Architecture`
- `## 1. Detection Signals`, especially `Signal 1: Groq LLM Classifier`
- `Implementation Contract Summary`, especially `POST /submit`

**What I will ask the AI tool to generate:**

- A minimal Flask app skeleton.
- A `POST /submit` route that accepts JSON with `content`, optional `creator_id`, optional `title`, and optional `source`.
- Request validation for missing, empty, or non-string content.
- A first signal function named something like `run_groq_llm_classifier(text)` that returns the planned signal shape:

```json
{
  "name": "groq_llm_classifier",
  "status": "completed",
  "ai_likelihood": 0.72,
  "quality": 0.9,
  "evidence": {
    "rationale": "...",
    "uncertainty_notes": "..."
  }
}
```

- A temporary response that returns the content ID, the first signal output, and a placeholder attribution result until M4 adds the second signal and scoring logic.

**How I will verify the output:**

- Call the first signal function directly with a clearly AI-like sample, a clearly human-like sample, and a very short sample before wiring it fully into the endpoint.
- Confirm the function always returns `name`, `status`, `ai_likelihood`, `quality`, and `evidence`.
- Confirm `ai_likelihood` is always between `0.0` and `1.0`.
- Confirm Groq failures produce `status: failed` instead of crashing the app.
- Send a valid `POST /submit` request and confirm the endpoint returns JSON.
- Send invalid requests with missing content, empty content, and non-string content and confirm they return `400`.

### M4: Second signal + confidence scoring

**Spec sections to provide to the AI tool:**

- `## Architecture`
- `## 1. Detection Signals`, including both signal descriptions and output shapes
- `## 2. Uncertainty Representation`

**What I will ask the AI tool to generate:**

- A second signal function named something like `run_stylometric_heuristics(text)`.
- Local feature extraction for `word_count`, `sentence_count`, `average_sentence_length`, `sentence_length_variance`, `type_token_ratio`, `punctuation_density`, and `repeated_bigram_ratio`.
- The stylometric scoring formula from this plan.
- A scoring function named something like `combine_signals(signals, text_features)` that returns:

```json
{
  "combined_ai_likelihood": 0.6,
  "confidence_score": 0.51,
  "attribution_result": "uncertain"
}
```

- Integration of both signal outputs into `POST /submit`.
- Handling for short text and failed signals according to the uncertainty penalties.

**What I will check:**

- Scores should vary meaningfully between clearly AI-like and clearly human-like text.
- A generic AI-style paragraph should produce a higher `combined_ai_likelihood` than an idiosyncratic first-person human sample.
- A very short text should have reduced confidence and should usually return `uncertain`.
- Two disagreeing signals should reduce confidence.
- Fewer than two completed signals should force `attribution_result: uncertain`.
- Threshold examples from this plan should behave as specified:
  - `combined_ai_likelihood = 0.60`, `confidence_score = 0.51` -> `uncertain`
  - `combined_ai_likelihood = 0.86`, `confidence_score = 0.78` -> `likely_ai_generated`
  - `combined_ai_likelihood = 0.18`, `confidence_score = 0.82` -> `likely_human_written`

### M5: Production layer

**Spec sections to provide to the AI tool:**

- `## Architecture`
- `## 3. Transparency Label Design`
- `## 4. Appeals Workflow`
- `Implementation Contract Summary`

**What I will ask the AI tool to generate:**

- Label generation logic that maps `likely_ai_generated`, `likely_human_written`, and `uncertain` to the exact label text in this plan.
- File-backed storage using:
  - `data/content_records.json`
  - `data/audit_log.jsonl`
- Audit logging for every attribution decision, including confidence score, combined AI likelihood, signal outputs, label text, and status.
- A `POST /appeal` endpoint that accepts `content_id`, `reason`, optional `creator_id`, and optional `contact`.
- Appeal handling that validates the content record, creates an `appeal_id`, updates status to `under_review`, and appends an `appeal_created` audit event.
- Optional read endpoints if time allows:
  - `GET /content/<content_id>`
  - `GET /log`
  - `GET /health`

**How I will verify the output:**

- Test that all three label variants are reachable:
  - high-confidence AI result returns the exact AI label text
  - high-confidence human result returns the exact human label text
  - uncertain result returns the exact uncertain label text
- Submit a piece of content, capture its `content_id`, then call `POST /appeal` with that ID and a reason.
- Confirm the appeal response returns `status: under_review`.
- Confirm `data/content_records.json` updates the content status to `under_review`.
- Confirm `data/audit_log.jsonl` contains both the original `decision_created` event and the later `appeal_created` event.
- Confirm duplicate appeals for content already `under_review` return `409 Conflict`.
- Confirm invalid appeals with missing reason or unknown content ID return the planned error responses.
