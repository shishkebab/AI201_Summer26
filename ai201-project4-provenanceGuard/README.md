# Provenance Guard

## Architecture Overview

Provenance Guard is a Flask API that turns a text submission into a cautious, auditable transparency label. The system does not try to prove authorship from one clue; it collects two independent detection signals, combines them with uncertainty-aware scoring, writes the decision to an audit log, and returns plain-language label text that a platform could display.

```text
[Creator or Platform Client]
        |
        | POST /submit
        | passes: text + creator_id
        v
[Flask Submission Route]
        |
        | passes: accepted request after rate limiting
        v
[Request Validator + Text Normalizer]
        |
        | passes: validated metadata + normalized text
        v
[Content ID Generator]
        |
        | passes: content_id + normalized text
        v
[Signal 1: Groq LLM Classifier]
        |
        | passes: llm_score + quality + rationale
        v
[Signal 2: Stylometric Heuristic Analyzer]
        |
        | passes: stylometric_score + quality + measured features
        v
[Decision and Confidence Engine]
        |
        | passes: combined_ai_likelihood + confidence + attribution
        v
[Transparency Label Builder]
        |
        | passes: label text
        v
[Content Record Store + Audit Logger]
        |
        | writes: current status + structured JSONL decision event
        v
[JSON Response]
        |
        | returns: content_id + attribution + confidence + label + signal summaries
        v
[Creator or Platform Client]
```

A submission starts when the client sends `POST /submit` with at least `text` and `creator_id`. Flask-Limiter first protects the route from abusive request volume, then the route validates the JSON body, normalizes the text, creates a unique `content_id`, and sends the text through the detection pipeline.

The first signal, the Groq LLM classifier, evaluates the passage holistically for AI-like or human-like writing patterns and returns an AI-likelihood score plus quality and rationale fields. The second signal, the stylometric heuristic analyzer, runs locally and measures structural features such as sentence length variance, type-token ratio, punctuation density, and repeated bigrams; it also returns an AI-likelihood score and quality value.

The decision engine combines those two scores with quality-weighted logic, penalizing weak inputs, signal disagreement, and failed signals. It produces `combined_ai_likelihood`, a separate `confidence` score, and one attribution category: `likely_ai_generated`, `likely_human_written`, or `uncertain`. The label builder then converts that decision into the exact transparency label shown to the user, such as "Likely AI-generated..." or "Origin unclear..." with the confidence percentage included.

Before the response is returned, the system saves the current content record and appends a structured event to `data/audit_log.jsonl`. The final `/submit` response includes the `content_id`, attribution result, confidence score, transparency label, status, and compact signal summaries, so the label can be displayed and later appealed using the same content ID.

Example successful `/submit` response:

```json
{
  "content_id": "cnt_20260628052501143237_f488da1d",
  "creator_id": "audit-demo-ai",
  "status": "analyzed",
  "attribution": "likely_ai_generated",
  "confidence": 0.873,
  "combined_ai_likelihood": 0.911,
  "label": "Likely AI-generated. Our review found strong AI-generation signals with 87% confidence. The creator may appeal this label.",
  "transparency_label": "Likely AI-generated. Our review found strong AI-generation signals with 87% confidence. The creator may appeal this label.",
  "signals": [
    {
      "name": "groq_llm_classifier",
      "status": "completed",
      "ai_likelihood": 0.93,
      "quality": 0.9,
      "evidence": {
        "rationale": "The passage is polished, generic, and uses predictable transitions.",
        "uncertainty_notes": "Formal human writing can share these traits."
      }
    },
    {
      "name": "stylometric_heuristics",
      "status": "completed",
      "ai_likelihood": 0.88,
      "quality": 0.85,
      "evidence": {
        "word_count": 96,
        "sentence_count": 5,
        "sentence_length_variance": 8.64,
        "type_token_ratio": 0.54,
        "punctuation_density": 0.047,
        "repeated_bigram_ratio": 0.031
      }
    }
  ],
  "created_at": "2026-06-28T05:25:01.143420+00:00"
}
```

