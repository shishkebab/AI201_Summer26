from typing import Any


GROQ_WEIGHT = 0.60
STYLOMETRIC_WEIGHT = 0.40
AI_THRESHOLD = 0.65
HUMAN_THRESHOLD = 0.25
CONFIDENCE_THRESHOLD = 0.45


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _signal_by_name(signals: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((signal for signal in signals if signal.get("name") == name), None)


def _score(signal: dict[str, Any] | None) -> float:
    if not signal or signal.get("status") != "completed":
        return 0.5
    return clamp(float(signal.get("ai_likelihood", 0.5)))


def _quality(signal: dict[str, Any] | None) -> float:
    if not signal or signal.get("status") != "completed":
        return 0.0
    return clamp(float(signal.get("quality", 0.0)))


def _word_count(signals: list[dict[str, Any]]) -> int:
    stylometric = _signal_by_name(signals, "stylometric_heuristics")
    if not stylometric:
        return 0
    evidence = stylometric.get("evidence", {})
    if not isinstance(evidence, dict):
        return 0
    return int(evidence.get("word_count", 0))


def _quality_weighted_average(
    groq_score: float,
    groq_quality: float,
    stylometric_score: float,
    stylometric_quality: float,
) -> float:
    groq_weight = GROQ_WEIGHT * groq_quality
    stylometric_weight = STYLOMETRIC_WEIGHT * stylometric_quality
    total_weight = groq_weight + stylometric_weight
    if total_weight == 0:
        return 0.5
    return ((groq_weight * groq_score) + (stylometric_weight * stylometric_score)) / total_weight


def combine_signals(signals: list[dict[str, Any]]) -> dict[str, Any]:
    groq = _signal_by_name(signals, "groq_llm_classifier")
    stylometric = _signal_by_name(signals, "stylometric_heuristics")

    groq_score = _score(groq)
    stylometric_score = _score(stylometric)
    groq_quality = _quality(groq)
    stylometric_quality = _quality(stylometric)
    combined_ai_likelihood = _quality_weighted_average(
        groq_score=groq_score,
        groq_quality=groq_quality,
        stylometric_score=stylometric_score,
        stylometric_quality=stylometric_quality,
    )

    distance_from_middle = abs(combined_ai_likelihood - 0.50) * 2
    lower_quality = min(groq_quality, stylometric_quality)
    signal_agreement = 1 - (abs(groq_score - stylometric_score) * lower_quality)
    quality_factor = (groq_quality + stylometric_quality) / 2

    confidence_score = (
        0.50 * distance_from_middle
        + 0.30 * signal_agreement
        + 0.20 * quality_factor
    )

    completed_count = sum(1 for signal in signals if signal.get("status") == "completed")
    if _word_count(signals) < 80:
        confidence_score -= 0.05 * (1 - stylometric_quality)
    if abs(groq_score - stylometric_score) > 0.30:
        confidence_score -= 0.10 * lower_quality
    if completed_count < len(signals):
        confidence_score -= 0.20

    confidence_score = clamp(confidence_score)

    if completed_count < 2:
        attribution = "uncertain"
    elif combined_ai_likelihood >= AI_THRESHOLD and confidence_score >= CONFIDENCE_THRESHOLD:
        attribution = "likely_ai_generated"
    elif combined_ai_likelihood <= HUMAN_THRESHOLD and confidence_score >= CONFIDENCE_THRESHOLD:
        attribution = "likely_human_written"
    else:
        attribution = "uncertain"

    return {
        "combined_ai_likelihood": round(combined_ai_likelihood, 3),
        "confidence_score": round(confidence_score, 3),
        "attribution": attribution,
    }


def _confidence_percent(confidence_score: float) -> int:
    return round(clamp(confidence_score) * 100)


def generate_transparency_label(attribution: str, confidence_score: float) -> str:
    confidence = _confidence_percent(confidence_score)
    if attribution == "likely_ai_generated":
        return (
            "Likely AI-generated. Our review found strong AI-generation signals "
            f"with {confidence}% confidence. The creator may appeal this label."
        )
    if attribution == "likely_human_written":
        return (
            "Likely human-written. Our review found strong human-writing signals "
            f"with {confidence}% confidence."
        )
    return (
        "Origin unclear. Our review found mixed or limited signals "
        f"with {confidence}% confidence, so this should not be treated as an "
        "AI-generated finding."
    )


def label_for_attribution(attribution: str, confidence_score: float | None = None) -> str:
    if confidence_score is None:
        confidence_score = 0.0
    return generate_transparency_label(attribution, confidence_score)
