from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from scoring import combine_signals, generate_transparency_label
from signals import run_groq_llm_classifier, run_stylometric_heuristics


app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


MIN_CONTENT_LENGTH = 1
MAX_CONTENT_LENGTH = 20000
DATA_DIR = Path("data")
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"
CONTENT_RECORDS_PATH = DATA_DIR / "content_records.json"


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


def signal_details_from(signals: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        str(signal.get("name")): {
            "score": signal.get("ai_likelihood"),
            "quality": signal.get("quality"),
            "status": signal.get("status"),
        }
        for signal in signals
    }


def build_audit_entry(
    content_id: str,
    creator_id: object,
    timestamp: str,
    attribution: str,
    confidence: float,
    combined_ai_likelihood: float,
    label: str,
    signals: list[dict[str, object]],
) -> dict[str, object]:
    signal_details = signal_details_from(signals)
    return {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "combined_confidence_score": confidence,
        "combined_ai_likelihood": combined_ai_likelihood,
        "label": label,
        "llm_score": signal_details.get("groq_llm_classifier", {}).get("score"),
        "stylometric_score": signal_details.get("stylometric_heuristics", {}).get("score"),
        "signal_scores": signal_details,
        "appeal_filed": False,
        "status": "classified",
    }


def load_content_records() -> dict[str, dict[str, object]]:
    if not CONTENT_RECORDS_PATH.exists():
        return {}
    return json.loads(CONTENT_RECORDS_PATH.read_text(encoding="utf-8"))


def save_content_records(records: dict[str, dict[str, object]]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    CONTENT_RECORDS_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def save_content_record(content_id: str, record: dict[str, object]) -> None:
    records = load_content_records()
    records[content_id] = record
    save_content_records(records)


def read_audit_events(limit: int | None = None) -> list[dict[str, object]]:
    if not AUDIT_LOG_PATH.exists():
        return []

    events = []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    if limit is not None:
        lines = lines[-limit:]
    for line in lines:
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def find_original_decision(content_id: str) -> dict[str, object] | None:
    records = load_content_records()
    if content_id in records:
        return records[content_id]

    for event in reversed(read_audit_events()):
        if event.get("content_id") == content_id and event.get("status") in {"classified", "analyzed"}:
            return event
        if event.get("content_id") == content_id and event.get("event_type") == "submission_analyzed":
            return event
    return None


def get_log(limit: int = 20) -> list[dict[str, object]]:
    return read_audit_events(limit=limit)


def validate_appeal_payload(payload: object) -> tuple[dict[str, object] | None, tuple[dict[str, object], int] | None]:
    if not isinstance(payload, dict):
        return None, ({"error": "Request body must be a JSON object."}, 400)

    content_id = payload.get("content_id")
    if not isinstance(content_id, str) or not content_id.strip():
        return None, ({"error": "Field 'content_id' is required and must be a non-empty string."}, 400)

    creator_reasoning = payload.get("creator_reasoning")
    if not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return None, (
            {"error": "Field 'creator_reasoning' is required and must be a non-empty string."},
            400,
        )

    return {
        "content_id": content_id.strip(),
        "creator_reasoning": creator_reasoning.strip(),
        "creator_id": payload.get("creator_id"),
        "contact": payload.get("contact"),
    }, None


def make_appeal_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"app_{timestamp}_{uuid4().hex[:8]}"


@app.post("/submit")
@limiter.limit("10 per minute;100 per day")
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
    signal_details = signal_details_from(signals)
    decision = combine_signals(signals)
    attribution = str(decision["attribution"])
    confidence = float(decision["confidence_score"])
    combined_ai_likelihood = float(decision["combined_ai_likelihood"])
    label = generate_transparency_label(attribution, confidence)

    write_audit_event(
        build_audit_entry(
            content_id=content_id,
            creator_id=metadata["creator_id"],
            timestamp=created_at,
            attribution=attribution,
            confidence=confidence,
            combined_ai_likelihood=combined_ai_likelihood,
            label=label,
            signals=signals,
        )
    )
    save_content_record(
        content_id,
        {
            "content_id": content_id,
            "creator_id": metadata["creator_id"],
            "status": "classified",
            "attribution": attribution,
            "confidence": confidence,
            "combined_ai_likelihood": combined_ai_likelihood,
            "label": label,
            "llm_score": signal_details.get("groq_llm_classifier", {}).get("score"),
            "stylometric_score": signal_details.get("stylometric_heuristics", {}).get("score"),
            "signal_scores": signal_details,
            "appeal_filed": False,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )

    response = {
        "content_id": content_id,
        "creator_id": metadata["creator_id"],
        "status": "analyzed",
        "attribution": attribution,
        "confidence": confidence,
        "combined_ai_likelihood": combined_ai_likelihood,
        "label": label,
        "transparency_label": label,
        "signals": signals,
        "created_at": created_at,
    }
    return jsonify(response), 201


@app.post("/appeal")
def appeal_content():
    payload = request.get_json(silent=True)
    appeal, error = validate_appeal_payload(payload)
    if error:
        body, status_code = error
        return jsonify(body), status_code

    content_id = str(appeal["content_id"])
    original_decision = find_original_decision(content_id)
    if original_decision is None:
        return jsonify({"error": "No content record exists for the provided content_id."}), 404

    appealed_at = datetime.now(timezone.utc).isoformat()
    appeal_id = make_appeal_id()
    records = load_content_records()
    existing_record = records.get(content_id, {})
    previous_status = str(existing_record.get("status") or original_decision.get("status") or "classified")

    updated_record = {
        **original_decision,
        **existing_record,
        "content_id": content_id,
        "status": "under_review",
        "appeal_id": appeal_id,
        "appeal_reasoning": appeal["creator_reasoning"],
        "appeal_filed": True,
        "updated_at": appealed_at,
    }
    if appeal.get("creator_id"):
        updated_record["creator_id"] = appeal["creator_id"]
    elif "creator_id" not in updated_record:
        updated_record["creator_id"] = original_decision.get("creator_id")
    if appeal.get("contact"):
        updated_record["contact"] = appeal["contact"]

    records[content_id] = updated_record
    save_content_records(records)

    appeal_event = {
        "event_type": "appeal_created",
        "appeal_id": appeal_id,
        "content_id": content_id,
        "creator_id": updated_record.get("creator_id"),
        "timestamp": appealed_at,
        "status": "under_review",
        "appeal_filed": True,
        "previous_status": previous_status,
        "appeal_reasoning": appeal["creator_reasoning"],
        "original_attribution": original_decision.get("attribution"),
        "original_confidence": original_decision.get("confidence"),
        "original_llm_score": original_decision.get("llm_score"),
        "original_stylometric_score": original_decision.get("stylometric_score"),
        "original_signal_scores": original_decision.get("signal_scores"),
    }
    write_audit_event(appeal_event)

    return jsonify(
        {
            "appeal_id": appeal_id,
            "content_id": content_id,
            "status": "under_review",
            "message": "Appeal received. This content is now under review.",
            "received_at": appealed_at,
        }
    ), 200


@app.get("/log")
def log_entries():
    return jsonify({"entries": get_log()})


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "provenance-guard"})


if __name__ == "__main__":
    app.run(debug=True)
