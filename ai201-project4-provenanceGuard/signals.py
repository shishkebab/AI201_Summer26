import json
import os
from typing import Any

from dotenv import load_dotenv


SIGNAL_NAME = "groq_llm_classifier"


def _base_signal(status: str, ai_likelihood: float, quality: float, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": SIGNAL_NAME,
        "status": status,
        "ai_likelihood": _clamp(ai_likelihood),
        "quality": _clamp(quality),
        "evidence": evidence,
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _parse_json_response(content: str) -> dict[str, Any]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Groq response was not a JSON object")
    return parsed


def run_groq_llm_classifier(text: str) -> dict[str, Any]:
    """Return the first detection signal as an ai_likelihood score from 0.0 to 1.0."""
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        return _base_signal(
            status="failed",
            ai_likelihood=0.5,
            quality=0.0,
            evidence={
                "rationale": "Groq classifier did not run because GROQ_API_KEY is not configured.",
                "uncertainty_notes": "Without the LLM signal, the system should treat attribution as uncertain.",
            },
        )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an attribution analysis component. Return only JSON with "
                        "ai_likelihood, rationale, and uncertainty_notes. ai_likelihood must be "
                        "a number from 0.0 to 1.0, where 0.0 means strongly human-likely and "
                        "1.0 means strongly AI-likely. Do not claim proof of authorship."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this text for AI-like versus human-like writing patterns. "
                        "Consider voice, specificity, flow, transitions, generic phrasing, "
                        "topic handling, and whether the writing feels personally situated.\n\n"
                        f"Text:\n{text}"
                    ),
                },
            ],
        )

        content = completion.choices[0].message.content or "{}"
        parsed = _parse_json_response(content)
        ai_likelihood = parsed.get("ai_likelihood")
        if ai_likelihood is None:
            raise ValueError("Groq response did not include ai_likelihood")

        return _base_signal(
            status="completed",
            ai_likelihood=float(ai_likelihood),
            quality=0.9,
            evidence={
                "rationale": str(parsed.get("rationale", "")),
                "uncertainty_notes": str(parsed.get("uncertainty_notes", "")),
            },
        )
    except Exception as exc:
        return _base_signal(
            status="failed",
            ai_likelihood=0.5,
            quality=0.0,
            evidence={
                "rationale": "Groq classifier failed to produce a usable structured response.",
                "uncertainty_notes": f"Signal failed with {type(exc).__name__}.",
            },
        )
