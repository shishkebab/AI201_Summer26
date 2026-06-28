# Provenance Guard

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