---

## Detection Signals

Provenance Guard uses two independent signals for every valid submission. Each signal returns an `ai_likelihood` score from `0.0` to `1.0`, where `0.0` means strongly human-likely and `1.0` means strongly AI-likely. Neither signal is treated as proof on its own; the final label comes from combining the signals and then applying uncertainty rules.

### Signal 1: Groq LLM Classifier

The Groq LLM classifier measures whole-passage writing patterns that are difficult to capture with simple formulas. It looks for qualities such as voice, specificity, flow, transitions, level of polish, generic phrasing, and whether the writing feels personally situated or templated.

This signal was chosen because AI-generated prose often has a smooth, evenly organized quality: balanced paragraphs, predictable transitions, consistent tone, and generalized claims. Human writing is often more uneven or locally specific, with sharper preferences, rough edges, unusual details, or rhythm shifts. A language model is useful here because it can evaluate those semantic and stylistic patterns across the whole passage.

What it misses: the LLM classifier cannot prove authorship. It can misclassify polished human writing, academic prose, marketing copy, professional writing, short excerpts, poems, experimental prose, or work from writers whose style differs from the model's expectations. It can also miss AI text that has been heavily edited by a human or prompted to imitate a personal voice. If Groq fails or returns an unusable response, the signal is marked as failed and the system should become more uncertain.

### Signal 2: Stylometric Heuristic Analyzer

The stylometric heuristic analyzer measures the statistical shape of the text without using an external model. It computes features including word count, sentence count, average sentence length, sentence length variance, type-token ratio, punctuation density, and repeated bigram ratio. These features describe rhythm, vocabulary diversity, punctuation regularity, and repetition.

This signal was chosen because it gives the system an independent structural check. AI-generated prose is often optimized for fluency and coherence, which can make sentence lengths, vocabulary spread, punctuation, and repeated phrasing look unusually regular. Human writing often has more irregular rhythm: short fragments beside long sentences, repeated favorite words, abrupt turns, odd punctuation choices, or very specific vocabulary.

What it misses: stylometry cannot understand meaning, intent, drafting history, or actual authorship. It is sensitive to genre and length, so poems, dialogue, lists, very short excerpts, children's writing, highly edited prose, and formulaic business writing can produce misleading scores. A careful human editor can make AI text look less regular, and a careful human writer can produce smooth text that looks AI-like.

### How The Signals Are Combined

The decision engine combines the two `ai_likelihood` scores with quality-aware weights. The Groq signal carries more starting weight because it can evaluate meaning and flow, while the stylometric signal provides a local, model-independent check. Low-quality signals, short text, failed signals, and disagreement between the two signals reduce confidence rather than being hidden.

The output of scoring is not just one binary answer. The system stores `combined_ai_likelihood`, `confidence`, and `attribution`, then maps them to one of three label categories: `likely_ai_generated`, `likely_human_written`, or `uncertain`.

---

## Confidence Scoring

The scoring layer keeps two related values separate:

- `combined_ai_likelihood`: the direction of the evidence, from `0.0` human-likely to `1.0` AI-likely.
- `confidence`: how strongly the system supports the displayed label after accounting for signal quality, signal agreement, short text, and failed signals.

The two signal scores are combined with quality-aware weights. The Groq classifier starts with `60%` weight and the stylometric analyzer starts with `40%` weight, but each weight is multiplied by that signal's quality value:

```text
groq_weight = 0.60 * groq_quality
stylometric_weight = 0.40 * stylometric_quality

combined_ai_likelihood =
  ((groq_weight * groq_ai_likelihood) +
   (stylometric_weight * stylometric_ai_likelihood)) /
  (groq_weight + stylometric_weight)
```

Confidence is then calculated from three ideas: how far the combined score is from the uncertain middle, how much the two signals agree, and how reliable the signal qualities are.

