from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request

from scoring import combine_signals, label_for_attribution
from signals import run_groq_llm_classifier, run_stylometric_heuristics


app = Flask(__name__)


MIN_CONTENT_LENGTH = 1
MAX_CONTENT_LENGTH = 20000
DATA_DIR = Path("data")
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"


def validate_submit_payload(payload: object) -> tuple[dict[str, object] | None, tuple[dict[str, object], int] | None]:
    if not isinstance(payload, dict):
        return None, ({"error": "Request body must be a JSON object."}, 400)

    text = payload.get("text")
    if not isinstance(text, str):
        return None, ({"error": "Field 'text' is required and must be a string."}, 400)

    normalized_text = text.strip()
    if len(normalized_text) < MIN_CONTENT_LENGTH:
        return None, ({"error": "Field 'text' must not be empty."}, 400)

    if len(normalized_text) > MAX_CONTENT_LENGTH:
        return None, (
            {"error": f"Field 'text' must be {MAX_CONTENT_LENGTH} characters or fewer."},
            400,
        )

    creator_id = payload.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return None, ({"error": "Field 'creator_id' is required and must be a non-empty string."}, 400)

    metadata = {
        "text": normalized_text,
        "creator_id": creator_id.strip(),
        "title": payload.get("title"),
        "source": payload.get("source"),
    }
    return metadata, None


def make_content_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"cnt_{timestamp}_{uuid4().hex[:8]}"


def write_audit_event(event: dict[str, object]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as audit_log:
        audit_log.write(json.dumps(event) + "\n")


def build_audit_entry(
    content_id: str,
    creator_id: object,
    timestamp: str,
    attribution: str,
    confidence: float,
    combined_ai_likelihood: float,
    signals: list[dict[str, object]],
) -> dict[str, object]:
    signal_details = {
        str(signal.get("name")): {
            "score": signal.get("ai_likelihood"),
            "quality": signal.get("quality"),
            "status": signal.get("status"),
        }
        for signal in signals
    }
    return {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "combined_confidence_score": confidence,
        "combined_ai_likelihood": combined_ai_likelihood,
        "llm_score": signal_details.get("groq_llm_classifier", {}).get("score"),
        "stylometric_score": signal_details.get("stylometric_heuristics", {}).get("score"),
        "signal_scores": signal_details,
        "status": "classified",
    }


def get_log(limit: int = 20) -> list[dict[str, object]]:
    if not AUDIT_LOG_PATH.exists():
        return []

    entries = []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    for line in lines[-limit:]:
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return entries


@app.post("/submit")
def submit_content():
    payload = request.get_json(silent=True)
    metadata, error = validate_submit_payload(payload)
    if error:
        body, status_code = error
        return jsonify(body), status_code

    content_id = make_content_id()
    created_at = datetime.now(timezone.utc).isoformat()
    text = str(metadata["text"])
    signals = [
        run_groq_llm_classifier(text),
        run_stylometric_heuristics(text),
    ]
    decision = combine_signals(signals)
    attribution = str(decision["attribution"])
    confidence = float(decision["confidence_score"])
    combined_ai_likelihood = float(decision["combined_ai_likelihood"])
    label = label_for_attribution(attribution)

    write_audit_event(
        build_audit_entry(
            content_id=content_id,
            creator_id=metadata["creator_id"],
            timestamp=created_at,
            attribution=attribution,
            confidence=confidence,
            combined_ai_likelihood=combined_ai_likelihood,
            signals=signals,
        )
    )

    response = {
        "content_id": content_id,
        "creator_id": metadata["creator_id"],
        "status": "analyzed",
        "attribution": attribution,
        "confidence": confidence,
        "combined_ai_likelihood": combined_ai_likelihood,
        "label": label,
        "signals": signals,
        "created_at": created_at,
    }
    return jsonify(response), 201


@app.get("/log")
def log_entries():
    return jsonify({"entries": get_log()})


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "provenance-guard"})


if __name__ == "__main__":
    app.run(debug=True)