```text
distance_from_middle = abs(combined_ai_likelihood - 0.50) * 2
signal_agreement = 1 - (abs(groq_score - stylometric_score) * lower_quality)
quality_factor = average(groq_quality, stylometric_quality)

confidence =
  0.50 * distance_from_middle +
  0.30 * signal_agreement +
  0.20 * quality_factor
```

The implementation then subtracts uncertainty penalties for short text, strong disagreement between signals, or failed signals. This means a high AI-likelihood score can still become an `uncertain` label if the evidence is unstable.

The current thresholds are:

```text
likely_ai_generated:
  combined_ai_likelihood >= 0.65
  and confidence >= 0.45

likely_human_written:
  combined_ai_likelihood <= 0.25
  and confidence >= 0.45

uncertain:
  anything in the middle,
  or confidence < 0.45,
  or fewer than two completed signals
```

I validated that the score is meaningful by testing deliberately different inputs: a polished generic AI-style paragraph, a casual first-person ramen review, a formal human-written borderline paragraph, and a lightly edited AI-style paragraph. The useful behavior was not just "above or below 0.5"; the confidence changed when the signals agreed strongly versus when one signal was AI-leaning and the other was not. That is the behavior the project needs because borderline writing should not be treated the same as a strongly aligned AI-looking submission.

### Example: high-confidence AI-style submission

This saved audit-log entry shows both signals pointing in the same direction:

```json
{
  "content_id": "cnt_20260628052501143237_f488da1d",
  "creator_id": "audit-demo-ai",
  "attribution": "likely_ai_generated",
  "llm_score": 0.93,
  "stylometric_score": 0.88,
  "combined_ai_likelihood": 0.911,
  "confidence": 0.873,
  "label": "Likely AI-generated. Our review found strong AI-generation signals with 87% confidence. The creator may appeal this label."
}
```

Because the LLM score and stylometric score are both high and close together, the system reports a high confidence score and returns the AI-generated label variant.

### Example: lower-confidence borderline submission

This earlier validation entry shows a polished or formal submission where the signals disagreed:

```json
{
  "content_id": "cnt_20260628043116039871_0bc6b377",
  "creator_id": "polished-user",
  "attribution": "uncertain",
  "llm_score": 0.92,
  "stylometric_score": 0.255,
  "combined_ai_likelihood": 0.654,
  "confidence": 0.129
}
```

The combined AI likelihood is near the AI threshold, but confidence drops sharply because the LLM signal is high while the stylometric signal is much lower. The final label is therefore `uncertain`, which is the intended conservative behavior for borderline cases.

---

## Transparency Label

The transparency label is the reader-facing text returned by `POST /submit` in both the `label` and `transparency_label` fields. It turns the internal attribution result into plain language, includes the confidence percentage, and avoids claiming certainty about authorship.

The label is generated from two values:

- `attribution`: one of `likely_ai_generated`, `likely_human_written`, or `uncertain`
- `confidence`: the system's confidence in the displayed label, formatted as a percentage

### High-confidence AI result

Used when the combined AI likelihood is high enough and confidence passes the decision threshold.

Exact text:

```text
Likely AI-generated. Our review found strong AI-generation signals with {confidence}% confidence. The creator may appeal this label.
```

Example:

```text
Likely AI-generated. Our review found strong AI-generation signals with 87% confidence. The creator may appeal this label.
```

This wording is intentionally cautious. It says `Likely AI-generated`, not "AI-written," and it explicitly tells the creator that an appeal is available.

### High-confidence human result

Used when the combined AI likelihood is low and confidence passes the decision threshold.

Exact text:

```text
Likely human-written. Our review found strong human-writing signals with {confidence}% confidence.
```

Example:

```text
Likely human-written. Our review found strong human-writing signals with 87% confidence.
```

This label communicates that the system found stronger human-writing evidence while still presenting the result as a likelihood instead of proof.

### Uncertain result

Used when the evidence falls in the middle, confidence is too low, the signals disagree, or fewer than two signals complete successfully.

Exact text:

```text
Origin unclear. Our review found mixed or limited signals with {confidence}% confidence, so this should not be treated as an AI-generated finding.
```

Example:

```text
Origin unclear. Our review found mixed or limited signals with 51% confidence, so this should not be treated as an AI-generated finding.
```

This is the safest label for borderline cases. It prevents weak or mixed evidence from becoming a public AI-generated accusation.

---

## Rate Limiting

`POST /submit` is rate limited with Flask-Limiter:

```text
10 submissions per minute
100 submissions per day
```

The local development limiter uses in-memory storage:

```python
Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
```

These limits are intentionally tied to expected writing-platform behavior. A real creator may submit a few drafts, revisions, or excerpts in quick succession, so `10 per minute` leaves room for normal testing and editing without making the interface feel brittle. A daily cap of `100` is high enough for an active writer, classroom demo, or grader testing several examples, but low enough to slow down a script trying to flood the endpoint or run many costly Groq classifications.

The in-memory limiter resets when the Flask process restarts. For production, this should move to shared storage such as Redis so limits work across multiple server processes.

**Rate Limiting Test:** The following is the results of a rate-limiting test run on a local development server.
```bash
(22:13:54 on main ✹)──> for i in $(seq 1 12); do                                                 ──(Sat,Jun27)─┘
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
201
201
201
201
201
201
201
201
201
201
429
429
```

```bash
127.0.0.1 - - [27/Jun/2026 22:14:39] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:40] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:41] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:42] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:43] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:43] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:44] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:45] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:46] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:46] "POST /submit HTTP/1.1" 201 -
127.0.0.1 - - [27/Jun/2026 22:14:46] "POST /submit HTTP/1.1" 429 -
127.0.0.1 - - [27/Jun/2026 22:14:47] "POST /submit HTTP/1.1" 429 -
```

The screenshot is also attached in the project directory (rate_limiting_test1.jpeg and rate_limiting_test1.png).

---

## Audit Log Examples

Audit events are stored as structured JSON Lines in `data/audit_log.jsonl` and surfaced through `GET /log` as:

```json
{
  "entries": [...]
}
```

The log captures the timestamp, content ID, attribution result, confidence score, individual signal scores, combined score, transparency label, and appeal status. Here are three representative entries:

### Classified as likely AI-generated

```json
{
  "content_id": "cnt_20260628052501143237_f488da1d",
  "creator_id": "audit-demo-ai",
  "timestamp": "2026-06-28T05:25:01.143420+00:00",
  "attribution": "likely_ai_generated",
  "confidence": 0.873,
  "combined_confidence_score": 0.873,
  "combined_ai_likelihood": 0.911,
  "label": "Likely AI-generated. Our review found strong AI-generation signals with 87% confidence. The creator may appeal this label.",
  "llm_score": 0.93,
  "stylometric_score": 0.88,
  "signal_scores": {
    "groq_llm_classifier": {
      "score": 0.93,
      "quality": 0.9,
      "status": "completed"
    },
    "stylometric_heuristics": {
      "score": 0.88,
      "quality": 0.85,
      "status": "completed"
    }
  },
  "appeal_filed": false,
  "status": "classified"
}
```

### Classified as likely human-written

```json
{
  "content_id": "cnt_20260628052501144469_666f0eab",
  "creator_id": "audit-demo-human",
  "timestamp": "2026-06-28T05:25:01.144548+00:00",
  "attribution": "likely_human_written",
  "confidence": 0.869,
  "combined_confidence_score": 0.869,
  "combined_ai_likelihood": 0.095,
  "label": "Likely human-written. Our review found strong human-writing signals with 87% confidence.",
  "llm_score": 0.08,
  "stylometric_score": 0.12,
  "signal_scores": {
    "groq_llm_classifier": {
      "score": 0.08,
      "quality": 0.9,
      "status": "completed"
    },
    "stylometric_heuristics": {
      "score": 0.12,
      "quality": 0.85,
      "status": "completed"
    }
  },
  "appeal_filed": false,
  "status": "classified"
}
```

### Appeal filed

```json
{
  "event_type": "appeal_created",
  "appeal_id": "app_20260628052501145260_f9a770dc",
  "content_id": "cnt_20260628052501143237_f488da1d",
  "creator_id": "audit-demo-ai",
  "timestamp": "2026-06-28T05:25:01.145257+00:00",
  "status": "under_review",
  "appeal_filed": true,
  "previous_status": "classified",
  "appeal_reasoning": "I wrote this myself and want a human review of the classification.",
  "original_attribution": "likely_ai_generated",
  "original_confidence": 0.873,
  "original_llm_score": 0.93,
  "original_stylometric_score": 0.88,
  "original_signal_scores": {
    "groq_llm_classifier": {
      "score": 0.93,
      "quality": 0.9,
      "status": "completed"
    },
    "stylometric_heuristics": {
      "score": 0.88,
      "quality": 0.85,
      "status": "completed"
    }
  }
}
```

---

## Known Limitations

Provenance Guard can misclassify polished human writing, especially formal academic or professional prose. A human-written essay about monetary policy, for example, may use balanced sentence lengths, careful transitions, restrained tone, and abstract vocabulary. The Groq classifier may read that polish as AI-like, while the stylometric analyzer may also score the regular sentence structure as AI-like. The confidence logic and appeal flow are designed to reduce the harm of that kind of false positive, but the system still cannot prove authorship from text alone.

The system also handles poems and highly repetitive creative writing poorly. A human poem that repeats the same opening phrase across many lines may have low vocabulary diversity and a high repeated-bigram ratio, which can push the stylometric score toward AI-like even though repetition is an intentional poetic device.

Very short submissions are another weak case. Titles, captions, two-sentence excerpts, and short dialogue fragments do not provide enough text for stable stylometric measurements. The implementation lowers stylometric quality for short inputs, but the safest outcome is often `uncertain` rather than a strong label.

---

## Spec Reflection

The planning spec helped by forcing the system to separate `combined_ai_likelihood` from `confidence`. That made the implementation more careful: a passage can look AI-leaning but still receive an `uncertain` label when the two signals disagree or the evidence quality is weak.

One implementation detail diverged from the early API sketch: the final `/submit` endpoint requires `text` and `creator_id`, while the first planning draft sometimes referred to a generic `content` field and optional creator metadata. I used `text` because that became the explicit tested contract, and I made `creator_id` required so audit entries and appeals always have a creator identifier attached.

The thresholding also changed from the earliest narrative. The first draft described a very high AI threshold around `0.82`; the implemented version uses `combined_ai_likelihood >= 0.65` plus `confidence >= 0.45`. That change happened because the scoring function now uses quality weighting and disagreement penalties, so the confidence gate does more of the work of preventing weak or conflicting evidence from becoming a strong AI label.

---

## AI Usage

I used AI assistance (Claude and Codex) to turn the architecture plan into the first Flask skeleton. I directed it to create `POST /submit`, accept JSON with `text` and `creator_id`, return a hardcoded response first, and then wire in the first Groq signal only after the route was testable. I revised the output by checking the function signatures against the spec and keeping the signal return shape consistent: `name`, `status`, `ai_likelihood`, `quality`, and `evidence`.

I used AI assistance again for the stylometric signal and confidence scoring layer. I directed it to compute concrete metrics from the plan, including sentence length variance, type-token ratio, punctuation density, and repeated bigram ratio. I revised the scoring after testing because the initial behavior did not separate borderline cases well enough. The final version quality-weights the two signals and penalizes strong disagreement.

I also used AI assistance to implement and document the production layer: structured JSONL audit logging, `GET /log`, label generation, `POST /appeal`, and Flask-Limiter. I overrode generic wording in the labels and README so the user-facing text matched the exact variants from `planning.md`, especially the uncertain label: "so this should not be treated as an AI-generated finding."

---
